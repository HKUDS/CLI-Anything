"""Unit tests for Inkscape CLI core modules.

Tests use synthetic data only — no real SVG files or Inkscape installation.
"""

import json
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from cli_anything.inkscape.utils.svg_utils import (
    parse_style, serialize_style, validate_color, generate_id,
    reset_id_counter, create_svg_element, serialize_svg,
    find_defs, find_element_by_id, remove_element_by_id,
    SVG_NS, INKSCAPE_NS,
)
from cli_anything.inkscape.core.document import (
    create_document, open_document, save_document, get_document_info,
    set_canvas_size, set_units, list_profiles, PROFILES, VALID_UNITS,
    project_to_svg, save_svg,
)
from cli_anything.inkscape.core.shapes import (
    add_rect, add_circle, add_ellipse, add_line, add_polygon,
    add_path, add_star, remove_object, duplicate_object,
    list_objects, get_object, SHAPE_TYPES,
)
from cli_anything.inkscape.core.text import (
    add_text, set_text_property, list_text_objects, TEXT_PROPERTIES,
)
from cli_anything.inkscape.core.styles import (
    set_fill, set_stroke, set_opacity, set_style,
    list_style_properties, get_object_style, STYLE_PROPERTIES,
)
from cli_anything.inkscape.core.transforms import (
    translate, rotate, scale, skew_x, skew_y,
    get_transform, set_transform, clear_transform,
    parse_transform_string, serialize_transform_string,
)
from cli_anything.inkscape.core.layers import (
    add_layer, remove_layer, move_to_layer, set_layer_property,
    list_layers, reorder_layers, get_layer,
)
from cli_anything.inkscape.core.paths import (
    path_union, path_intersection, path_difference, path_exclusion,
    convert_to_path, list_path_operations, PATH_OPERATIONS, CONVERTIBLE_TYPES,
)
from cli_anything.inkscape.core.gradients import (
    add_linear_gradient, add_radial_gradient, apply_gradient,
    list_gradients, get_gradient, remove_gradient,
)
from cli_anything.inkscape.core.export import EXPORT_PRESETS, list_presets
from cli_anything.inkscape.core.session import Session


@pytest.fixture(autouse=True)
def reset_ids():
    """Reset the ID counter before each test."""
    reset_id_counter()


# ── SVG Utils Tests ─────────────────────────────────────────────

class TestSVGUtils:
    def test_parse_style(self):
        result = parse_style("fill:#ff0000;stroke:#000;stroke-width:2")
        assert result["fill"] == "#ff0000"
        assert result["stroke"] == "#000"
        assert result["stroke-width"] == "2"

    def test_parse_empty_style(self):
        assert parse_style("") == {}
        assert parse_style(None) == {}

    def test_serialize_style(self):
        s = serialize_style({"fill": "#ff0000", "stroke": "#000"})
        assert "fill:#ff0000" in s
        assert "stroke:#000" in s

    def test_serialize_empty_style(self):
        assert serialize_style({}) == ""

    def test_roundtrip_style(self):
        original = "fill:#ff0000;stroke:#000000;stroke-width:2"
        parsed = parse_style(original)
        serialized = serialize_style(parsed)
        reparsed = parse_style(serialized)
        assert reparsed == parsed

    def test_validate_color_hex(self):
        assert validate_color("#ff0000")
        assert validate_color("#fff")
        assert validate_color("#aabbcc")

    def test_validate_color_named(self):
        assert validate_color("red")
        assert validate_color("blue")
        assert validate_color("transparent")
        assert validate_color("none")

    def test_validate_color_rgb(self):
        assert validate_color("rgb(255,0,0)")
        assert validate_color("rgba(255,0,0,0.5)")

    def test_validate_color_invalid(self):
        assert not validate_color("")
        assert not validate_color(None)

    def test_generate_id(self):
        id1 = generate_id("test")
        id2 = generate_id("test")
        assert id1 != id2
        assert id1.startswith("test")

    def test_create_svg_element(self):
        svg = create_svg_element(800, 600, "px")
        assert svg.tag == f"{{{SVG_NS}}}svg"
        assert svg.get("width") == "800px"
        assert svg.get("height") == "600px"

    def test_serialize_svg(self):
        svg = create_svg_element()
        xml_str = serialize_svg(svg)
        assert "<?xml" in xml_str
        assert "svg" in xml_str

    def test_find_defs(self):
        svg = create_svg_element()
        defs = find_defs(svg)
        assert defs is not None
        assert defs.tag == f"{{{SVG_NS}}}defs"


