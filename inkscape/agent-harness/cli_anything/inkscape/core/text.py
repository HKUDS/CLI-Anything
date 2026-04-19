"""Inkscape CLI - Text management module.

Handles adding text elements and modifying text properties.
"""

from typing import Dict, Any, List, Optional

from cli_anything.inkscape.utils.svg_utils import generate_id, parse_style, serialize_style


# Font properties that can be set
TEXT_PROPERTIES = {
    "text": {"type": "str", "description": "The text content"},
    "font-family": {"type": "str", "description": "Font family name"},
    "font-size": {"type": "float", "description": "Font size"},
    "font-weight": {"type": "str", "description": "Font weight (normal, bold, 100-900)"},
    "font-style": {"type": "str", "description": "Font style (normal, italic, oblique)"},
    "text-anchor": {"type": "str", "description": "Text alignment (start, middle, end)"},
    "text-decoration": {"type": "str", "description": "Decoration (none, underline, overline, line-through)"},
    "letter-spacing": {"type": "float", "description": "Letter spacing"},
    "word-spacing": {"type": "float", "description": "Word spacing"},
    "line-height": {"type": "float", "description": "Line height multiplier"},
    "box-width": {"type": "float", "description": "Optional text box width for wrapping"},
    "box-height": {"type": "float", "description": "Optional text box height for wrapping"},
    "fill": {"type": "str", "description": "Text fill color"},
    "stroke": {"type": "str", "description": "Text stroke color"},
    "opacity": {"type": "float", "description": "Text opacity (0.0-1.0)"},
    "x": {"type": "float", "description": "X position"},
    "y": {"type": "float", "description": "Y position"},
}

VALID_FONT_WEIGHTS = {"normal", "bold", "bolder", "lighter",
                       "100", "200", "300", "400", "500", "600", "700", "800", "900"}
VALID_FONT_STYLES = {"normal", "italic", "oblique"}
VALID_TEXT_ANCHORS = {"start", "middle", "end"}
VALID_TEXT_DECORATIONS = {"none", "underline", "overline", "line-through"}


def add_text(
    project: Dict[str, Any],
    text: str = "Text",
    x: float = 0,
    y: float = 50,
    font_family: str = "sans-serif",
    font_size: float = 24,
    font_weight: str = "normal",
    font_style: str = "normal",
    fill: str = "#000000",
    text_anchor: str = "start",
    box_width: Optional[float] = None,
    box_height: Optional[float] = None,
    line_height: float = 1.2,
    name: Optional[str] = None,
    layer: Optional[str] = None,
) -> Dict[str, Any]:
    """Add a text element to the document."""
    if not text:
        raise ValueError("Text content cannot be empty")
    if font_size <= 0:
        raise ValueError(f"Font size must be positive: {font_size}")
    if box_width is not None and box_width <= 0:
        raise ValueError(f"Text box width must be positive: {box_width}")
    if box_height is not None and box_height <= 0:
        raise ValueError(f"Text box height must be positive: {box_height}")
    if line_height <= 0:
        raise ValueError(f"Line height must be positive: {line_height}")

    # Build style string
    style_parts = {
        "font-family": font_family,
        "font-size": f"{font_size}px",
        "font-weight": font_weight,
        "font-style": font_style,
        "fill": fill,
        "text-anchor": text_anchor,
    }
    style = serialize_style(style_parts)

    obj_id = generate_id("text")
    obj = {
        "id": obj_id,
        "name": name or obj_id,
        "type": "text",
        "text": text,
        "x": x,
        "y": y,
        "font_family": font_family,
        "font_size": font_size,
        "font_weight": font_weight,
        "font_style": font_style,
        "fill": fill,
        "text_anchor": text_anchor,
        "line_height": line_height,
        "style": style,
        "transform": "",
        "layer": _default_layer_id(project),
    }
    if box_width is not None:
        obj["box_width"] = box_width
    if box_height is not None:
        obj["box_height"] = box_height
    if layer:
        obj["layer"] = layer

    _add_object(project, obj)
    return obj


