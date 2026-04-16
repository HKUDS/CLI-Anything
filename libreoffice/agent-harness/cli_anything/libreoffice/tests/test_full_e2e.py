"""End-to-end tests for LibreOffice CLI with real ODF file validation
and real LibreOffice headless conversion.

These tests:
1. Create ODF files and validate their XML structure (native tests)
2. Convert ODF -> PDF/DOCX/XLSX/PPTX via LibreOffice headless (true E2E)
3. Verify output files exist, have correct format, and contain expected content
4. Print all generated artifact paths so users can inspect the output

Requires: libreoffice (system package) for the LibreOffice backend tests.
"""

import json
import os
import sys
import tempfile
import zipfile
import subprocess
import xml.etree.ElementTree as ET
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from cli_anything.libreoffice.core.document import create_document, save_document, open_document, get_document_info
from cli_anything.libreoffice.core.writer import (
    add_paragraph, add_heading, add_list, add_table, add_page_break,
    list_content, remove_content,
)
from cli_anything.libreoffice.core.calc import add_sheet, set_cell, get_cell, list_sheets, remove_sheet
from cli_anything.libreoffice.core.impress import (
    add_slide, remove_slide, set_slide_content, add_slide_element, list_slides,
)
from cli_anything.libreoffice.core.styles import create_style, apply_style, list_styles
from cli_anything.libreoffice.core.export import (
    export, to_odt, to_ods, to_odp, to_html, to_text, list_presets,
)
from cli_anything.libreoffice.core.session import Session
from cli_anything.libreoffice.utils.odf_utils import validate_odf, parse_odf, ODF_MIMETYPES
from cli_anything.libreoffice.utils.lo_backend import find_libreoffice, get_version, convert_odf_to


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


# ── ODF Structure Validation ────────────────────────────────────

class TestODFStructure:
    def test_odt_is_valid_zip(self, tmp_dir):
        proj = create_document(doc_type="writer", name="test")
        add_paragraph(proj, text="Hello world")
        path = os.path.join(tmp_dir, "test.odt")
        to_odt(proj, path)
        assert zipfile.is_zipfile(path)

    def test_odt_mimetype_first_uncompressed(self, tmp_dir):
        proj = create_document(doc_type="writer")
        add_paragraph(proj, text="Test")
        path = os.path.join(tmp_dir, "test.odt")
        to_odt(proj, path)

        with zipfile.ZipFile(path, "r") as zf:
            names = zf.namelist()
            assert names[0] == "mimetype"
            info = zf.getinfo("mimetype")
            assert info.compress_type == zipfile.ZIP_STORED

    def test_odt_mimetype_content(self, tmp_dir):
        proj = create_document(doc_type="writer")
        path = os.path.join(tmp_dir, "test.odt")
        to_odt(proj, path)

        with zipfile.ZipFile(path, "r") as zf:
            mimetype = zf.read("mimetype").decode("utf-8")
            assert mimetype == ODF_MIMETYPES["writer"]

    def test_odt_has_required_files(self, tmp_dir):
        proj = create_document(doc_type="writer")
        add_paragraph(proj, text="Content")
        path = os.path.join(tmp_dir, "test.odt")
        to_odt(proj, path)

        with zipfile.ZipFile(path, "r") as zf:
            names = zf.namelist()
            assert "mimetype" in names
            assert "content.xml" in names
            assert "styles.xml" in names
            assert "meta.xml" in names
            assert "META-INF/manifest.xml" in names

    def test_odt_content_xml_valid(self, tmp_dir):
        proj = create_document(doc_type="writer")
        add_heading(proj, text="Title", level=1)
        add_paragraph(proj, text="Body text")
        path = os.path.join(tmp_dir, "test.odt")
        to_odt(proj, path)

        with zipfile.ZipFile(path, "r") as zf:
            content = zf.read("content.xml").decode("utf-8")
            root = ET.fromstring(content)
            assert root is not None

    def test_odt_styles_xml_valid(self, tmp_dir):
        proj = create_document(doc_type="writer")
        path = os.path.join(tmp_dir, "test.odt")
        to_odt(proj, path)

        with zipfile.ZipFile(path, "r") as zf:
            styles = zf.read("styles.xml").decode("utf-8")
            root = ET.fromstring(styles)
            assert root is not None

    def test_odt_meta_xml_valid(self, tmp_dir):
        proj = create_document(doc_type="writer")
        path = os.path.join(tmp_dir, "test.odt")
        to_odt(proj, path)

        with zipfile.ZipFile(path, "r") as zf:
            meta = zf.read("meta.xml").decode("utf-8")
            root = ET.fromstring(meta)
            assert root is not None

    def test_odt_validate_utility(self, tmp_dir):
        proj = create_document(doc_type="writer")
        add_paragraph(proj, text="Validate me")
        path = os.path.join(tmp_dir, "test.odt")
        to_odt(proj, path)

        result = validate_odf(path)
        assert result["valid"] is True
        assert len(result["errors"]) == 0

    def test_ods_structure(self, tmp_dir):
        proj = create_document(doc_type="calc")
        set_cell(proj, "A1", "Hello")
        set_cell(proj, "B1", "42", cell_type="float")
        path = os.path.join(tmp_dir, "test.ods")
        to_ods(proj, path)

        result = validate_odf(path)
        assert result["valid"] is True
        with zipfile.ZipFile(path, "r") as zf:
            mimetype = zf.read("mimetype").decode("utf-8")
            assert mimetype == ODF_MIMETYPES["calc"]

    def test_odp_structure(self, tmp_dir):
        proj = create_document(doc_type="impress")
        add_slide(proj, title="Welcome", content="Hello")
        path = os.path.join(tmp_dir, "test.odp")
        to_odp(proj, path)

        result = validate_odf(path)
        assert result["valid"] is True
        with zipfile.ZipFile(path, "r") as zf:
            mimetype = zf.read("mimetype").decode("utf-8")
            assert mimetype == ODF_MIMETYPES["impress"]


