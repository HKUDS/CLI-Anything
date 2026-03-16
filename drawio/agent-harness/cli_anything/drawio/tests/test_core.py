"""Tests for the Draw.io CLI core modules."""

import os
import sys
import json
import tempfile
import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from cli_anything.drawio.core.session import Session
from cli_anything.drawio.core import project as proj_mod
from cli_anything.drawio.core import shapes as shapes_mod
from cli_anything.drawio.core import connectors as conn_mod
from cli_anything.drawio.core import pages as pages_mod
from cli_anything.drawio.core import export as export_mod
from cli_anything.drawio.utils import drawio_xml


# ============================================================================
# XML utilities
# ============================================================================

class TestDrawioXml:
    def test_create_blank_diagram(self):
        root = drawio_xml.create_blank_diagram(850, 1100)
        assert root.tag == "mxfile"
        diagrams = root.findall("diagram")
        assert len(diagrams) == 1
        model = diagrams[0].find("mxGraphModel")
        assert model is not None
        assert model.get("pageWidth") == "850"
        assert model.get("pageHeight") == "1100"

    def test_system_cells_present(self):
        root = drawio_xml.create_blank_diagram()
        xml_root = drawio_xml.get_root(root)
        cells = xml_root.findall("mxCell")
        ids = [c.get("id") for c in cells]
        assert "0" in ids
        assert "1" in ids

    def test_no_user_cells_in_blank(self):
        root = drawio_xml.create_blank_diagram()
        assert len(drawio_xml.get_all_cells(root)) == 0

    def test_add_vertex(self):
        root = drawio_xml.create_blank_diagram()
        cell_id = drawio_xml.add_vertex(root, "rectangle", 10, 20, 120, 60, "Test")
        assert cell_id is not None
        cells = drawio_xml.get_all_cells(root)
        assert len(cells) == 1
        assert cells[0].get("value") == "Test"
        assert cells[0].get("vertex") == "1"

    def test_generated_ids_are_unique(self):
        root = drawio_xml.create_blank_diagram()
        ids = {
            drawio_xml.add_vertex(root, "rectangle", i * 10, 0, 100, 50, f"Cell {i}")
            for i in range(20)
        }
        assert len(ids) == 20

    def test_add_edge(self):
        root = drawio_xml.create_blank_diagram()
        v1 = drawio_xml.add_vertex(root, "rectangle", 10, 20, 120, 60, "A")
        v2 = drawio_xml.add_vertex(root, "rectangle", 200, 20, 120, 60, "B")
        e1 = drawio_xml.add_edge(root, v1, v2, "orthogonal", "connects")
        assert e1 is not None
        edges = drawio_xml.get_edges(root)
        assert len(edges) == 1
        assert edges[0].get("source") == v1
        assert edges[0].get("target") == v2
        assert edges[0].get("value") == "connects"

    def test_remove_cell(self):
        root = drawio_xml.create_blank_diagram()
        v1 = drawio_xml.add_vertex(root, "rectangle", 10, 20, 120, 60, "A")
        assert len(drawio_xml.get_all_cells(root)) == 1
        drawio_xml.remove_cell(root, v1)
        assert len(drawio_xml.get_all_cells(root)) == 0

    def test_remove_vertex_also_removes_edges(self):
        root = drawio_xml.create_blank_diagram()
        v1 = drawio_xml.add_vertex(root, "rectangle", 10, 20, 120, 60, "A")
        v2 = drawio_xml.add_vertex(root, "rectangle", 200, 20, 120, 60, "B")
        drawio_xml.add_edge(root, v1, v2)
        assert len(drawio_xml.get_edges(root)) == 1
        drawio_xml.remove_cell(root, v1)
        assert len(drawio_xml.get_edges(root)) == 0

    def test_find_cell_by_id(self):
        root = drawio_xml.create_blank_diagram()
        v1 = drawio_xml.add_vertex(root, "ellipse", 10, 20, 100, 100, "Circle")
        found = drawio_xml.find_cell_by_id(root, v1)
        assert found is not None
        assert found.get("value") == "Circle"

    def test_find_cell_not_exists(self):
        root = drawio_xml.create_blank_diagram()
        assert drawio_xml.find_cell_by_id(root, "nonexistent") is None

    def test_update_cell_label(self):
        root = drawio_xml.create_blank_diagram()
        v1 = drawio_xml.add_vertex(root, "rectangle", 0, 0, 100, 50, "Old")
        drawio_xml.update_cell_label(root, v1, "New")
        cell = drawio_xml.find_cell_by_id(root, v1)
        assert cell.get("value") == "New"

    def test_move_cell(self):
        root = drawio_xml.create_blank_diagram()
        v1 = drawio_xml.add_vertex(root, "rectangle", 10, 20, 100, 50)
        drawio_xml.move_cell(root, v1, 300, 400)
        geo = drawio_xml.get_cell_geometry(drawio_xml.find_cell_by_id(root, v1))
        assert geo["x"] == 300.0
        assert geo["y"] == 400.0

    def test_resize_cell(self):
        root = drawio_xml.create_blank_diagram()
        v1 = drawio_xml.add_vertex(root, "rectangle", 10, 20, 100, 50)
        drawio_xml.resize_cell(root, v1, 200, 150)
        geo = drawio_xml.get_cell_geometry(drawio_xml.find_cell_by_id(root, v1))
        assert geo["width"] == 200.0
        assert geo["height"] == 150.0

    def test_get_cell_info(self):
        root = drawio_xml.create_blank_diagram()
        v1 = drawio_xml.add_vertex(root, "rectangle", 10, 20, 120, 60, "Hello")
        info = drawio_xml.get_cell_info(drawio_xml.find_cell_by_id(root, v1))
        assert info["id"] == v1
        assert info["value"] == "Hello"
        assert info["type"] == "vertex"
        assert info["width"] == 120.0

    def test_get_vertices(self):
        root = drawio_xml.create_blank_diagram()
        drawio_xml.add_vertex(root, "rectangle", 0, 0, 100, 50)
        drawio_xml.add_vertex(root, "ellipse", 200, 0, 100, 100)
        v1 = drawio_xml.add_vertex(root, "diamond", 0, 200, 80, 80)
        v2 = drawio_xml.add_vertex(root, "rectangle", 200, 200, 100, 50)
        drawio_xml.add_edge(root, v1, v2)
        assert len(drawio_xml.get_vertices(root)) == 4
        assert len(drawio_xml.get_edges(root)) == 1

    def test_write_and_parse_roundtrip(self):
        root = drawio_xml.create_blank_diagram(1200, 800)
        drawio_xml.add_vertex(root, "rectangle", 10, 20, 120, 60, "Test Shape")

        with tempfile.NamedTemporaryFile(suffix=".drawio", delete=False) as f:
            path = f.name

        try:
            drawio_xml.write_drawio(root, path)
            assert os.path.exists(path)
            assert os.path.getsize(path) > 0

            parsed = drawio_xml.parse_drawio(path)
            assert parsed.tag == "mxfile"
            cells = drawio_xml.get_all_cells(parsed)
            assert len(cells) == 1
            assert cells[0].get("value") == "Test Shape"
        finally:
            os.unlink(path)


