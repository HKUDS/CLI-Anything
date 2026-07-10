"""Unit tests for LibreOffice CLI core modules.

Tests use synthetic data only -- no LibreOffice installation needed.
"""

import json
import os
import sys
import tempfile
import shutil
import zipfile
from pathlib import Path
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from cli_anything.libreoffice.core.document import (
    create_document, open_document, save_document,
    get_document_info, list_profiles, PROFILES,
)
from cli_anything.libreoffice.core.writer import (
    add_paragraph, add_heading, add_list, add_table, add_page_break,
    remove_content, list_content, get_content, set_content_text,
)
from cli_anything.libreoffice.core.calc import (
    add_sheet, remove_sheet, rename_sheet, set_cell, get_cell,
    clear_cell, list_sheets, get_sheet_data,
)
from cli_anything.libreoffice.core.impress import (
    add_slide, remove_slide, set_slide_content, add_slide_element,
    remove_slide_element, move_slide, duplicate_slide, list_slides, get_slide,
)
from cli_anything.libreoffice.core.styles import (
    create_style, modify_style, remove_style, list_styles,
    get_style, apply_style,
)
from cli_anything.libreoffice.core.session import Session
from cli_anything.libreoffice.core.export import to_odt, to_ods, to_odp
from cli_anything.libreoffice.core import importer as importer_mod
from cli_anything.libreoffice.utils.odf_utils import parse_odf


# ── Document Tests ───────────────────────────────────────────────

class TestDocument:
    def test_create_writer(self):
        proj = create_document(doc_type="writer")
        assert proj["type"] == "writer"
        assert proj["version"] == "1.0"
        assert "content" in proj
        assert isinstance(proj["content"], list)

    def test_create_calc(self):
        proj = create_document(doc_type="calc")
        assert proj["type"] == "calc"
        assert "sheets" in proj
        assert len(proj["sheets"]) == 1

    def test_create_impress(self):
        proj = create_document(doc_type="impress")
        assert proj["type"] == "impress"
        assert "slides" in proj

    def test_create_with_name(self):
        proj = create_document(name="My Report")
        assert proj["name"] == "My Report"

    def test_create_with_profile(self):
        proj = create_document(profile="a4_portrait")
        assert proj["settings"]["page_width"] == "21cm"
        assert proj["settings"]["page_height"] == "29.7cm"

    def test_create_with_letter_profile(self):
        proj = create_document(profile="letter_portrait")
        assert proj["settings"]["page_width"] == "21.59cm"

    def test_create_invalid_type(self):
        with pytest.raises(ValueError, match="Invalid document type"):
            create_document(doc_type="spreadsheet")

    def test_create_invalid_profile(self):
        with pytest.raises(ValueError, match="Unknown profile"):
            create_document(profile="bogus")

    def test_save_and_open(self):
        proj = create_document(name="roundtrip_test")
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = f.name
        try:
            save_document(proj, path)
            loaded = open_document(path)
            assert loaded["name"] == "roundtrip_test"
            assert loaded["type"] == "writer"
        finally:
            os.unlink(path)

    def test_open_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            open_document("/nonexistent/file.json")

    def test_open_invalid_file(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            json.dump({"foo": "bar"}, f)
            path = f.name
        try:
            with pytest.raises(ValueError, match="Invalid project file"):
                open_document(path)
        finally:
            os.unlink(path)

    def test_open_odt_as_project_gives_import_hint(self):
        proj = create_document(doc_type="writer")
        add_paragraph(proj, text="Existing file")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "existing.odt")
            to_odt(proj, path)
            with pytest.raises(ValueError, match="document import"):
                open_document(path)

    def test_get_document_info_writer(self):
        proj = create_document(name="info_test", doc_type="writer")
        info = get_document_info(proj)
        assert info["name"] == "info_test"
        assert info["type"] == "writer"
        assert info["content_count"] == 0

    def test_get_document_info_calc(self):
        proj = create_document(doc_type="calc")
        info = get_document_info(proj)
        assert info["sheet_count"] == 1

    def test_list_profiles(self):
        profiles = list_profiles()
        assert len(profiles) > 0
        names = [p["name"] for p in profiles]
        assert "a4_portrait" in names
        assert "letter_portrait" in names

    def test_metadata_populated(self):
        proj = create_document()
        assert "metadata" in proj
        assert "created" in proj["metadata"]
        assert proj["metadata"]["software"] == "libreoffice-cli 1.0"


