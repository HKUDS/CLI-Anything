"""Unit tests for cli-anything-calibre core modules.

All tests use synthetic data — no real Calibre installation required.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


# ── session.py tests ───────────────────────────────────────────────────────


class TestSession(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        # Patch the session file location
        self.patcher = mock.patch(
            "cli_anything.calibre.core.session._SESSION_FILE",
            Path(self.tmp) / "session.json",
        )
        self.patcher2 = mock.patch(
            "cli_anything.calibre.core.session._SESSION_DIR",
            Path(self.tmp),
        )
        self.patcher.start()
        self.patcher2.start()

    def tearDown(self):
        self.patcher.stop()
        self.patcher2.stop()

    def test_load_session_defaults(self):
        from cli_anything.calibre.core.session import load_session
        sess = load_session()
        self.assertIsNone(sess["library_path"])
        self.assertIsNone(sess["last_command"])

    def test_save_and_load_session(self):
        from cli_anything.calibre.core.session import load_session, save_session
        sess = load_session()
        sess["library_path"] = "/tmp/calibre-lib"
        save_session(sess)
        sess2 = load_session()
        self.assertEqual(sess2["library_path"], "/tmp/calibre-lib")

    def test_set_library_path(self):
        from cli_anything.calibre.core.session import set_library_path, load_session
        # Create a real directory to resolve
        target = Path(self.tmp) / "mylib"
        target.mkdir()
        sess = load_session()
        new_sess = set_library_path(str(target), sess)
        self.assertEqual(new_sess["library_path"], str(target))

    def test_get_library_path_from_session(self):
        from cli_anything.calibre.core.session import get_library_path
        sess = {"library_path": "/test/library"}
        result = get_library_path(sess)
        self.assertEqual(result, "/test/library")

    def test_get_library_path_from_env(self):
        from cli_anything.calibre.core.session import get_library_path
        with mock.patch.dict(os.environ, {"CALIBRE_LIBRARY": "/env/library"}):
            result = get_library_path({"library_path": "/session/library"})
        self.assertEqual(result, "/env/library")

    def test_require_library_no_path(self):
        from cli_anything.calibre.core.session import require_library
        sess = {"library_path": None}
        with self.assertRaises(RuntimeError) as ctx:
            require_library(sess)
        self.assertIn("No Calibre library", str(ctx.exception))


# ── metadata.py tests ──────────────────────────────────────────────────────


class TestMetadataParsing(unittest.TestCase):
    BASIC_OPF = """<?xml version='1.0' encoding='utf-8'?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"
            xmlns:opf="http://www.idpf.org/2007/opf">
    <dc:title>Foundation</dc:title>
    <dc:creator>Isaac Asimov</dc:creator>
    <dc:publisher>Gnome Press</dc:publisher>
    <dc:language>en</dc:language>
    <dc:subject>science fiction</dc:subject>
    <dc:subject>classic</dc:subject>
    <dc:identifier opf:scheme="ISBN">978-0-553-29335-7</dc:identifier>
  </metadata>
</package>"""

    CALIBRE_OPF = """<?xml version='1.0' encoding='utf-8'?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"
            xmlns:opf="http://www.idpf.org/2007/opf">
    <dc:title>Foundation</dc:title>
    <dc:creator>Isaac Asimov</dc:creator>
    <opf:meta name="calibre:series" content="Foundation"/>
    <opf:meta name="calibre:series_index" content="1.0"/>
    <opf:meta name="calibre:rating" content="5"/>
  </metadata>
</package>"""

    MULTI_AUTHOR_OPF = """<?xml version='1.0' encoding='utf-8'?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"
            xmlns:opf="http://www.idpf.org/2007/opf">
    <dc:title>Good Omens</dc:title>
    <dc:creator>Terry Pratchett</dc:creator>
    <dc:creator>Neil Gaiman</dc:creator>
  </metadata>