# ── Document Tests ──────────────────────────────────────────────

class TestDocument:
    def test_create_default(self):
        proj = create_document()
        assert proj["document"]["width"] == 1920
        assert proj["document"]["height"] == 1080
        assert proj["document"]["units"] == "px"
        assert proj["version"] == "1.0"

    def test_create_with_dimensions(self):
        proj = create_document(width=800, height=600)
        assert proj["document"]["width"] == 800
        assert proj["document"]["height"] == 600

    def test_create_with_profile(self):
        proj = create_document(profile="a4_portrait")
        assert proj["document"]["width"] == 210
        assert proj["document"]["height"] == 297
        assert proj["document"]["units"] == "mm"

    def test_create_with_icon_profile(self):
        proj = create_document(profile="icon_256")
        assert proj["document"]["width"] == 256
        assert proj["document"]["height"] == 256

    def test_create_invalid_units(self):
        with pytest.raises(ValueError, match="Invalid units"):
            create_document(units="em")

    def test_create_invalid_dimensions(self):
        with pytest.raises(ValueError, match="must be positive"):
            create_document(width=0, height=100)

    def test_create_has_default_layer(self):
        proj = create_document()
        assert len(proj["layers"]) == 1
        assert proj["layers"][0]["name"] == "Layer 1"

    def test_save_and_open(self):
        proj = create_document(name="test_doc")
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            save_document(proj, path)
            loaded = open_document(path)
            assert loaded["name"] == "test_doc"
            assert loaded["document"]["width"] == 1920
        finally:
            os.unlink(path)

    def test_open_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            open_document("/nonexistent/path.json")

    def test_get_info(self):
        proj = create_document(name="info_test")
        info = get_document_info(proj)
        assert info["name"] == "info_test"
        assert info["counts"]["objects"] == 0
        assert info["counts"]["layers"] == 1

    def test_set_canvas_size(self):
        proj = create_document()
        result = set_canvas_size(proj, 800, 600)
        assert proj["document"]["width"] == 800
        assert proj["document"]["height"] == 600
        assert "old_size" in result

    def test_set_canvas_size_invalid(self):
        proj = create_document()
        with pytest.raises(ValueError, match="must be positive"):
            set_canvas_size(proj, 0, 0)

    def test_set_units(self):
        proj = create_document()
        result = set_units(proj, "mm")
        assert proj["document"]["units"] == "mm"
        assert result["old_units"] == "px"

    def test_set_units_invalid(self):
        proj = create_document()
        with pytest.raises(ValueError, match="Invalid units"):
            set_units(proj, "em")

    def test_list_profiles(self):
        profiles = list_profiles()
        assert len(profiles) > 0
        names = [p["name"] for p in profiles]
        assert "default" in names
        assert "a4_portrait" in names
        assert "hd1080p" in names

    def test_all_valid_units(self):
        for unit in VALID_UNITS:
            proj = create_document(units=unit)
            assert proj["document"]["units"] == unit

    def test_project_to_svg(self):
        proj = create_document(name="svg_test", width=800, height=600)
        svg = project_to_svg(proj)
        assert svg.tag == f"{{{SVG_NS}}}svg"
        assert "800" in svg.get("width", "")


# ── Shape Tests ─────────────────────────────────────────────────