class TestImport:
    def test_list_import_formats_includes_office_and_odf(self):
        formats = importer_mod.list_import_formats()
        extensions = {item["extension"] for item in formats}
        assert ".odt" in extensions
        assert ".docx" in extensions
        assert ".xlsx" in extensions
        assert ".pptx" in extensions

    def test_import_writer_odt(self):
        proj = create_document(doc_type="writer", name="import_writer")
        add_heading(proj, text="Imported Heading", level=2)
        add_paragraph(proj, text="Imported paragraph")
        add_list(proj, items=["One", "Two"])
        add_table(proj, rows=2, cols=2, data=[["A", "B"], ["C", "D"]])

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "writer.odt")
            to_odt(proj, path)
            imported = importer_mod.import_document(path)

        assert imported["type"] == "writer"
        assert imported["metadata"]["import_method"] == "native-odf"
        assert [item["type"] for item in imported["content"]] == [
            "heading", "paragraph", "list", "table",
        ]
        assert imported["content"][0]["text"] == "Imported Heading"
        assert imported["content"][0]["level"] == 2
        assert imported["content"][3]["data"][1][1] == "D"

    def test_import_calc_ods(self):
        proj = create_document(doc_type="calc", name="import_calc")
        set_cell(proj, "A1", "Name")
        set_cell(proj, "B1", "42", cell_type="float")

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "sheet.ods")
            to_ods(proj, path)
            imported = importer_mod.import_document(path)

        assert imported["type"] == "calc"
        assert imported["sheets"][0]["name"] == "Sheet1"
        assert imported["sheets"][0]["cells"]["A1"]["value"] == "Name"
        assert imported["sheets"][0]["cells"]["B1"]["value"] == 42.0
        assert imported["sheets"][0]["cells"]["B1"]["type"] == "float"

    def test_import_calc_formula_normalizes_odf_prefix(self):
        proj = create_document(doc_type="calc", name="formula_calc")
        set_cell(proj, "A1", "1", cell_type="float")
        set_cell(proj, "A2", "2", cell_type="float")
        set_cell(proj, "A3", "0", cell_type="float", formula="=A1+A2")

        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, "formula.ods")
            roundtrip = os.path.join(tmp, "roundtrip.ods")
            to_ods(proj, source)
            imported = importer_mod.import_document(source)
            to_ods(imported, roundtrip)
            content_xml = parse_odf(roundtrip)["content_xml"]

        formula = imported["sheets"][0]["cells"]["A3"]["formula"]
        assert formula == "=A1+A2"
        assert 'table:formula="of:=A1+A2"' in content_xml
        assert "of:of:=" not in content_xml

    def test_import_impress_odp(self):
        proj = create_document(doc_type="impress", name="import_impress")
        add_slide(proj, title="Intro", content="Welcome")
        add_slide(proj, title="End", content="Questions")

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "deck.odp")
            to_odp(proj, path)
            imported = importer_mod.import_document(path)

        assert imported["type"] == "impress"
        assert len(imported["slides"]) == 2
        assert imported["slides"][0]["title"] == "Intro"
        assert imported["slides"][0]["content"] == "Welcome"

    def test_import_docx_uses_libreoffice_conversion(self, monkeypatch):
        source_proj = create_document(doc_type="writer")
        add_paragraph(source_proj, text="Converted content")

        with tempfile.TemporaryDirectory() as tmp:
            odt_path = os.path.join(tmp, "converted.odt")
            to_odt(source_proj, odt_path)
            docx_path = os.path.join(tmp, "input.docx")
            with open(docx_path, "wb") as f:
                f.write(b"fake docx; conversion is monkeypatched")

            def fake_convert(input_path, output_format, output_dir=None, timeout=120):
                assert input_path == docx_path
                assert output_format == "odt"
                out = os.path.join(output_dir, "input.odt")
                shutil.copyfile(odt_path, out)
                return out

            monkeypatch.setattr(importer_mod, "convert", fake_convert)
            imported = importer_mod.import_document(docx_path)

        assert imported["type"] == "writer"
        assert imported["metadata"]["import_method"] == "libreoffice-headless"
        assert imported["metadata"]["original_format"] == "docx"
        assert imported["content"][0]["text"] == "Converted content"

    def test_reject_unsupported_import_format(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            path = f.name
        try:
            with pytest.raises(ValueError, match="Unsupported import format"):
                importer_mod.import_document(path)
        finally:
            os.unlink(path)

    def test_reject_invalid_odf_file(self):
        with tempfile.NamedTemporaryFile(suffix=".odt", delete=False) as f:
            f.write(b"not a zip")
            path = f.name
        try:
            with pytest.raises(ValueError, match="Invalid ODF file"):
                importer_mod.import_document(path)
        finally:
            os.unlink(path)

    def test_reject_malformed_odf_meta_xml(self):
        proj = create_document(doc_type="writer")
        add_paragraph(proj, text="body")

        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, "source.odt")
            malformed = os.path.join(tmp, "malformed.odt")
            to_odt(proj, source)

            with zipfile.ZipFile(source, "r") as zin, zipfile.ZipFile(malformed, "w") as zout:
                for info in zin.infolist():
                    data = zin.read(info.filename)
                    if info.filename == "meta.xml":
                        data = b"<broken>"
                    zout.writestr(info, data)

            with pytest.raises(ValueError, match="Invalid ODF meta.xml"):
                importer_mod.import_document(malformed)


