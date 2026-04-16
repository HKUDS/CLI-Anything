"""Inkscape CLI - Shape operations module.

Handles adding, removing, duplicating, and listing SVG shape objects.
All operations modify the project JSON; SVG is generated from it.
"""

import copy
import math
from typing import Dict, Any, List, Optional

from cli_anything.inkscape.utils.svg_utils import generate_id, serialize_style

# ── Shape Registry ──────────────────────────────────────────────

SHAPE_TYPES = {
    "rect": {
        "description": "Rectangle",
        "required_attrs": [],
        "default_attrs": {
            "x": 0, "y": 0, "width": 100, "height": 100,
            "rx": 0, "ry": 0,
        },
    },
    "circle": {
        "description": "Circle",
        "required_attrs": [],
        "default_attrs": {"cx": 50, "cy": 50, "r": 50},
    },
    "ellipse": {
        "description": "Ellipse",
        "required_attrs": [],
        "default_attrs": {"cx": 50, "cy": 50, "rx": 75, "ry": 50},
    },
    "line": {
        "description": "Line",
        "required_attrs": [],
        "default_attrs": {"x1": 0, "y1": 0, "x2": 100, "y2": 100},
    },
    "polygon": {
        "description": "Polygon (closed polyline)",
        "required_attrs": [],
        "default_attrs": {"points": "50,0 100,100 0,100"},
    },
    "polyline": {
        "description": "Polyline (open line segments)",
        "required_attrs": [],
        "default_attrs": {"points": "0,0 50,50 100,0"},
    },
    "path": {
        "description": "SVG Path (bezier curves, arcs, etc.)",
        "required_attrs": [],
        "default_attrs": {"d": "M 0,0 L 100,0 L 100,100 Z"},
    },
    "text": {
        "description": "Text element",
        "required_attrs": [],
        "default_attrs": {"x": 0, "y": 50, "text": "Text"},
    },
    "star": {
        "description": "Star / regular polygon",
        "required_attrs": [],
        "default_attrs": {
            "cx": 50, "cy": 50,
            "points_count": 5,
            "outer_r": 50, "inner_r": 25,
        },
    },
    "image": {
        "description": "Embedded/linked image",
        "required_attrs": [],
        "default_attrs": {
            "x": 0, "y": 0, "width": 100, "height": 100,
            "href": "",
        },
    },
}

DEFAULT_STYLE = "fill:#0000ff;stroke:#000000;stroke-width:1"


def add_rect(
    project: Dict[str, Any],
    x: float = 0, y: float = 0,
    width: float = 100, height: float = 100,
    rx: float = 0, ry: float = 0,
    name: Optional[str] = None,
    style: Optional[str] = None,
    layer: Optional[str] = None,
) -> Dict[str, Any]:
    """Add a rectangle to the document."""
    if width <= 0 or height <= 0:
        raise ValueError(f"Rectangle dimensions must be positive: {width}x{height}")

    obj_id = generate_id("rect")
    obj = {
        "id": obj_id,
        "name": name or obj_id,
        "type": "rect",
        "x": x, "y": y,
        "width": width, "height": height,
        "rx": rx, "ry": ry,
        "style": style or DEFAULT_STYLE,
        "transform": "",
        "layer": layer or _default_layer_id(project),
    }
    _add_object(project, obj)
    return obj


def add_circle(
    project: Dict[str, Any],
    cx: float = 50, cy: float = 50, r: float = 50,
    name: Optional[str] = None,
    style: Optional[str] = None,
    layer: Optional[str] = None,
) -> Dict[str, Any]:
    """Add a circle to the document."""
    if r <= 0:
        raise ValueError(f"Circle radius must be positive: {r}")

    obj_id = generate_id("circle")
    obj = {
        "id": obj_id,
        "name": name or obj_id,
        "type": "circle",
        "cx": cx, "cy": cy, "r": r,
        "style": style or DEFAULT_STYLE,
        "transform": "",
        "layer": layer or _default_layer_id(project),
    }
    _add_object(project, obj)
    return obj


def add_ellipse(
    project: Dict[str, Any],
    cx: float = 50, cy: float = 50,
    rx: float = 75, ry: float = 50,
    name: Optional[str] = None,
    style: Optional[str] = None,
    layer: Optional[str] = None,
) -> Dict[str, Any]:
    """Add an ellipse to the document."""
    if rx <= 0 or ry <= 0:
        raise ValueError(f"Ellipse radii must be positive: rx={rx}, ry={ry}")

    obj_id = generate_id("ellipse")
    obj = {
        "id": obj_id,
        "name": name or obj_id,
        "type": "ellipse",
        "cx": cx, "cy": cy, "rx": rx, "ry": ry,
        "style": style or DEFAULT_STYLE,
        "transform": "",
        "layer": layer or _default_layer_id(project),
    }
    _add_object(project, obj)
    return obj


def add_line(
    project: Dict[str, Any],
    x1: float = 0, y1: float = 0,
    x2: float = 100, y2: float = 100,
    name: Optional[str] = None,
    style: Optional[str] = None,
    layer: Optional[str] = None,
) -> Dict[str, Any]:
    """Add a line to the document."""
    obj_id = generate_id("line")
    line_style = style or "fill:none;stroke:#000000;stroke-width:2"
    obj = {
        "id": obj_id,
        "name": name or obj_id,
        "type": "line",
        "x1": x1, "y1": y1, "x2": x2, "y2": y2,
        "style": line_style,
        "transform": "",
        "layer": layer or _default_layer_id(project),
    }
    _add_object(project, obj)
    return obj