def set_text_property(
    project: Dict[str, Any],
    index: int,
    prop: str,
    value: Any,
) -> Dict[str, Any]:
    """Set a property on a text object.

    Args:
        index: Object index in the objects list.
        prop: Property name (from TEXT_PROPERTIES).
        value: New value.

    Returns:
        Updated object dict.
    """
    objects = project.get("objects", [])
    if index < 0 or index >= len(objects):
        raise IndexError(f"Object index {index} out of range (0-{len(objects)-1})")

    obj = objects[index]
    if obj.get("type") != "text":
        raise ValueError(f"Object at index {index} is not a text element (type={obj.get('type')})")

    if prop not in TEXT_PROPERTIES:
        raise ValueError(f"Unknown text property: {prop}. Valid: {', '.join(TEXT_PROPERTIES.keys())}")

    # Validate specific properties
    if prop == "font-weight" and str(value) not in VALID_FONT_WEIGHTS:
        raise ValueError(f"Invalid font-weight: {value}. Valid: {', '.join(VALID_FONT_WEIGHTS)}")
    if prop == "font-style" and str(value) not in VALID_FONT_STYLES:
        raise ValueError(f"Invalid font-style: {value}. Valid: {', '.join(VALID_FONT_STYLES)}")
    if prop == "text-anchor" and str(value) not in VALID_TEXT_ANCHORS:
        raise ValueError(f"Invalid text-anchor: {value}. Valid: {', '.join(VALID_TEXT_ANCHORS)}")
    if prop == "text-decoration" and str(value) not in VALID_TEXT_DECORATIONS:
        raise ValueError(f"Invalid text-decoration: {value}. Valid: {', '.join(VALID_TEXT_DECORATIONS)}")
    if prop == "font-size":
        value = float(value)
        if value <= 0:
            raise ValueError(f"Font size must be positive: {value}")
    if prop in {"box-width", "box-height"}:
        value = float(value)
        if value <= 0:
            raise ValueError(f"{prop} must be positive: {value}")
    if prop == "line-height":
        value = float(value)
        if value <= 0:
            raise ValueError(f"Line height must be positive: {value}")
    if prop == "opacity":
        value = float(value)
        if value < 0 or value > 1:
            raise ValueError(f"Opacity must be 0.0-1.0: {value}")

    # Apply the property
    # Map CSS property names to internal field names
    field_map = {
        "font-family": "font_family",
        "font-size": "font_size",
        "font-weight": "font_weight",
        "font-style": "font_style",
        "text-anchor": "text_anchor",
        "text-decoration": "text_decoration",
        "letter-spacing": "letter_spacing",
        "word-spacing": "word_spacing",
        "line-height": "line_height",
        "box-width": "box_width",
        "box-height": "box_height",
    }

    internal_name = field_map.get(prop, prop)
    obj[internal_name] = value

    # Rebuild style string
    _rebuild_text_style(obj)

    return obj


def list_text_objects(project: Dict[str, Any]) -> List[Dict[str, Any]]:
    """List all text objects in the document."""
    result = []
    for i, obj in enumerate(project.get("objects", [])):
        if obj.get("type") == "text":
            result.append({
                "index": i,
                "id": obj.get("id", ""),
                "name": obj.get("name", ""),
                "text": obj.get("text", ""),
                "font_family": obj.get("font_family", "sans-serif"),
                "font_size": obj.get("font_size", 24),
                "fill": obj.get("fill", "#000000"),
                "x": obj.get("x", 0),
                "y": obj.get("y", 0),
                "box_width": obj.get("box_width"),
                "box_height": obj.get("box_height"),
            })
    return result