class TestShapes:
    def _make_doc(self):
        return create_document()

    def test_add_rect(self):
        proj = self._make_doc()
        obj = add_rect(proj, x=10, y=20, width=200, height=100)
        assert obj["type"] == "rect"
        assert obj["x"] == 10
        assert obj["width"] == 200
        assert len(proj["objects"]) == 1

    def test_add_rect_invalid_dimensions(self):
        proj = self._make_doc()
        with pytest.raises(ValueError, match="must be positive"):
            add_rect(proj, width=0, height=100)

    def test_add_circle(self):
        proj = self._make_doc()
        obj = add_circle(proj, cx=100, cy=100, r=50)
        assert obj["type"] == "circle"
        assert obj["r"] == 50

    def test_add_circle_invalid_radius(self):
        proj = self._make_doc()
        with pytest.raises(ValueError, match="must be positive"):
            add_circle(proj, r=-5)

    def test_add_ellipse(self):
        proj = self._make_doc()
        obj = add_ellipse(proj, cx=50, cy=50, rx=100, ry=50)
        assert obj["type"] == "ellipse"
        assert obj["rx"] == 100
        assert obj["ry"] == 50

    def test_add_ellipse_invalid(self):
        proj = self._make_doc()
        with pytest.raises(ValueError, match="must be positive"):
            add_ellipse(proj, rx=-1, ry=50)

    def test_add_line(self):
        proj = self._make_doc()
        obj = add_line(proj, x1=0, y1=0, x2=100, y2=100)
        assert obj["type"] == "line"
        assert obj["x2"] == 100

    def test_add_polygon(self):
        proj = self._make_doc()
        obj = add_polygon(proj, points="50,0 100,100 0,100")
        assert obj["type"] == "polygon"
        assert "50,0" in obj["points"]

    def test_add_polygon_empty(self):
        proj = self._make_doc()
        with pytest.raises(ValueError, match="at least one point"):
            add_polygon(proj, points="")

    def test_add_path(self):
        proj = self._make_doc()
        obj = add_path(proj, d="M 0,0 L 100,0 L 100,100 Z")
        assert obj["type"] == "path"
        assert "M 0,0" in obj["d"]

    def test_add_path_empty(self):
        proj = self._make_doc()
        with pytest.raises(ValueError, match="cannot be empty"):
            add_path(proj, d="")

    def test_add_star(self):
        proj = self._make_doc()
        obj = add_star(proj, cx=100, cy=100, points_count=5, outer_r=50, inner_r=25)
        assert obj["type"] == "star"
        assert obj["points_count"] == 5
        assert "d" in obj

    def test_add_star_invalid_points(self):
        proj = self._make_doc()
        with pytest.raises(ValueError, match="at least 3"):
            add_star(proj, points_count=2)

    def test_add_star_invalid_radius(self):
        proj = self._make_doc()
        with pytest.raises(ValueError, match="must be positive"):
            add_star(proj, outer_r=-1, inner_r=25)

    def test_remove_object(self):
        proj = self._make_doc()
        add_rect(proj, name="A")
        add_circle(proj, name="B")
        removed = remove_object(proj, 0)
        assert removed["name"] == "A"
        assert len(proj["objects"]) == 1

    def test_remove_object_empty(self):
        proj = self._make_doc()
        with pytest.raises(ValueError, match="No objects"):
            remove_object(proj, 0)

    def test_remove_object_invalid_index(self):
        proj = self._make_doc()
        add_rect(proj)
        with pytest.raises(IndexError):
            remove_object(proj, 5)

    def test_duplicate_object(self):
        proj = self._make_doc()
        add_rect(proj, name="Original")
        dup = duplicate_object(proj, 0)
        assert "copy" in dup["name"]
        assert len(proj["objects"]) == 2
        assert dup["id"] != proj["objects"][0]["id"]

    def test_list_objects(self):
        proj = self._make_doc()
        add_rect(proj, name="R")
        add_circle(proj, name="C")
        result = list_objects(proj)
        assert len(result) == 2

    def test_get_object(self):
        proj = self._make_doc()
        add_rect(proj, name="Test")
        obj = get_object(proj, 0)
        assert obj["name"] == "Test"

    def test_unique_ids(self):
        proj = self._make_doc()
        a = add_rect(proj, name="A")
        b = add_rect(proj, name="B")
        assert a["id"] != b["id"]

    def test_object_added_to_layer(self):
        proj = self._make_doc()
        obj = add_rect(proj)
        assert obj["id"] in proj["layers"][0]["objects"]

    def test_all_shape_types_registered(self):
        expected = {"rect", "circle", "ellipse", "line", "polygon",
                    "polyline", "path", "text", "star", "image"}
        assert expected.issubset(set(SHAPE_TYPES.keys()))

    def test_add_rect_with_custom_style(self):
        proj = self._make_doc()
        obj = add_rect(proj, style="fill:#ff0000;stroke:none")
        assert "fill:#ff0000" in obj["style"]

    def test_add_rect_rounded_corners(self):
        proj = self._make_doc()
        obj = add_rect(proj, rx=10, ry=10)
        assert obj["rx"] == 10
        assert obj["ry"] == 10