# ── Writer Tests ─────────────────────────────────────────────────

class TestWriter:
    def _make_doc(self):
        return create_document(doc_type="writer")

    def test_add_paragraph(self):
        proj = self._make_doc()
        item = add_paragraph(proj, text="Hello world")
        assert item["type"] == "paragraph"
        assert item["text"] == "Hello world"
        assert len(proj["content"]) == 1

    def test_add_paragraph_with_style(self):
        proj = self._make_doc()
        item = add_paragraph(proj, text="Styled", style={"bold": True, "font_size": "14pt"})
        assert item["style"]["bold"] is True
        assert item["style"]["font_size"] == "14pt"

    def test_add_heading(self):
        proj = self._make_doc()
        item = add_heading(proj, text="Title", level=1)
        assert item["type"] == "heading"
        assert item["level"] == 1

    def test_add_heading_level_range(self):
        proj = self._make_doc()
        add_heading(proj, text="H1", level=1)
        add_heading(proj, text="H6", level=6)
        assert len(proj["content"]) == 2

    def test_add_heading_invalid_level(self):
        proj = self._make_doc()
        with pytest.raises(ValueError, match="Heading level"):
            add_heading(proj, level=7)

    def test_add_list_bullet(self):
        proj = self._make_doc()
        item = add_list(proj, items=["A", "B", "C"], list_style="bullet")
        assert item["type"] == "list"
        assert item["list_style"] == "bullet"
        assert len(item["items"]) == 3

    def test_add_list_number(self):
        proj = self._make_doc()
        item = add_list(proj, items=["First", "Second"], list_style="number")
        assert item["list_style"] == "number"

    def test_add_list_invalid_style(self):
        proj = self._make_doc()
        with pytest.raises(ValueError, match="Invalid list style"):
            add_list(proj, list_style="roman")

    def test_add_table(self):
        proj = self._make_doc()
        item = add_table(proj, rows=3, cols=4)
        assert item["type"] == "table"
        assert item["rows"] == 3
        assert item["cols"] == 4
        assert len(item["data"]) == 3
        assert len(item["data"][0]) == 4

    def test_add_table_with_data(self):
        proj = self._make_doc()
        data = [["Name", "Age"], ["Alice", "30"]]
        item = add_table(proj, rows=2, cols=2, data=data)
        assert item["data"][0][0] == "Name"

    def test_add_table_invalid_dims(self):
        proj = self._make_doc()
        with pytest.raises(ValueError, match="at least 1"):
            add_table(proj, rows=0, cols=2)

    def test_add_page_break(self):
        proj = self._make_doc()
        item = add_page_break(proj)
        assert item["type"] == "page_break"

    def test_add_at_position(self):
        proj = self._make_doc()
        add_paragraph(proj, text="First")
        add_paragraph(proj, text="Third")
        add_paragraph(proj, text="Second", position=1)
        assert proj["content"][1]["text"] == "Second"

    def test_add_at_invalid_position(self):
        proj = self._make_doc()
        with pytest.raises(IndexError):
            add_paragraph(proj, text="Bad", position=5)

    def test_remove_content(self):
        proj = self._make_doc()
        add_paragraph(proj, text="A")
        add_paragraph(proj, text="B")
        removed = remove_content(proj, 0)
        assert removed["text"] == "A"
        assert len(proj["content"]) == 1

    def test_remove_content_empty(self):
        proj = self._make_doc()
        with pytest.raises(ValueError, match="No content"):
            remove_content(proj, 0)

    def test_list_content(self):
        proj = self._make_doc()
        add_heading(proj, text="Title", level=1)
        add_paragraph(proj, text="Body text")
        add_list(proj, items=["A", "B"])
        result = list_content(proj)
        assert len(result) == 3
        assert result[0]["type"] == "heading"
        assert result[1]["type"] == "paragraph"
        assert result[2]["type"] == "list"

    def test_get_content(self):
        proj = self._make_doc()
        add_paragraph(proj, text="Test")
        item = get_content(proj, 0)
        assert item["text"] == "Test"

    def test_set_content_text(self):
        proj = self._make_doc()
        add_paragraph(proj, text="Old")
        item = set_content_text(proj, 0, "New")
        assert item["text"] == "New"

    def test_set_content_text_on_table(self):
        proj = self._make_doc()
        add_table(proj)
        with pytest.raises(ValueError, match="Cannot set text"):
            set_content_text(proj, 0, "Text")

    def test_writer_rejects_calc(self):
        proj = create_document(doc_type="calc")
        with pytest.raises(ValueError, match="expected 'writer'"):
            add_paragraph(proj, text="Hello")