# ============================================================================
# Style parsing
# ============================================================================

class TestStyleParsing:
    def test_parse_empty(self):
        assert drawio_xml.parse_style("") == {}

    def test_parse_basic(self):
        style = drawio_xml.parse_style("rounded=1;whiteSpace=wrap;html=1;")
        assert style["rounded"] == "1"
        assert style["whiteSpace"] == "wrap"
        assert style["html"] == "1"

    def test_parse_base_style(self):
        style = drawio_xml.parse_style("ellipse;whiteSpace=wrap;html=1;")
        assert style["ellipse"] == ""
        assert style["html"] == "1"

    def test_build_style(self):
        style = drawio_xml.build_style({"rounded": "1", "html": "1"})
        assert "rounded=1" in style
        assert "html=1" in style

    def test_roundtrip(self):
        original = "rounded=1;whiteSpace=wrap;html=1;"
        style = drawio_xml.parse_style(original)
        rebuilt = drawio_xml.build_style(style)
        reparsed = drawio_xml.parse_style(rebuilt)
        assert style == reparsed

    def test_set_style_property(self):
        root = drawio_xml.create_blank_diagram()
        v1 = drawio_xml.add_vertex(root, "rectangle", 0, 0, 100, 50)
        cell = drawio_xml.find_cell_by_id(root, v1)
        drawio_xml.set_style_property(cell, "fillColor", "#ff0000")
        style = drawio_xml.parse_style(cell.get("style", ""))
        assert style["fillColor"] == "#ff0000"

    def test_remove_style_property(self):
        root = drawio_xml.create_blank_diagram()
        v1 = drawio_xml.add_vertex(root, "rectangle", 0, 0, 100, 50)
        cell = drawio_xml.find_cell_by_id(root, v1)
        drawio_xml.set_style_property(cell, "fillColor", "#ff0000")
        drawio_xml.remove_style_property(cell, "fillColor")
        style = drawio_xml.parse_style(cell.get("style", ""))
        assert "fillColor" not in style


