"""extract.py — turn tender documents into the text payload Gatekeeper expects.

The website extracts text in the browser and posts only the text, so this
module ports those rules exactly (evaluate.html): same accepted types, same
10-file / 10 MB limits, the same DOCX paragraph/tab handling, the same XLSX
"[Sheet N]" tab-separated layout, and the same scanned-PDF warning.

One deliberate difference: XLSX cells are placed by their A1 reference, so
blank cells — omitted entirely, or written self-closing (<c r="B4" s="1"/>)
when formatted — stay as empty columns. The web app reads cells sequentially,
which shifts BOM values left under the wrong headers.
"""

from __future__ import annotations

import html
import re
import zipfile
from pathlib import Path
from typing import Any

ACCEPT = ("pdf", "docx", "xlsx", "txt")
MAX_FILES = 10
MAX_BYTES = 10 * 1024 * 1024


class ExtractError(ValueError):
    pass


def _xml_text(xml: str) -> str:
    text = re.sub(r"<[^>]+>", "", xml)
    return (text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
                .replace("&quot;", '"').replace("&apos;", "'"))


def extract_docx(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as z:
            if "word/document.xml" not in z.namelist():
                raise ExtractError("not a Word document")
            xml = z.read("word/document.xml").decode("utf-8", errors="replace")
    except zipfile.BadZipFile as exc:
        raise ExtractError("not a Word document") from exc
    return _xml_text(xml.replace("</w:p>", "\n").replace("<w:tab/>", "\t"))


def extract_xlsx(path: Path) -> str:
    try:
        z = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise ExtractError("not an Excel workbook") from exc
    with z:
        names = z.namelist()
        shared: list[str] = []
        if "xl/sharedStrings.xml" in names:
            ss = z.read("xl/sharedStrings.xml").decode("utf-8", errors="replace")
            shared = [_xml_text(m) for m in re.findall(r"<si>([\s\S]*?)</si>", ss)]
        sheets = sorted((n for n in names if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n)),
                        key=lambda n: int(re.search(r"sheet(\d+)", n).group(1)))
        if not sheets:
            raise ExtractError("not an Excel workbook")
        out = []
        for name in sheets:
            xml = z.read(name).decode("utf-8", errors="replace")
            sheet_no = re.search(r"sheet(\d+)", name).group(1)
            out.append(f"[Sheet {sheet_no}]\n")
            for row in re.findall(r"<row[^>]*>([\s\S]*?)</row>", xml):
                out.append("\t".join(_xlsx_row(row, shared)) + "\n")
    return "".join(out)


_CELL_RE = re.compile(r"<c(\s[^>]*?)?/>|<c(\s[^>]*)?>([\s\S]*?)</c>")
_REF_RE = re.compile(r'\br="([A-Z]+)\d+"')


def _col_index(letters: str) -> int:
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def _xlsx_row(row: str, shared: list[str]) -> list[str]:
    """Cells of one <row>, placed by their A1 reference.

    OOXML omits unformatted blank cells entirely and writes formatted blank
    cells as self-closing <c .../>. Placing each value by its r="C2"
    reference keeps every value under its own column header; cells without a
    reference fall back to the next position. (The web app's sequential regex
    gets both cases wrong, shifting BOM values left.)
    """
    cells: list[str] = []
    for m in _CELL_RE.finditer(row):
        self_closing = m.group(3) is None
        attrs = (m.group(1) if self_closing else m.group(2)) or ""
        if self_closing:
            value = ""
        else:
            inner = m.group(3)
            vm = re.search(r"<v>([\s\S]*?)</v>", inner)
            v = vm.group(1) if vm else None
            if 't="s"' in attrs:
                try:
                    value = shared[int(v)]
                except (TypeError, ValueError, IndexError):
                    value = ""
            elif 't="inlineStr"' in attrs:
                value = _xml_text(inner)
            else:
                value = html.unescape(v) if v is not None else ""
        ref = _REF_RE.search(attrs)
        idx = _col_index(ref.group(1)) if ref else len(cells)
        if idx < len(cells):  # malformed/out-of-order reference: don't overwrite
            idx = len(cells)
        cells.extend([""] * (idx - len(cells)))
        cells.append(value)
    return cells


def extract_pdf(path: Path) -> tuple[str, int]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise ExtractError("pypdf is required for PDF files: pip install pypdf") from exc
    try:
        reader = PdfReader(str(path))
    except Exception as exc:  # noqa: BLE001
        raise ExtractError(f"unreadable PDF ({exc})") from exc
    pages = []
    for page in reader.pages:
        pages.append(" ".join((page.extract_text() or "").split()) + "\n")
    return "".join(pages), len(reader.pages)


def extract_file(path: str | Path) -> dict[str, Any]:
    """Extract one file. Never raises for content problems — returns `warn`."""
    p = Path(path)
    if not p.is_file():
        raise ExtractError(f"{p}: file not found")
    size = p.stat().st_size
    ext = p.suffix.lower().lstrip(".")
    if ext not in ACCEPT:
        raise ExtractError(f"{p.name}: use PDF, DOCX, XLSX or TXT")
    if size > MAX_BYTES:
        raise ExtractError(f"{p.name} exceeds 10MB limit")
    entry: dict[str, Any] = {"name": p.name, "path": str(p.resolve()), "ext": ext,
                             "size": size, "content": "", "warn": ""}
    try:
        if ext == "pdf":
            text, pages = extract_pdf(p)
            entry["content"], entry["pages"] = text, pages
            if len(text.strip()) < 40 * pages:
                entry["warn"] = ("Very little text found — this looks like a scanned PDF. "
                                 "OCR is not supported yet; upload a text-based PDF.")
        elif ext == "txt":
            entry["content"] = p.read_text(encoding="utf-8", errors="replace")
        elif ext == "docx":
            entry["content"] = extract_docx(p)
        elif ext == "xlsx":
            entry["content"] = extract_xlsx(p)
    except ExtractError as exc:
        entry["content"] = ""
        entry["warn"] = f"Could not read {p.name}: {exc}"
    if not entry["content"].strip() and not entry["warn"]:
        entry["warn"] = "No text could be extracted from this file."
    entry["chars"] = len(entry["content"])
    return entry


def collect(paths: list[str]) -> list[str]:
    """Expand directories to the accepted files inside them (sorted, non-recursive)."""
    out: list[str] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            out += [str(f) for f in sorted(p.iterdir())
                    if f.is_file() and f.suffix.lower().lstrip(".") in ACCEPT]
        else:
            out.append(raw)
    return out


def extract_many(paths: list[str]) -> list[dict[str, Any]]:
    files = collect(paths)
    if not files:
        raise ExtractError("No input files. Pass PDF/DOCX/XLSX/TXT files or a folder.")
    if len(files) > MAX_FILES:
        raise ExtractError(f"Up to {MAX_FILES} files per evaluation (got {len(files)}).")
    return [extract_file(f) for f in files]


def summarize(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Metadata view (no document text) — what agents should look at first."""
    files = [{k: e.get(k) for k in ("name", "ext", "size", "chars", "pages", "warn") if k in e}
             for e in entries]
    unreadable = [e["name"] for e in entries if not e["content"].strip()]
    return {"files": files, "total_chars": sum(e["chars"] for e in entries),
            "ready": not unreadable, "unreadable": unreadable}
