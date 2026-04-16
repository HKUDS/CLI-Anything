"""Inkscape CLI - Gradient management module.

Handles creating linear and radial gradients, applying them to objects,
and listing gradients.
"""

from typing import Dict, Any, List, Optional

from cli_anything.inkscape.utils.svg_utils import generate_id, parse_style, serialize_style


def add_linear_gradient(
    project: Dict[str, Any],
    stops: Optional[List[Dict[str, Any]]] = None,
    x1: float = 0, y1: float = 0,
    x2: float = 1, y2: float = 0,
    name: Optional[str] = None,
    gradient_units: str = "objectBoundingBox",
) -> Dict[str, Any]:
    """Add a linear gradient definition.

    Args:
        stops: List of dicts with 'offset', 'color', and optionally 'opacity'.
               Example: [{"offset": 0, "color": "#ff0000"}, {"offset": 1, "color": "#0000ff"}]
        x1, y1, x2, y2: Gradient vector coordinates (0-1 for objectBoundingBox).
        gradient_units: "objectBoundingBox" or "userSpaceOnUse".
    """
    if stops is None:
        stops = [
            {"offset": 0, "color": "#000000", "opacity": 1},
            {"offset": 1, "color": "#ffffff", "opacity": 1},
        ]

    _validate_stops(stops)
    if gradient_units not in ("objectBoundingBox", "userSpaceOnUse"):
        raise ValueError(f"Invalid gradientUnits: {gradient_units}")

    grad_id = generate_id("linearGradient")
    gradient = {
        "id": grad_id,
        "name": name or grad_id,
        "type": "linear",
        "x1": x1, "y1": y1,
        "x2": x2, "y2": y2,
        "gradientUnits": gradient_units,
        "stops": stops,
    }

    project.setdefault("gradients", []).append(gradient)
    return gradient


def add_radial_gradient(
    project: Dict[str, Any],
    stops: Optional[List[Dict[str, Any]]] = None,
    cx: float = 0.5, cy: float = 0.5,
    r: float = 0.5,
    fx: Optional[float] = None, fy: Optional[float] = None,
    name: Optional[str] = None,
    gradient_units: str = "objectBoundingBox",
) -> Dict[str, Any]:
    """Add a radial gradient definition.

    Args:
        stops: List of color stops.
        cx, cy: Center point.
        r: Radius.
        fx, fy: Focal point (defaults to cx, cy).
        gradient_units: "objectBoundingBox" or "userSpaceOnUse".
    """
    if stops is None:
        stops = [
            {"offset": 0, "color": "#ffffff", "opacity": 1},
            {"offset": 1, "color": "#000000", "opacity": 1},
        ]

    _validate_stops(stops)
    if gradient_units not in ("objectBoundingBox", "userSpaceOnUse"):
        raise ValueError(f"Invalid gradientUnits: {gradient_units}")

    if fx is None:
        fx = cx
    if fy is None:
        fy = cy

    grad_id = generate_id("radialGradient")
    gradient = {
        "id": grad_id,
        "name": name or grad_id,
        "type": "radial",
        "cx": cx, "cy": cy,
        "r": r,
        "fx": fx, "fy": fy,
        "gradientUnits": gradient_units,
        "stops": stops,
    }

    project.setdefault("gradients", []).append(gradient)
    return gradient


def apply_gradient(
    project: Dict[str, Any],
    object_index: int,
    gradient_index: int,
    target: str = "fill",
) -> Dict[str, Any]:
    """Apply a gradient to an object's fill or stroke.

    Args:
        target: "fill" or "stroke".
    """
    objects = project.get("objects", [])
    gradients = project.get("gradients", [])

    if object_index < 0 or object_index >= len(objects):
        raise IndexError(f"Object index {object_index} out of range (0-{len(objects)-1})")
    if gradient_index < 0 or gradient_index >= len(gradients):
        raise IndexError(f"Gradient index {gradient_index} out of range (0-{len(gradients)-1})")
    if target not in ("fill", "stroke"):
        raise ValueError(f"Target must be 'fill' or 'stroke', got: {target}")

    gradient = gradients[gradient_index]
    grad_id = gradient.get("id", "")
    obj = objects[object_index]

    # Update style to reference gradient
    style = parse_style(obj.get("style", ""))
    style[target] = f"url(#{grad_id})"
    obj["style"] = serialize_style(style)

    return {
        "object": obj.get("name", obj.get("id", "")),
        "gradient": gradient.get("name", grad_id),
        "target": target,
    }


def list_gradients(project: Dict[str, Any]) -> List[Dict[str, Any]]:
    """List all gradients in the document."""
    result = []
    for i, grad in enumerate(project.get("gradients", [])):
        result.append({
            "index": i,
            "id": grad.get("id", ""),
            "name": grad.get("name", ""),
            "type": grad.get("type", "unknown"),
            "stops_count": len(grad.get("stops", [])),
        })
    return result


def get_gradient(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Get detailed info about a gradient."""
    gradients = project.get("gradients", [])
    if index < 0 or index >= len(gradients):
        raise IndexError(f"Gradient index {index} out of range (0-{len(gradients)-1})")
    return gradients[index]


def remove_gradient(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Remove a gradient by index."""
    gradients = project.get("gradients", [])
    if index < 0 or index >= len(gradients):
        raise IndexError(f"Gradient index {index} out of range (0-{len(gradients)-1})")
    return gradients.pop(index)


# ── Internal ────────────────────────────────────────────────────

def _validate_stops(stops: List[Dict[str, Any]]) -> None:
    """Validate gradient stop definitions."""
    if not stops or len(stops) < 2:
        raise ValueError("Gradient must have at least 2 stops")

    for i, stop in enumerate(stops):
        if "offset" not in stop:
            raise ValueError(f"Stop {i} missing 'offset'")
        if "color" not in stop:
            raise ValueError(f"Stop {i} missing 'color'")
        offset = float(stop["offset"])
        if offset < 0 or offset > 1:
            raise ValueError(f"Stop {i} offset must be 0-1: {offset}")
        stop.setdefault("opacity", 1)