# ============================================================================
# Shape presets
# ============================================================================

class TestShapePresets:
    @pytest.mark.parametrize("shape_type", list(drawio_xml.SHAPE_STYLES.keys()))
    def test_all_shape_types(self, shape_type):
        root = drawio_xml.create_blank_diagram()
        cell_id = drawio_xml.add_vertex(root, shape_type, 0, 0, 100, 60, shape_type)
        assert cell_id is not None
        cell = drawio_xml.find_cell_by_id(root, cell_id)
        assert cell is not None
        assert cell.get("value") == shape_type

    @pytest.mark.parametrize("edge_style", list(drawio_xml.EDGE_STYLES.keys()))
    def test_all_edge_styles(self, edge_style):
        root = drawio_xml.create_blank_diagram()
        v1 = drawio_xml.add_vertex(root, "rectangle", 0, 0, 100, 50, "A")
        v2 = drawio_xml.add_vertex(root, "rectangle", 200, 0, 100, 50, "B")
        edge_id = drawio_xml.add_edge(root, v1, v2, edge_style)
        assert edge_id is not None
        edge = drawio_xml.find_cell_by_id(root, edge_id)
        assert edge is not None
        assert edge.get("edge") == "1"


# ============================================================================
# Multi-page operations
# ============================================================================

class TestPages:
    def test_single_page_default(self):
        root = drawio_xml.create_blank_diagram()
        pages = drawio_xml.list_pages(root)
        assert len(pages) == 1
        assert pages[0]["name"] == "Page-1"

    def test_add_page(self):
        root = drawio_xml.create_blank_diagram()
        drawio_xml.add_page(root, "Second Page")
        pages = drawio_xml.list_pages(root)
        assert len(pages) == 2
        assert pages[1]["name"] == "Second Page"

    def test_remove_page(self):
        root = drawio_xml.create_blank_diagram()
        drawio_xml.add_page(root, "To Remove")
        assert len(drawio_xml.list_pages(root)) == 2
        drawio_xml.remove_page(root, 1)
        assert len(drawio_xml.list_pages(root)) == 1

    def test_cannot_remove_last_page(self):
        root = drawio_xml.create_blank_diagram()
        with pytest.raises(RuntimeError, match="Cannot remove the last page"):
            drawio_xml.remove_page(root, 0)

    def test_rename_page(self):
        root = drawio_xml.create_blank_diagram()
        drawio_xml.rename_page(root, 0, "My Diagram")
        pages = drawio_xml.list_pages(root)
        assert pages[0]["name"] == "My Diagram"

    def test_shapes_on_different_pages(self):
        root = drawio_xml.create_blank_diagram()
        drawio_xml.add_vertex(root, "rectangle", 0, 0, 100, 50, "Page1Shape", diagram_index=0)
        drawio_xml.add_page(root, "Page 2")
        drawio_xml.add_vertex(root, "ellipse", 0, 0, 80, 80, "Page2Shape", diagram_index=1)
        assert len(drawio_xml.get_vertices(root, 0)) == 1
        assert len(drawio_xml.get_vertices(root, 1)) == 1