# ── Writer E2E ──────────────────────────────────────────────────

class TestWriterE2E:
    def test_full_document_odt(self, tmp_dir):
        proj = create_document(doc_type="writer", name="Full Report")
        add_heading(proj, text="Introduction", level=1)
        add_paragraph(proj, text="This is the intro paragraph.")
        add_heading(proj, text="Data", level=2)
        add_table(proj, rows=3, cols=3, data=[
            ["Name", "Age", "City"],
            ["Alice", "30", "NYC"],
            ["Bob", "25", "LA"],
        ])
        add_list(proj, items=["Point A", "Point B", "Point C"], list_style="bullet")
        add_page_break(proj)
        add_heading(proj, text="Conclusion", level=1)
        add_paragraph(proj, text="In conclusion...")

        path = os.path.join(tmp_dir, "report.odt")
        result = to_odt(proj, path)
        assert os.path.exists(path)
        assert result["format"] == "writer"

        # Validate content
        parsed = parse_odf(path)
        assert "Title" not in parsed.get("mimetype", "")  # just mimetype check
        content_xml = parsed["content_xml"]
        assert "Introduction" in content_xml
        assert "Alice" in content_xml
        assert "Point A" in content_xml

    def test_styled_paragraph_in_odt(self, tmp_dir):
        proj = create_document(doc_type="writer")
        add_paragraph(proj, text="Bold text", style={"bold": True, "font_size": "16pt"})
        path = os.path.join(tmp_dir, "styled.odt")
        to_odt(proj, path)

        parsed = parse_odf(path)
        content = parsed["content_xml"]
        assert "Bold text" in content
        assert "bold" in content.lower() or "font-weight" in content.lower()

    def test_writer_html_export(self, tmp_dir):
        proj = create_document(doc_type="writer", name="HTML Test")
        add_heading(proj, text="Title", level=1)
        add_paragraph(proj, text="Body text")
        add_list(proj, items=["A", "B"])
        path = os.path.join(tmp_dir, "doc.html")
        result = to_html(proj, path)
        assert os.path.exists(path)

        with open(path) as f:
            html = f.read()
        assert "<h1>Title</h1>" in html
        assert "<p>Body text</p>" in html
        assert "<li>A</li>" in html

    def test_writer_text_export(self, tmp_dir):
        proj = create_document(doc_type="writer")
        add_heading(proj, text="Header", level=1)
        add_paragraph(proj, text="Paragraph text")
        add_list(proj, items=["X", "Y"], list_style="number")
        path = os.path.join(tmp_dir, "doc.txt")
        result = to_text(proj, path)
        assert os.path.exists(path)

        with open(path) as f:
            text = f.read()
        assert "# Header" in text
        assert "Paragraph text" in text
        assert "1. X" in text


# ── Calc E2E ────────────────────────────────────────────────────

class TestCalcE2E:
    def test_multi_sheet_ods(self, tmp_dir):
        proj = create_document(doc_type="calc", name="Budget")
        set_cell(proj, "A1", "Item", sheet=0)
        set_cell(proj, "B1", "Cost", sheet=0)
        set_cell(proj, "A2", "Rent", sheet=0)
        set_cell(proj, "B2", "1500", cell_type="float", sheet=0)

        add_sheet(proj, name="Summary")
        set_cell(proj, "A1", "Total", sheet=1)

        path = os.path.join(tmp_dir, "budget.ods")
        to_ods(proj, path)

        result = validate_odf(path)
        assert result["valid"] is True

        parsed = parse_odf(path)
        assert "Item" in parsed["content_xml"]
        assert "Rent" in parsed["content_xml"]
        assert "Summary" in parsed["content_xml"]

    def test_calc_html_export(self, tmp_dir):
        proj = create_document(doc_type="calc")
        set_cell(proj, "A1", "Name")
        set_cell(proj, "B1", "Score")
        set_cell(proj, "A2", "Alice")
        set_cell(proj, "B2", "95")
        path = os.path.join(tmp_dir, "sheet.html")
        to_html(proj, path)

        with open(path) as f:
            html = f.read()
        assert "Name" in html
        assert "Alice" in html
        assert "<table" in html

    def test_calc_text_export(self, tmp_dir):
        proj = create_document(doc_type="calc")
        set_cell(proj, "A1", "X")
        set_cell(proj, "B1", "Y")
        path = os.path.join(tmp_dir, "sheet.txt")
        to_text(proj, path)

        with open(path) as f:
            text = f.read()
        assert "X" in text
        assert "Y" in text


