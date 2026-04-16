"""End-to-end tests for Inkscape CLI.

These tests verify full workflows: document creation, manipulation,
SVG generation, SVG validation, export verification, and CLI subprocess
invocation. No actual Inkscape installation is required.
"""

import json
import os
import sys
import tempfile
import subprocess
import xml.etree.ElementTree as ET
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from cli_anything.inkscape.utils.svg_utils import (
    SVG_NS, INKSCAPE_NS, SODIPODI_NS, reset_id_counter,
    parse_style, serialize_svg,
)
from cli_anything.inkscape.core.document import (
    create_document, save_document, open_document, save_svg,
    get_document_info, project_to_svg,
)
from cli_anything.inkscape.core.shapes import (
    add_rect, add_circle, add_ellipse, add_line, add_polygon,
    add_path, add_star, remove_object, duplicate_object, list_objects,
)
from cli_anything.inkscape.core.text import add_text, set_text_property, list_text_objects
from cli_anything.inkscape.core.styles import set_fill, set_stroke, set_opacity, set_style, get_object_style
from cli_anything.inkscape.core.transforms import translate, rotate, scale, get_transform, clear_transform
from cli_anything.inkscape.core.layers import add_layer, remove_layer, move_to_layer, list_layers, get_layer
from cli_anything.inkscape.core.paths import (
    path_union, path_intersection, path_difference,
    convert_to_path,
)
from cli_anything.inkscape.core.gradients import add_linear_gradient, add_radial_gradient, apply_gradient
from cli_anything.inkscape.core.export import render_to_png, export_svg, list_presets
from cli_anything.inkscape.core.session import Session


@pytest.fixture(autouse=True)
def reset_ids():
    """Reset the ID counter before each test."""
    reset_id_counter()


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


# ── SVG Validity Tests ──────────────────────────────────────────