# ============================================================================
# Session
# ============================================================================

class TestSession:
    def test_new_session(self):
        s = Session()
        assert s.is_open is False
        assert s.is_modified is False

    def test_new_project(self):
        s = Session()
        s.new_project(850, 1100)
        assert s.is_open is True
        assert s.is_modified is False

    def test_undo_redo(self):
        s = Session()
        s.new_project()
        assert s.undo() is False  # Nothing to undo

        s.checkpoint()
        drawio_xml.add_vertex(s.root, "rectangle", 0, 0, 100, 50, "Test")
        assert len(drawio_xml.get_vertices(s.root)) == 1

        assert s.undo() is True
        assert len(drawio_xml.get_vertices(s.root)) == 0

        assert s.redo() is True
        assert len(drawio_xml.get_vertices(s.root)) == 1

    def test_multiple_undo(self):
        s = Session()
        s.new_project()

        s.checkpoint()
        drawio_xml.add_vertex(s.root, "rectangle", 0, 0, 100, 50, "First")

        s.checkpoint()
        drawio_xml.add_vertex(s.root, "rectangle", 200, 0, 100, 50, "Second")

        assert len(drawio_xml.get_vertices(s.root)) == 2
        s.undo()
        assert len(drawio_xml.get_vertices(s.root)) == 1
        s.undo()
        assert len(drawio_xml.get_vertices(s.root)) == 0

    def test_save_and_open(self):
        s = Session()
        s.new_project()
        drawio_xml.add_vertex(s.root, "rectangle", 0, 0, 100, 50, "Persisted")

        with tempfile.NamedTemporaryFile(suffix=".drawio", delete=False) as f:
            path = f.name

        try:
            s.save_project(path)
            assert not s.is_modified
            assert os.path.exists(path)

            s2 = Session()
            s2.open_project(path)
            assert s2.is_open
            cells = drawio_xml.get_vertices(s2.root)
            assert len(cells) == 1
            assert cells[0].get("value") == "Persisted"
        finally:
            os.unlink(path)

    def test_save_no_project(self):
        s = Session()
        with pytest.raises(RuntimeError, match="No project is open"):
            s.save_project("test.drawio")

    def test_open_nonexistent(self):
        s = Session()
        with pytest.raises(FileNotFoundError):
            s.open_project("/nonexistent/path.drawio")

    def test_status(self):
        s = Session()
        status = s.status()
        assert status["project_open"] is False

        s.new_project()
        drawio_xml.add_vertex(s.root, "rectangle", 0, 0, 100, 50)
        status = s.status()
        assert status["project_open"] is True
        assert status["shape_count"] == 1
        assert status["edge_count"] == 0


# ============================================================================
# Project module
# ============================================================================

class TestProject:
    def test_new_project(self):
        s = Session()
        result = proj_mod.new_project(s, "letter")
        assert result["action"] == "new_project"
        assert result["preset"] == "letter"
        assert s.is_open

    def test_new_project_all_presets(self):
        for name in proj_mod.PAGE_PRESETS:
            s = Session()
            result = proj_mod.new_project(s, name)
            assert result["action"] == "new_project"
            assert s.is_open

    def test_new_project_invalid_preset(self):
        s = Session()
        with pytest.raises(ValueError, match="Unknown preset"):
            proj_mod.new_project(s, "nonexistent")

    def test_new_project_custom_size(self):
        s = Session()
        result = proj_mod.new_project(s, "custom", width=1920, height=1080)
        assert result["page_size"] == "1920x1080"

    def test_save_and_open(self):
        s = Session()
        proj_mod.new_project(s, "a4")
        shapes_mod.add_shape(s, "rectangle", label="Test")

        with tempfile.NamedTemporaryFile(suffix=".drawio", delete=False) as f:
            path = f.name

        try:
            proj_mod.save_project(s, path)
            assert os.path.exists(path)

            s2 = Session()
            result = proj_mod.open_project(s2, path)
            assert result["action"] == "open_project"
            assert result["shape_count"] == 1
        finally:
            os.unlink(path)

    def test_project_info(self):
        s = Session()
        proj_mod.new_project(s, "letter")
        shapes_mod.add_shape(s, "rectangle", label="A")
        shapes_mod.add_shape(s, "ellipse", label="B")
        info = proj_mod.project_info(s)
        assert len(info["shapes"]) == 2
        assert info["canvas"]["pageWidth"] == "850"

    def test_project_info_no_project(self):
        s = Session()
        with pytest.raises(RuntimeError, match="No project is open"):
            proj_mod.project_info(s)

    def test_list_presets(self):
        presets = proj_mod.list_presets()
        assert "letter" in presets
        assert "a4" in presets