</package>"""

    def test_parse_opf_basic(self):
        from cli_anything.calibre.core.metadata import _parse_opf_to_dict
        result = _parse_opf_to_dict(self.BASIC_OPF, book_id=42)
        self.assertEqual(result["id"], 42)
        self.assertEqual(result["title"], "Foundation")
        self.assertEqual(result["authors"], ["Isaac Asimov"])
        self.assertIn("science fiction", result["tags"])
        self.assertIn("classic", result["tags"])
        self.assertEqual(result["publisher"], "Gnome Press")

    def test_parse_opf_calibre_meta(self):
        from cli_anything.calibre.core.metadata import _parse_opf_to_dict
        result = _parse_opf_to_dict(self.CALIBRE_OPF, book_id=1)
        self.assertEqual(result["series"], "Foundation")
        self.assertEqual(result["series_index"], 1.0)
        self.assertEqual(result["rating"], 5.0)

    def test_parse_opf_identifiers(self):
        from cli_anything.calibre.core.metadata import _parse_opf_to_dict
        result = _parse_opf_to_dict(self.BASIC_OPF, book_id=1)
        self.assertIn("isbn", result["identifiers"])
        self.assertEqual(result["identifiers"]["isbn"], "978-0-553-29335-7")

    def test_parse_opf_empty(self):
        from cli_anything.calibre.core.metadata import _parse_opf_to_dict
        minimal = """<?xml version='1.0'?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"/>
</package>"""
        result = _parse_opf_to_dict(minimal, book_id=99)
        self.assertEqual(result["id"], 99)
        self.assertEqual(result["title"], "")
        self.assertEqual(result["authors"], [])
        self.assertEqual(result["tags"], [])

    def test_parse_opf_bad_xml(self):
        from cli_anything.calibre.core.metadata import _parse_opf_to_dict
        result = _parse_opf_to_dict("NOT XML <<<<", book_id=1)
        self.assertEqual(result["id"], 1)
        self.assertIn("raw_opf", result)

    def test_settable_fields_set(self):
        from cli_anything.calibre.core.metadata import SETTABLE_FIELDS
        for field in ("title", "authors", "tags", "series", "series_index",
                      "rating", "publisher", "pubdate", "comments"):
            self.assertIn(field, SETTABLE_FIELDS)

    def test_parse_opf_multiple_authors(self):
        from cli_anything.calibre.core.metadata import _parse_opf_to_dict
        result = _parse_opf_to_dict(self.MULTI_AUTHOR_OPF, book_id=5)
        self.assertEqual(len(result["authors"]), 2)
        self.assertIn("Terry Pratchett", result["authors"])
        self.assertIn("Neil Gaiman", result["authors"])

    def test_parse_opf_no_tags(self):
        from cli_anything.calibre.core.metadata import _parse_opf_to_dict
        opf = """<?xml version='1.0'?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>No Tags Book</dc:title>
    <dc:creator>Author</dc:creator>
  </metadata>
