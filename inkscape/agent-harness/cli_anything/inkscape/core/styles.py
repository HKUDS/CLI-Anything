"""Inkscape CLI - Style management module.

Handles setting fill, stroke, opacity, and other CSS style properties
on SVG objects.
"""

from typing import Dict, Any, List, Optional

from cli_anything.inkscape.utils.svg_utils import parse_style, serialize_style, validate_color


# Style properties that can be set
STYLE_PROPERTIES = {
    "fill": {"type": "color", "description": "Fill color (hex, named, rgb, none)"},
    "stroke": {"type": "color", "description": "Stroke color (hex, named, rgb, none)"},
    "stroke-width": {"type": "float", "description": "Stroke width in user units"},
    "stroke-linecap": {"type": "choice", "choices": ["butt", "round", "square"],
                        "description": "Stroke line cap style"},
    "stroke-linejoin": {"type": "choice", "choices": ["miter", "round", "bevel"],
                         "description": "Stroke line join style"},
    "stroke-dasharray": {"type": "str", "description": "Dash pattern (e.g. '5,3')"},
    "stroke-dashoffset": {"type": "float", "description": "Dash pattern offset"},
    "stroke-miterlimit": {"type": "float", "description": "Miter limit for stroke joins"},
    "stroke-opacity": {"type": "float", "description": "Stroke opacity (0.0-1.0)"},
    "fill-opacity": {"type": "float", "description": "Fill opacity (0.0-1.0)"},
    "opacity": {"type": "float", "description": "Overall opacity (0.0-1.0)"},
    "fill-rule": {"type": "choice", "choices": ["nonzero", "evenodd"],
                   "description": "Fill rule for complex paths"},
    "display": {"type": "choice", "choices": ["inline", "none"],
                 "description": "Display visibility"},
    "visibility": {"type": "choice", "choices": ["visible", "hidden", "collapse"],
                    "description": "Visibility"},
    "mix-blend-mode": {"type": "choice",
                        "choices": ["normal", "multiply", "screen", "overlay",
                                    "darken", "lighten", "color-dodge", "color-burn",
                                    "hard-light", "soft-light", "difference",
                                    "exclusion", "hue", "saturation", "color", "luminosity"],
                        "description": "Blend mode"},
    "filter": {"type": "str", "description": "CSS filter (e.g. 'blur(5px)')"},
}


def set_fill(project: Dict[str, Any], index: int, color: str) -> Dict[str, Any]:
    """Set the fill color of an object."""
    return _set_style_prop(project, index, "fill", color)


def set_stroke(project: Dict[str, Any], index: int, color: str,
               width: Optional[float] = None) -> Dict[str, Any]:
    """Set the stroke color (and optionally width) of an object."""
    obj = _set_style_prop(project, index, "stroke", color)
    if width is not None:
        if width < 0:
            raise ValueError(f"Stroke width must be non-negative: {width}")
        _set_style_prop(project, index, "stroke-width", str(width))
    return obj


def set_opacity(project: Dict[str, Any], index: int, opacity: float) -> Dict[str, Any]:
    """Set the overall opacity of an object."""
    if opacity < 0 or opacity > 1:
        raise ValueError(f"Opacity must be 0.0-1.0: {opacity}")
    return _set_style_prop(project, index, "opacity", str(opacity))


def set_style(project: Dict[str, Any], index: int, prop: str, value: str) -> Dict[str, Any]:
    """Set an arbitrary style property on an object."""
    if prop not in STYLE_PROPERTIES:
        raise ValueError(f"Unknown style property: {prop}. Valid: {', '.join(sorted(STYLE_PROPERTIES.keys()))}")

    spec = STYLE_PROPERTIES[prop]

    # Validate based on type
    if spec["type"] == "color":
        if not validate_color(value):
            raise ValueError(f"Invalid color value: {value}")
    elif spec["type"] == "float":
        try:
            fval = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid float value for {prop}: {value}")
        if prop in ("opacity", "fill-opacity", "stroke-opacity"):
            if fval < 0 or fval > 1:
                raise ValueError(f"{prop} must be 0.0-1.0: {value}")
        if prop in ("stroke-width", "stroke-dashoffset", "stroke-miterlimit"):
            if fval < 0:
                raise ValueError(f"{prop} must be non-negative: {value}")
    elif spec["type"] == "choice":
        if value not in spec["choices"]:
            raise ValueError(f"Invalid value for {prop}: {value}. Valid: {', '.join(spec['choices'])}")

    return _set_style_prop(project, index, prop, value)


def list_style_properties() -> List[Dict[str, str]]:
    """List all available style properties."""
    result = []
    for name, spec in sorted(STYLE_PROPERTIES.items()):
        entry = {
            "name": name,
            "type": spec["type"],
            "description": spec["description"],
        }
        if "choices" in spec:
            entry["choices"] = spec["choices"]
        result.append(entry)
    return result


def get_object_style(project: Dict[str, Any], index: int) -> Dict[str, str]:
    """Get the parsed style dict of an object."""
    objects = project.get("objects", [])
    if index < 0 or index >= len(objects):
        raise IndexError(f"Object index {index} out of range (0-{len(objects)-1})")
    return parse_style(objects[index].get("style", ""))


# ── Internal ────────────────────────────────────────────────────

def _set_style_prop(project: Dict[str, Any], index: int,
                    prop: str, value: str) -> Dict[str, Any]:
    """Set a single CSS style property on an object."""
    objects = project.get("objects", [])
    if index < 0 or index >= len(objects):
        raise IndexError(f"Object index {index} out of range (0-{len(objects)-1})")

    obj = objects[index]
    style = parse_style(obj.get("style", ""))
    style[prop] = value
    obj["style"] = serialize_style(style)
    return obj
