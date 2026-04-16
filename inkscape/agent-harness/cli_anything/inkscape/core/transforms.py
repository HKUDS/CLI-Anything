"""Inkscape CLI - Transform operations module.

Handles translate, rotate, scale, and skew transforms on SVG objects.
Transforms are stored as SVG transform attribute strings.
"""

import re
import math
from typing import Dict, Any, List, Optional, Tuple


def translate(project: Dict[str, Any], index: int, tx: float, ty: float = 0) -> Dict[str, Any]:
    """Apply a translation to an object (additive)."""
    obj = _get_object(project, index)
    current = parse_transform_string(obj.get("transform", ""))
    current.append(("translate", [tx, ty]))
    obj["transform"] = serialize_transform_string(current)
    return obj


def rotate(project: Dict[str, Any], index: int, angle: float,
           cx: Optional[float] = None, cy: Optional[float] = None) -> Dict[str, Any]:
    """Apply a rotation to an object (additive).

    Args:
        angle: Rotation angle in degrees.
        cx, cy: Optional rotation center. If not given, rotates around origin.
    """
    obj = _get_object(project, index)
    current = parse_transform_string(obj.get("transform", ""))
    if cx is not None and cy is not None:
        current.append(("rotate", [angle, cx, cy]))
    else:
        current.append(("rotate", [angle]))
    obj["transform"] = serialize_transform_string(current)
    return obj


def scale(project: Dict[str, Any], index: int,
          sx: float, sy: Optional[float] = None) -> Dict[str, Any]:
    """Apply a scale to an object (additive).

    Args:
        sx: Horizontal scale factor.
        sy: Vertical scale factor. If None, uses sx (uniform scale).
    """
    if sx == 0 or (sy is not None and sy == 0):
        raise ValueError("Scale factors must be non-zero")
    obj = _get_object(project, index)
    current = parse_transform_string(obj.get("transform", ""))
    if sy is not None:
        current.append(("scale", [sx, sy]))
    else:
        current.append(("scale", [sx]))
    obj["transform"] = serialize_transform_string(current)
    return obj


def skew_x(project: Dict[str, Any], index: int, angle: float) -> Dict[str, Any]:
    """Apply a horizontal skew to an object."""
    obj = _get_object(project, index)
    current = parse_transform_string(obj.get("transform", ""))
    current.append(("skewX", [angle]))
    obj["transform"] = serialize_transform_string(current)
    return obj


def skew_y(project: Dict[str, Any], index: int, angle: float) -> Dict[str, Any]:
    """Apply a vertical skew to an object."""
    obj = _get_object(project, index)
    current = parse_transform_string(obj.get("transform", ""))
    current.append(("skewY", [angle]))
    obj["transform"] = serialize_transform_string(current)
    return obj


def get_transform(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Get the current transform of an object as a parsed structure."""
    obj = _get_object(project, index)
    transform_str = obj.get("transform", "")
    parsed = parse_transform_string(transform_str)
    return {
        "raw": transform_str,
        "operations": [{"type": op, "values": vals} for op, vals in parsed],
    }


def set_transform(project: Dict[str, Any], index: int, transform: str) -> Dict[str, Any]:
    """Set the transform of an object to an exact string."""
    obj = _get_object(project, index)
    obj["transform"] = transform
    return obj


def clear_transform(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Clear all transforms from an object."""
    obj = _get_object(project, index)
    old = obj.get("transform", "")
    obj["transform"] = ""
    return {"old_transform": old, "new_transform": ""}


# ── Transform String Parsing ───────────────────────────────────

def parse_transform_string(transform: str) -> List[Tuple[str, List[float]]]:
    """Parse an SVG transform attribute string into a list of operations.

    Example: "translate(10, 20) rotate(45)" ->
             [("translate", [10.0, 20.0]), ("rotate", [45.0])]
    """
    if not transform or not transform.strip():
        return []

    result = []
    # Match transform functions like: translate(10, 20), rotate(45, 50, 50)
    pattern = r'(translate|rotate|scale|skewX|skewY|matrix)\s*\(([^)]*)\)'
    for match in re.finditer(pattern, transform):
        func = match.group(1)
        args_str = match.group(2).strip()
        if not args_str:
            args = []
        else:
            # Split by comma or whitespace
            args = [float(x.strip()) for x in re.split(r'[,\s]+', args_str) if x.strip()]
        result.append((func, args))

    return result


def serialize_transform_string(operations: List[Tuple[str, List[float]]]) -> str:
    """Serialize transform operations back to an SVG transform string.

    Example: [("translate", [10.0, 20.0]), ("rotate", [45.0])] ->
             "translate(10, 20) rotate(45)"
    """
    if not operations:
        return ""

    parts = []
    for func, args in operations:
        args_str = ", ".join(_format_number(a) for a in args)
        parts.append(f"{func}({args_str})")

    return " ".join(parts)


# ── Helpers ─────────────────────────────────────────────────────

def _get_object(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Get an object by index with bounds checking."""
    objects = project.get("objects", [])
    if index < 0 or index >= len(objects):
        raise IndexError(f"Object index {index} out of range (0-{len(objects)-1})")
    return objects[index]


def _format_number(n: float) -> str:
    """Format a number for SVG output (strip trailing zeros)."""
    if n == int(n):
        return str(int(n))
    return f"{n:g}"