</package>"""
        result = _parse_opf_to_dict(opf, book_id=7)
        self.assertEqual(result["tags"], [])


# ── custom.py tests ────────────────────────────────────────────────────────


class TestCustomColumns(unittest.TestCase):
    def test_valid_datatypes_set(self):
        from cli_anything.calibre.core.custom import VALID_DATATYPES
        expected = {
            "rating", "text", "comments", "datetime", "int",
            "float", "bool", "series", "enumeration", "composite",
        }
        self.assertEqual(VALID_DATATYPES, expected)

    def test_invalid_datatype_raises(self):
        from cli_anything.calibre.core.custom import add_custom_column
        with mock.patch("cli_anything.calibre.core.custom.find_calibredb",
                        return_value="/usr/bin/calibredb"):
            with self.assertRaises(ValueError) as ctx:
                add_custom_column("/lib", "#myfield", "My Field", "badtype")
        self.assertIn("Invalid datatype", str(ctx.exception))

    def test_label_normalization_add_hash(self):
        """add_custom_column adds # prefix if missing."""
        from cli_anything.calibre.utils.calibre_backend import find_calibredb
        called_with = []

        def fake_run(cmd, library_path=None, timeout=120):
            called_with.append(cmd)
            return {"stdout": "", "stderr": "", "returncode": 0}

        with mock.patch("cli_anything.calibre.core.custom.find_calibredb",
                        return_value="/usr/bin/calibredb"), \
             mock.patch("cli_anything.calibre.core.custom.run_calibredb",
                        side_effect=fake_run):
            from cli_anything.calibre.core.custom import add_custom_column
            add_custom_column("/lib", "myfield", "My Field", "text")

        self.assertTrue(called_with[0][1].startswith("#"))

    def test_label_already_has_hash(self):
        """add_custom_column doesn't double-prefix # if already present."""
        called_with = []

        def fake_run(cmd, library_path=None, timeout=120):
            called_with.append(cmd)
            return {"stdout": "", "stderr": "", "returncode": 0}

        with mock.patch("cli_anything.calibre.core.custom.find_calibredb",
                        return_value="/usr/bin/calibredb"), \
             mock.patch("cli_anything.calibre.core.custom.run_calibredb",
                        side_effect=fake_run):
            from cli_anything.calibre.core.custom import add_custom_column
            add_custom_column("/lib", "#myfield", "My Field", "text")

        label = called_with[0][1]
        self.assertFalse(label.startswith("##"), f"Label double-prefixed: {label}")

    def test_custom_label_normalization_remove(self):
        """remove_custom_column adds # prefix if missing."""
        called_with = []

        def fake_run(cmd, library_path=None, timeout=120):
            called_with.append(cmd)
            return {"stdout": "", "stderr": "", "returncode": 0}

        with mock.patch("cli_anything.calibre.core.custom.find_calibredb",
                        return_value="/usr/bin/calibredb"), \
             mock.patch("cli_anything.calibre.core.custom.run_calibredb",
                        side_effect=fake_run):
            from cli_anything.calibre.core.custom import remove_custom_column
            remove_custom_column("/lib", "genre")

        label = called_with[0][1]
        self.assertTrue(label.startswith("#"))


# ── calibre_backend.py tests ───────────────────────────────────────────────


class TestCalibreBackend(unittest.TestCase):
    def test_find_calibredb_missing(self):
        from cli_anything.calibre.utils.calibre_backend import find_calibredb
        with mock.patch("shutil.which", return_value=None):
            with self.assertRaises(RuntimeError) as ctx:
                find_calibredb()
        self.assertIn("calibredb", str(ctx.exception))

    def test_find_ebook_convert_missing(self):
        from cli_anything.calibre.utils.calibre_backend import find_ebook_convert
        with mock.patch("shutil.which", return_value=None):
            with self.assertRaises(RuntimeError) as ctx:
                find_ebook_convert()
        self.assertIn("ebook-convert", str(ctx.exception))

    def test_find_ebook_meta_missing(self):
        from cli_anything.calibre.utils.calibre_backend import find_ebook_meta
        with mock.patch("shutil.which", return_value=None):
            with self.assertRaises(RuntimeError) as ctx:
                find_ebook_meta()
        self.assertIn("ebook-meta", str(ctx.exception))

    def test_error_message_contains_install_hint(self):
        from cli_anything.calibre.utils.calibre_backend import find_calibredb
        with mock.patch("shutil.which", return_value=None):
            try:
                find_calibredb()
            except RuntimeError as e:
                self.assertIn("apt", str(e).lower())


# ── library.py helper tests ────────────────────────────────────────────────