# ── Impress E2E ─────────────────────────────────────────────────

class TestImpressE2E:
    def test_multi_slide_odp(self, tmp_dir):
        proj = create_document(doc_type="impress", name="Deck")
        add_slide(proj, title="Welcome", content="Hello everyone")
        add_slide(proj, title="Agenda", content="1. Intro\n2. Main\n3. Q&A")
        add_slide(proj, title="Thank You")

        path = os.path.join(tmp_dir, "deck.odp")
        to_odp(proj, path)

        result = validate_odf(path)
        assert result["valid"] is True

        parsed = parse_odf(path)
        assert "Welcome" in parsed["content_xml"]
        assert "Agenda" in parsed["content_xml"]

    def test_impress_with_elements(self, tmp_dir):
        proj = create_document(doc_type="impress")
        add_slide(proj, title="Slide 1")
        add_slide_element(proj, 0, text="Custom text box", x="5cm", y="10cm")
        path = os.path.join(tmp_dir, "elem.odp")
        to_odp(proj, path)

        parsed = parse_odf(path)
        assert "Custom text box" in parsed["content_xml"]

    def test_impress_html_export(self, tmp_dir):
        proj = create_document(doc_type="impress")
        add_slide(proj, title="Slide 1", content="Content 1")
        add_slide(proj, title="Slide 2", content="Content 2")
        path = os.path.join(tmp_dir, "pres.html")
        to_html(proj, path)

        with open(path) as f:
            html = f.read()
        assert "Slide 1" in html
        assert "Content 1" in html
        assert "<hr>" in html


# ── Export Edge Cases ───────────────────────────────────────────

class TestExportEdgeCases:
    def test_overwrite_protection(self, tmp_dir):
        proj = create_document(doc_type="writer")
        add_paragraph(proj, text="Test")
        path = os.path.join(tmp_dir, "test.odt")
        to_odt(proj, path, overwrite=True)
        with pytest.raises(FileExistsError):
            to_odt(proj, path, overwrite=False)

    def test_overwrite_allowed(self, tmp_dir):
        proj = create_document(doc_type="writer")
        add_paragraph(proj, text="V1")
        path = os.path.join(tmp_dir, "test.odt")
        to_odt(proj, path, overwrite=True)
        to_odt(proj, path, overwrite=True)
        assert os.path.exists(path)

    def test_export_empty_writer(self, tmp_dir):
        proj = create_document(doc_type="writer")
        path = os.path.join(tmp_dir, "empty.odt")
        to_odt(proj, path)
        result = validate_odf(path)
        assert result["valid"] is True

    def test_export_empty_calc(self, tmp_dir):
        proj = create_document(doc_type="calc")
        path = os.path.join(tmp_dir, "empty.ods")
        to_ods(proj, path)
        result = validate_odf(path)
        assert result["valid"] is True

    def test_export_empty_impress(self, tmp_dir):
        proj = create_document(doc_type="impress")
        path = os.path.join(tmp_dir, "empty.odp")
        to_odp(proj, path)
        result = validate_odf(path)
        assert result["valid"] is True

    def test_export_preset_odt(self, tmp_dir):
        proj = create_document(doc_type="writer")
        add_paragraph(proj, text="Preset test")
        path = os.path.join(tmp_dir, "preset.odt")
        result = export(proj, path, preset="odt")
        assert result["format"] == "writer"
        assert os.path.exists(path)

    def test_export_preset_html(self, tmp_dir):
        proj = create_document(doc_type="writer")
        add_paragraph(proj, text="HTML preset")
        path = os.path.join(tmp_dir, "preset.html")
        result = export(proj, path, preset="html")
        assert result["format"] == "html"

    def test_export_preset_text(self, tmp_dir):
        proj = create_document(doc_type="writer")
        add_paragraph(proj, text="Text preset")
        path = os.path.join(tmp_dir, "preset.txt")
        result = export(proj, path, preset="text")
        assert result["format"] == "text"

    def test_export_invalid_preset(self, tmp_dir):
        proj = create_document()
        with pytest.raises(ValueError, match="Unknown preset"):
            export(proj, "/tmp/test.xyz", preset="xyz")

    def test_list_presets(self):
        presets = list_presets()
        names = [p["name"] for p in presets]
        assert "odt" in names
        assert "ods" in names
        assert "odp" in names
        assert "html" in names
        assert "text" in names


