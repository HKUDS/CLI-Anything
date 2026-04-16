"""Export pipeline — wraps calibredb export and supports catalog generation."""

import os
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from cli_anything.calibre.utils.calibre_backend import (
    run_calibredb,
    run_ebook_convert,
    find_calibredb,
    find_ebook_convert,
)

_CONTAINER_NS = "urn:oasis:names:tc:opendocument:xmlns:container"
_OPF_NS = "http://www.idpf.org/2007/opf"
_XHTML_NS = "http://www.w3.org/1999/xhtml"
_NCX_NS = "http://www.daisy.org/z3986/2005/ncx/"


def export_books(
    library_path: str,
    book_ids: list[int],
    output_dir: str,
    formats: list[str] | None = None,
    template: str | None = None,
    progress: bool = False,
    export_all: bool = False,
) -> dict:
    """
    Export books from the library to a directory.

    Invokes the real calibredb export — preserves Calibre's original
    folder structure, cover.jpg, and metadata.opf per book.

    Args:
        library_path: Path to the Calibre library.
        book_ids: List of book IDs to export (ignored if export_all=True).
        output_dir: Directory to export books to.
        formats: Optional list of formats to export (e.g. ["EPUB", "MOBI"]).
        template: Optional filename template.
        progress: Whether to show progress output.
        export_all: If True, export all books in library (ignores book_ids).
    """
    find_calibredb()

    os.makedirs(output_dir, exist_ok=True)

    file_count_before = sum(1 for _ in Path(output_dir).rglob("*") if _.is_file())

    cmd = ["export", "--to-dir", output_dir]
    if export_all:
        cmd.append("--all")
    if formats:
        cmd.extend(["--formats", ",".join(formats)])
    if template:
        cmd.extend(["--template", template])
    if progress:
        cmd.append("--progress")
    if not export_all:
        ids_str = ",".join(str(i) for i in book_ids)
        cmd.append(ids_str)

    result = run_calibredb(cmd, library_path=library_path)

    exported_files = [
        str(p) for p in Path(output_dir).rglob("*") if p.is_file()
    ]
    new_files = exported_files[file_count_before:]

    for f in new_files:
        print(f"  Exported: {f} ({Path(f).stat().st_size:,} bytes)")

    return {
        "output_dir": output_dir,
        "book_ids": book_ids if not export_all else "all",
        "exported_files": new_files,
        "count": len(new_files),
        "stdout": result["stdout"],
    }


def generate_catalog(
    library_path: str,
    output_path: str,
    catalog_format: str = "epub",
    title: str = "My Calibre Library",
    extra_options: list[str] | None = None,
) -> dict:
    """
    Generate a catalog of the library using calibredb catalog.

    The catalog format can be epub, csv, or opds.
    """
    find_calibredb()

    output_path = str(Path(output_path).with_suffix(f".{catalog_format.lower()}"))
    os.makedirs(Path(output_path).parent, exist_ok=True)

    cmd = ["catalog", output_path, f"--catalog-title={title}"]
    if extra_options:
        cmd.extend(extra_options)

    result = run_calibredb(cmd, library_path=library_path)

    if not Path(output_path).exists():
        raise RuntimeError(
            f"calibredb catalog did not produce output at {output_path}\n"
            f"stdout: {result['stdout']}\nstderr: {result['stderr']}"
        )

    size = Path(output_path).stat().st_size

    return {
        "output_path": output_path,
        "format": catalog_format,
        "title": title,
        "file_size": size,
        "stdout": result["stdout"],
    }


def _safe_chapter_filename(title: str, index: int) -> str:
    """Convert a chapter title to a safe, zero-padded filename (no extension)."""
    safe = re.sub(r"[^\w\s-]", "", title)[:50].strip()
    safe = re.sub(r"\s+", "_", safe)
    return f"{index:03d}_{safe}" if safe else f"{index:03d}_chapter"