# ── Text Tests ──────────────────────────────────────────────────

class TestText:
    def _make_doc(self):
        return create_document()

    def test_add_text(self):
        proj = self._make_doc()
        obj = add_text(proj, text="Hello World", x=100, y=200)
        assert obj["type"] == "text"
        assert obj["text"] == "Hello World"
        assert obj["x"] == 100

    def test_add_text_empty(self):
        proj = self._make_doc()
        with pytest.raises(ValueError, match="cannot be empty"):
            add_text(proj, text="")

    def test_add_text_invalid_font_size(self):
        proj = self._make_doc()
        with pytest.raises(ValueError, match="must be positive"):
            add_text(proj, text="Hi", font_size=0)

    def test_set_text_content(self):
        proj = self._make_doc()
        add_text(proj, text="Old")
        set_text_property(proj, 0, "text", "New")
        assert proj["objects"][0]["text"] == "New"

    def test_set_font_family(self):
        proj = self._make_doc()
        add_text(proj, text="Hi")
        set_text_property(proj, 0, "font-family", "serif")
        assert proj["objects"][0]["font_family"] == "serif"

    def test_set_font_size(self):
        proj = self._make_doc()
        add_text(proj, text="Hi")
        set_text_property(proj, 0, "font-size", "48")
        assert proj["objects"][0]["font_size"] == 48.0

    def test_set_invalid_font_weight(self):
        proj = self._make_doc()
        add_text(proj, text="Hi")
        with pytest.raises(ValueError, match="Invalid font-weight"):
            set_text_property(proj, 0, "font-weight", "extra-heavy")

    def test_set_invalid_property(self):
        proj = self._make_doc()
        add_text(proj, text="Hi")
        with pytest.raises(ValueError, match="Unknown text property"):
            set_text_property(proj, 0, "bogus", "value")

    def test_set_on_non_text(self):
        proj = self._make_doc()
        add_rect(proj)
        with pytest.raises(ValueError, match="not a text element"):
            set_text_property(proj, 0, "text", "Hi")

    def test_list_text_objects(self):
        proj = self._make_doc()
        add_text(proj, text="A")
        add_rect(proj)
        add_text(proj, text="B")
        result = list_text_objects(proj)
        assert len(result) == 2

    def test_text_style_rebuilt(self):
        proj = self._make_doc()
        add_text(proj, text="Hi", fill="#ff0000")
        set_text_property(proj, 0, "font-size", "48")
        style = proj["objects"][0]["style"]
        assert "48" in style and "px" in style
        assert "#ff0000" in style


# ── Style Tests ─────────────────────────────────────────────────