# ── Styles in ODF ───────────────────────────────────────────────

class TestStylesInODF:
    def test_custom_style_in_odt(self, tmp_dir):
        proj = create_document(doc_type="writer")
        create_style(proj, "MyTitle", properties={
            "font_size": "24pt", "bold": True, "color": "#003366"
        })
        add_paragraph(proj, text="Styled text")
        apply_style(proj, "MyTitle", 0)

        path = os.path.join(tmp_dir, "styled.odt")
        to_odt(proj, path)

        parsed = parse_odf(path)
        styles_xml = parsed["styles_xml"]
        assert "MyTitle" in styles_xml
        assert "24pt" in styles_xml

    def test_page_layout_in_odt(self, tmp_dir):
        proj = create_document(doc_type="writer", profile="letter_portrait")
        add_paragraph(proj, text="Letter size")
        path = os.path.join(tmp_dir, "letter.odt")
        to_odt(proj, path)

        parsed = parse_odf(path)
        styles_xml = parsed["styles_xml"]
        assert "21.59cm" in styles_xml


# ── Project Lifecycle ───────────────────────────────────────────

class TestProjectLifecycle:
    def test_create_save_open_roundtrip(self, tmp_dir):
        proj = create_document(name="roundtrip")
        path = os.path.join(tmp_dir, "project.lo-cli.json")
        save_document(proj, path)
        loaded = open_document(path)
        assert loaded["name"] == "roundtrip"
        assert loaded["type"] == "writer"

    def test_complex_project_roundtrip(self, tmp_dir):
        proj = create_document(doc_type="writer", name="complex")
        add_heading(proj, text="Title", level=1)
        add_paragraph(proj, text="Body")
        add_table(proj, rows=2, cols=2, data=[["A", "B"], ["C", "D"]])
        create_style(proj, "Bold", properties={"bold": True})

        path = os.path.join(tmp_dir, "complex.json")
        save_document(proj, path)
        loaded = open_document(path)
        assert len(loaded["content"]) == 3
        assert "Bold" in loaded["styles"]

    def test_calc_project_roundtrip(self, tmp_dir):
        proj = create_document(doc_type="calc")
        set_cell(proj, "A1", "Test")
        set_cell(proj, "B1", "42", cell_type="float")
        path = os.path.join(tmp_dir, "calc.json")
        save_document(proj, path)
        loaded = open_document(path)
        assert loaded["sheets"][0]["cells"]["A1"]["value"] == "Test"
        assert loaded["sheets"][0]["cells"]["B1"]["value"] == 42.0


# ── Session Integration ─────────────────────────────────────────

class TestSessionIntegration:
    def test_undo_paragraph_add(self):
        sess = Session()
        proj = create_document(doc_type="writer")
        sess.set_project(proj)

        sess.snapshot("add paragraph")
        add_paragraph(proj, text="Hello")
        assert len(proj["content"]) == 1

        sess.undo()
        assert len(sess.get_project()["content"]) == 0

    def test_undo_cell_change(self):
        sess = Session()
        proj = create_document(doc_type="calc")
        sess.set_project(proj)

        sess.snapshot("set cell")
        set_cell(proj, "A1", "Original")

        sess.snapshot("change cell")
        set_cell(proj, "A1", "Changed")

        sess.undo()
        assert sess.get_project()["sheets"][0]["cells"]["A1"]["value"] == "Original"

    def test_undo_slide_add(self):
        sess = Session()
        proj = create_document(doc_type="impress")
        sess.set_project(proj)

        sess.snapshot("add slide")
        add_slide(proj, title="Slide 1")
        assert len(proj["slides"]) == 1

        sess.undo()
        assert len(sess.get_project()["slides"]) == 0

    def test_undo_style_create(self):
        sess = Session()
        proj = create_document(doc_type="writer")
        sess.set_project(proj)

        sess.snapshot("create style")
        create_style(proj, "TestStyle")
        assert "TestStyle" in proj["styles"]

        sess.undo()
        assert "TestStyle" not in sess.get_project()["styles"]


# ── CLI Subprocess Tests ────────────────────────────────────────

def _resolve_cli(name):
    """Resolve installed CLI command; falls back to python -m for dev.

    Set env CLI_ANYTHING_FORCE_INSTALLED=1 to require the installed command.
    """
    import shutil
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    module = name.replace("cli-anything-", "cli_anything.") + "." + name.split("-")[-1] + "_cli"
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m {module}")
    return [sys.executable, "-m", module]


