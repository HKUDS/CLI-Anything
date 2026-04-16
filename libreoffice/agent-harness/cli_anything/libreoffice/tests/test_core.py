"""Unit tests for LibreOffice CLI core modules.

Tests use synthetic data only -- no LibreOffice installation needed.
"""

import json
import os
import sys
import tempfile
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