# ============================================================================
# Shapes module
# ============================================================================

class TestShapes:
    def test_add_shape(self):
        s = Session()
        proj_mod.new_project(s)
        result = shapes_mod.add_shape(s, "rectangle", 10, 20, 120, 60, "Hello")
        assert result["action"] == "add_shape"
        assert result["label"] == "Hello"
        assert result["id"] is not None

    def test_add_shape_no_project(self):
        s = Session()
        with pytest.raises(RuntimeError, match="No project is open"):
            shapes_mod.add_shape(s, "rectangle")

    def test_list_shapes(self):
        s = Session()
        proj_mod.new_project(s)
        shapes_mod.add_shape(s, "rectangle", label="A")
        shapes_mod.add_shape(s, "ellipse", label="B")
        result = shapes_mod.list_shapes(s)
        assert len(result) == 2

    def test_remove_shape(self):
        s = Session()
        proj_mod.new_project(s)
        result = shapes_mod.add_shape(s, "rectangle", label="ToRemove")
        cell_id = result["id"]
        shapes_mod.remove_shape(s, cell_id)
        assert len(shapes_mod.list_shapes(s)) == 0

    def test_remove_shape_not_found(self):
        s = Session()
        proj_mod.new_project(s)
        with pytest.raises(ValueError, match="Shape not found"):
            shapes_mod.remove_shape(s, "nonexistent")

    def test_update_label(self):
        s = Session()
        proj_mod.new_project(s)
        result = shapes_mod.add_shape(s, "rectangle", label="Old")
        shapes_mod.update_label(s, result["id"], "New")
        shapes = shapes_mod.list_shapes(s)
        assert shapes[0]["value"] == "New"

    def test_move_shape(self):
        s = Session()
        proj_mod.new_project(s)
        result = shapes_mod.add_shape(s, "rectangle", 10, 20, 100, 50)
        shapes_mod.move_shape(s, result["id"], 300, 400)
        info = shapes_mod.get_shape_info(s, result["id"])
        assert info["x"] == 300.0
        assert info["y"] == 400.0

    def test_resize_shape(self):
        s = Session()
        proj_mod.new_project(s)
        result = shapes_mod.add_shape(s, "rectangle", 10, 20, 100, 50)
        shapes_mod.resize_shape(s, result["id"], 200, 150)
        info = shapes_mod.get_shape_info(s, result["id"])
        assert info["width"] == 200.0
        assert info["height"] == 150.0

    def test_set_style(self):
        s = Session()
        proj_mod.new_project(s)
        result = shapes_mod.add_shape(s, "rectangle")
        shapes_mod.set_style(s, result["id"], "fillColor", "#ff0000")
        info = shapes_mod.get_shape_info(s, result["id"])
        assert info["style_parsed"]["fillColor"] == "#ff0000"

    def test_get_shape_info(self):
        s = Session()
        proj_mod.new_project(s)
        result = shapes_mod.add_shape(s, "ellipse", 50, 60, 80, 80, "Circle")
        info = shapes_mod.get_shape_info(s, result["id"])
        assert info["value"] == "Circle"
        assert info["type"] == "vertex"
        assert "style_parsed" in info

    def test_list_shape_types(self):
        types = shapes_mod.list_shape_types()
        assert "rectangle" in types
        assert "ellipse" in types
        assert "diamond" in types

    @pytest.mark.parametrize("shape_type", [
        "rectangle", "rounded", "ellipse", "diamond", "triangle",
        "hexagon", "cylinder", "cloud", "parallelogram", "process",
        "document", "callout", "note", "actor", "text",
    ])
    def test_all_shape_types_via_module(self, shape_type):
        s = Session()
        proj_mod.new_project(s)
        result = shapes_mod.add_shape(s, shape_type, label=shape_type)
        assert result["shape_type"] == shape_type

    def test_undo_add_shape(self):
        s = Session()
        proj_mod.new_project(s)
        shapes_mod.add_shape(s, "rectangle", label="Test")
        assert len(shapes_mod.list_shapes(s)) == 1
        s.undo()
        assert len(shapes_mod.list_shapes(s)) == 0