class TestCLISubprocess:
    CLI_BASE = _resolve_cli("cli-anything-libreoffice")

    def _run(self, args, check=True):
        return subprocess.run(
            self.CLI_BASE + args,
            capture_output=True, text=True,
            check=check,
        )

    def test_help(self):
        result = self._run(["--help"])
        assert result.returncode == 0
        assert "LibreOffice CLI" in result.stdout

    def test_document_new(self, tmp_dir):
        out = os.path.join(tmp_dir, "test.json")
        result = self._run(["document", "new", "-o", out])
        assert result.returncode == 0
        assert os.path.exists(out)

    def test_document_new_json(self, tmp_dir):
        out = os.path.join(tmp_dir, "test.json")
        result = self._run(["--json", "document", "new", "-o", out])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["type"] == "writer"

    def test_document_profiles(self):
        result = self._run(["document", "profiles"])
        assert result.returncode == 0
        assert "a4_portrait" in result.stdout

    def test_export_presets(self):
        result = self._run(["export", "presets"])
        assert result.returncode == 0
        assert "odt" in result.stdout

    def test_full_workflow(self, tmp_dir):
        proj_path = os.path.join(tmp_dir, "workflow.json")
        odt_path = os.path.join(tmp_dir, "output.odt")

        # Create project
        self._run(["--json", "document", "new", "-o", proj_path,
                    "--type", "writer", "-n", "Workflow"])

        # Add content
        self._run(["--project", proj_path,
                    "writer", "add-heading", "-t", "Title", "-l", "1"])

        # Save
        self._run(["--project", proj_path, "document", "save"])

        # Export to ODF
        self._run(["--project", proj_path,
                    "export", "render", odt_path, "-p", "odt", "--overwrite"])

        assert os.path.exists(odt_path)
        result = validate_odf(odt_path)
        assert result["valid"] is True

    def test_calc_workflow(self, tmp_dir):
        proj_path = os.path.join(tmp_dir, "calc.json")
        ods_path = os.path.join(tmp_dir, "output.ods")

        self._run(["document", "new", "--type", "calc", "-o", proj_path])
        self._run(["--project", proj_path, "calc", "set-cell", "A1", "Hello"])
        self._run(["--project", proj_path, "document", "save"])
        self._run(["--project", proj_path,
                    "export", "render", ods_path, "-p", "ods", "--overwrite"])

        assert os.path.exists(ods_path)
        result = validate_odf(ods_path)
        assert result["valid"] is True

    def test_impress_workflow(self, tmp_dir):
        proj_path = os.path.join(tmp_dir, "impress.json")
        odp_path = os.path.join(tmp_dir, "output.odp")

        self._run(["document", "new", "--type", "impress", "-o", proj_path])
        self._run(["--project", proj_path,
                    "impress", "add-slide", "-t", "Welcome"])
        self._run(["--project", proj_path, "document", "save"])
        self._run(["--project", proj_path,
                    "export", "render", odp_path, "-p", "odp", "--overwrite"])

        assert os.path.exists(odp_path)
        result = validate_odf(odp_path)
        assert result["valid"] is True


# ── ODF Content Verification ────────────────────────────────────

class TestODFContent:
    def test_writer_heading_in_xml(self, tmp_dir):
        proj = create_document(doc_type="writer")
        add_heading(proj, text="My Heading", level=2)
        path = os.path.join(tmp_dir, "h.odt")
        to_odt(proj, path)

        parsed = parse_odf(path)
        assert "My Heading" in parsed["content_xml"]
        # ODF heading element
        assert "text:h" in parsed["content_xml"] or "h" in parsed["content_xml"]

    def test_writer_table_in_xml(self, tmp_dir):
        proj = create_document(doc_type="writer")
        add_table(proj, rows=2, cols=2, data=[["A", "B"], ["C", "D"]])
        path = os.path.join(tmp_dir, "t.odt")
        to_odt(proj, path)

        parsed = parse_odf(path)
        for val in ["A", "B", "C", "D"]:
            assert val in parsed["content_xml"]

    def test_writer_list_in_xml(self, tmp_dir):
        proj = create_document(doc_type="writer")
        add_list(proj, items=["Apple", "Banana"])
        path = os.path.join(tmp_dir, "l.odt")
        to_odt(proj, path)

        parsed = parse_odf(path)
        assert "Apple" in parsed["content_xml"]
        assert "Banana" in parsed["content_xml"]

    def test_calc_cells_in_xml(self, tmp_dir):
        proj = create_document(doc_type="calc")
        set_cell(proj, "A1", "Name")
        set_cell(proj, "B1", "100", cell_type="float")
        path = os.path.join(tmp_dir, "c.ods")
        to_ods(proj, path)

        parsed = parse_odf(path)
        assert "Name" in parsed["content_xml"]
        assert "100" in parsed["content_xml"]

    def test_impress_slides_in_xml(self, tmp_dir):
        proj = create_document(doc_type="impress")
        add_slide(proj, title="Intro Slide", content="Welcome all")
        path = os.path.join(tmp_dir, "i.odp")
        to_odp(proj, path)

        parsed = parse_odf(path)
        assert "Intro Slide" in parsed["content_xml"]
        assert "Welcome all" in parsed["content_xml"]

    def test_meta_xml_has_title(self, tmp_dir):
        proj = create_document(doc_type="writer", name="MetaTest")
        proj["metadata"]["title"] = "My Document Title"
        path = os.path.join(tmp_dir, "meta.odt")
        to_odt(proj, path)

        parsed = parse_odf(path)
        assert "My Document Title" in parsed["meta_xml"]

    def test_manifest_has_entries(self, tmp_dir):
        proj = create_document(doc_type="writer")
        path = os.path.join(tmp_dir, "manifest.odt")
        to_odt(proj, path)

        parsed = parse_odf(path)
        manifest = parsed["manifest_xml"]
        assert "content.xml" in manifest
        assert "styles.xml" in manifest
        assert "meta.xml" in manifest