class TestStyles:
    def _make_doc_with_rect(self):
        proj = create_document()
        add_rect(proj)
        return proj

    def test_set_fill(self):
        proj = self._make_doc_with_rect()
        set_fill(proj, 0, "#ff0000")
        style = parse_style(proj["objects"][0]["style"])
        assert style["fill"] == "#ff0000"

    def test_set_stroke(self):
        proj = self._make_doc_with_rect()
        set_stroke(proj, 0, "#00ff00", width=3)
        style = parse_style(proj["objects"][0]["style"])
        assert style["stroke"] == "#00ff00"
        assert style["stroke-width"] == "3"

    def test_set_stroke_negative_width(self):
        proj = self._make_doc_with_rect()
        with pytest.raises(ValueError, match="non-negative"):
            set_stroke(proj, 0, "#000", width=-1)

    def test_set_opacity(self):
        proj = self._make_doc_with_rect()
        set_opacity(proj, 0, 0.5)
        style = parse_style(proj["objects"][0]["style"])
        assert style["opacity"] == "0.5"

    def test_set_opacity_invalid(self):
        proj = self._make_doc_with_rect()
        with pytest.raises(ValueError, match="0.0-1.0"):
            set_opacity(proj, 0, 1.5)

    def test_set_style_arbitrary(self):
        proj = self._make_doc_with_rect()
        set_style(proj, 0, "stroke-linecap", "round")
        style = parse_style(proj["objects"][0]["style"])
        assert style["stroke-linecap"] == "round"

    def test_set_style_invalid_property(self):
        proj = self._make_doc_with_rect()
        with pytest.raises(ValueError, match="Unknown style property"):
            set_style(proj, 0, "bogus", "value")

    def test_set_style_invalid_choice(self):
        proj = self._make_doc_with_rect()
        with pytest.raises(ValueError, match="Invalid value"):
            set_style(proj, 0, "stroke-linecap", "diamond")

    def test_get_object_style(self):
        proj = self._make_doc_with_rect()
        set_fill(proj, 0, "#ff0000")
        style = get_object_style(proj, 0)
        assert "fill" in style

    def test_list_style_properties(self):
        props = list_style_properties()
        assert len(props) > 0
        names = [p["name"] for p in props]
        assert "fill" in names
        assert "stroke" in names
        assert "opacity" in names

    def test_set_fill_opacity(self):
        proj = self._make_doc_with_rect()
        set_style(proj, 0, "fill-opacity", "0.5")
        style = parse_style(proj["objects"][0]["style"])
        assert style["fill-opacity"] == "0.5"

    def test_set_fill_opacity_invalid(self):
        proj = self._make_doc_with_rect()
        with pytest.raises(ValueError, match="0.0-1.0"):
            set_style(proj, 0, "fill-opacity", "2.0")


# ── Transform Tests ─────────────────────────────────────────────

class TestTransforms:
    def _make_doc_with_rect(self):
        proj = create_document()
        add_rect(proj)
        return proj

    def test_translate(self):
        proj = self._make_doc_with_rect()
        translate(proj, 0, 100, 50)
        t = get_transform(proj, 0)
        assert "translate(100, 50)" in t["raw"]

    def test_rotate(self):
        proj = self._make_doc_with_rect()
        rotate(proj, 0, 45)
        t = get_transform(proj, 0)
        assert "rotate(45)" in t["raw"]

    def test_rotate_with_center(self):
        proj = self._make_doc_with_rect()
        rotate(proj, 0, 90, cx=50, cy=50)
        t = get_transform(proj, 0)
        assert "rotate(90, 50, 50)" in t["raw"]

    def test_scale(self):
        proj = self._make_doc_with_rect()
        scale(proj, 0, 2)
        t = get_transform(proj, 0)
        assert "scale(2)" in t["raw"]

    def test_scale_non_uniform(self):
        proj = self._make_doc_with_rect()
        scale(proj, 0, 2, 3)
        t = get_transform(proj, 0)
        assert "scale(2, 3)" in t["raw"]

    def test_scale_zero_raises(self):
        proj = self._make_doc_with_rect()
        with pytest.raises(ValueError, match="non-zero"):
            scale(proj, 0, 0)

    def test_skew_x(self):
        proj = self._make_doc_with_rect()
        skew_x(proj, 0, 30)
        t = get_transform(proj, 0)
        assert "skewX(30)" in t["raw"]

    def test_skew_y(self):
        proj = self._make_doc_with_rect()
        skew_y(proj, 0, 15)
        t = get_transform(proj, 0)
        assert "skewY(15)" in t["raw"]

    def test_compound_transforms(self):
        proj = self._make_doc_with_rect()
        translate(proj, 0, 10, 20)
        rotate(proj, 0, 45)
        t = get_transform(proj, 0)
        assert "translate" in t["raw"]
        assert "rotate" in t["raw"]
        assert len(t["operations"]) == 2

    def test_set_transform(self):
        proj = self._make_doc_with_rect()
        set_transform(proj, 0, "matrix(1,0,0,1,10,20)")
        t = get_transform(proj, 0)
        assert "matrix" in t["raw"]

    def test_clear_transform(self):
        proj = self._make_doc_with_rect()
        translate(proj, 0, 100, 100)
        result = clear_transform(proj, 0)
        assert result["new_transform"] == ""
        assert proj["objects"][0]["transform"] == ""

    def test_parse_transform_string(self):
        ops = parse_transform_string("translate(10, 20) rotate(45) scale(2, 3)")
        assert len(ops) == 3
        assert ops[0] == ("translate", [10.0, 20.0])
        assert ops[1] == ("rotate", [45.0])
        assert ops[2] == ("scale", [2.0, 3.0])

    def test_parse_empty_transform(self):
        assert parse_transform_string("") == []
        assert parse_transform_string(None) == []

    def test_serialize_transform_string(self):
        ops = [("translate", [10.0, 20.0]), ("rotate", [45.0])]
        result = serialize_transform_string(ops)
        assert "translate(10, 20)" in result
        assert "rotate(45)" in result

    def test_serialize_empty(self):
        assert serialize_transform_string([]) == ""