class TestLibrarySearch(unittest.TestCase):
    def test_search_empty_result(self):
        """Returns [] when calibredb search output is empty."""
        def fake_run(cmd, library_path=None, timeout=120):
            return {"stdout": "", "stderr": "", "returncode": 0}

        with mock.patch("cli_anything.calibre.core.library.find_calibredb",
                        return_value="/usr/bin/calibredb"), \
             mock.patch("cli_anything.calibre.core.library.run_calibredb",
                        side_effect=fake_run):
            from cli_anything.calibre.core.library import search_books
            result = search_books("/lib", "author:nobody")

        self.assertEqual(result, [])

    def test_search_parses_ids(self):
        """Correctly parses comma-separated IDs from calibredb output."""
        def fake_run(cmd, library_path=None, timeout=120):
            return {"stdout": "1, 2, 3, 42", "stderr": "", "returncode": 0}

        with mock.patch("cli_anything.calibre.core.library.find_calibredb",
                        return_value="/usr/bin/calibredb"), \
             mock.patch("cli_anything.calibre.core.library.run_calibredb",
                        side_effect=fake_run):
            from cli_anything.calibre.core.library import search_books
            result = search_books("/lib", "author:asimov")

        self.assertEqual(result, [1, 2, 3, 42])

    def test_list_fields_default(self):
        """Default field list includes required fields."""
        from cli_anything.calibre.core.library import list_books
        captured = []

        def fake_run(cmd, library_path=None, timeout=120):
            captured.append(cmd)
            return {"stdout": "", "stderr": "", "returncode": 0}

        with mock.patch("cli_anything.calibre.core.library.find_calibredb",
                        return_value="/usr/bin/calibredb"), \
             mock.patch("cli_anything.calibre.core.library.run_calibredb",
                        side_effect=fake_run):
            list_books("/lib")

        fields_arg = next((a for a in captured[0] if a.startswith("--fields=")), "")
        self.assertIn("id", fields_arg)
        self.assertIn("title", fields_arg)
        self.assertIn("authors", fields_arg)

    def test_export_creates_output_dir(self):
        """export_books creates the output directory if it doesn't exist."""
        import tempfile
        from cli_anything.calibre.core.export import export_books

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = os.path.join(tmp, "does-not-exist")
            # The directory should not exist yet
            self.assertFalse(os.path.exists(out_dir))

            def fake_run(cmd, library_path=None, timeout=120):
                return {"stdout": "", "stderr": "", "returncode": 0}

            with mock.patch("cli_anything.calibre.core.export.find_calibredb",
                            return_value="/usr/bin/calibredb"), \
                 mock.patch("cli_anything.calibre.core.export.run_calibredb",
                            side_effect=fake_run):
                export_books("/lib", [1], out_dir)

            self.assertTrue(os.path.isdir(out_dir))


# ── EPUB chapter parsing tests ─────────────────────────────────────────────


class TestEpubChapterParsing(unittest.TestCase):
    """Tests for _parse_epub_chapters, _parse_nav_titles, _parse_ncx_titles."""

    _NAV_XHTML = """\
<?xml version='1.0' encoding='utf-8'?>
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:epub="http://www.idpf.org/2007/ops">
<body>
  <nav epub:type="toc">
    <ol>
      <li><a href="Text/chapter1.xhtml">Chapter One</a></li>
      <li><a href="Text/chapter2.xhtml">Chapter Two</a></li>
    </ol>
  </nav>
</body>
</html>"""

    _NCX = """\
<?xml version='1.0' encoding='utf-8'?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <navMap>
    <navPoint id="n1" playOrder="1">
      <navLabel><text>Introduction</text></navLabel>
      <content src="Text/chapter1.xhtml"/>
    </navPoint>
    <navPoint id="n2" playOrder="2">
      <navLabel><text>Main Content</text></navLabel>
      <content src="Text/chapter2.xhtml"/>
    </navPoint>
  </navMap>
</ncx>"""

    _CONTAINER_XML = """\
<?xml version='1.0'?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf"
              media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""

    def _make_epub_dir(self, tmp, *, use_nav: bool) -> Path:
        """Write a minimal EPUB directory to *tmp* and return the path."""
        epub_dir = Path(tmp) / "epub"
        (epub_dir / "META-INF").mkdir(parents=True)
        (epub_dir / "OEBPS" / "Text").mkdir(parents=True)

        (epub_dir / "META-INF" / "container.xml").write_text(self._CONTAINER_XML)
        (epub_dir / "OEBPS" / "Text" / "chapter1.xhtml").write_text(
            "<html><body><h1>Ch 1</h1></body></html>"
        )
        (epub_dir / "OEBPS" / "Text" / "chapter2.xhtml").write_text(
            "<html><body><h1>Ch 2</h1></body></html>"
        )

        if use_nav:
            (epub_dir / "OEBPS" / "nav.xhtml").write_text(self._NAV_XHTML)
            opf = """\
