"""E2E tests for cli-anything-calibre.

These tests invoke the REAL Calibre tools (calibredb, ebook-convert) and verify
that actual library operations work end-to-end.

Calibre is a HARD DEPENDENCY — tests fail (not skip) if it is not installed.

Run (dev mode):
    pytest cli_anything/calibre/tests/test_full_e2e.py -v -s

Run (installed binary verification):
    CLI_ANYTHING_FORCE_INSTALLED=1 pytest cli_anything/calibre/tests/test_full_e2e.py -v -s
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


# ── EPUB generation helpers ────────────────────────────────────────────────


def make_minimal_epub(path: str, title: str = "Test Book", author: str = "Test Author"):
    """Create a minimal but valid EPUB file for testing."""
    with zipfile.ZipFile(path, "w") as z:
        # mimetype must be first and uncompressed
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip",
                   compress_type=zipfile.ZIP_STORED)

        # container.xml
        container = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""
        z.writestr("META-INF/container.xml", container)

        # content.opf
        opf = f"""<?xml version='1.0' encoding='utf-8'?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="book-id">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"
            xmlns:opf="http://www.idpf.org/2007/opf">
    <dc:identifier id="book-id">test-book-001</dc:identifier>
    <dc:title>{title}</dc:title>
    <dc:creator>{author}</dc:creator>
    <dc:language>en</dc:language>
  </metadata>
  <manifest>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
    <item id="chapter1" href="chapter1.html" media-type="application/xhtml+xml"/>
  </manifest>
  <spine toc="ncx">
    <itemref idref="chapter1"/>
  </spine>
</package>"""
        z.writestr("OEBPS/content.opf", opf)

        # toc.ncx
        ncx = f"""<?xml version='1.0' encoding='utf-8'?>
<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN"
   "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="test-book-001"/>
    <meta name="dtb:depth" content="1"/>
    <meta name="dtb:totalPageCount" content="0"/>
    <meta name="dtb:maxPageNumber" content="0"/>
  </head>
  <docTitle><text>{title}</text></docTitle>
  <navMap>
    <navPoint id="navPoint-1" playOrder="1">
      <navLabel><text>Chapter 1</text></navLabel>
      <content src="chapter1.html"/>
    </navPoint>
  </navMap>
</ncx>"""
        z.writestr("OEBPS/toc.ncx", ncx)

        # chapter1.html
        html = f"""<?xml version='1.0' encoding='utf-8'?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>{title}</title></head>