# ── Calc Tests ───────────────────────────────────────────────────

class TestCalc:
    def _make_doc(self):
        return create_document(doc_type="calc")

    def test_add_sheet(self):
        proj = self._make_doc()
        sheet = add_sheet(proj, name="Data")
        assert sheet["name"] == "Data"
        assert len(proj["sheets"]) == 2  # Sheet1 + Data

    def test_add_sheet_duplicate_name(self):
        proj = self._make_doc()
        with pytest.raises(ValueError, match="already exists"):
            add_sheet(proj, name="Sheet1")

    def test_remove_sheet(self):
        proj = self._make_doc()
        add_sheet(proj, name="Extra")
        removed = remove_sheet(proj, 1)
        assert removed["name"] == "Extra"
        assert len(proj["sheets"]) == 1

    def test_remove_last_sheet(self):
        proj = self._make_doc()
        with pytest.raises(ValueError, match="Cannot remove the last"):
            remove_sheet(proj, 0)

    def test_rename_sheet(self):
        proj = self._make_doc()
        sheet = rename_sheet(proj, 0, "Renamed")
        assert sheet["name"] == "Renamed"

    def test_set_cell_string(self):
        proj = self._make_doc()
        result = set_cell(proj, "A1", "Hello")
        assert result["value"] == "Hello"
        assert result["type"] == "string"

    def test_set_cell_float(self):
        proj = self._make_doc()
        result = set_cell(proj, "B2", "42.5", cell_type="float")
        assert result["value"] == 42.5

    def test_set_cell_formula(self):
        proj = self._make_doc()
        result = set_cell(proj, "C1", "0", formula="=A1+B1")
        assert result["formula"] == "=A1+B1"

    def test_get_cell(self):
        proj = self._make_doc()
        set_cell(proj, "A1", "Test")
        result = get_cell(proj, "A1")
        assert result["value"] == "Test"

    def test_get_cell_empty(self):
        proj = self._make_doc()
        result = get_cell(proj, "Z99")
        assert result["type"] == "empty"
        assert result["value"] is None

    def test_clear_cell(self):
        proj = self._make_doc()
        set_cell(proj, "A1", "Temp")
        result = clear_cell(proj, "A1")
        assert result["cleared"] is True
        result2 = get_cell(proj, "A1")
        assert result2["type"] == "empty"

    def test_invalid_cell_ref(self):
        proj = self._make_doc()
        with pytest.raises(ValueError, match="Invalid cell reference"):
            set_cell(proj, "123", "Bad")

    def test_list_sheets(self):
        proj = self._make_doc()
        add_sheet(proj, name="Sheet2")
        result = list_sheets(proj)
        assert len(result) == 2
        assert result[0]["name"] == "Sheet1"
        assert result[1]["name"] == "Sheet2"

    def test_get_sheet_data(self):
        proj = self._make_doc()
        set_cell(proj, "A1", "X")
        set_cell(proj, "B1", "Y")
        data = get_sheet_data(proj)
        assert data["cell_count"] == 2

    def test_calc_rejects_writer(self):
        proj = create_document(doc_type="writer")
        with pytest.raises(ValueError, match="expected 'calc'"):
            add_sheet(proj, name="S1")

    def test_cell_ref_case_insensitive(self):
        proj = self._make_doc()
        set_cell(proj, "a1", "lower")
        result = get_cell(proj, "A1")
        assert result["value"] == "lower"