<?xml version='1.0'?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml"
          properties="nav"/>
    <item id="c1" href="Text/chapter1.xhtml"
          media-type="application/xhtml+xml"/>
    <item id="c2" href="Text/chapter2.xhtml"
          media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="c1"/>
    <itemref idref="c2"/>
  </spine>
</package>"""
        else:
            (epub_dir / "OEBPS" / "toc.ncx").write_text(self._NCX)
            opf = """\
<?xml version='1.0'?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
  <manifest>
    <item id="ncx" href="toc.ncx"
          media-type="application/x-dtbncx+xml"/>
    <item id="c1" href="Text/chapter1.xhtml"
          media-type="application/xhtml+xml"/>
    <item id="c2" href="Text/chapter2.xhtml"
          media-type="application/xhtml+xml"/>
  </manifest>
  <spine toc="ncx">
    <itemref idref="c1"/>
    <itemref idref="c2"/>
  </spine>
</package>"""

        (epub_dir / "OEBPS" / "content.opf").write_text(opf)
        return epub_dir

    # ── _parse_epub_chapters ────────────────────────────────────────────────

    def test_parse_epub3_nav_titles_and_order(self):
        from cli_anything.calibre.core.export import _parse_epub_chapters
        with tempfile.TemporaryDirectory() as tmp:
            epub_dir = self._make_epub_dir(tmp, use_nav=True)
            chapters = _parse_epub_chapters(epub_dir)
        self.assertEqual(len(chapters), 2)
        self.assertEqual(chapters[0]["title"], "Chapter One")
        self.assertEqual(chapters[1]["title"], "Chapter Two")
        self.assertEqual(chapters[0]["order"], 1)
        self.assertEqual(chapters[1]["order"], 2)

    def test_parse_epub2_ncx_titles_and_order(self):
        from cli_anything.calibre.core.export import _parse_epub_chapters
        with tempfile.TemporaryDirectory() as tmp:
            epub_dir = self._make_epub_dir(tmp, use_nav=False)
            chapters = _parse_epub_chapters(epub_dir)
        self.assertEqual(len(chapters), 2)
        self.assertEqual(chapters[0]["title"], "Introduction")
        self.assertEqual(chapters[1]["title"], "Main Content")

    def test_parse_epub_src_is_relative(self):
        """src paths must be relative to epub_dir, not absolute."""
        from cli_anything.calibre.core.export import _parse_epub_chapters
        with tempfile.TemporaryDirectory() as tmp:
            epub_dir = self._make_epub_dir(tmp, use_nav=True)
            chapters = _parse_epub_chapters(epub_dir)
        for ch in chapters:
            self.assertFalse(
                Path(ch["src"]).is_absolute(),
                f"src should be relative, got: {ch['src']}",
            )

    def test_parse_epub_fallback_default_titles(self):
        """When there is no nav or NCX, chapters get generic fallback titles."""
        from cli_anything.calibre.core.export import _parse_epub_chapters
        with tempfile.TemporaryDirectory() as tmp:
            epub_dir = Path(tmp) / "epub"
            (epub_dir / "META-INF").mkdir(parents=True)
            (epub_dir / "OEBPS").mkdir()
            (epub_dir / "META-INF" / "container.xml").write_text(
                self._CONTAINER_XML
            )
            (epub_dir / "OEBPS" / "solo.xhtml").write_text(
                "<html><body>solo</body></html>"
            )
            (epub_dir / "OEBPS" / "content.opf").write_text("""\