class TestSVGValidity:
    """Verify that generated SVG is well-formed XML with correct namespaces."""

    def test_empty_document_svg_is_valid_xml(self, tmp_dir):
        proj = create_document(name="empty")
        path = os.path.join(tmp_dir, "empty.svg")
        save_svg(proj, path)
        # Parse it back — will raise if invalid XML
        tree = ET.parse(path)
        root = tree.getroot()
        assert root.tag == f"{{{SVG_NS}}}svg"

    def test_svg_has_xml_declaration(self, tmp_dir):
        proj = create_document()
        path = os.path.join(tmp_dir, "test.svg")
        save_svg(proj, path)
        with open(path) as f:
            content = f.read()
        assert content.startswith("<?xml")

    def test_svg_has_correct_dimensions(self, tmp_dir):
        proj = create_document(width=800, height=600)
        path = os.path.join(tmp_dir, "test.svg")
        save_svg(proj, path)
        tree = ET.parse(path)
        root = tree.getroot()
        assert "800" in root.get("width", "")
        assert "600" in root.get("height", "")

    def test_svg_has_viewbox(self, tmp_dir):
        proj = create_document(width=1920, height=1080)
        path = os.path.join(tmp_dir, "test.svg")
        save_svg(proj, path)
        tree = ET.parse(path)
        root = tree.getroot()
        assert root.get("viewBox") == "0 0 1920 1080"

    def test_svg_has_inkscape_namespace(self, tmp_dir):
        proj = create_document()
        svg = project_to_svg(proj)
        xml_str = serialize_svg(svg)
        assert "inkscape" in xml_str

    def test_svg_with_shapes_is_valid(self, tmp_dir):
        proj = create_document()
        add_rect(proj, x=10, y=10, width=100, height=50)
        add_circle(proj, cx=200, cy=200, r=30)
        add_ellipse(proj, cx=300, cy=100, rx=60, ry=30)
        path = os.path.join(tmp_dir, "shapes.svg")
        save_svg(proj, path)
        tree = ET.parse(path)
        root = tree.getroot()
        # Should have layer group and shapes inside
        groups = list(root.iter(f"{{{SVG_NS}}}g"))
        assert len(groups) >= 1  # At least the layer group

    def test_svg_with_text_is_valid(self, tmp_dir):
        proj = create_document()
        add_text(proj, text="Hello SVG", x=50, y=100, font_size=48)
        path = os.path.join(tmp_dir, "text.svg")
        save_svg(proj, path)
        tree = ET.parse(path)
        # Find text element
        texts = list(tree.getroot().iter(f"{{{SVG_NS}}}text"))
        assert len(texts) >= 1
        assert texts[0].text == "Hello SVG"

    def test_svg_with_gradients_is_valid(self, tmp_dir):
        proj = create_document()
        add_linear_gradient(proj, stops=[
            {"offset": 0, "color": "#ff0000"},
            {"offset": 1, "color": "#0000ff"},
        ])
        add_rect(proj, name="GradRect")
        apply_gradient(proj, 0, 0, "fill")
        path = os.path.join(tmp_dir, "gradient.svg")
        save_svg(proj, path)
        tree = ET.parse(path)
        defs = tree.getroot().find(f"{{{SVG_NS}}}defs")
        grads = list(defs.iter(f"{{{SVG_NS}}}linearGradient"))
        assert len(grads) >= 1
        stops = list(grads[0].iter(f"{{{SVG_NS}}}stop"))
        assert len(stops) == 2

    def test_svg_with_layers_is_valid(self, tmp_dir):
        proj = create_document()
        add_layer(proj, name="Foreground")
        add_rect(proj, name="BgRect")
        add_rect(proj, name="FgRect", layer=proj["layers"][1]["id"])
        path = os.path.join(tmp_dir, "layers.svg")
        save_svg(proj, path)
        tree = ET.parse(path)
        root = tree.getroot()
        groups = list(root.iter(f"{{{SVG_NS}}}g"))
        # Should have at least 2 layer groups
        assert len(groups) >= 2

    def test_svg_with_transform_is_valid(self, tmp_dir):
        proj = create_document()
        add_rect(proj)
        translate(proj, 0, 50, 50)
        rotate(proj, 0, 45)
        path = os.path.join(tmp_dir, "transform.svg")
        save_svg(proj, path)
        tree = ET.parse(path)
        rects = list(tree.getroot().iter(f"{{{SVG_NS}}}rect"))
        # Find rect with transform (skip background)
        transformed = [r for r in rects if r.get("transform")]
        assert len(transformed) >= 1
        assert "translate" in transformed[0].get("transform", "")

    def test_svg_radial_gradient(self, tmp_dir):
        proj = create_document()
        add_radial_gradient(proj, cx=0.5, cy=0.5, r=0.5)
        add_circle(proj)
        apply_gradient(proj, 0, 0, "fill")
        path = os.path.join(tmp_dir, "radial.svg")
        save_svg(proj, path)
        tree = ET.parse(path)
        defs = tree.getroot().find(f"{{{SVG_NS}}}defs")
        grads = list(defs.iter(f"{{{SVG_NS}}}radialGradient"))
        assert len(grads) >= 1


# ── Document Lifecycle ──────────────────────────────────────────