# ── Impress Tests ────────────────────────────────────────────────

class TestImpress:
    def _make_doc(self):
        return create_document(doc_type="impress")

    def test_add_slide(self):
        proj = self._make_doc()
        slide = add_slide(proj, title="Welcome", content="Hello")
        assert slide["title"] == "Welcome"
        assert len(proj["slides"]) == 1

    def test_add_slide_at_position(self):
        proj = self._make_doc()
        add_slide(proj, title="First")
        add_slide(proj, title="Third")
        add_slide(proj, title="Second", position=1)
        assert proj["slides"][1]["title"] == "Second"

    def test_remove_slide(self):
        proj = self._make_doc()
        add_slide(proj, title="Remove Me")
        removed = remove_slide(proj, 0)
        assert removed["title"] == "Remove Me"
        assert len(proj["slides"]) == 0

    def test_remove_slide_empty(self):
        proj = self._make_doc()
        with pytest.raises(ValueError, match="No slides"):
            remove_slide(proj, 0)

    def test_set_slide_content(self):
        proj = self._make_doc()
        add_slide(proj, title="Old Title", content="Old Content")
        slide = set_slide_content(proj, 0, title="New Title")
        assert slide["title"] == "New Title"
        assert slide["content"] == "Old Content"  # Unchanged

    def test_add_element(self):
        proj = self._make_doc()
        add_slide(proj, title="Slide 1")
        elem = add_slide_element(proj, 0, text="Box text")
        assert elem["type"] == "text_box"
        assert elem["text"] == "Box text"

    def test_remove_element(self):
        proj = self._make_doc()
        add_slide(proj, title="S1")
        add_slide_element(proj, 0, text="E1")
        removed = remove_slide_element(proj, 0, 0)
        assert removed["text"] == "E1"

    def test_move_slide(self):
        proj = self._make_doc()
        add_slide(proj, title="A")
        add_slide(proj, title="B")
        add_slide(proj, title="C")
        move_slide(proj, 0, 2)
        assert proj["slides"][2]["title"] == "A"

    def test_duplicate_slide(self):
        proj = self._make_doc()
        add_slide(proj, title="Original")
        dup = duplicate_slide(proj, 0)
        assert dup["title"] == "Original (copy)"
        assert len(proj["slides"]) == 2

    def test_list_slides(self):
        proj = self._make_doc()
        add_slide(proj, title="S1")
        add_slide(proj, title="S2")
        result = list_slides(proj)
        assert len(result) == 2
        assert result[0]["title"] == "S1"

    def test_get_slide(self):
        proj = self._make_doc()
        add_slide(proj, title="Test Slide")
        slide = get_slide(proj, 0)
        assert slide["title"] == "Test Slide"

    def test_impress_rejects_writer(self):
        proj = create_document(doc_type="writer")
        with pytest.raises(ValueError, match="expected 'impress'"):
            add_slide(proj, title="No")

    def test_invalid_element_type(self):
        proj = self._make_doc()
        add_slide(proj, title="S1")
        with pytest.raises(ValueError, match="Invalid element type"):
            add_slide_element(proj, 0, element_type="video")