def _parse_nav_titles(nav_path: Path, epub_dir: Path) -> dict:
    """Parse EPUB 3 nav.xhtml.  Returns {path-relative-to-epub-dir: title}."""
    titles: dict[str, str] = {}
    nav_dir = nav_path.parent
    try:
        tree = ET.parse(nav_path)
        for a in tree.findall(f".//{{{_XHTML_NS}}}a"):
            href = a.get("href", "").split("#")[0]
            if not href:
                continue
            text = "".join(a.itertext()).strip()
            if not text:
                continue
            try:
                rel = str((nav_dir / href).resolve().relative_to(epub_dir.resolve()))
                titles[rel] = text
            except ValueError:
                titles[href] = text
    except ET.ParseError:
        pass
    return titles


def _parse_ncx_titles(ncx_path: Path, epub_dir: Path) -> dict:
    """Parse EPUB 2 NCX.  Returns {path-relative-to-epub-dir: title}."""
    titles: dict[str, str] = {}
    ncx_dir = ncx_path.parent
    try:
        tree = ET.parse(ncx_path)
        for nav_point in tree.findall(f".//{{{_NCX_NS}}}navPoint"):
            content = nav_point.find(f"{{{_NCX_NS}}}content")
            label = nav_point.find(f".//{{{_NCX_NS}}}text")
            if content is None or label is None:
                continue
            src = content.get("src", "").split("#")[0]
            text = (label.text or "").strip()
            if not src or not text:
                continue
            try:
                rel = str((ncx_dir / src).resolve().relative_to(epub_dir.resolve()))
                titles[rel] = text
            except ValueError:
                titles[src] = text
    except ET.ParseError:
        pass
    return titles


def _parse_epub_chapters(epub_dir: Path) -> list[dict]:
    """Parse an extracted EPUB directory and return an ordered chapter list.

    Each entry: {order (int), title (str), src (str, relative to epub_dir)}.
    """
    container_path = epub_dir / "META-INF" / "container.xml"
    if not container_path.exists():
        raise RuntimeError("Not a valid EPUB: META-INF/container.xml not found")

    container_tree = ET.parse(container_path)
    rootfile = container_tree.find(f".//{{{_CONTAINER_NS}}}rootfile")
    if rootfile is None:
        raise RuntimeError("Could not find rootfile in container.xml")

    opf_path = epub_dir / rootfile.get("full-path", "")
    opf_dir = opf_path.parent
    opf_tree = ET.parse(opf_path)

    # Build manifest id → {href, media_type, properties}
    manifest: dict[str, dict] = {}
    for item in opf_tree.findall(f".//{{{_OPF_NS}}}item"):
        manifest[item.get("id", "")] = {
            "href": item.get("href", ""),
            "media_type": item.get("media-type", ""),
            "properties": item.get("properties", ""),
        }

    # Locate nav (EPUB 3) or NCX (EPUB 2) for chapter titles
    chapter_titles: dict[str, str] = {}
    nav_item = next(
        (v for v in manifest.values() if "nav" in v.get("properties", "")), None
    )
    ncx_item = next(
        (v for v in manifest.values()
         if v.get("media_type") == "application/x-dtbncx+xml"),
        None,
    )
    if nav_item:
        nav_path = opf_dir / nav_item["href"]
        if nav_path.exists():
            chapter_titles = _parse_nav_titles(nav_path, epub_dir)
    elif ncx_item:
        ncx_path = opf_dir / ncx_item["href"]
        if ncx_path.exists():
            chapter_titles = _parse_ncx_titles(ncx_path, epub_dir)

    # Walk the spine to build the ordered chapter list
    chapters: list[dict] = []
    for itemref in opf_tree.findall(f".//{{{_OPF_NS}}}itemref"):
        item = manifest.get(itemref.get("idref", ""), {})
        href = item.get("href", "")
        media_type = item.get("media_type", "")
        is_html = (
            href.endswith((".html", ".xhtml", ".htm")) or "html" in media_type
        )
        if not is_html:
            continue

        abs_path = opf_dir / href
        if not abs_path.exists():
            continue

        try:
            rel = str(abs_path.resolve().relative_to(epub_dir.resolve()))
        except ValueError:
            rel = str((opf_dir.relative_to(epub_dir)) / href)

        order = len(chapters) + 1
        title = chapter_titles.get(rel) or f"Chapter {order}"
        chapters.append({"order": order, "title": title, "src": rel})

    return chapters