class TestDocumentLifecycle:
    def test_create_save_open_roundtrip(self, tmp_dir):
        proj = create_document(name="roundtrip")
        path = os.path.join(tmp_dir, "doc.inkscape-cli.json")
        save_document(proj, path)
        loaded = open_document(path)
        assert loaded["name"] == "roundtrip"
        assert loaded["document"]["width"] == 1920

    def test_document_with_objects_roundtrip(self, tmp_dir):
        proj = create_document(name="with_objects")
        add_rect(proj, name="MyRect", x=10, y=20, width=200, height=100)
        add_circle(proj, name="MyCircle", cx=300, cy=300, r=50)
        path = os.path.join(tmp_dir, "doc.json")
        save_document(proj, path)
        loaded = open_document(path)
        assert len(loaded["objects"]) == 2
        assert loaded["objects"][0]["type"] == "rect"
        assert loaded["objects"][1]["type"] == "circle"

    def test_document_with_styles_roundtrip(self, tmp_dir):
        proj = create_document()
        add_rect(proj)
        set_fill(proj, 0, "#ff0000")
        set_stroke(proj, 0, "#000000", width=3)
        set_opacity(proj, 0, 0.8)
        path = os.path.join(tmp_dir, "styled.json")
        save_document(proj, path)
        loaded = open_document(path)
        style = get_object_style(loaded, 0)
        assert style["fill"] == "#ff0000"
        assert style["stroke"] == "#000000"

    def test_document_with_layers_roundtrip(self, tmp_dir):
        proj = create_document()
        add_layer(proj, name="Layer 2")
        add_rect(proj, name="Shape1")
        add_rect(proj, name="Shape2", layer=proj["layers"][1]["id"])
        path = os.path.join(tmp_dir, "layered.json")
        save_document(proj, path)
        loaded = open_document(path)
        assert len(loaded["layers"]) == 2
        assert len(loaded["objects"]) == 2

    def test_document_with_gradients_roundtrip(self, tmp_dir):
        proj = create_document()
        add_linear_gradient(proj, name="MyGrad", stops=[
            {"offset": 0, "color": "#ff0000"},
            {"offset": 1, "color": "#0000ff"},
        ])
        path = os.path.join(tmp_dir, "grads.json")
        save_document(proj, path)
        loaded = open_document(path)
        assert len(loaded["gradients"]) == 1
        assert loaded["gradients"][0]["name"] == "MyGrad"

    def test_document_info_complete(self):
        proj = create_document(name="info_test")
        add_rect(proj)
        add_circle(proj)
        add_text(proj, text="Hello")
        add_layer(proj, name="Extra")
        add_linear_gradient(proj)
        info = get_document_info(proj)
        assert info["counts"]["objects"] == 3
        assert info["counts"]["layers"] == 2
        assert info["counts"]["gradients"] == 1

    def test_complex_document_roundtrip(self, tmp_dir):
        """Create a complex document, save, reload, verify."""
        proj = create_document(name="complex", width=1920, height=1080)

        # Shapes
        add_rect(proj, x=0, y=0, width=1920, height=1080, name="Background",
                 style="fill:#f0f0f0;stroke:none")
        add_rect(proj, x=100, y=100, width=400, height=300, rx=20, ry=20,
                 name="Card", style="fill:#ffffff;stroke:#cccccc;stroke-width:1")
        add_circle(proj, cx=960, cy=540, r=200, name="MainCircle",
                   style="fill:#3498db;stroke:none")
        add_ellipse(proj, cx=500, cy=800, rx=150, ry=80, name="Shadow",
                    style="fill:#00000033;stroke:none")
        add_line(proj, x1=100, y1=500, x2=1820, y2=500, name="Divider")
        add_star(proj, cx=1500, cy=200, points_count=5, outer_r=100, inner_r=40,
                 name="Star", style="fill:#f1c40f;stroke:#e67e22;stroke-width:2")
        add_polygon(proj, points="960,50 1050,350 750,350", name="Triangle",
                    style="fill:#e74c3c;stroke:none")

        # Text
        add_text(proj, text="Inkscape CLI Demo", x=100, y=50, font_size=36,
                 font_family="sans-serif", fill="#333333")

        # Styles
        set_opacity(proj, 3, 0.5)  # Shadow at half opacity

        # Transforms
        translate(proj, 2, 0, -20)  # Lift main circle
        rotate(proj, 5, 15, cx=1500, cy=200)  # Rotate star

        # Layers
        add_layer(proj, name="Foreground")

        # Gradients
        add_linear_gradient(proj, stops=[
            {"offset": 0, "color": "#3498db"},
            {"offset": 1, "color": "#2ecc71"},
        ], name="BlueGreen")
        apply_gradient(proj, 2, 0, "fill")  # Apply to MainCircle

        # Save JSON and SVG
        json_path = os.path.join(tmp_dir, "complex.json")
        svg_path = os.path.join(tmp_dir, "complex.svg")
        save_document(proj, json_path)
        save_svg(proj, svg_path)

        # Verify JSON roundtrip
        loaded = open_document(json_path)
        assert len(loaded["objects"]) == 8
        assert len(loaded["layers"]) == 2
        assert len(loaded["gradients"]) == 1

        # Verify SVG is valid XML
        tree = ET.parse(svg_path)
        root = tree.getroot()
        assert root.tag == f"{{{SVG_NS}}}svg"

    def test_svg_and_json_stay_in_sync(self, tmp_dir):
        """Verify that both JSON and SVG reflect the same state."""
        proj = create_document(width=800, height=600)
        add_rect(proj, x=10, y=10, width=100, height=50, name="R1")
        add_circle(proj, cx=200, cy=200, r=30, name="C1")

        json_path = os.path.join(tmp_dir, "sync.json")
        svg_path = os.path.join(tmp_dir, "sync.svg")
        save_document(proj, json_path)
        save_svg(proj, svg_path)

        # Both files should exist
        assert os.path.exists(json_path)
        assert os.path.exists(svg_path)

        # JSON has 2 objects
        loaded = open_document(json_path)
        assert len(loaded["objects"]) == 2

        # SVG has shapes (rect for bg + 2 shapes)
        tree = ET.parse(svg_path)
        rects = list(tree.getroot().iter(f"{{{SVG_NS}}}rect"))
        circles = list(tree.getroot().iter(f"{{{SVG_NS}}}circle"))
        assert len(rects) >= 2  # background + R1
        assert len(circles) >= 1