# ── Style Tests ──────────────────────────────────────────────────

class TestStyles:
    def _make_doc(self):
        return create_document(doc_type="writer")

    def test_create_style(self):
        proj = self._make_doc()
        result = create_style(proj, "MyStyle", properties={"bold": True})
        assert result["name"] == "MyStyle"
        assert result["properties"]["bold"] is True

    def test_create_style_duplicate(self):
        proj = self._make_doc()
        create_style(proj, "S1")
        with pytest.raises(ValueError, match="already exists"):
            create_style(proj, "S1")

    def test_create_style_invalid_family(self):
        proj = self._make_doc()
        with pytest.raises(ValueError, match="Invalid style family"):
            create_style(proj, "S1", family="table")

    def test_create_style_invalid_property(self):
        proj = self._make_doc()
        with pytest.raises(ValueError, match="Unknown style properties"):
            create_style(proj, "S1", properties={"bogus": True})

    def test_modify_style(self):
        proj = self._make_doc()
        create_style(proj, "S1", properties={"bold": True})
        result = modify_style(proj, "S1", properties={"italic": True})
        assert result["properties"]["bold"] is True
        assert result["properties"]["italic"] is True

    def test_modify_nonexistent(self):
        proj = self._make_doc()
        with pytest.raises(ValueError, match="not found"):
            modify_style(proj, "NoStyle")

    def test_remove_style(self):
        proj = self._make_doc()
        create_style(proj, "S1")
        removed = remove_style(proj, "S1")
        assert removed["name"] == "S1"
        assert "S1" not in proj["styles"]

    def test_list_styles(self):
        proj = self._make_doc()
        create_style(proj, "A")
        create_style(proj, "B")
        result = list_styles(proj)
        assert len(result) == 2

    def test_get_style(self):
        proj = self._make_doc()
        create_style(proj, "TestStyle", properties={"font_size": "14pt"})
        result = get_style(proj, "TestStyle")
        assert result["properties"]["font_size"] == "14pt"

    def test_apply_style(self):
        proj = self._make_doc()
        add_paragraph(proj, text="Hello")
        create_style(proj, "Bold", properties={"bold": True})
        result = apply_style(proj, "Bold", 0)
        assert result["style_applied"] == "Bold"
        assert proj["content"][0]["style"]["bold"] is True

    def test_apply_style_not_writer(self):
        proj = create_document(doc_type="calc")
        with pytest.raises(ValueError, match="only supported for Writer"):
            apply_style(proj, "S1", 0)

    def test_apply_nonexistent_style(self):
        proj = self._make_doc()
        add_paragraph(proj, text="Test")
        with pytest.raises(ValueError, match="not found"):
            apply_style(proj, "NoStyle", 0)


# ── Session Tests ────────────────────────────────────────────────