# ============================================================================
# Connectors module
# ============================================================================

class TestConnectors:
    def test_add_connector(self):
        s = Session()
        proj_mod.new_project(s)
        v1 = shapes_mod.add_shape(s, "rectangle", label="A")["id"]
        v2 = shapes_mod.add_shape(s, "rectangle", 200, 100, label="B")["id"]
        result = conn_mod.add_connector(s, v1, v2, "orthogonal", "flow")
        assert result["action"] == "add_connector"
        assert result["source"] == v1
        assert result["target"] == v2
        assert result["label"] == "flow"

    def test_add_connector_invalid_source(self):
        s = Session()
        proj_mod.new_project(s)
        v1 = shapes_mod.add_shape(s, "rectangle", label="A")["id"]
        with pytest.raises(ValueError, match="Source cell not found"):
            conn_mod.add_connector(s, "nonexistent", v1)

    def test_add_connector_invalid_target(self):
        s = Session()
        proj_mod.new_project(s)
        v1 = shapes_mod.add_shape(s, "rectangle", label="A")["id"]
        with pytest.raises(ValueError, match="Target cell not found"):
            conn_mod.add_connector(s, v1, "nonexistent")

    def test_list_connectors(self):
        s = Session()
        proj_mod.new_project(s)
        v1 = shapes_mod.add_shape(s, "rectangle", label="A")["id"]
        v2 = shapes_mod.add_shape(s, "rectangle", 200, 100, label="B")["id"]
        conn_mod.add_connector(s, v1, v2)
        result = conn_mod.list_connectors(s)
        assert len(result) == 1

    def test_remove_connector(self):
        s = Session()
        proj_mod.new_project(s)
        v1 = shapes_mod.add_shape(s, "rectangle", label="A")["id"]
        v2 = shapes_mod.add_shape(s, "rectangle", 200, 100, label="B")["id"]
        edge = conn_mod.add_connector(s, v1, v2)
        conn_mod.remove_connector(s, edge["id"])
        assert len(conn_mod.list_connectors(s)) == 0

    def test_update_connector_label(self):
        s = Session()
        proj_mod.new_project(s)
        v1 = shapes_mod.add_shape(s, "rectangle", label="A")["id"]
        v2 = shapes_mod.add_shape(s, "rectangle", 200, 100, label="B")["id"]
        edge = conn_mod.add_connector(s, v1, v2, label="old")
        conn_mod.update_connector_label(s, edge["id"], "new")
        connectors = conn_mod.list_connectors(s)
        assert connectors[0]["value"] == "new"

    def test_set_connector_style(self):
        s = Session()
        proj_mod.new_project(s)
        v1 = shapes_mod.add_shape(s, "rectangle", label="A")["id"]
        v2 = shapes_mod.add_shape(s, "rectangle", 200, 100, label="B")["id"]
        edge = conn_mod.add_connector(s, v1, v2)
        conn_mod.set_connector_style(s, edge["id"], "strokeColor", "#0000ff")
        cell = drawio_xml.find_cell_by_id(s.root, edge["id"])
        style = drawio_xml.parse_style(cell.get("style", ""))
        assert style["strokeColor"] == "#0000ff"

    def test_list_edge_styles(self):
        styles = conn_mod.list_edge_styles()
        assert "orthogonal" in styles
        assert "straight" in styles
        assert "curved" in styles

    @pytest.mark.parametrize("edge_style", ["straight", "orthogonal", "curved", "entity-relation"])
    def test_all_edge_styles_via_module(self, edge_style):
        s = Session()
        proj_mod.new_project(s)
        v1 = shapes_mod.add_shape(s, "rectangle", label="A")["id"]
        v2 = shapes_mod.add_shape(s, "rectangle", 200, 100, label="B")["id"]
        result = conn_mod.add_connector(s, v1, v2, edge_style)
        assert result["action"] == "add_connector"


