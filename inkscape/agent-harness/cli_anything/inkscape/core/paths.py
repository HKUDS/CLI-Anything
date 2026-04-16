"""Inkscape CLI - Path boolean operations module.

Handles union, intersection, difference, exclusion, and path conversion.
These operations modify the JSON model. Actual SVG path computation for
complex shapes would require Inkscape CLI or a path library. For simple
cases, we represent the operation as metadata and generate the appropriate
Inkscape actions for rendering.
"""

from typing import Dict, Any, List, Optional
import copy

from cli_anything.inkscape.utils.svg_utils import generate_id

# Path operations that Inkscape supports
PATH_OPERATIONS = {
    "union": {
        "description": "Union (combine) two shapes",
        "inkscape_verb": "SelectionUnion",
        "inkscape_action": "path-union",
    },
    "intersection": {
        "description": "Intersection of two shapes",
        "inkscape_verb": "SelectionIntersect",
        "inkscape_action": "path-intersection",
    },
    "difference": {
        "description": "Difference (subtract bottom from top)",
        "inkscape_verb": "SelectionDiff",
        "inkscape_action": "path-difference",
    },
    "exclusion": {
        "description": "Exclusion (XOR of two shapes)",
        "inkscape_verb": "SelectionSymDiff",
        "inkscape_action": "path-exclusion",
    },
    "division": {
        "description": "Division (cut bottom with top)",
        "inkscape_verb": "SelectionCutPath",
        "inkscape_action": "path-division",
    },
    "cut_path": {
        "description": "Cut path (split path at intersections)",
        "inkscape_verb": "SelectionCutPath",
        "inkscape_action": "path-cut",
    },
}

# Simple shapes that can be converted to path
CONVERTIBLE_TYPES = {"rect", "circle", "ellipse", "line", "polygon",
                      "polyline", "star", "text"}