def export_chapters_pdf(
    library_path: str,
    book_id: int,
    output_dir: str,
    chapter_range: tuple[int, int] | None = None,
) -> dict:
    """Export each chapter of a book as a separate PDF file.

    Workflow:
      1. Export the book from the Calibre library to obtain the EPUB file.
      2. Unpack the EPUB and parse the TOC (nav.xhtml for EPUB 3, NCX for
         EPUB 2) to retrieve chapter titles and file order.
      3. Convert each chapter HTML file to PDF with ``ebook-convert``.
      4. Write zero-padded, title-slugified PDFs to *output_dir*.

    Args:
        library_path: Path to the Calibre library.
        book_id:      ID of the book to export.
        output_dir:   Directory that will receive the chapter PDFs.
        chapter_range: Optional ``(start, end)`` tuple (1-indexed, inclusive)
                       to export only a slice of chapters.

    Returns:
        dict with keys ``book_id``, ``output_dir``, ``total_chapters``,
        ``exported_chapters``, and ``exported_pdfs`` (list of per-chapter
        dicts with ``index``, ``title``, ``file``, ``size``).

    Raises:
        FileNotFoundError: Book has no EPUB format in the library.
        RuntimeError:      EPUB structure is invalid or has no chapters.
    """
    import tempfile

    find_calibredb()
    find_ebook_convert()

    os.makedirs(output_dir, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Step 1: export book from calibre to get the EPUB
        # Note: DO NOT use --all, it would export all books and ignore book_id
        run_calibredb(
            ["export", "--to-dir", tmpdir, str(book_id)],
            library_path=library_path,
        )

        epub_files = list(Path(tmpdir).rglob("*.epub"))
        if not epub_files:
            raise FileNotFoundError(
                f"Book {book_id} has no EPUB format in the library. "
                f"Convert it first:  formats convert {book_id} <FMT> EPUB"
            )

        # Step 2: extract EPUB and parse chapter list
        epub_dir = Path(tmpdir) / "epub_content"
        epub_dir.mkdir()
        with zipfile.ZipFile(epub_files[0]) as zf:
            zf.extractall(epub_dir)

        chapters = _parse_epub_chapters(epub_dir)
        if not chapters:
            raise RuntimeError(
                f"No chapters found in book {book_id}. "
                "The EPUB may not have a valid TOC or spine."
            )

        # Step 3: apply optional range filter
        if chapter_range:
            start, end = chapter_range
            chapters = [c for c in chapters if start <= c["order"] <= end]

        # Step 4: convert each chapter to PDF
        exported_pdfs: list[dict] = []
        total = len(chapters)
        for i, chapter in enumerate(chapters, 1):
            src_path = epub_dir / chapter["src"]
            if not src_path.exists():
                print(f"  ⚠ Missing source file: {chapter['src']}, skipping")
                continue

            out_name = _safe_chapter_filename(chapter["title"], chapter["order"]) + ".pdf"
            out_path = Path(output_dir) / out_name
            print(f"  [{i}/{total}] {chapter['title']} → {out_name}")

            try:
                run_ebook_convert([str(src_path), str(out_path)])
            except RuntimeError as exc:
                print(f"  ⚠ Conversion failed (chapter {chapter['order']}): {exc}")
                continue

            if out_path.exists():
                exported_pdfs.append({
                    "index": chapter["order"],
                    "title": chapter["title"],
                    "file": str(out_path),
                    "size": out_path.stat().st_size,
                })

    print(f"\n  Exported {len(exported_pdfs)}/{total} chapters to {output_dir}")
    return {
        "book_id": book_id,
        "output_dir": output_dir,
        "total_chapters": total,
        "exported_chapters": len(exported_pdfs),
        "exported_pdfs": exported_pdfs,
    }


def backup_metadata(library_path: str, output_dir: str | None = None) -> dict:
    """Backup all book metadata.opf files to a directory."""
    find_calibredb()

    cmd = ["backup_metadata"]
    if output_dir:
        cmd.extend(["--to-dir", output_dir])

    result = run_calibredb(cmd, library_path=library_path)
    return {
        "library_path": library_path,
        "output_dir": output_dir,
        "stdout": result["stdout"],
    }
