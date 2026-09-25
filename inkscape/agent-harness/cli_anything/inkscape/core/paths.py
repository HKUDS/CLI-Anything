"""Inkscape CLI - Path operations module.

Handles representable shape-to-path conversion and potential boolean operations.
Unsupported operations fail explicitly until Inkscape can compute their geometry.
"""

from typing import Dict, Any, List, NoReturn, Optional

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


def require_path_boolean_support(
    project: Dict[str, Any],
    index_a: int,
    index_b: int,
) -> NoReturn:
    """Reject boolean requests until Inkscape-backed geometry is implemented."""
    objects = project.get("objects", [])
    if index_a < 0 or index_a >= len(objects):
        raise IndexError(f"Object A index {index_a} out of range (0-{len(objects)-1})")
    if index_b < 0 or index_b >= len(objects):
        raise IndexError(f"Object B index {index_b} out of range (0-{len(objects)-1})")
    if index_a == index_b:
        raise ValueError("Cannot perform boolean operation on the same object")

    raise RuntimeError(
        "Path boolean operations require the Inkscape backend and are not yet "
        "implemented; no objects were modified"
    )


def require_path_conversion_support(
    project: Dict[str, Any],
    index: int,
) -> None:
    """Reject conversions that have no representable SVG path data."""
    objects = project.get("objects", [])
    if index < 0 or index >= len(objects):
        raise IndexError(f"Object index {index} out of range (0-{len(objects)-1})")

    obj = objects[index]
    obj_type = obj.get("type", "")
    if obj_type == "path":
        return
    if obj_type not in CONVERTIBLE_TYPES:
        raise ValueError(f"Cannot convert type '{obj_type}' to path. "
                         f"Convertible types: {', '.join(sorted(CONVERTIBLE_TYPES))}")

    if obj_type == "text" or (
        _shape_to_path_data(obj) is None and not obj.get("d")
    ):
        raise RuntimeError(
            "Converting this object to a path requires the Inkscape backend and is "
            "not yet implemented; the object was not modified"
        )


def path_union(
    project: Dict[str, Any],
    index_a: int,
    index_b: int,
    name: Optional[str] = None,
) -> NoReturn:
    """Reject a union until Inkscape-backed geometry is implemented."""
    _path_boolean(project, index_a, index_b)


def path_intersection(
    project: Dict[str, Any],
    index_a: int,
    index_b: int,
    name: Optional[str] = None,
) -> NoReturn:
    """Reject an intersection until Inkscape-backed geometry is implemented."""
    _path_boolean(project, index_a, index_b)


def path_difference(
    project: Dict[str, Any],
    index_a: int,
    index_b: int,
    name: Optional[str] = None,
) -> NoReturn:
    """Reject a difference until Inkscape-backed geometry is implemented."""
    _path_boolean(project, index_a, index_b)


def path_exclusion(
    project: Dict[str, Any],
    index_a: int,
    index_b: int,
    name: Optional[str] = None,
) -> NoReturn:
    """Reject an exclusion until Inkscape-backed geometry is implemented."""
    _path_boolean(project, index_a, index_b)


def convert_to_path(
    project: Dict[str, Any],
    index: int,
) -> Dict[str, Any]:
    """Convert a shape to a path element when its geometry is representable."""
    require_path_conversion_support(project, index)
    obj = project["objects"][index]
    if obj["type"] == "path":
        return obj

    obj_type = obj["type"]
    d = _shape_to_path_data(obj)

    obj["type"] = "path"
    obj["d"] = d if d is not None else obj["d"]
    obj["original_type"] = obj_type
    if d is None:
        obj["conversion_pending"] = True

    return obj


def list_path_operations() -> List[Dict[str, str]]:
    """List potential path boolean operations."""
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
) -> NoReturn:
    """Reject boolean operations until Inkscape-backed geometry is implemented."""
    require_path_boolean_support(project, index_a, index_b)


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