class TestSession:
    def test_create_session(self):
        sess = Session()
        assert not sess.has_project()

    def test_set_project(self):
        sess = Session()
        proj = create_document()
        sess.set_project(proj)
        assert sess.has_project()

    def test_get_project_no_project(self):
        sess = Session()
        with pytest.raises(RuntimeError, match="No document loaded"):
            sess.get_project()

    def test_undo_redo(self):
        sess = Session()
        proj = create_document(name="original")
        sess.set_project(proj)

        sess.snapshot("change name")
        proj["name"] = "modified"

        assert proj["name"] == "modified"
        sess.undo()
        assert sess.get_project()["name"] == "original"
        sess.redo()
        assert sess.get_project()["name"] == "modified"

    def test_undo_empty(self):
        sess = Session()
        sess.set_project(create_document())
        with pytest.raises(RuntimeError, match="Nothing to undo"):
            sess.undo()

    def test_redo_empty(self):
        sess = Session()
        sess.set_project(create_document())
        with pytest.raises(RuntimeError, match="Nothing to redo"):
            sess.redo()

    def test_snapshot_clears_redo(self):
        sess = Session()
        proj = create_document(name="v1")
        sess.set_project(proj)

        sess.snapshot("v2")
        proj["name"] = "v2"
        sess.undo()

        sess.snapshot("v3")
        sess.get_project()["name"] = "v3"

        with pytest.raises(RuntimeError, match="Nothing to redo"):
            sess.redo()

    def test_status(self):
        sess = Session()
        proj = create_document(name="test")
        sess.set_project(proj, "/tmp/test.json")
        status = sess.status()
        assert status["has_project"] is True
        assert status["project_path"] == "/tmp/test.json"
        assert status["undo_count"] == 0
        assert status["document_type"] == "writer"

    def test_save_session(self):
        sess = Session()
        proj = create_document(name="save_test")
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            sess.set_project(proj, path)
            saved = sess.save_session()
            assert os.path.exists(saved)
            with open(saved) as f:
                loaded = json.load(f)
            assert loaded["name"] == "save_test"
        finally:
            os.unlink(path)

    def test_list_history(self):
        sess = Session()
        proj = create_document()
        sess.set_project(proj)
        sess.snapshot("action 1")
        sess.snapshot("action 2")
        history = sess.list_history()
        assert len(history) == 2
        assert history[0]["description"] == "action 2"

    def test_max_undo(self):
        sess = Session()
        sess.MAX_UNDO = 5
        proj = create_document()
        sess.set_project(proj)
        for i in range(10):
            sess.snapshot(f"action {i}")
        assert len(sess._undo_stack) == 5

    def test_multiple_undo(self):
        sess = Session()
        proj = create_document(doc_type="writer")
        sess.set_project(proj)

        sess.snapshot("add first")
        add_paragraph(proj, text="First")

        sess.snapshot("add second")
        add_paragraph(proj, text="Second")

        assert len(sess.get_project()["content"]) == 2
        sess.undo()
        assert len(sess.get_project()["content"]) == 1
        sess.undo()
        assert len(sess.get_project()["content"]) == 0


# ── LibreOffice backend (subprocess-mocked) ────────────────────────

from unittest.mock import patch, MagicMock
import subprocess as _subprocess
from cli_anything.libreoffice.utils import lo_backend


def _make_completed(returncode=0, stderr="", stdout=""):
    """Build a subprocess.CompletedProcess for monkeypatched runs."""
    return _subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr,
    )