# ── Layer Tests ─────────────────────────────────────────────────

class TestLayers:
    def _make_doc(self):
        return create_document()

    def test_add_layer(self):
        proj = self._make_doc()
        layer = add_layer(proj, name="Layer 2")
        assert layer["name"] == "Layer 2"
        assert len(proj["layers"]) == 2

    def test_add_layer_unique_names(self):
        proj = self._make_doc()
        l1 = add_layer(proj, name="Layer 1")
        # "Layer 1" already exists as default
        assert l1["name"] == "Layer 1 2"

    def test_add_layer_invalid_opacity(self):
        proj = self._make_doc()
        with pytest.raises(ValueError, match="0.0-1.0"):
            add_layer(proj, opacity=1.5)

    def test_remove_layer(self):
        proj = self._make_doc()
        add_layer(proj, name="Second")
        removed = remove_layer(proj, 1)
        assert removed["name"] == "Second"
        assert len(proj["layers"]) == 1

    def test_remove_last_layer_fails(self):
        proj = self._make_doc()
        with pytest.raises(ValueError, match="Cannot remove the last"):
            remove_layer(proj, 0)

    def test_move_to_layer(self):
        proj = self._make_doc()
        add_rect(proj, name="Shape")
        add_layer(proj, name="Layer 2")
        result = move_to_layer(proj, 0, 1)
        assert proj["objects"][0]["layer"] == proj["layers"][1]["id"]

    def test_set_layer_property_visible(self):
        proj = self._make_doc()
        set_layer_property(proj, 0, "visible", "false")
        assert proj["layers"][0]["visible"] is False

    def test_set_layer_property_locked(self):
        proj = self._make_doc()
        set_layer_property(proj, 0, "locked", "true")
        assert proj["layers"][0]["locked"] is True

    def test_set_layer_property_opacity(self):
        proj = self._make_doc()
        set_layer_property(proj, 0, "opacity", "0.5")
        assert proj["layers"][0]["opacity"] == 0.5

    def test_set_layer_property_name(self):
        proj = self._make_doc()
        set_layer_property(proj, 0, "name", "Renamed")
        assert proj["layers"][0]["name"] == "Renamed"

    def test_set_layer_property_invalid(self):
        proj = self._make_doc()
        with pytest.raises(ValueError, match="Unknown layer property"):
            set_layer_property(proj, 0, "bogus", "value")

    def test_list_layers(self):
        proj = self._make_doc()
        add_layer(proj, name="Second")
        result = list_layers(proj)
        assert len(result) == 2

    def test_reorder_layers(self):
        proj = self._make_doc()
        add_layer(proj, name="Second")
        add_layer(proj, name="Third")
        reorder_layers(proj, 0, 2)
        assert proj["layers"][2]["name"] == "Layer 1"
        assert proj["layers"][0]["name"] == "Second"

    def test_get_layer(self):
        proj = self._make_doc()
        add_rect(proj, name="Shape")
        layer = get_layer(proj, 0)
        assert layer["name"] == "Layer 1"
        assert len(layer["objects"]) == 1

    def test_remove_layer_moves_objects(self):
        proj = self._make_doc()
        add_layer(proj, name="Second")
        # Add object to second layer
        obj = add_rect(proj, name="Shape", layer=proj["layers"][1]["id"])
        # Remove second layer
        remove_layer(proj, 1)
        # Object should be moved to first layer
        assert obj["id"] in proj["layers"][0]["objects"]