# ── Export Tests ────────────────────────────────────────────────

class TestExport:
    def test_export_svg(self, tmp_dir):
        proj = create_document()
        add_rect(proj, x=10, y=10, width=100, height=50)
        out = os.path.join(tmp_dir, "export.svg")
        result = export_svg(proj, out, overwrite=True)
        assert os.path.exists(out)
        assert result["format"] == "svg"
        assert result["size_bytes"] > 0

    def test_export_svg_overwrite_protection(self, tmp_dir):
        proj = create_document()
        out = os.path.join(tmp_dir, "existing.svg")
        with open(out, "w") as f:
            f.write("<svg/>")
        with pytest.raises(FileExistsError):
            export_svg(proj, out, overwrite=False)

    def test_export_svg_is_valid_xml(self, tmp_dir):
        proj = create_document()
        add_rect(proj)
        add_circle(proj)
        add_text(proj, text="Test")
        out = os.path.join(tmp_dir, "valid.svg")
        export_svg(proj, out, overwrite=True)
        tree = ET.parse(out)
        assert tree.getroot().tag == f"{{{SVG_NS}}}svg"

    def test_render_to_png(self, tmp_dir):
        """Test PNG rendering if Pillow is available."""
        try:
            import PIL
        except ImportError:
            pytest.skip("Pillow not installed")

        proj = create_document(width=200, height=200, background="#ffffff")
        add_rect(proj, x=10, y=10, width=80, height=80,
                 style="fill:#ff0000;stroke:#000000;stroke-width:2")
        add_circle(proj, cx=100, cy=100, r=40,
                   style="fill:#00ff00;stroke:none")

        out = os.path.join(tmp_dir, "render.png")
        result = render_to_png(proj, out, overwrite=True)
        assert os.path.exists(out)
        assert result["format"] == "png"

        # Verify it's a valid PNG
        from PIL import Image
        img = Image.open(out)
        assert img.size == (200, 200)

    def test_render_to_png_custom_size(self, tmp_dir):
        """Test PNG rendering at custom dimensions."""
        try:
            import PIL
        except ImportError:
            pytest.skip("Pillow not installed")

        proj = create_document(width=1920, height=1080)
        add_rect(proj, x=0, y=0, width=1920, height=1080,
                 style="fill:#3498db;stroke:none")

        out = os.path.join(tmp_dir, "scaled.png")
        result = render_to_png(proj, out, width=480, height=270, overwrite=True)
        assert os.path.exists(out)

        from PIL import Image
        img = Image.open(out)
        assert img.size == (480, 270)

    def test_render_to_png_overwrite_protection(self, tmp_dir):
        proj = create_document()
        out = os.path.join(tmp_dir, "existing.png")
        with open(out, "w") as f:
            f.write("fake")
        with pytest.raises(FileExistsError):
            render_to_png(proj, out, overwrite=False)

    def test_render_shapes(self, tmp_dir):
        """Test rendering multiple shape types."""
        try:
            import PIL
        except ImportError:
            pytest.skip("Pillow not installed")

        proj = create_document(width=400, height=400, background="#ffffff")
        add_rect(proj, x=10, y=10, width=80, height=60,
                 style="fill:#ff0000;stroke:#000;stroke-width:2")
        add_circle(proj, cx=200, cy=50, r=40,
                   style="fill:#00ff00;stroke:none")
        add_ellipse(proj, cx=350, cy=50, rx=40, ry=25,
                    style="fill:#0000ff;stroke:none")
        add_line(proj, x1=10, y1=200, x2=390, y2=200,
                 style="fill:none;stroke:#000;stroke-width:3")
        add_polygon(proj, points="200,250 250,350 150,350",
                    style="fill:#ff00ff;stroke:#000;stroke-width:1")
        add_text(proj, text="Shapes", x=10, y=390, font_size=24, fill="#333")

        out = os.path.join(tmp_dir, "shapes.png")
        result = render_to_png(proj, out, overwrite=True)
        assert os.path.exists(out)
        assert result["size_bytes"] > 0

    def test_render_star(self, tmp_dir):
        """Test rendering a star shape."""
        try:
            import PIL
        except ImportError:
            pytest.skip("Pillow not installed")

        proj = create_document(width=200, height=200)
        add_star(proj, cx=100, cy=100, points_count=5, outer_r=80, inner_r=30,
                 style="fill:#f1c40f;stroke:#e67e22;stroke-width:2")

        out = os.path.join(tmp_dir, "star.png")
        result = render_to_png(proj, out, overwrite=True)
        assert os.path.exists(out)