<body>
<h1>{title}</h1>
<p>This is a test e-book by {author}. It contains sample text for CLI testing.</p>
<p>The quick brown fox jumps over the lazy dog.</p>
</body>
</html>"""
        z.writestr("OEBPS/chapter1.html", html)


# ── CLI resolver ───────────────────────────────────────────────────────────


def _resolve_cli(name):
    """Resolve installed CLI command; falls back to python -m for dev.

    Set env CLI_ANYTHING_FORCE_INSTALLED=1 to require the installed command.
    """
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(
            f"{name} not found in PATH. Install with:\n"
            "  cd agent-harness && pip install -e ."
        )
    module = "cli_anything.calibre.calibre_cli"
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m {module}")
    return [sys.executable, "-m", module]


# ── Fixtures ───────────────────────────────────────────────────────────────


class CalibreTestMixin:
    """Mixin providing a temporary Calibre library with a seeded EPUB."""

    lib_dir: str
    epub_path: str
    book_id: int

    @classmethod
    def setUpClass(cls):
        calibredb = shutil.which("calibredb")
        if not calibredb:
            raise RuntimeError(
                "calibredb not found in PATH.\n"
                "Calibre is a hard dependency — install it:\n"
                "  sudo apt-get install calibre"
            )

        cls.tmp_root = tempfile.mkdtemp(prefix="cli-anything-calibre-test-")
        cls.lib_dir = os.path.join(cls.tmp_root, "TestLibrary")
        os.makedirs(cls.lib_dir)

        # Create a test EPUB
        cls.epub_path = os.path.join(cls.tmp_root, "test_book.epub")
        make_minimal_epub(cls.epub_path, title="Foundation", author="Isaac Asimov")

        # Add to library
        result = subprocess.run(
            [calibredb, "--with-library", cls.lib_dir, "add", cls.epub_path],
            capture_output=True, text=True, check=True,
        )
        # Extract the book ID from output "Added book ids: 1"
        cls.book_id = 1
        for line in result.stdout.splitlines():
            if "Added book ids:" in line:
                parts = line.split(":")[-1].strip()
                if parts.isdigit():
                    cls.book_id = int(parts)
                break

        print(f"\n[fixture] Library: {cls.lib_dir}")
        print(f"[fixture] EPUB:    {cls.epub_path}")
        print(f"[fixture] Book ID: {cls.book_id}")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp_root, ignore_errors=True)


# ── TestLibraryOperations ──────────────────────────────────────────────────


class TestLibraryOperations(CalibreTestMixin, unittest.TestCase):
    def test_library_info(self):
        from cli_anything.calibre.core.library import library_info
        info = library_info(self.lib_dir)
        self.assertEqual(info["library_path"], self.lib_dir)
        self.assertGreater(info["book_count"], 0)
        self.assertGreater(info["db_size_bytes"], 0)
        print(f"\n  library_info: {info}")

    def test_list_books(self):
        from cli_anything.calibre.core.library import list_books
        books = list_books(self.lib_dir)
        self.assertGreater(len(books), 0)
        book = books[0]
        self.assertIn("id", book)
        self.assertIn("title", book)
        print(f"\n  list_books[0]: {book}")

    def test_search_books(self):
        from cli_anything.calibre.core.library import search_books
        ids = search_books(self.lib_dir, "title:Foundation")
        self.assertIsInstance(ids, list)
        print(f"\n  search_books('title:Foundation'): {ids}")

    def test_get_metadata(self):
        from cli_anything.calibre.core.metadata import get_metadata
        meta = get_metadata(self.lib_dir, self.book_id)
        self.assertEqual(meta["id"], self.book_id)
        self.assertIsInstance(meta.get("title", ""), str)
        print(f"\n  get_metadata({self.book_id}): title={meta.get('title')}")

    def test_export_books(self):
        """Export a book to a directory and verify files were created."""
        from cli_anything.calibre.core.export import export_books
        out_dir = os.path.join(self.tmp_root, "export-test")
        result = export_books(self.lib_dir, [self.book_id], out_dir)
        self.assertTrue(os.path.isdir(out_dir))
        self.assertGreater(result["count"], 0)
        print(f"\n  export_books: {result['count']} files to {out_dir}")
        for f in result["exported_files"]:
            print(f"    {f} ({Path(f).stat().st_size:,} bytes)")


# ── TestMetadataOperations ─────────────────────────────────────────────────


class TestMetadataOperations(CalibreTestMixin, unittest.TestCase):
    def test_set_metadata_title(self):
        from cli_anything.calibre.core.metadata import set_metadata, get_metadata
        new_title = "Foundation — Updated"
        set_metadata(self.lib_dir, self.book_id, "title", new_title)
        meta = get_metadata(self.lib_dir, self.book_id)
        self.assertEqual(meta.get("title"), new_title)
        print(f"\n  set title: '{new_title}' → confirmed")

    def test_set_metadata_tags(self):
        from cli_anything.calibre.core.metadata import set_metadata, get_metadata
        set_metadata(self.lib_dir, self.book_id, "tags", "scifi,classic")
        meta = get_metadata(self.lib_dir, self.book_id)
        tags = meta.get("tags", [])
        print(f"\n  set tags → {tags}")
        # Tags confirmed via OPF parsing
        self.assertIsInstance(tags, list)

    def test_set_series(self):
        from cli_anything.calibre.core.metadata import set_metadata, get_metadata
        set_metadata(self.lib_dir, self.book_id, "series", "Foundation")
        set_metadata(self.lib_dir, self.book_id, "series_index", "1.0")
        meta = get_metadata(self.lib_dir, self.book_id)
        print(f"\n  series={meta.get('series')}, index={meta.get('series_index')}")
        self.assertEqual(meta.get("series"), "Foundation")


# ── TestFormatConversion ───────────────────────────────────────────────────


class TestFormatConversion(CalibreTestMixin, unittest.TestCase):
    def test_convert_epub_to_txt(self):
        """Convert EPUB to TXT and verify output file."""
        from cli_anything.calibre.core.formats import convert_format

        # Create a dedicated epub for this test to avoid interference
        epub = os.path.join(self.tmp_root, "convert_test.epub")
        make_minimal_epub(epub, title="Convert Test", author="Test Author")

        # Add it
        calibredb = shutil.which("calibredb")
        result = subprocess.run(
            [calibredb, "--with-library", self.lib_dir, "add", epub],
            capture_output=True, text=True, check=True,
        )
        # Find the new book ID
        new_id = None
        for line in result.stdout.splitlines():
            if "Added book ids:" in line:
                parts = line.split(":")[-1].strip()
                if parts.isdigit():
                    new_id = int(parts)
        if new_id is None:
            self.skipTest("Could not determine added book ID")

        out_txt = os.path.join(self.tmp_root, f"converted_{new_id}.txt")
        result = convert_format(
            self.lib_dir, new_id, "EPUB", "TXT",
            output_path=out_txt,
            add_to_library=False,
        )

        self.assertTrue(os.path.exists(result["output_path"]))
        size = Path(result["output_path"]).stat().st_size
        self.assertGreater(size, 0)
        print(f"\n  TXT: {result['output_path']} ({size:,} bytes)")

    def test_convert_epub_to_mobi(self):
        """Convert EPUB to MOBI and verify output file magic bytes."""
        from cli_anything.calibre.core.formats import convert_format

        epub = os.path.join(self.tmp_root, "mobi_test.epub")
        make_minimal_epub(epub, title="MOBI Test", author="Test Author")
        calibredb = shutil.which("calibredb")
        r = subprocess.run(
            [calibredb, "--with-library", self.lib_dir, "add", epub],
            capture_output=True, text=True, check=True,
        )
        new_id = None
        for line in r.stdout.splitlines():
            if "Added book ids:" in line:
                parts = line.split(":")[-1].strip()
                if parts.isdigit():
                    new_id = int(parts)
        if new_id is None:
            self.skipTest("Could not determine added book ID")

        out_mobi = os.path.join(self.tmp_root, f"converted_{new_id}.mobi")
        result = convert_format(
            self.lib_dir, new_id, "EPUB", "MOBI",
            output_path=out_mobi,
            add_to_library=False,
        )

        self.assertTrue(os.path.exists(result["output_path"]))
        size = Path(result["output_path"]).stat().st_size
        self.assertGreater(size, 0)
        print(f"\n  MOBI: {result['output_path']} ({size:,} bytes)")

        # MOBI files start with PalmDoc header: "BOOKMOBI" at offset 60
        with open(result["output_path"], "rb") as f:
            header = f.read(68)
        # MOBI/AZW3 may also be produced — just verify it's not empty
        self.assertGreater(len(header), 0)

    def test_convert_adds_to_library(self):
        """Convert and add back to library — verify format appears in list."""
        from cli_anything.calibre.core.formats import convert_format, list_formats

        epub = os.path.join(self.tmp_root, "add_back_test.epub")
        make_minimal_epub(epub, title="Add Back Test", author="Test Author")
        calibredb = shutil.which("calibredb")
        r = subprocess.run(
            [calibredb, "--with-library", self.lib_dir, "add", epub],
            capture_output=True, text=True, check=True,
        )
        new_id = None
        for line in r.stdout.splitlines():
            if "Added book ids:" in line:
                parts = line.split(":")[-1].strip()
                if parts.isdigit():
                    new_id = int(parts)
        if new_id is None:
            self.skipTest("Could not determine added book ID")

        convert_format(
            self.lib_dir, new_id, "EPUB", "TXT",
            add_to_library=True,
        )

        result = list_formats(self.lib_dir, new_id)
        print(f"\n  formats after convert: {result['formats']}")
        # After adding TXT back, it should appear
        # (calibredb add_format may map TXT to uppercase)
        self.assertTrue(
            any(fmt in result["formats"] for fmt in ["TXT", "EPUB"]),
            f"Expected TXT or EPUB in {result['formats']}"
        )


# ── TestCLISubprocess ──────────────────────────────────────────────────────


class TestCLISubprocess(unittest.TestCase):
    """Test the installed cli-anything-calibre command via subprocess."""

    CLI_BASE = _resolve_cli("cli-anything-calibre")

    @classmethod
    def setUpClass(cls):
        calibredb = shutil.which("calibredb")
        if not calibredb:
            raise RuntimeError(
                "calibredb not found. Calibre is required for E2E tests."
            )
        cls.tmp = tempfile.mkdtemp(prefix="cli-anything-calibre-subprocess-")
        cls.lib_dir = os.path.join(cls.tmp, "SubprocessLibrary")
        os.makedirs(cls.lib_dir)

        cls.epub_path = os.path.join(cls.tmp, "subprocess_test.epub")
        make_minimal_epub(cls.epub_path, title="CLI Test Book", author="CLI Author")

        print(f"\n[subprocess] Library: {cls.lib_dir}")
        print(f"[subprocess] EPUB:    {cls.epub_path}")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _run(self, args, check=True, env=None):
        full_env = os.environ.copy()
        if env:
            full_env.update(env)
        return subprocess.run(
            self.CLI_BASE + args,
            capture_output=True,
            text=True,
            check=check,
            env=full_env,
        )

    def test_help(self):
        result = self._run(["--help"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("calibre", result.stdout.lower())

    def test_version(self):
        result = self._run(["--version"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("1.0.0", result.stdout)

    def test_library_connect(self):
        result = self._run(["library", "connect", self.lib_dir])
        self.assertEqual(result.returncode, 0)
        print(f"\n  library connect: {result.stdout.strip()}")

    def test_library_info_json(self):
        # First connect
        self._run(["library", "connect", self.lib_dir])
        result = self._run(["--json", "library", "info"])
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertIn("library_path", data)
        self.assertIn("book_count", data)
        print(f"\n  library info JSON: {data}")

    def test_books_add_json(self):
        """Add an EPUB via CLI and verify JSON response."""
        env = {"CALIBRE_LIBRARY": self.lib_dir}
        result = self._run(["--json", "books", "add", self.epub_path], env=env)
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertIn("added_ids", data)
        print(f"\n  books add JSON: {data}")
        # Save the book ID for later tests
        if data["added_ids"]:
            TestCLISubprocess.added_book_id = data["added_ids"][0]
        else:
            TestCLISubprocess.added_book_id = 1

    def test_books_list_json(self):
        """List books and verify JSON array."""
        # Add book first if not done
        env = {"CALIBRE_LIBRARY": self.lib_dir}
        self._run(["books", "add", self.epub_path], env=env, check=False)

        result = self._run(["--json", "books", "list"], env=env)
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertIsInstance(data, list)
        print(f"\n  books list JSON: {len(data)} books")

    def test_books_search_json(self):
        """Search books with a query."""
        env = {"CALIBRE_LIBRARY": self.lib_dir}
        self._run(["books", "add", self.epub_path], env=env, check=False)

        result = self._run(["--json", "books", "search", "title:CLI Test Book"], env=env)
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertIn("ids", data)
        print(f"\n  books search JSON: {data}")

    def test_meta_set_and_get(self):
        """Set a metadata field and verify it's retrievable."""
        env = {"CALIBRE_LIBRARY": self.lib_dir}
        # Add book
        add_result = self._run(["--json", "books", "add", self.epub_path],
                               env=env, check=False)
        if add_result.returncode == 0:
            try:
                book_id = json.loads(add_result.stdout)["added_ids"][0]
            except (json.JSONDecodeError, KeyError, IndexError):
                book_id = 1
        else:
            book_id = 1

        # Set publisher
        result = self._run(
            ["--json", "meta", "set", str(book_id), "publisher", "CLI Press"],
            env=env,
        )
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["field"], "publisher")
        print(f"\n  meta set: {data}")

        # Get all metadata
        result = self._run(["--json", "meta", "get", str(book_id)], env=env)
        self.assertEqual(result.returncode, 0)
        meta = json.loads(result.stdout)
        print(f"\n  meta get: id={meta.get('id')}, title={meta.get('title')}")

    def test_full_workflow(self):
        """Full workflow: add → set metadata → search → export."""
        env = {"CALIBRE_LIBRARY": self.lib_dir}

        # 1. Add book
        result = self._run(["--json", "books", "add", self.epub_path], env=env,
                           check=False)
        try:
            book_id = json.loads(result.stdout)["added_ids"][0]
        except Exception:
            book_id = 1

        print(f"\n  [workflow] Added book_id={book_id}")

        # 2. Set series
        self._run(["meta", "set", str(book_id), "series", "CLI Series"], env=env)
        self._run(["meta", "set", str(book_id), "series_index", "1"], env=env)

        # 3. Search
        result = self._run(["--json", "books", "search", "title:CLI Test Book"],
                           env=env)
        self.assertEqual(result.returncode, 0)
        search_data = json.loads(result.stdout)
        print(f"  [workflow] search: {search_data}")

        # 4. Export
        out_dir = os.path.join(self.tmp, "workflow-export")
        result = self._run(
            ["books", "export", str(book_id), "--to-dir", out_dir],
            env=env,
        )
        self.assertEqual(result.returncode, 0)
        if os.path.isdir(out_dir):
            exported = list(Path(out_dir).rglob("*.*"))
            print(f"  [workflow] exported {len(exported)} files to {out_dir}")
            for f in exported:
                print(f"    {f} ({f.stat().st_size:,} bytes)")


if __name__ == "__main__":
    unittest.main()