# ── Path Operations Tests ───────────────────────────────────────

class TestPaths:
    def _make_doc_with_shapes(self):
        proj = create_document()
        add_rect(proj, name="Rect1")
        add_circle(proj, name="Circle1")
        return proj

    def test_union(self):
        proj = self._make_doc_with_shapes()
        result = path_union(proj, 0, 1)
        assert result["type"] == "path"
        assert result["boolean_operation"]["type"] == "union"
        assert len(proj["objects"]) == 1

    def test_intersection(self):
        proj = self._make_doc_with_shapes()
        result = path_intersection(proj, 0, 1)
        assert result["boolean_operation"]["type"] == "intersection"

    def test_difference(self):
        proj = self._make_doc_with_shapes()
        result = path_difference(proj, 0, 1)
        assert result["boolean_operation"]["type"] == "difference"

    def test_exclusion(self):
        proj = self._make_doc_with_shapes()
        result = path_exclusion(proj, 0, 1)
        assert result["boolean_operation"]["type"] == "exclusion"

    def test_boolean_same_object_fails(self):
        proj = self._make_doc_with_shapes()
        with pytest.raises(ValueError, match="same object"):
            path_union(proj, 0, 0)

    def test_boolean_invalid_index(self):
        proj = self._make_doc_with_shapes()
        with pytest.raises(IndexError):
            path_union(proj, 0, 5)

    def test_convert_rect_to_path(self):
        proj = create_document()
        add_rect(proj, x=10, y=10, width=100, height=50)
        result = convert_to_path(proj, 0)
        assert result["type"] == "path"
        assert "M" in result["d"]
        assert result["original_type"] == "rect"

    def test_convert_circle_to_path(self):
        proj = create_document()
        add_circle(proj, cx=50, cy=50, r=25)
        result = convert_to_path(proj, 0)
        assert result["type"] == "path"
        assert "A" in result["d"]

    def test_convert_ellipse_to_path(self):
        proj = create_document()
        add_ellipse(proj)
        result = convert_to_path(proj, 0)
        assert result["type"] == "path"

    def test_convert_path_is_noop(self):
        proj = create_document()
        add_path(proj, d="M 0,0 L 100,100")
        result = convert_to_path(proj, 0)
        assert result["d"] == "M 0,0 L 100,100"

    def test_list_path_operations(self):
        ops = list_path_operations()
        assert len(ops) >= 4
        names = [o["name"] for o in ops]
        assert "union" in names
        assert "difference" in names

    def test_convert_line_to_path(self):
        proj = create_document()
        add_line(proj, x1=0, y1=0, x2=100, y2=100)
        result = convert_to_path(proj, 0)
        assert result["type"] == "path"
        assert "M" in result["d"]

    def test_convert_polygon_to_path(self):
        proj = create_document()
        add_polygon(proj, points="50,0 100,100 0,100")
        result = convert_to_path(proj, 0)
        assert result["type"] == "path"
        assert "Z" in result["d"]


# ── Gradient Tests ──────────────────────────────────────────────