<?xml version='1.0'?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
  <manifest>
    <item id="c1" href="solo.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine><itemref idref="c1"/></spine>
</package>""")
            chapters = _parse_epub_chapters(epub_dir)
        self.assertEqual(len(chapters), 1)
        self.assertIn("Chapter", chapters[0]["title"])

    def test_parse_epub_missing_container_raises(self):
        from cli_anything.calibre.core.export import _parse_epub_chapters
        with tempfile.TemporaryDirectory() as tmp:
            epub_dir = Path(tmp) / "bad_epub"
            epub_dir.mkdir()
            with self.assertRaises(RuntimeError):
                _parse_epub_chapters(epub_dir)

    # ── export_chapters_pdf ─────────────────────────────────────────────────

    def test_export_chapters_pdf_no_epub_raises(self):
        """FileNotFoundError when the book has no EPUB format."""
        from cli_anything.calibre.core.export import export_chapters_pdf

        def fake_calibredb(cmd, library_path=None, timeout=120):
            return {"stdout": "", "stderr": "", "returncode": 0}

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch(
                "cli_anything.calibre.core.export.find_calibredb",
                return_value="/usr/bin/calibredb",
            ), mock.patch(
                "cli_anything.calibre.core.export.find_ebook_convert",
                return_value="/usr/bin/ebook-convert",
            ), mock.patch(
                "cli_anything.calibre.core.export.run_calibredb",
                side_effect=fake_calibredb,
            ):
                with self.assertRaises(FileNotFoundError) as ctx:
                    export_chapters_pdf("/lib", 42, tmp)
            self.assertIn("EPUB", str(ctx.exception))

    # ── CLI command ─────────────────────────────────────────────────────────

    def _run_cli(self, args):
        from click.testing import CliRunner
        from cli_anything.calibre.calibre_cli import main
        return CliRunner().invoke(main, args)

    def test_books_export_chapters_help(self):
        result = self._run_cli(["books", "export-chapters", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("PDF", result.output)

    def test_books_export_chapters_invalid_range(self):
        """Non-numeric --chapters value exits with error."""
        with mock.patch(
            "cli_anything.calibre.core.session.load_session",
            return_value={"library_path": "/lib", "last_command": None},
        ):
            result = self._run_cli(
                ["books", "export-chapters", "1", "--to-dir", "/tmp", "--chapters", "abc"]
            )
        self.assertNotEqual(result.exit_code, 0)


# ── CLI invocation tests ───────────────────────────────────────────────────


class TestCLIHelp(unittest.TestCase):
    def _run_cli(self, args):
        from click.testing import CliRunner
        from cli_anything.calibre.calibre_cli import main
        runner = CliRunner()
        return runner.invoke(main, args)

    def test_cli_help_exits_zero(self):
        result = self._run_cli(["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("calibre", result.output.lower())

    def test_cli_version(self):
        result = self._run_cli(["--version"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("1.0.0", result.output)

    def test_cli_missing_library_error(self):
        """list command without a library set shows helpful error."""
        with mock.patch("cli_anything.calibre.core.session.load_session",
                        return_value={"library_path": None, "last_command": None}), \
             mock.patch("cli_anything.calibre.utils.calibre_backend.find_calibredb",
                        return_value="/usr/bin/calibredb"):
            result = self._run_cli(["books", "list"])
        # Should exit non-zero or print error about missing library
        self.assertTrue(
            result.exit_code != 0 or "library" in result.output.lower() or
            "library" in (result.output + (result.stderr or "")).lower()
        )


if __name__ == "__main__":
    unittest.main()