# ── LibreOffice Backend Tests ──────────────────────────────────
# These tests invoke the real LibreOffice installation via headless mode.
# They produce actual PDF, DOCX, XLSX, PPTX files — not simulations.


class TestLibreOfficeBackend:
    """Test that LibreOffice is installed and the backend works."""

    def test_libreoffice_is_installed(self):
        lo = find_libreoffice()
        assert os.path.exists(lo), f"LibreOffice not found at {lo}"
        print(f"\n  LibreOffice binary: {lo}")

    def test_libreoffice_version(self):
        version = get_version()
        assert "LibreOffice" in version
        print(f"\n  {version}")


class TestWriterToPDF:
    """True E2E: Writer document -> ODF -> PDF via LibreOffice headless."""

    def test_simple_writer_to_pdf(self, tmp_dir):
        proj = create_document(doc_type="writer", name="PDF Test")
        add_heading(proj, text="Hello World", level=1)
        add_paragraph(proj, text="This paragraph was generated by cli-anything-libreoffice "
                                  "and converted to PDF by LibreOffice headless.")

        pdf_path = os.path.join(tmp_dir, "simple.pdf")
        result = export(proj, pdf_path, preset="pdf", overwrite=True)

        assert os.path.exists(result["output"]), f"PDF not created: {result['output']}"
        assert result["format"] == "pdf"
        assert result["file_size"] > 0
        # PDF magic bytes
        with open(result["output"], "rb") as f:
            magic = f.read(5)
        assert magic == b"%PDF-", f"Not a valid PDF file (magic: {magic!r})"
        print(f"\n  PDF output: {result['output']} ({result['file_size']:,} bytes)")

    def test_rich_writer_to_pdf(self, tmp_dir):
        """Full Writer document with headings, tables, lists -> PDF."""
        proj = create_document(doc_type="writer", name="Full Report")
        add_heading(proj, text="Quarterly Report", level=1)
        add_paragraph(proj, text="Executive summary of Q1 performance.")
        add_heading(proj, text="Sales Data", level=2)
        add_table(proj, rows=3, cols=3, data=[
            ["Product", "Q1 Sales", "Q2 Sales"],
            ["Widget A", "$15,000", "$18,000"],
            ["Widget B", "$12,000", "$14,500"],
        ])
        add_list(proj, items=[
            "Increase marketing spend by 20%",
            "Launch Widget C in Q3",
            "Expand to EU market",
        ])
        add_page_break(proj)
        add_heading(proj, text="Conclusion", level=1)
        add_paragraph(proj, text="Results exceeded expectations.")

        pdf_path = os.path.join(tmp_dir, "full_report.pdf")
        result = export(proj, pdf_path, preset="pdf", overwrite=True)

        assert os.path.exists(result["output"])
        assert result["file_size"] > 1000, "PDF suspiciously small for a rich document"
        with open(result["output"], "rb") as f:
            assert f.read(5) == b"%PDF-"
        print(f"\n  Rich PDF: {result['output']} ({result['file_size']:,} bytes)")

    def test_styled_writer_to_pdf(self, tmp_dir):
        """Writer with custom styles -> PDF."""
        proj = create_document(doc_type="writer")
        create_style(proj, "BoldTitle", properties={
            "font_size": "24pt", "bold": True, "color": "#003366"
        })
        add_paragraph(proj, text="Styled Document Title")
        apply_style(proj, "BoldTitle", 0)
        add_paragraph(proj, text="Normal body text following the styled title.")

        pdf_path = os.path.join(tmp_dir, "styled.pdf")
        result = export(proj, pdf_path, preset="pdf", overwrite=True)
        assert os.path.exists(result["output"])
        assert result["file_size"] > 0
        print(f"\n  Styled PDF: {result['output']} ({result['file_size']:,} bytes)")


class TestWriterToDOCX:
    """True E2E: Writer document -> ODF -> DOCX via LibreOffice headless."""

    def test_writer_to_docx(self, tmp_dir):
        proj = create_document(doc_type="writer", name="DOCX Test")
        add_heading(proj, text="Word Document", level=1)
        add_paragraph(proj, text="Converted from ODF to DOCX via LibreOffice.")
        add_table(proj, rows=2, cols=2, data=[["A", "B"], ["C", "D"]])

        docx_path = os.path.join(tmp_dir, "output.docx")
        result = export(proj, docx_path, preset="docx", overwrite=True)

        assert os.path.exists(result["output"])
        assert result["format"] == "docx"
        # DOCX is a ZIP file (OOXML)
        assert zipfile.is_zipfile(result["output"]), "DOCX is not a valid ZIP/OOXML file"
        with zipfile.ZipFile(result["output"]) as zf:
            names = zf.namelist()
            assert "[Content_Types].xml" in names, "Missing OOXML content types"
            assert any("document.xml" in n for n in names), "Missing document.xml in DOCX"
        print(f"\n  DOCX output: {result['output']} ({result['file_size']:,} bytes)")


