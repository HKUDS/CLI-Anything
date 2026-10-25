"""Text edits must preserve styling supplied by the style/gradient commands."""

import xml.etree.ElementTree as ET

import pytest

from cli_anything.inkscape.core.document import create_document, save_svg
from cli_anything.inkscape.core.gradients import add_linear_gradient, apply_gradient
from cli_anything.inkscape.core.styles import set_stroke, set_opacity, set_style
from cli_anything.inkscape.core.text import add_text, set_text_property
from cli_anything.inkscape.utils.svg_utils import parse_style


@pytest.mark.parametrize("prop,value,css_value", [
    ("text", "Updated label", None),
    ("x", 80, None),
    ("font-size", 32, "32.0px"),
    ("fill", "#ff0000", "#ff0000"),
    ("opacity", 0.75, "0.75"),
])
def test_text_edit_preserves_unrelated_styles_in_svg(tmp_path, prop, value, css_value):
    project = create_document()
    obj = add_text(project, text="Label")
    add_linear_gradient(project)
    apply_gradient(project, 0, 0)
    set_stroke(project, 0, "#0000ff", width=3)
    set_opacity(project, 0, 0.5)
    set_style(project, 0, "stroke-dasharray", "4,2")
    expected = parse_style(obj["style"])
    if css_value is not None:
        expected[prop] = css_value

    set_text_property(project, 0, prop, value)
    output = str(tmp_path / "edited.svg")
    save_svg(project, output)
    text = ET.parse(output).getroot().find(".//{http://www.w3.org/2000/svg}text")
    assert text is not None
    assert parse_style(text.attrib["style"]) == expected
    if prop == "text":
        assert text.text == value
    if prop == "x":
        assert float(text.attrib["x"]) == value