# ── Workflow Tests ──────────────────────────────────────────────

class TestWorkflows:
    def test_logo_design_workflow(self, tmp_dir):
        """Simulate designing a simple logo."""
        proj = create_document(name="logo", width=512, height=512, profile="icon_512")

        # Background circle
        add_circle(proj, cx=256, cy=256, r=250, name="BgCircle",
                   style="fill:#2c3e50;stroke:none")

        # Decorative elements
        add_star(proj, cx=256, cy=200, points_count=6, outer_r=80, inner_r=40,
                 name="StarDecor", style="fill:#f39c12;stroke:none")

        # Text
        add_text(proj, text="LOGO", x=256, y=350, font_size=72,
                 font_family="sans-serif", fill="#ecf0f1",
                 text_anchor="middle")

        # Apply gradient to background
        add_linear_gradient(proj, stops=[
            {"offset": 0, "color": "#2c3e50"},
            {"offset": 1, "color": "#3498db"},
        ], y1=0, y2=1)
        apply_gradient(proj, 0, 0, "fill")

        # Save both formats
        json_path = os.path.join(tmp_dir, "logo.json")
        svg_path = os.path.join(tmp_dir, "logo.svg")
        save_document(proj, json_path)
        save_svg(proj, svg_path)

        # Verify
        assert os.path.exists(json_path)
        assert os.path.exists(svg_path)
        tree = ET.parse(svg_path)
        assert tree.getroot().tag == f"{{{SVG_NS}}}svg"

    def test_infographic_workflow(self, tmp_dir):
        """Simulate creating a simple infographic."""
        proj = create_document(name="infographic", width=800, height=1200)

        # Title
        add_text(proj, text="Infographic Title", x=400, y=60,
                 font_size=36, text_anchor="middle", fill="#2c3e50")

        # Data bars
        colors = ["#e74c3c", "#3498db", "#2ecc71", "#f39c12", "#9b59b6"]
        values = [80, 65, 90, 45, 70]
        for i, (color, val) in enumerate(zip(colors, values)):
            y = 150 + i * 80
            # Bar background
            add_rect(proj, x=100, y=y, width=600, height=40,
                     style=f"fill:#ecf0f1;stroke:none")
            # Bar value
            bar_width = val * 6  # scale
            add_rect(proj, x=100, y=y, width=bar_width, height=40,
                     style=f"fill:{color};stroke:none")
            # Label
            add_text(proj, text=f"Item {i+1}: {val}%", x=110, y=y + 28,
                     font_size=16, fill="#ffffff")

        # Save
        svg_path = os.path.join(tmp_dir, "infographic.svg")
        save_svg(proj, svg_path)
        tree = ET.parse(svg_path)
        root = tree.getroot()
        assert root.tag == f"{{{SVG_NS}}}svg"

    def test_multi_layer_workflow(self, tmp_dir):
        """Work with multiple layers."""
        proj = create_document(name="layers_test")

        # Create layers
        add_layer(proj, name="Background")
        add_layer(proj, name="Foreground")

        # Add objects to specific layers
        add_rect(proj, name="BgFill", width=1920, height=1080,
                 style="fill:#eeeeee;stroke:none", layer=proj["layers"][1]["id"])
        add_circle(proj, cx=960, cy=540, r=100, name="MainShape",
                   layer=proj["layers"][2]["id"])

        # Verify layer structure
        layers = list_layers(proj)
        assert len(layers) == 3  # Default + 2 added

        # Save and verify
        json_path = os.path.join(tmp_dir, "layers.json")
        save_document(proj, json_path)
        loaded = open_document(json_path)
        assert len(loaded["layers"]) == 3
        assert len(loaded["objects"]) == 2

    def test_transform_workflow(self):
        """Apply multiple transforms and verify."""
        proj = create_document()
        add_rect(proj, x=0, y=0, width=100, height=100)

        translate(proj, 0, 50, 50)
        rotate(proj, 0, 45, cx=100, cy=100)
        scale(proj, 0, 1.5)

        t = get_transform(proj, 0)
        assert len(t["operations"]) == 3
        assert t["operations"][0]["type"] == "translate"
        assert t["operations"][1]["type"] == "rotate"
        assert t["operations"][2]["type"] == "scale"

    def test_style_workflow(self):
        """Apply various styles and verify."""
        proj = create_document()
        add_rect(proj)

        set_fill(proj, 0, "#ff0000")
        set_stroke(proj, 0, "#000000", width=2)
        set_opacity(proj, 0, 0.8)
        set_style(proj, 0, "stroke-linejoin", "round")
        set_style(proj, 0, "stroke-dasharray", "5,3")

        style = get_object_style(proj, 0)
        assert style["fill"] == "#ff0000"
        assert style["stroke"] == "#000000"
        assert style["stroke-width"] == "2"
        assert style["opacity"] == "0.8"
        assert style["stroke-linejoin"] == "round"
        assert style["stroke-dasharray"] == "5,3"

    def test_path_operations_workflow(self):
        """Test path boolean operations."""
        proj = create_document()
        add_rect(proj, x=0, y=0, width=100, height=100, name="Square")
        add_circle(proj, cx=80, cy=50, r=50, name="Circle")

        result = path_union(proj, 0, 1, name="Combined")
        assert result["type"] == "path"
        assert result["boolean_operation"]["type"] == "union"
        assert len(proj["objects"]) == 1

    def test_undo_redo_workflow(self):
        """Test undo/redo through a complex editing workflow."""
        sess = Session()
        proj = create_document(name="undo_test")
        sess.set_project(proj)

        # Step 1: Add rect
        sess.snapshot("add rect")
        add_rect(proj, name="Rect")
        assert len(proj["objects"]) == 1

        # Step 2: Add circle
        sess.snapshot("add circle")
        add_circle(proj, name="Circle")
        assert len(proj["objects"]) == 2

        # Step 3: Style change
        sess.snapshot("change style")
        set_fill(proj, 0, "#ff0000")
        style = get_object_style(proj, 0)
        assert style["fill"] == "#ff0000"

        # Undo style change
        sess.undo()
        proj = sess.get_project()
        style = get_object_style(proj, 0)
        assert style["fill"] != "#ff0000"

        # Undo circle add
        sess.undo()
        proj = sess.get_project()
        assert len(proj["objects"]) == 1

        # Redo circle add
        sess.redo()
        proj = sess.get_project()
        assert len(proj["objects"]) == 2

    def test_gradient_workflow(self, tmp_dir):
        """Create and apply gradients, then export."""
        proj = create_document(width=400, height=400)

        # Create gradient
        add_linear_gradient(proj, stops=[
            {"offset": 0, "color": "#ff0000"},
            {"offset": 0.5, "color": "#00ff00"},
            {"offset": 1, "color": "#0000ff"},
        ], name="Rainbow")

        # Create shape and apply gradient
        add_rect(proj, x=50, y=50, width=300, height=300, name="GradBox")
        apply_gradient(proj, 0, 0, "fill")

        # Export SVG
        svg_path = os.path.join(tmp_dir, "gradient.svg")
        save_svg(proj, svg_path)
        tree = ET.parse(svg_path)
        defs = tree.getroot().find(f"{{{SVG_NS}}}defs")
        grads = list(defs.iter(f"{{{SVG_NS}}}linearGradient"))
        assert len(grads) >= 1
        stops = list(grads[0].iter(f"{{{SVG_NS}}}stop"))
        assert len(stops) == 3

    def test_full_document_export(self, tmp_dir):
        """Full workflow: create, edit, export to all formats."""
        proj = create_document(name="full", width=800, height=600)

        # Add various elements
        add_rect(proj, x=0, y=0, width=800, height=600,
                 style="fill:#f0f0f0;stroke:none")
        add_circle(proj, cx=400, cy=300, r=100,
                   style="fill:#3498db;stroke:#2980b9;stroke-width:3")
        add_text(proj, text="Full Export Test", x=400, y=50,
                 font_size=32, text_anchor="middle")

        # Export SVG
        svg_path = os.path.join(tmp_dir, "full.svg")
        result = export_svg(proj, svg_path, overwrite=True)
        assert os.path.exists(svg_path)

        # Export JSON
        json_path = os.path.join(tmp_dir, "full.json")
        save_document(proj, json_path)
        assert os.path.exists(json_path)

        # Export PNG (if Pillow available)
        try:
            import PIL
            png_path = os.path.join(tmp_dir, "full.png")
            result = render_to_png(proj, png_path, overwrite=True)
            assert os.path.exists(png_path)
        except ImportError:
            pass


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
    CLI_BASE = _resolve_cli("cli-anything-inkscape")

    def _run(self, args, check=True):
        return subprocess.run(
            self.CLI_BASE + args,
            capture_output=True, text=True,
            check=check,
        )

    def test_help(self):
        result = self._run(["--help"])
        assert result.returncode == 0
        assert "Inkscape CLI" in result.stdout

    def test_document_new(self, tmp_dir):
        out = os.path.join(tmp_dir, "test.json")
        result = self._run(["document", "new", "-o", out])
        assert result.returncode == 0
        assert os.path.exists(out)

    def test_document_new_json_output(self, tmp_dir):
        out = os.path.join(tmp_dir, "test.json")
        result = self._run(["--json", "document", "new", "-o", out])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["document"]["width"] == 1920

    def test_document_profiles(self):
        result = self._run(["document", "profiles"])
        assert result.returncode == 0
        assert "a4_portrait" in result.stdout

    def test_shape_types(self):
        result = self._run(["shape", "--help"])
        assert result.returncode == 0
        assert "add-rect" in result.stdout

    def test_style_list_properties(self):
        result = self._run(["style", "list-properties"])
        assert result.returncode == 0
        assert "fill" in result.stdout

    def test_export_presets(self):
        result = self._run(["export", "presets"])
        assert result.returncode == 0
        assert "png_web" in result.stdout

    def test_path_list_operations(self):
        result = self._run(["path", "list-operations"])
        assert result.returncode == 0
        assert "union" in result.stdout

    def test_full_workflow_json(self, tmp_dir):
        proj_path = os.path.join(tmp_dir, "workflow.json")

        # Create document
        self._run(["--json", "document", "new", "-o", proj_path, "-n", "workflow"])
        assert os.path.exists(proj_path)

        # Load and verify
        result = self._run(["--json", "--project", proj_path, "document", "info"])
        assert result.returncode == 0
        info = json.loads(result.stdout)
        assert info["name"] == "workflow"

    def test_cli_error_handling(self):
        result = self._run(["document", "open", "/nonexistent/file.json"], check=False)
        assert result.returncode != 0

    def test_gradient_commands(self):
        result = self._run(["gradient", "--help"])
        assert result.returncode == 0
        assert "add-linear" in result.stdout

    def test_transform_commands(self):
        result = self._run(["transform", "--help"])
        assert result.returncode == 0
        assert "translate" in result.stdout

    def test_layer_commands(self):
        result = self._run(["layer", "--help"])
        assert result.returncode == 0
        assert "add" in result.stdout