class TestCalcToXLSX:
    """True E2E: Calc spreadsheet -> ODS -> XLSX via LibreOffice headless."""

    def test_calc_to_xlsx(self, tmp_dir):
        proj = create_document(doc_type="calc", name="Spreadsheet Test")
        set_cell(proj, "A1", "Item")
        set_cell(proj, "B1", "Cost")
        set_cell(proj, "A2", "Rent")
        set_cell(proj, "B2", "1500", cell_type="float")
        set_cell(proj, "A3", "Food")
        set_cell(proj, "B3", "600", cell_type="float")

        xlsx_path = os.path.join(tmp_dir, "budget.xlsx")
        result = export(proj, xlsx_path, preset="xlsx", overwrite=True)

        assert os.path.exists(result["output"])
        assert result["format"] == "xlsx"
        assert zipfile.is_zipfile(result["output"]), "XLSX is not a valid ZIP/OOXML file"
        with zipfile.ZipFile(result["output"]) as zf:
            names = zf.namelist()
            assert "[Content_Types].xml" in names
            # XLSX should contain a sheet
            assert any("sheet" in n.lower() for n in names), \
                f"No sheet found in XLSX. Files: {names}"
        print(f"\n  XLSX output: {result['output']} ({result['file_size']:,} bytes)")

    def test_calc_to_csv(self, tmp_dir):
        proj = create_document(doc_type="calc", name="CSV Test")
        set_cell(proj, "A1", "Name")
        set_cell(proj, "B1", "Score")
        set_cell(proj, "A2", "Alice")
        set_cell(proj, "B2", "95", cell_type="float")

        csv_path = os.path.join(tmp_dir, "scores.csv")
        result = export(proj, csv_path, preset="csv", overwrite=True)

        assert os.path.exists(result["output"])
        with open(result["output"]) as f:
            content = f.read()
        # CSV should contain our data
        assert "Name" in content or "Alice" in content, \
            f"CSV doesn't contain expected data: {content[:200]}"
        print(f"\n  CSV output: {result['output']} ({result['file_size']:,} bytes)")
        print(f"  CSV content:\n{content}")

    def test_calc_to_pdf(self, tmp_dir):
        proj = create_document(doc_type="calc", name="PDF Calc")
        set_cell(proj, "A1", "Budget Item")
        set_cell(proj, "B1", "Amount")
        set_cell(proj, "A2", "Salary")
        set_cell(proj, "B2", "5000", cell_type="float")

        pdf_path = os.path.join(tmp_dir, "calc.pdf")
        result = export(proj, pdf_path, preset="pdf", overwrite=True)

        assert os.path.exists(result["output"])
        with open(result["output"], "rb") as f:
            assert f.read(5) == b"%PDF-"
        print(f"\n  Calc PDF: {result['output']} ({result['file_size']:,} bytes)")


class TestImpressToPPTX:
    """True E2E: Impress presentation -> ODP -> PPTX via LibreOffice headless."""

    def test_impress_to_pptx(self, tmp_dir):
        proj = create_document(doc_type="impress", name="Presentation Test")
        add_slide(proj, title="Welcome", content="Our Annual Report")
        add_slide(proj, title="Key Metrics", content="Revenue: $10M\nGrowth: 25%")
        add_slide(proj, title="Thank You", content="Questions?")

        pptx_path = os.path.join(tmp_dir, "deck.pptx")
        result = export(proj, pptx_path, preset="pptx", overwrite=True)

        assert os.path.exists(result["output"])
        assert result["format"] == "pptx"
        assert zipfile.is_zipfile(result["output"]), "PPTX is not a valid ZIP/OOXML file"
        with zipfile.ZipFile(result["output"]) as zf:
            names = zf.namelist()
            assert "[Content_Types].xml" in names
            assert any("slide" in n.lower() for n in names), \
                f"No slides found in PPTX. Files: {names}"
        print(f"\n  PPTX output: {result['output']} ({result['file_size']:,} bytes)")

    def test_impress_to_pdf(self, tmp_dir):
        proj = create_document(doc_type="impress", name="PDF Deck")
        add_slide(proj, title="Title Slide", content="Subtitle text")
        add_slide(proj, title="Content Slide", content="Bullet points here")

        pdf_path = os.path.join(tmp_dir, "slides.pdf")
        result = export(proj, pdf_path, preset="pdf", overwrite=True)

        assert os.path.exists(result["output"])
        with open(result["output"], "rb") as f:
            assert f.read(5) == b"%PDF-"
        print(f"\n  Impress PDF: {result['output']} ({result['file_size']:,} bytes)")