# ============================================================================
# Pages module
# ============================================================================

class TestPagesModule:
    def test_list_pages(self):
        s = Session()
        proj_mod.new_project(s)
        result = pages_mod.list_pages(s)
        assert len(result) == 1

    def test_add_page(self):
        s = Session()
        proj_mod.new_project(s)
        result = pages_mod.add_page(s, "Extra Page")
        assert result["action"] == "add_page"
        assert result["page_count"] == 2

    def test_remove_page(self):
        s = Session()
        proj_mod.new_project(s)
        pages_mod.add_page(s, "To Delete")
        pages_mod.remove_page(s, 1)
        assert len(pages_mod.list_pages(s)) == 1

    def test_rename_page(self):
        s = Session()
        proj_mod.new_project(s)
        pages_mod.rename_page(s, 0, "Flowchart")
        result = pages_mod.list_pages(s)
        assert result[0]["name"] == "Flowchart"


# ============================================================================
# Export module
# ============================================================================

class TestExport:
    def test_list_formats(self):
        formats = export_mod.list_formats()
        names = [f["name"] for f in formats]
        assert "png" in names
        assert "pdf" in names
        assert "svg" in names

    def test_export_xml_direct(self):
        """XML export doesn't need draw.io CLI."""
        s = Session()
        proj_mod.new_project(s)
        shapes_mod.add_shape(s, "rectangle", label="ExportTest")

        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
            path = f.name

        try:
            result = export_mod.render(s, path, fmt="xml", overwrite=True)
            assert result["action"] == "export"
            assert result["format"] == "xml"
            assert result["method"] == "direct-write"
            assert os.path.exists(path)
            assert result["file_size"] > 0

            # Verify the XML is valid drawio
            parsed = drawio_xml.parse_drawio(path)
            assert parsed.tag == "mxfile"
            cells = drawio_xml.get_all_cells(parsed)
            assert len(cells) == 1
        finally:
            os.unlink(path)

    def test_render_or_save_propagates_backend_errors(self, monkeypatch):
        s = Session()
        proj_mod.new_project(s)

        def _fail(*args, **kwargs):
            raise RuntimeError("draw.io desktop app is not installed")

        monkeypatch.setattr(export_mod, "render", _fail)

        with pytest.raises(RuntimeError, match="not installed"):
            export_mod.render_or_save(s, "missing.png", fmt="png")

    def test_export_no_project(self):
        s = Session()
        with pytest.raises(RuntimeError, match="No project is open"):
            export_mod.render(s, "test.png")

    def test_export_invalid_format(self):
        s = Session()
        proj_mod.new_project(s)
        with pytest.raises(ValueError, match="Unknown format"):
            export_mod.render(s, "test.bmp", fmt="bmp")

    def test_export_file_exists(self):
        s = Session()
        proj_mod.new_project(s)
        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
            path = f.name

        try:
            with pytest.raises(FileExistsError):
                export_mod.render(s, path, fmt="xml", overwrite=False)
        finally:
            os.unlink(path)


# ============================================================================
# Complex workflows
# ============================================================================