class TestBackend:
    def test_conservative_flags_present(self, monkeypatch, tmp_path):
        """Direct headless invocation includes the full conservative flag set."""
        monkeypatch.setattr(lo_backend, "find_libreoffice",
                            lambda: "/Applications/LibreOffice.app/Contents/MacOS/soffice")
        monkeypatch.setattr(lo_backend.sys, "platform", "linux")

        input_file = tmp_path / "doc.odt"
        input_file.write_bytes(b"fake")
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        captured = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            # Simulate the output file being produced
            base = os.path.splitext(os.path.basename(cmd[-1]))[0]
            out_path = os.path.join(kwargs.get("env", {}).get("OUTDIR", str(out_dir)),
                                    f"{base}.pdf")
            # The real cmd has --outdir <dir> as positional args; pluck from cmd
            outdir_idx = cmd.index("--outdir") + 1
            out_path = os.path.join(cmd[outdir_idx], f"{base}.pdf")
            Path(out_path).write_bytes(b"%PDF-")
            return _make_completed(returncode=0)

        monkeypatch.setattr(lo_backend.subprocess, "run", fake_run)

        result = lo_backend.convert(str(input_file), "pdf", output_dir=str(out_dir))
        assert result == str((out_dir / "doc.pdf").resolve())
        cmd = captured["cmd"]
        for flag in ("--headless", "--nologo", "--nodefault",
                     "--norestore", "--nolockcheck", "--nofirststartwizard"):
            assert flag in cmd, f"missing flag {flag} in cmd: {cmd}"

    def test_macos_app_bundle_resolution(self):
        with patch.object(lo_backend.sys, "platform", "darwin"):
            bundle = lo_backend._macos_app_bundle(
                "/Applications/LibreOffice.app/Contents/MacOS/soffice")
            assert bundle == "/Applications/LibreOffice.app"

    def test_macos_app_bundle_returns_none_on_linux(self):
        with patch.object(lo_backend.sys, "platform", "linux"):
            assert lo_backend._macos_app_bundle(
                "/Applications/LibreOffice.app/Contents/MacOS/soffice") is None

    def test_looks_like_macos_abort_signal(self):
        assert lo_backend._looks_like_macos_abort(_make_completed(returncode=-6))
        assert not lo_backend._looks_like_macos_abort(_make_completed(returncode=0))

    def test_looks_like_macos_abort_stderr_text(self):
        assert lo_backend._looks_like_macos_abort(
            _make_completed(returncode=1, stderr="something Trace/BPT trap: 5"))
        assert lo_backend._looks_like_macos_abort(
            _make_completed(returncode=1, stderr="Abort trap: 6"))
        assert not lo_backend._looks_like_macos_abort(
            _make_completed(returncode=1, stderr="some other failure"))

    def test_macos_fallback_invoked_on_abort(self, monkeypatch, tmp_path):
        """On macOS, when direct soffice aborts, LaunchServices is retried."""
        monkeypatch.setattr(lo_backend, "find_libreoffice",
                            lambda: "/Applications/LibreOffice.app/Contents/MacOS/soffice")
        monkeypatch.setattr(lo_backend.sys, "platform", "darwin")

        input_file = tmp_path / "doc.odt"
        input_file.write_bytes(b"fake")
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            if len(calls) == 1:
                # Direct soffice invocation: simulate SIGABRT
                return _make_completed(returncode=-6, stderr="Trace/BPT trap: 5")
            # LaunchServices retry: write the output and return success
            outdir_idx = cmd.index("--outdir") + 1
            out_path = os.path.join(cmd[outdir_idx], "doc.pdf")
            Path(out_path).write_bytes(b"%PDF-")
            return _make_completed(returncode=0)

        monkeypatch.setattr(lo_backend.subprocess, "run", fake_run)

        result = lo_backend.convert(str(input_file), "pdf", output_dir=str(out_dir))
        assert result == str((out_dir / "doc.pdf").resolve())
        assert len(calls) == 2
        # Second call must be the LaunchServices `open -W -n -a <bundle> --args`
        assert calls[1][0] == "open"
        assert "-W" in calls[1] and "-n" in calls[1]
        assert "/Applications/LibreOffice.app" in calls[1]
        assert "--args" in calls[1]

    def test_no_fallback_on_linux(self, monkeypatch, tmp_path):
        """Linux/Windows: direct soffice failure is surfaced without `open`."""
        monkeypatch.setattr(lo_backend, "find_libreoffice", lambda: "/usr/bin/soffice")
        monkeypatch.setattr(lo_backend.sys, "platform", "linux")

        input_file = tmp_path / "doc.odt"
        input_file.write_bytes(b"fake")
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return _make_completed(returncode=1, stderr="some failure")

        monkeypatch.setattr(lo_backend.subprocess, "run", fake_run)

        with pytest.raises(RuntimeError, match="exit 1"):
            lo_backend.convert(str(input_file), "pdf", output_dir=str(out_dir))
        assert len(calls) == 1
        assert calls[0][0] == "/usr/bin/soffice"

    def test_macos_double_failure_raises_helpful_error(self, monkeypatch, tmp_path):
        """When both direct and LaunchServices paths fail on macOS, the error
        mentions the upstream bug + manual workarounds."""
        monkeypatch.setattr(lo_backend, "find_libreoffice",
                            lambda: "/Applications/LibreOffice.app/Contents/MacOS/soffice")
        monkeypatch.setattr(lo_backend.sys, "platform", "darwin")

        input_file = tmp_path / "doc.odt"
        input_file.write_bytes(b"fake")
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        # Both invocations report failure and produce no output file
        monkeypatch.setattr(lo_backend.subprocess, "run",
                            lambda cmd, **kw: _make_completed(returncode=-6,
                                                              stderr="Trace/BPT trap: 5"))

        with pytest.raises(RuntimeError) as exc:
            lo_backend.convert(str(input_file), "pdf", output_dir=str(out_dir))
        msg = str(exc.value)
        assert "bugs.documentfoundation.org/show_bug.cgi?id=169711" in msg
        assert "open -W -n -a" in msg
        assert "soffice" in msg