# ── True Backend E2E Tests (requires Inkscape installed) ─────────

class TestInkscapeBackend:
    """Tests that verify Inkscape is installed and accessible."""

    def test_inkscape_is_installed(self):
        from cli_anything.inkscape.utils.inkscape_backend import find_inkscape
        path = find_inkscape()
        assert os.path.exists(path)
        print(f"\n  Inkscape binary: {path}")

    def test_inkscape_version(self):
        from cli_anything.inkscape.utils.inkscape_backend import get_version
        version = get_version()
        assert "Inkscape" in version
        print(f"\n  Inkscape version: {version}")


class TestInkscapeExportE2E:
    """True E2E tests: create SVG → Inkscape export → verify output."""

    def test_svg_to_png(self):
        """Export SVG to PNG using Inkscape."""
        from cli_anything.inkscape.utils.inkscape_backend import export_svg_to_png

        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create a simple SVG
            svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="200" height="150" viewBox="0 0 200 150">
  <rect width="200" height="150" fill="#3498db"/>
  <circle cx="100" cy="75" r="50" fill="#e74c3c"/>
  <text x="100" y="80" text-anchor="middle" fill="white" font-size="20">Test</text>
</svg>'''
            svg_path = os.path.join(tmp_dir, "test.svg")
            with open(svg_path, 'w') as f:
                f.write(svg_content)

            png_path = os.path.join(tmp_dir, "test.png")
            result = export_svg_to_png(svg_path, png_path, dpi=96, overwrite=True)

            assert os.path.exists(result["output"])
            assert result["file_size"] > 0
            assert result["method"] == "inkscape"
            print(f"\n  SVG→PNG: {result['output']} ({result['file_size']:,} bytes)")

    def test_svg_to_pdf(self):
        """Export SVG to PDF using Inkscape."""
        from cli_anything.inkscape.utils.inkscape_backend import export_svg_to_pdf

        with tempfile.TemporaryDirectory() as tmp_dir:
            svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="200" height="150">
  <rect width="200" height="150" fill="#2ecc71"/>
  <text x="100" y="80" text-anchor="middle" fill="white" font-size="24">PDF Test</text>
</svg>'''
            svg_path = os.path.join(tmp_dir, "test.svg")
            with open(svg_path, 'w') as f:
                f.write(svg_content)

            pdf_path = os.path.join(tmp_dir, "test.pdf")
            result = export_svg_to_pdf(svg_path, pdf_path, overwrite=True)

            assert os.path.exists(result["output"])
            assert result["file_size"] > 0
            # Verify PDF magic bytes
            with open(result["output"], "rb") as f:
                magic = f.read(5)
            assert magic == b"%PDF-", f"Not a valid PDF: {magic}"
            print(f"\n  SVG→PDF: {result['output']} ({result['file_size']:,} bytes)")

    def test_svg_to_png_with_dimensions(self):
        """Export SVG to PNG with specific dimensions."""
        from cli_anything.inkscape.utils.inkscape_backend import export_svg_to_png

        with tempfile.TemporaryDirectory() as tmp_dir:
            svg_content = '''<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
  <rect width="100" height="100" fill="purple"/>
</svg>'''
            svg_path = os.path.join(tmp_dir, "small.svg")
            with open(svg_path, 'w') as f:
                f.write(svg_content)

            png_path = os.path.join(tmp_dir, "large.png")
            result = export_svg_to_png(svg_path, png_path, width=400, height=400, overwrite=True)

            assert os.path.exists(result["output"])
            assert result["file_size"] > 0
            print(f"\n  SVG→PNG (400x400): {result['output']} ({result['file_size']:,} bytes)")