def layout_text_lines(obj: Dict[str, Any]) -> List[str]:
    """Lay out wrapped text lines for a text object."""
    text = str(obj.get("text", ""))
    if not text:
        return [""]

    box_width = obj.get("box_width")
    line_height = float(obj.get("line_height", 1.2) or 1.2)
    font_size = float(obj.get("font_size", 24) or 24)

    if not box_width:
        return text.splitlines() or [text]

    avg_char_width = max(1.0, font_size * 0.58)
    max_chars = max(1, int(float(box_width) / avg_char_width))

    lines: List[str] = []
    for paragraph in text.splitlines() or [text]:
        wrapped = _wrap_paragraph(paragraph, max_chars)
        lines.extend(wrapped or [""])

    box_height = obj.get("box_height")
    if box_height:
        max_lines = max(1, int(float(box_height) / max(1.0, font_size * line_height)))
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            lines[-1] = _truncate_with_ellipsis(lines[-1], max_chars)

    return lines


# ── Internal Helpers ────────────────────────────────────────────

def _rebuild_text_style(obj: Dict[str, Any]) -> None:
    """Rebuild the style string from object properties."""
    style_parts = {}
    if "font_family" in obj:
        style_parts["font-family"] = obj["font_family"]
    if "font_size" in obj:
        style_parts["font-size"] = f"{obj['font_size']}px"
    if "font_weight" in obj:
        style_parts["font-weight"] = obj["font_weight"]
    if "font_style" in obj:
        style_parts["font-style"] = obj["font_style"]
    if "fill" in obj:
        style_parts["fill"] = obj["fill"]
    if "text_anchor" in obj:
        style_parts["text-anchor"] = obj["text_anchor"]
    if "opacity" in obj:
        style_parts["opacity"] = str(obj["opacity"])
    if "text_decoration" in obj:
        style_parts["text-decoration"] = obj["text_decoration"]
    if "letter_spacing" in obj:
        style_parts["letter-spacing"] = f"{obj['letter_spacing']}px"
    if "word_spacing" in obj:
        style_parts["word-spacing"] = f"{obj['word_spacing']}px"
    if "line_height" in obj:
        style_parts["line-height"] = str(obj["line_height"])
    if "stroke" in obj:
        style_parts["stroke"] = obj["stroke"]

    obj["style"] = serialize_style(style_parts)


def text_anchor_x(obj: Dict[str, Any]) -> float:
    """Compute the anchor x-position, taking text boxes into account."""
    x = float(obj.get("x", 0))
    box_width = obj.get("box_width")
    anchor = obj.get("text_anchor", "start")
    if not box_width:
        return x
    if anchor == "middle":
        return x + float(box_width) / 2.0
    if anchor == "end":
        return x + float(box_width)
    return x


def _default_layer_id(project: Dict[str, Any]) -> str:
    """Get the ID of the first layer."""
    layers = project.get("layers", [])
    if layers:
        return layers[0].get("id", "layer1")
    return ""


def _add_object(project: Dict[str, Any], obj: Dict[str, Any]) -> None:
    """Add an object to the project's objects list and its layer."""
    project.setdefault("objects", []).append(obj)

    layer_id = obj.get("layer", "")
    if layer_id:
        for layer in project.get("layers", []):
            if layer.get("id") == layer_id:
                layer.setdefault("objects", []).append(obj["id"])
                break


def _wrap_paragraph(paragraph: str, max_chars: int) -> List[str]:
    """Wrap a paragraph to an approximate character count."""
    words = paragraph.split()
    if not words:
        return [""]

    lines: List[str] = []
    current = ""
    for word in words:
        if len(word) > max_chars:
            if current:
                lines.append(current)
                current = ""
            while len(word) > max_chars:
                lines.append(word[:max_chars])
                word = word[max_chars:]
            current = word
            continue

        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            lines.append(current)
            current = word

    if current:
        lines.append(current)
    return lines


def _truncate_with_ellipsis(text: str, max_chars: int) -> str:
    """Trim text to fit and add an ellipsis when needed."""
    if len(text) <= max_chars:
        return text
    if max_chars <= 1:
        return text[:max_chars]
    return text[: max_chars - 1].rstrip() + "…"