class TestGradients:
    def _make_doc(self):
        return create_document()

    def test_add_linear_gradient(self):
        proj = self._make_doc()
        grad = add_linear_gradient(proj)
        assert grad["type"] == "linear"
        assert len(grad["stops"]) == 2
        assert len(proj["gradients"]) == 1

    def test_add_linear_gradient_custom_stops(self):
        proj = self._make_doc()
        stops = [
            {"offset": 0, "color": "#ff0000"},
            {"offset": 0.5, "color": "#00ff00"},
            {"offset": 1, "color": "#0000ff"},
        ]
        grad = add_linear_gradient(proj, stops=stops)
        assert len(grad["stops"]) == 3

    def test_add_radial_gradient(self):
        proj = self._make_doc()
        grad = add_radial_gradient(proj, cx=0.5, cy=0.5, r=0.5)
        assert grad["type"] == "radial"
        assert grad["cx"] == 0.5

    def test_gradient_invalid_stops(self):
        proj = self._make_doc()
        with pytest.raises(ValueError, match="at least 2"):
            add_linear_gradient(proj, stops=[{"offset": 0, "color": "#000"}])

    def test_gradient_missing_offset(self):
        proj = self._make_doc()
        with pytest.raises(ValueError, match="missing 'offset'"):
            add_linear_gradient(proj, stops=[
                {"color": "#000"},
                {"offset": 1, "color": "#fff"},
            ])

    def test_gradient_invalid_offset(self):
        proj = self._make_doc()
        with pytest.raises(ValueError, match="0-1"):
            add_linear_gradient(proj, stops=[
                {"offset": -0.5, "color": "#000"},
                {"offset": 1, "color": "#fff"},
            ])

    def test_apply_gradient_fill(self):
        proj = self._make_doc()
        add_rect(proj, name="Shape")
        add_linear_gradient(proj, name="MyGrad")
        result = apply_gradient(proj, 0, 0, "fill")
        style = parse_style(proj["objects"][0]["style"])
        assert "url(#" in style["fill"]

    def test_apply_gradient_stroke(self):
        proj = self._make_doc()
        add_rect(proj, name="Shape")
        add_linear_gradient(proj, name="MyGrad")
        result = apply_gradient(proj, 0, 0, "stroke")
        style = parse_style(proj["objects"][0]["style"])
        assert "url(#" in style["stroke"]

    def test_apply_gradient_invalid_target(self):
        proj = self._make_doc()
        add_rect(proj)
        add_linear_gradient(proj)
        with pytest.raises(ValueError, match="fill.*stroke"):
            apply_gradient(proj, 0, 0, "background")

    def test_list_gradients(self):
        proj = self._make_doc()
        add_linear_gradient(proj, name="A")
        add_radial_gradient(proj, name="B")
        result = list_gradients(proj)
        assert len(result) == 2

    def test_get_gradient(self):
        proj = self._make_doc()
        add_linear_gradient(proj, name="Test")
        grad = get_gradient(proj, 0)
        assert grad["name"] == "Test"

    def test_remove_gradient(self):
        proj = self._make_doc()
        add_linear_gradient(proj, name="ToRemove")
        removed = remove_gradient(proj, 0)
        assert removed["name"] == "ToRemove"
        assert len(proj["gradients"]) == 0

    def test_invalid_gradient_units(self):
        proj = self._make_doc()
        with pytest.raises(ValueError, match="Invalid gradientUnits"):
            add_linear_gradient(proj, gradient_units="invalidUnits")


# ── Export Tests ────────────────────────────────────────────────

class TestExport:
    def test_list_presets(self):
        presets = list_presets()
        assert len(presets) > 0
        names = [p["name"] for p in presets]
        assert "png_web" in names
        assert "svg" in names
        assert "pdf" in names

    def test_all_presets_have_format(self):
        for name, preset in EXPORT_PRESETS.items():
            assert "format" in preset
            assert "dpi" in preset
            assert "description" in preset


# ── Session Tests ───────────────────────────────────────────────

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
        assert sess.get_project()["name"] == "v1"

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

    def test_undo_shape_add(self):
        sess = Session()
        proj = create_document()
        sess.set_project(proj)

        sess.snapshot("add rect")
        add_rect(proj, name="Rect")
        assert len(proj["objects"]) == 1

        sess.undo()
        assert len(sess.get_project()["objects"]) == 0