def path_union(
    project: Dict[str, Any],
    index_a: int,
    index_b: int,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a union of two objects (stores as path operation record)."""
    return _path_boolean(project, index_a, index_b, "union", name)


def path_intersection(
    project: Dict[str, Any],
    index_a: int,
    index_b: int,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Create an intersection of two objects."""
    return _path_boolean(project, index_a, index_b, "intersection", name)


def path_difference(
    project: Dict[str, Any],
    index_a: int,
    index_b: int,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a difference of two objects (A minus B)."""
    return _path_boolean(project, index_a, index_b, "difference", name)


def path_exclusion(
    project: Dict[str, Any],
    index_a: int,
    index_b: int,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Create an exclusion (XOR) of two objects."""
    return _path_boolean(project, index_a, index_b, "exclusion", name)


def convert_to_path(
    project: Dict[str, Any],
    index: int,
) -> Dict[str, Any]:
    """Convert a shape to a path element.

    For basic shapes (rect, circle, ellipse), we can compute the
    equivalent SVG path data. For complex shapes, we record the
    conversion as a pending operation for Inkscape.
    """
    objects = project.get("objects", [])
    if index < 0 or index >= len(objects):
        raise IndexError(f"Object index {index} out of range (0-{len(objects)-1})")

    obj = objects[index]
    obj_type = obj.get("type", "")

    if obj_type == "path":
        return obj  # Already a path

    if obj_type not in CONVERTIBLE_TYPES:
        raise ValueError(f"Cannot convert type '{obj_type}' to path. "
                         f"Convertible types: {', '.join(sorted(CONVERTIBLE_TYPES))}")

    # Convert basic shapes to path data
    d = _shape_to_path_data(obj)

    if d is not None:
        obj["type"] = "path"
        obj["d"] = d
        obj["original_type"] = obj_type
    else:
        # For complex conversions, mark as pending
        obj["type"] = "path"
        obj["d"] = obj.get("d", "M 0,0")
        obj["original_type"] = obj_type
        obj["conversion_pending"] = True

    return obj


def list_path_operations() -> List[Dict[str, str]]:
    """List available path boolean operations."""
    return [
        {"name": name, "description": spec["description"],
         "inkscape_action": spec["inkscape_action"]}
        for name, spec in PATH_OPERATIONS.items()
    ]


# ── Internal ────────────────────────────────────────────────────

def _path_boolean(
    project: Dict[str, Any],
    index_a: int,
    index_b: int,
    operation: str,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Perform a boolean path operation between two objects."""
    objects = project.get("objects", [])
    if index_a < 0 or index_a >= len(objects):
        raise IndexError(f"Object A index {index_a} out of range (0-{len(objects)-1})")
    if index_b < 0 or index_b >= len(objects):
        raise IndexError(f"Object B index {index_b} out of range (0-{len(objects)-1})")
    if index_a == index_b:
        raise ValueError("Cannot perform boolean operation on the same object")

    obj_a = objects[index_a]
    obj_b = objects[index_b]

    # Create a new path object representing the boolean result
    obj_id = generate_id("path")
    result_obj = {
        "id": obj_id,
        "name": name or f"{operation}_{obj_a.get('name', '')}_{obj_b.get('name', '')}",
        "type": "path",
        "d": obj_a.get("d", "M 0,0"),  # Placeholder
        "style": obj_a.get("style", ""),
        "transform": "",
        "layer": obj_a.get("layer", ""),
        "boolean_operation": {
            "type": operation,
            "source_a": obj_a.get("id", ""),
            "source_b": obj_b.get("id", ""),
            "inkscape_action": PATH_OPERATIONS[operation]["inkscape_action"],
        },
    }

    # Remove the source objects (boolean ops consume both)
    # Remove higher index first to avoid index shifting
    higher = max(index_a, index_b)
    lower = min(index_a, index_b)

    removed_ids = {objects[higher].get("id", ""), objects[lower].get("id", "")}
    objects.pop(higher)
    objects.pop(lower)

    # Remove from layers
    for layer in project.get("layers", []):
        layer["objects"] = [oid for oid in layer.get("objects", []) if oid not in removed_ids]

    # Add result object
    objects.append(result_obj)

    # Add to layer
    layer_id = result_obj.get("layer", "")
    for layer in project.get("layers", []):
        if layer.get("id") == layer_id:
            layer.setdefault("objects", []).append(obj_id)
            break

    return result_obj


def _shape_to_path_data(obj: Dict[str, Any]) -> Optional[str]:
    """Convert a basic shape to SVG path data.

    Returns None if conversion requires Inkscape.
    """
    obj_type = obj.get("type", "")

    if obj_type == "rect":
        x = float(obj.get("x", 0))
        y = float(obj.get("y", 0))
        w = float(obj.get("width", 100))
        h = float(obj.get("height", 100))
        rx = float(obj.get("rx", 0))
        ry = float(obj.get("ry", 0))

        if rx == 0 and ry == 0:
            return f"M {x},{y} L {x+w},{y} L {x+w},{y+h} L {x},{y+h} Z"
        else:
            # Rounded rectangle
            rx = min(rx, w / 2)
            ry = min(ry, h / 2)
            return (
                f"M {x+rx},{y} "
                f"L {x+w-rx},{y} "
                f"A {rx},{ry} 0 0 1 {x+w},{y+ry} "
                f"L {x+w},{y+h-ry} "
                f"A {rx},{ry} 0 0 1 {x+w-rx},{y+h} "
                f"L {x+rx},{y+h} "
                f"A {rx},{ry} 0 0 1 {x},{y+h-ry} "
                f"L {x},{y+ry} "
                f"A {rx},{ry} 0 0 1 {x+rx},{y} Z"
            )

    elif obj_type == "circle":
        cx = float(obj.get("cx", 50))
        cy = float(obj.get("cy", 50))
        r = float(obj.get("r", 50))
        # Circle as two arcs
        return (
            f"M {cx-r},{cy} "
            f"A {r},{r} 0 1 0 {cx+r},{cy} "
            f"A {r},{r} 0 1 0 {cx-r},{cy} Z"
        )

    elif obj_type == "ellipse":
        cx = float(obj.get("cx", 50))
        cy = float(obj.get("cy", 50))
        rx = float(obj.get("rx", 75))
        ry = float(obj.get("ry", 50))
        return (
            f"M {cx-rx},{cy} "
            f"A {rx},{ry} 0 1 0 {cx+rx},{cy} "
            f"A {rx},{ry} 0 1 0 {cx-rx},{cy} Z"
        )

    elif obj_type == "line":
        x1 = float(obj.get("x1", 0))
        y1 = float(obj.get("y1", 0))
        x2 = float(obj.get("x2", 100))
        y2 = float(obj.get("y2", 100))
        return f"M {x1},{y1} L {x2},{y2}"

    elif obj_type == "polygon":
        points_str = obj.get("points", "")
        if not points_str:
            return None
        return "M " + " L ".join(points_str.strip().split()) + " Z"

    elif obj_type == "polyline":
        points_str = obj.get("points", "")
        if not points_str:
            return None
        return "M " + " L ".join(points_str.strip().split())

    return None