def add_polygon(
    project: Dict[str, Any],
    points: str = "50,0 100,100 0,100",
    name: Optional[str] = None,
    style: Optional[str] = None,
    layer: Optional[str] = None,
) -> Dict[str, Any]:
    """Add a polygon to the document.

    Args:
        points: SVG points string, e.g. "50,0 100,100 0,100"
    """
    if not points or not points.strip():
        raise ValueError("Polygon must have at least one point")

    obj_id = generate_id("polygon")
    obj = {
        "id": obj_id,
        "name": name or obj_id,
        "type": "polygon",
        "points": points,
        "style": style or DEFAULT_STYLE,
        "transform": "",
        "layer": layer or _default_layer_id(project),
    }
    _add_object(project, obj)
    return obj


def add_path(
    project: Dict[str, Any],
    d: str = "M 0,0 L 100,0 L 100,100 Z",
    name: Optional[str] = None,
    style: Optional[str] = None,
    layer: Optional[str] = None,
) -> Dict[str, Any]:
    """Add a path to the document.

    Args:
        d: SVG path data string.
    """
    if not d or not d.strip():
        raise ValueError("Path data (d) cannot be empty")

    obj_id = generate_id("path")
    obj = {
        "id": obj_id,
        "name": name or obj_id,
        "type": "path",
        "d": d,
        "style": style or DEFAULT_STYLE,
        "transform": "",
        "layer": layer or _default_layer_id(project),
    }
    _add_object(project, obj)
    return obj


def add_star(
    project: Dict[str, Any],
    cx: float = 50, cy: float = 50,
    points_count: int = 5,
    outer_r: float = 50, inner_r: float = 25,
    name: Optional[str] = None,
    style: Optional[str] = None,
    layer: Optional[str] = None,
) -> Dict[str, Any]:
    """Add a star (regular polygon) to the document."""
    if points_count < 3:
        raise ValueError(f"Star must have at least 3 points: {points_count}")
    if outer_r <= 0 or inner_r <= 0:
        raise ValueError(f"Star radii must be positive: outer={outer_r}, inner={inner_r}")

    # Generate star path data
    d = _star_path(cx, cy, points_count, outer_r, inner_r)

    obj_id = generate_id("star")
    obj = {
        "id": obj_id,
        "name": name or obj_id,
        "type": "star",
        "cx": cx, "cy": cy,
        "points_count": points_count,
        "outer_r": outer_r,
        "inner_r": inner_r,
        "d": d,
        "style": style or DEFAULT_STYLE,
        "transform": "",
        "layer": layer or _default_layer_id(project),
    }
    _add_object(project, obj)
    return obj


def remove_object(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Remove an object by index."""
    objects = project.get("objects", [])
    if not objects:
        raise ValueError("No objects in document")
    if index < 0 or index >= len(objects):
        raise IndexError(f"Object index {index} out of range (0-{len(objects)-1})")

    removed = objects.pop(index)

    # Remove from layer
    obj_id = removed.get("id", "")
    for layer in project.get("layers", []):
        if obj_id in layer.get("objects", []):
            layer["objects"].remove(obj_id)

    return removed


def duplicate_object(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Duplicate an object by index."""
    objects = project.get("objects", [])
    if index < 0 or index >= len(objects):
        raise IndexError(f"Object index {index} out of range (0-{len(objects)-1})")

    original = objects[index]
    dup = copy.deepcopy(original)
    new_id = generate_id(dup.get("type", "obj"))
    dup["id"] = new_id
    dup["name"] = f"{original.get('name', 'object')}_copy"

    objects.append(dup)

    # Add to same layer
    layer_id = dup.get("layer", "")
    for layer in project.get("layers", []):
        if layer.get("id") == layer_id:
            layer["objects"].append(new_id)
            break

    return dup


def list_objects(project: Dict[str, Any]) -> List[Dict[str, Any]]:
    """List all objects in the document."""
    result = []
    for i, obj in enumerate(project.get("objects", [])):
        result.append({
            "index": i,
            "id": obj.get("id", ""),
            "name": obj.get("name", ""),
            "type": obj.get("type", "unknown"),
            "layer": obj.get("layer", ""),
        })
    return result


def get_object(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Get detailed info about an object by index."""
    objects = project.get("objects", [])
    if index < 0 or index >= len(objects):
        raise IndexError(f"Object index {index} out of range (0-{len(objects)-1})")
    return copy.deepcopy(objects[index])


# ── Internal Helpers ────────────────────────────────────────────

def _default_layer_id(project: Dict[str, Any]) -> str:
    """Get the ID of the first layer, or empty string."""
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


def _star_path(cx: float, cy: float, n: int, outer_r: float, inner_r: float) -> str:
    """Generate SVG path data for a star with n points."""
    points = []
    for i in range(2 * n):
        angle = math.pi * i / n - math.pi / 2
        r = outer_r if i % 2 == 0 else inner_r
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        points.append(f"{x:.2f},{y:.2f}")

    return "M " + " L ".join(points) + " Z"