class TestWorkflows:
    def test_flowchart(self):
        """Build a complete flowchart: Start → Process → Decision → End."""
        s = Session()
        proj_mod.new_project(s, "letter")

        start = shapes_mod.add_shape(s, "ellipse", 350, 50, 120, 60, "Start")["id"]
        process = shapes_mod.add_shape(s, "rectangle", 340, 170, 140, 60, "Process Data")["id"]
        decision = shapes_mod.add_shape(s, "diamond", 340, 290, 140, 80, "Valid?")["id"]
        end = shapes_mod.add_shape(s, "ellipse", 350, 430, 120, 60, "End")["id"]

        conn_mod.add_connector(s, start, process)
        conn_mod.add_connector(s, process, decision)
        conn_mod.add_connector(s, decision, end, label="Yes")

        shapes = shapes_mod.list_shapes(s)
        assert len(shapes) == 4
        connectors = conn_mod.list_connectors(s)
        assert len(connectors) == 3

        # Save and reopen
        with tempfile.NamedTemporaryFile(suffix=".drawio", delete=False) as f:
            path = f.name
        try:
            proj_mod.save_project(s, path)
            s2 = Session()
            proj_mod.open_project(s2, path)
            assert len(drawio_xml.get_vertices(s2.root)) == 4
            assert len(drawio_xml.get_edges(s2.root)) == 3
        finally:
            os.unlink(path)

    def test_styled_diagram(self):
        """Build a diagram with custom styles."""
        s = Session()
        proj_mod.new_project(s)

        box = shapes_mod.add_shape(s, "rounded", 100, 100, 160, 80, "Styled Box")["id"]
        shapes_mod.set_style(s, box, "fillColor", "#dae8fc")
        shapes_mod.set_style(s, box, "strokeColor", "#6c8ebf")
        shapes_mod.set_style(s, box, "fontSize", "16")
        shapes_mod.set_style(s, box, "shadow", "1")

        info = shapes_mod.get_shape_info(s, box)
        assert info["style_parsed"]["fillColor"] == "#dae8fc"
        assert info["style_parsed"]["strokeColor"] == "#6c8ebf"
        assert info["style_parsed"]["fontSize"] == "16"
        assert info["style_parsed"]["shadow"] == "1"

    def test_multi_page_workflow(self):
        """Create a multi-page document."""
        s = Session()
        proj_mod.new_project(s)

        # Page 1: Architecture diagram
        pages_mod.rename_page(s, 0, "Architecture")
        shapes_mod.add_shape(s, "cylinder", 100, 100, 80, 100, "Database")
        shapes_mod.add_shape(s, "rectangle", 300, 100, 120, 60, "API Server")

        # Page 2: Flowchart
        pages_mod.add_page(s, "Flowchart")
        shapes_mod.add_shape(s, "ellipse", 100, 100, 100, 50, "Start", diagram_index=1)

        result = pages_mod.list_pages(s)
        assert len(result) == 2
        assert result[0]["name"] == "Architecture"
        assert result[1]["name"] == "Flowchart"

    def test_undo_redo_workflow(self):
        """Test undo/redo across multiple operations."""
        s = Session()
        proj_mod.new_project(s)

        shapes_mod.add_shape(s, "rectangle", label="First")
        shapes_mod.add_shape(s, "rectangle", 200, 100, label="Second")
        shapes_mod.add_shape(s, "rectangle", 400, 100, label="Third")

        assert len(shapes_mod.list_shapes(s)) == 3
        s.undo()
        assert len(shapes_mod.list_shapes(s)) == 2
        s.undo()
        assert len(shapes_mod.list_shapes(s)) == 1
        s.redo()
        assert len(shapes_mod.list_shapes(s)) == 2
        s.redo()
        assert len(shapes_mod.list_shapes(s)) == 3

    def test_export_xml_workflow(self):
        """Full workflow: create diagram, add content, export to XML."""
        s = Session()
        proj_mod.new_project(s)

        v1 = shapes_mod.add_shape(s, "rectangle", 100, 100, 120, 60, "Server")["id"]
        v2 = shapes_mod.add_shape(s, "cylinder", 300, 100, 80, 100, "DB")["id"]
        conn_mod.add_connector(s, v1, v2, "orthogonal", "query")

        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
            path = f.name

        try:
            result = export_mod.render(s, path, fmt="xml", overwrite=True)
            assert result["file_size"] > 0

            # Verify exported content
            parsed = drawio_xml.parse_drawio(path)
            vertices = drawio_xml.get_vertices(parsed)
            edges = drawio_xml.get_edges(parsed)
            assert len(vertices) == 2
            assert len(edges) == 1
        finally:
            os.unlink(path)