class TestCLISubprocessE2E:
    """True E2E via subprocess: invoke the installed CLI to produce real files."""

    CLI_BASE = _resolve_cli("cli-anything-libreoffice")

    def _run(self, args, check=True):
        return subprocess.run(
            self.CLI_BASE + args,
            capture_output=True, text=True,
            check=check,
        )

    def test_full_writer_pdf_workflow(self, tmp_dir):
        """CLI subprocess: create writer doc, add content, export to PDF."""
        proj_path = os.path.join(tmp_dir, "cli_test.json")
        pdf_path = os.path.join(tmp_dir, "cli_output.pdf")

        # Create project
        self._run(["document", "new", "-o", proj_path, "--type", "writer", "-n", "CLI PDF Test"])
        # Add content
        self._run(["--project", proj_path, "writer", "add-heading", "-t", "CLI Generated", "-l", "1"])
        self._run(["--project", proj_path, "writer", "add-paragraph", "-t",
                    "This PDF was generated entirely via the CLI subprocess."])
        # Save
        self._run(["--project", proj_path, "document", "save"])
        # Export to PDF
        self._run(["--project", proj_path, "export", "render", pdf_path, "-p", "pdf", "--overwrite"])

        assert os.path.exists(pdf_path), f"PDF not created at {pdf_path}"
        size = os.path.getsize(pdf_path)
        assert size > 0, "PDF is empty"
        with open(pdf_path, "rb") as f:
            assert f.read(5) == b"%PDF-", "Not a valid PDF"
        print(f"\n  CLI PDF: {pdf_path} ({size:,} bytes)")

    def test_full_calc_xlsx_workflow(self, tmp_dir):
        """CLI subprocess: create calc doc, set cells, export to XLSX."""
        proj_path = os.path.join(tmp_dir, "calc_test.json")
        xlsx_path = os.path.join(tmp_dir, "calc_output.xlsx")

        self._run(["document", "new", "-o", proj_path, "--type", "calc"])
        self._run(["--project", proj_path, "calc", "set-cell", "A1", "Name"])
        self._run(["--project", proj_path, "calc", "set-cell", "B1", "Score"])
        self._run(["--project", proj_path, "calc", "set-cell", "A2", "Alice"])
        self._run(["--project", proj_path, "calc", "set-cell", "B2", "95", "--type", "float"])
        self._run(["--project", proj_path, "document", "save"])
        self._run(["--project", proj_path, "export", "render", xlsx_path, "-p", "xlsx", "--overwrite"])

        assert os.path.exists(xlsx_path), f"XLSX not created at {xlsx_path}"
        assert zipfile.is_zipfile(xlsx_path), "XLSX is not a valid ZIP"
        print(f"\n  CLI XLSX: {xlsx_path} ({os.path.getsize(xlsx_path):,} bytes)")

    def test_full_impress_pptx_workflow(self, tmp_dir):
        """CLI subprocess: create presentation, add slides, export to PPTX."""
        proj_path = os.path.join(tmp_dir, "impress_test.json")
        pptx_path = os.path.join(tmp_dir, "impress_output.pptx")

        self._run(["document", "new", "-o", proj_path, "--type", "impress"])
        self._run(["--project", proj_path, "impress", "add-slide", "-t", "Welcome"])
        self._run(["--project", proj_path, "impress", "add-slide", "-t", "Agenda", "-c", "Overview"])
        self._run(["--project", proj_path, "document", "save"])
        self._run(["--project", proj_path, "export", "render", pptx_path, "-p", "pptx", "--overwrite"])

        assert os.path.exists(pptx_path), f"PPTX not created at {pptx_path}"
        assert zipfile.is_zipfile(pptx_path), "PPTX is not a valid ZIP"
        print(f"\n  CLI PPTX: {pptx_path} ({os.path.getsize(pptx_path):,} bytes)")

    def test_full_writer_docx_workflow(self, tmp_dir):
        """CLI subprocess: writer -> DOCX via LibreOffice headless."""
        proj_path = os.path.join(tmp_dir, "docx_test.json")
        docx_path = os.path.join(tmp_dir, "docx_output.docx")

        self._run(["document", "new", "-o", proj_path, "--type", "writer", "-n", "DOCX Test"])
        self._run(["--project", proj_path, "writer", "add-heading", "-t", "DOCX via CLI", "-l", "1"])
        self._run(["--project", proj_path, "writer", "add-paragraph", "-t", "Full E2E through subprocess."])
        self._run(["--project", proj_path, "document", "save"])
        self._run(["--project", proj_path, "export", "render", docx_path, "-p", "docx", "--overwrite"])

        assert os.path.exists(docx_path)
        assert zipfile.is_zipfile(docx_path)
        print(f"\n  CLI DOCX: {docx_path} ({os.path.getsize(docx_path):,} bytes)")
