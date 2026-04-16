"""
Sketch module for 2D constraint-based sketching in the FreeCAD CLI harness.

Provides creation and manipulation of parametric sketches with lines, circles,
arcs, rectangles, and geometric/dimensional constraints.
"""

import math
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Valid constants
# ---------------------------------------------------------------------------

VALID_PLANES = {"XY", "XZ", "YZ"}

VALID_CONSTRAINT_TYPES = {
    "coincident",
    "horizontal",
    "vertical",
    "parallel",
    "perpendicular",
    "equal",
    "fixed",
    "distance",
    "angle",
    "radius",
    "tangent",
    "symmetric",
    "block",
    "diameter",
    "point_on_object",
    "distance_x",
    "distance_y",
}

# Constraints that require a numeric value
VALUED_CONSTRAINTS = {"distance", "angle", "radius", "diameter", "distance_x", "distance_y"}

# Minimum number of element references each constraint type requires
CONSTRAINT_MIN_ELEMENTS = {
    "coincident": 2,
    "horizontal": 1,
    "vertical": 1,
    "parallel": 2,
    "perpendicular": 2,
    "equal": 2,
    "fixed": 1,
    "distance": 1,
    "angle": 1,
    "radius": 1,
    "tangent": 2,
    "symmetric": 3,
    "block": 1,
    "diameter": 1,
    "point_on_object": 2,
    "distance_x": 1,
    "distance_y": 1,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _next_id(project: Dict[str, Any], collection_key: str = "sketches") -> int:
    """Generate the next unique ID for a collection."""
    items = project.get(collection_key, [])
    existing_ids = [item.get("id", 0) for item in items]
    return max(existing_ids, default=-1) + 1


def _unique_name(project: Dict[str, Any], base_name: str, collection_key: str = "sketches") -> str:
    """Generate a unique name within a collection."""
    items = project.get(collection_key, [])
    existing_names = {item.get("name", "") for item in items}
    if base_name not in existing_names:
        return base_name
    counter = 1
    while f"{base_name}.{counter:03d}" in existing_names:
        counter += 1
    return f"{base_name}.{counter:03d}"


def _next_element_id(sketch: Dict[str, Any]) -> int:
    """Generate the next unique element ID within a sketch."""
    elements = sketch.get("elements", [])
    existing_ids = [el.get("id", 0) for el in elements]
    return max(existing_ids, default=-1) + 1


def _next_constraint_id(sketch: Dict[str, Any]) -> int:
    """Generate the next unique constraint ID within a sketch."""
    constraints = sketch.get("constraints", [])
    existing_ids = [c.get("id", 0) for c in constraints]
    return max(existing_ids, default=-1) + 1


def _validate_project(project: Dict[str, Any]) -> None:
    """Raise ``ValueError`` if *project* is not a valid dict with a sketches list."""
    if not isinstance(project, dict):
        raise ValueError("Project must be a dictionary")
    if "sketches" not in project:
        raise ValueError("Project is missing 'sketches' collection")
    if not isinstance(project["sketches"], list):
        raise ValueError("Project 'sketches' must be a list")


def _get_sketch(project: Dict[str, Any], sketch_index: int) -> Dict[str, Any]:
    """Return sketch at *sketch_index* or raise ``IndexError``."""
    sketches = project["sketches"]
    if sketch_index < 0 or sketch_index >= len(sketches):
        raise IndexError(
            f"Sketch index {sketch_index} out of range (0-{len(sketches) - 1})"
        )
    return sketches[sketch_index]


def _validate_point_2d(point: List[float], label: str = "point") -> List[float]:
    """Validate and return a 2D point as a list of two floats."""
    if not isinstance(point, (list, tuple)) or len(point) != 2:
        raise ValueError(f"{label} must be a list of 2 numbers, got {point!r}")
    try:
        return [float(point[0]), float(point[1])]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} components must be numeric: {exc}") from exc


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_sketch(
    project: Dict[str, Any],
    name: Optional[str] = None,
    plane: str = "XY",
    offset: float = 0.0,
) -> Dict[str, Any]:
    """Create a new sketch on the specified plane.

    Parameters
    ----------
    project:
        The project dictionary.
    name:
        Optional sketch name.  Auto-generated if ``None``.
    plane:
        Reference plane: ``"XY"``, ``"XZ"``, or ``"YZ"``.
    offset:
        Offset distance from the reference plane.

    Returns
    -------
    Dict[str, Any]
        The newly created sketch dictionary.

    Raises
    ------
    ValueError
        If the plane is invalid or the project is malformed.
    """
    _validate_project(project)

    plane = plane.upper()
    if plane not in VALID_PLANES:
        raise ValueError(
            f"Invalid plane '{plane}'. Must be one of: {', '.join(sorted(VALID_PLANES))}"
        )

    offset = float(offset)

    base_name = name if name else "Sketch"
    sketch_name = _unique_name(project, base_name)

    sketch: Dict[str, Any] = {
        "id": _next_id(project),
        "name": sketch_name,
        "plane": plane,
        "offset": offset,
        "elements": [],
        "constraints": [],
        "closed": False,
    }

    project["sketches"].append(sketch)
    return sketch


def add_line(
    project: Dict[str, Any],
    sketch_index: int,
    start: Optional[List[float]] = None,
    end: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Add a line element to a sketch.

    Parameters
    ----------
    project:
        The project dictionary.
    sketch_index:
        Index of the target sketch in ``project["sketches"]``.
    start:
        Start point ``[x, y]``.  Defaults to ``[0, 0]``.
    end:
        End point ``[x, y]``.  Defaults to ``[10, 0]``.

    Returns
    -------
    Dict[str, Any]
        The newly created line element.
    """
    _validate_project(project)
    sketch = _get_sketch(project, sketch_index)

    if sketch["closed"]:
        raise ValueError("Cannot add elements to a closed sketch")

    start = _validate_point_2d(start if start is not None else [0, 0], "start")
    end = _validate_point_2d(end if end is not None else [10, 0], "end")

    if start == end:
        raise ValueError("Line start and end points must be different")

    element: Dict[str, Any] = {
        "id": _next_element_id(sketch),
        "type": "line",
        "start": start,
        "end": end,
    }

    sketch["elements"].append(element)
    return element


def add_circle(
    project: Dict[str, Any],
    sketch_index: int,
    center: Optional[List[float]] = None,
    radius: float = 5.0,
) -> Dict[str, Any]:
    """Add a circle element to a sketch.

    Parameters
    ----------
    project:
        The project dictionary.
    sketch_index:
        Index of the target sketch.
    center:
        Center point ``[x, y]``.  Defaults to ``[0, 0]``.
    radius:
        Circle radius.  Must be positive.

    Returns
    -------
    Dict[str, Any]
        The newly created circle element.
    """
    _validate_project(project)
    sketch = _get_sketch(project, sketch_index)

    if sketch["closed"]:
        raise ValueError("Cannot add elements to a closed sketch")

    center = _validate_point_2d(center if center is not None else [0, 0], "center")
    radius = float(radius)
    if radius <= 0:
        raise ValueError(f"Radius must be positive, got {radius}")

    element: Dict[str, Any] = {
        "id": _next_element_id(sketch),
        "type": "circle",
        "center": center,
        "radius": radius,
    }

    sketch["elements"].append(element)
    return element


def add_rectangle(
    project: Dict[str, Any],
    sketch_index: int,
    corner: Optional[List[float]] = None,
    width: float = 10.0,
    height: float = 10.0,
) -> Dict[str, Any]:
    """Add a rectangle to a sketch (4 lines + 4 perpendicular constraints).

    The rectangle is axis-aligned with its bottom-left at *corner*.

    Parameters
    ----------
    project:
        The project dictionary.
    sketch_index:
        Index of the target sketch.
    corner:
        Bottom-left corner ``[x, y]``.  Defaults to ``[0, 0]``.
    width:
        Rectangle width (X extent).  Must be positive.
    height:
        Rectangle height (Y extent).  Must be positive.

    Returns
    -------
    Dict[str, Any]
        Summary containing the four line element IDs and four constraint IDs.
    """
    _validate_project(project)
    sketch = _get_sketch(project, sketch_index)

    if sketch["closed"]:
        raise ValueError("Cannot add elements to a closed sketch")

    corner = _validate_point_2d(corner if corner is not None else [0, 0], "corner")
    width = float(width)
    height = float(height)
    if width <= 0:
        raise ValueError(f"Width must be positive, got {width}")
    if height <= 0:
        raise ValueError(f"Height must be positive, got {height}")

    x, y = corner
    # Four corners: BL, BR, TR, TL
    bl = [x, y]
    br = [x + width, y]
    tr = [x + width, y + height]
    tl = [x, y + height]

    # Create four line elements
    lines: List[Dict[str, Any]] = []
    for start, end in [(bl, br), (br, tr), (tr, tl), (tl, bl)]:
        elem: Dict[str, Any] = {
            "id": _next_element_id(sketch),
            "type": "line",
            "start": list(start),
            "end": list(end),
        }
        sketch["elements"].append(elem)
        lines.append(elem)

    # Add 4 coincident constraints at the corners (each pair of adjacent lines)
    constraint_ids: List[int] = []
    for i in range(4):
        j = (i + 1) % 4
        constraint: Dict[str, Any] = {
            "id": _next_constraint_id(sketch),
            "type": "coincident",
            "elements": [lines[i]["id"], lines[j]["id"]],
            "value": None,
        }
        sketch["constraints"].append(constraint)
        constraint_ids.append(constraint["id"])

    return {
        "type": "rectangle",
        "line_ids": [line["id"] for line in lines],
        "constraint_ids": constraint_ids,
        "corner": corner,
        "width": width,
        "height": height,
    }


def add_arc(
    project: Dict[str, Any],
    sketch_index: int,
    center: Optional[List[float]] = None,
    radius: float = 5.0,
    start_angle: float = 0.0,
    end_angle: float = 90.0,
) -> Dict[str, Any]:
    """Add an arc element to a sketch.

    Parameters
    ----------
    project:
        The project dictionary.
    sketch_index:
        Index of the target sketch.
    center:
        Center point ``[x, y]``.  Defaults to ``[0, 0]``.
    radius:
        Arc radius.  Must be positive.
    start_angle:
        Start angle in degrees.
    end_angle:
        End angle in degrees.  Must differ from *start_angle*.

    Returns
    -------
    Dict[str, Any]
        The newly created arc element.
    """
    _validate_project(project)
    sketch = _get_sketch(project, sketch_index)

    if sketch["closed"]:
        raise ValueError("Cannot add elements to a closed sketch")

    center = _validate_point_2d(center if center is not None else [0, 0], "center")
    radius = float(radius)
    start_angle = float(start_angle)
    end_angle = float(end_angle)

    if radius <= 0:
        raise ValueError(f"Radius must be positive, got {radius}")
    if start_angle == end_angle:
        raise ValueError("Start angle and end angle must be different")

    # Compute start/end points for reference
    start_rad = math.radians(start_angle)
    end_rad = math.radians(end_angle)
    start_point = [
        center[0] + radius * math.cos(start_rad),
        center[1] + radius * math.sin(start_rad),
    ]
    end_point = [
        center[0] + radius * math.cos(end_rad),
        center[1] + radius * math.sin(end_rad),
    ]

    element: Dict[str, Any] = {
        "id": _next_element_id(sketch),
        "type": "arc",
        "center": center,
        "radius": radius,
        "start_angle": start_angle,
        "end_angle": end_angle,
        "start_point": start_point,
        "end_point": end_point,
    }

    sketch["elements"].append(element)
    return element


def add_constraint(
    project: Dict[str, Any],
    sketch_index: int,
    constraint_type: str,
    elements: List[int],
    value: Optional[float] = None,
) -> Dict[str, Any]:
    """Add a geometric or dimensional constraint to a sketch.

    Parameters
    ----------
    project:
        The project dictionary.
    sketch_index:
        Index of the target sketch.
    constraint_type:
        One of: ``"coincident"``, ``"horizontal"``, ``"vertical"``,
        ``"parallel"``, ``"perpendicular"``, ``"equal"``, ``"fixed"``,
        ``"distance"``, ``"angle"``, ``"radius"``, ``"tangent"``.
    elements:
        List of element IDs (indices within the sketch's ``elements``
        list) that participate in the constraint.
    value:
        Numeric value for dimensional constraints (``"distance"``,
        ``"angle"``, ``"radius"``).

    Returns
    -------
    Dict[str, Any]
        The newly created constraint dictionary.

    Raises
    ------
    ValueError
        If the constraint type is unknown, required value is missing,
        or element references are invalid.
    """
    _validate_project(project)
    sketch = _get_sketch(project, sketch_index)

    if sketch["closed"]:
        raise ValueError("Cannot add constraints to a closed sketch")

    constraint_type = constraint_type.lower()
    if constraint_type not in VALID_CONSTRAINT_TYPES:
        raise ValueError(
            f"Unknown constraint type '{constraint_type}'. "
            f"Valid types: {', '.join(sorted(VALID_CONSTRAINT_TYPES))}"
        )

    if not isinstance(elements, (list, tuple)) or len(elements) == 0:
        raise ValueError("Elements must be a non-empty list of element IDs")

    # Validate minimum element count
    min_elements = CONSTRAINT_MIN_ELEMENTS[constraint_type]
    if len(elements) < min_elements:
        raise ValueError(
            f"Constraint '{constraint_type}' requires at least {min_elements} "
            f"element(s), got {len(elements)}"
        )

    # Validate element IDs exist in the sketch
    existing_ids = {el["id"] for el in sketch["elements"]}
    for eid in elements:
        if eid not in existing_ids:
            raise ValueError(
                f"Element ID {eid} not found in sketch. "
                f"Existing IDs: {sorted(existing_ids)}"
            )

    # Validate value for dimensional constraints
    if constraint_type in VALUED_CONSTRAINTS:
        if value is None:
            raise ValueError(
                f"Constraint '{constraint_type}' requires a numeric value"
            )
        value = float(value)
        if constraint_type == "radius" and value <= 0:
            raise ValueError(f"Radius constraint value must be positive, got {value}")
        if constraint_type == "distance" and value < 0:
            raise ValueError(f"Distance constraint value must be non-negative, got {value}")
    else:
        # Geometric constraints ignore value
        value = None

    constraint: Dict[str, Any] = {
        "id": _next_constraint_id(sketch),
        "type": constraint_type,
        "elements": list(elements),
        "value": value,
    }

    sketch["constraints"].append(constraint)
    return constraint


def close_sketch(
    project: Dict[str, Any],
    sketch_index: int,
) -> Dict[str, Any]:
    """Mark a sketch as closed, preventing further modifications.

    Parameters
    ----------
    project:
        The project dictionary.
    sketch_index:
        Index of the target sketch.

    Returns
    -------
    Dict[str, Any]
        The closed sketch dictionary.
    """
    _validate_project(project)
    sketch = _get_sketch(project, sketch_index)

    if sketch["closed"]:
        raise ValueError(f"Sketch '{sketch['name']}' is already closed")

    sketch["closed"] = True
    return sketch


def list_sketches(project: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return a summary list of all sketches in the project.

    Parameters
    ----------
    project:
        The project dictionary.

    Returns
    -------
    List[Dict[str, Any]]
        List of sketch summaries with index, id, name, plane, element
        count, constraint count, and closed status.
    """
    _validate_project(project)

    result: List[Dict[str, Any]] = []
    for i, sk in enumerate(project["sketches"]):
        result.append({
            "index": i,
            "id": sk.get("id", i),
            "name": sk.get("name", f"Sketch {i}"),
            "plane": sk.get("plane", "XY"),
            "offset": sk.get("offset", 0.0),
            "element_count": len(sk.get("elements", [])),
            "constraint_count": len(sk.get("constraints", [])),
            "closed": sk.get("closed", False),
        })
    return result


def get_sketch(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Return the full sketch dictionary at the given index.

    Parameters
    ----------
    project:
        The project dictionary.
    index:
        Sketch index.

    Returns
    -------
    Dict[str, Any]
        The complete sketch dictionary.
    """
    _validate_project(project)
    return _get_sketch(project, index)


# ---------------------------------------------------------------------------
# New Geometry
# ---------------------------------------------------------------------------


def add_point(
    project: Dict[str, Any],
    sketch_index: int,
    position: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Add a point element to a sketch.

    Parameters
    ----------
    project:
        The project dictionary.
    sketch_index:
        Index of the target sketch.
    position:
        Point position ``[x, y]``.  Defaults to ``[0, 0]``.

    Returns
    -------
    Dict[str, Any]
        The newly created point element.
    """
    _validate_project(project)
    sketch = _get_sketch(project, sketch_index)

    if sketch["closed"]:
        raise ValueError("Cannot add elements to a closed sketch")

    position = _validate_point_2d(position if position is not None else [0, 0], "position")

    element: Dict[str, Any] = {
        "id": _next_element_id(sketch),
        "type": "point",
        "position": position,
    }

    sketch["elements"].append(element)
    return element


def add_ellipse(
    project: Dict[str, Any],
    sketch_index: int,
    center: Optional[List[float]] = None,
    major_radius: float = 10.0,
    minor_radius: float = 5.0,
    angle: float = 0.0,
) -> Dict[str, Any]:
    """Add an ellipse element to a sketch.

    Parameters
    ----------
    project:
        The project dictionary.
    sketch_index:
        Index of the target sketch.
    center:
        Center point ``[x, y]``.  Defaults to ``[0, 0]``.
    major_radius:
        Semi-major axis length.  Must be positive.
    minor_radius:
        Semi-minor axis length.  Must be positive.
    angle:
        Rotation angle of the major axis in degrees.

    Returns
    -------
    Dict[str, Any]
        The newly created ellipse element.
    """
    _validate_project(project)
    sketch = _get_sketch(project, sketch_index)

    if sketch["closed"]:
        raise ValueError("Cannot add elements to a closed sketch")

    center = _validate_point_2d(center if center is not None else [0, 0], "center")
    major_radius = float(major_radius)
    minor_radius = float(minor_radius)
    angle = float(angle)

    if major_radius <= 0:
        raise ValueError(f"Major radius must be positive, got {major_radius}")
    if minor_radius <= 0:
        raise ValueError(f"Minor radius must be positive, got {minor_radius}")
    if minor_radius > major_radius:
        raise ValueError(
            f"Minor radius ({minor_radius}) cannot exceed major radius ({major_radius})"
        )

    element: Dict[str, Any] = {
        "id": _next_element_id(sketch),
        "type": "ellipse",
        "center": center,
        "major_radius": major_radius,
        "minor_radius": minor_radius,
        "angle": angle,
    }

    sketch["elements"].append(element)
    return element


def add_polygon_sketch(
    project: Dict[str, Any],
    sketch_index: int,
    center: Optional[List[float]] = None,
    sides: int = 6,
    radius: float = 5.0,
) -> Dict[str, Any]:
    """Add a regular polygon to a sketch (N lines + N coincident constraints).

    Parameters
    ----------
    project:
        The project dictionary.
    sketch_index:
        Index of the target sketch.
    center:
        Center point ``[x, y]``.  Defaults to ``[0, 0]``.
    sides:
        Number of sides.  Must be at least 3.
    radius:
        Circumscribed circle radius.  Must be positive.

    Returns
    -------
    Dict[str, Any]
        Summary containing line element IDs and coincident constraint IDs.
    """
    _validate_project(project)
    sketch = _get_sketch(project, sketch_index)

    if sketch["closed"]:
        raise ValueError("Cannot add elements to a closed sketch")

    center = _validate_point_2d(center if center is not None else [0, 0], "center")
    sides = int(sides)
    radius = float(radius)

    if sides < 3:
        raise ValueError(f"Polygon must have at least 3 sides, got {sides}")
    if radius <= 0:
        raise ValueError(f"Radius must be positive, got {radius}")

    cx, cy = center

    # Compute vertices
    vertices: List[List[float]] = []
    for i in range(sides):
        angle_rad = 2 * math.pi * i / sides
        vertices.append([
            cx + radius * math.cos(angle_rad),
            cy + radius * math.sin(angle_rad),
        ])

    # Create line elements for each side
    lines: List[Dict[str, Any]] = []
    for i in range(sides):
        j = (i + 1) % sides
        elem: Dict[str, Any] = {
            "id": _next_element_id(sketch),
            "type": "line",
            "start": list(vertices[i]),
            "end": list(vertices[j]),
        }
        sketch["elements"].append(elem)
        lines.append(elem)

    # Add coincident constraints at each vertex (adjacent lines)
    constraint_ids: List[int] = []
    for i in range(sides):
        j = (i + 1) % sides
        constraint: Dict[str, Any] = {
            "id": _next_constraint_id(sketch),
            "type": "coincident",
            "elements": [lines[i]["id"], lines[j]["id"]],
            "value": None,
        }
        sketch["constraints"].append(constraint)
        constraint_ids.append(constraint["id"])

    return {
        "type": "polygon",
        "line_ids": [line["id"] for line in lines],
        "constraint_ids": constraint_ids,
        "center": center,
        "sides": sides,
        "radius": radius,
    }


def add_bspline(
    project: Dict[str, Any],
    sketch_index: int,
    points: List[List[float]],
    closed: bool = False,
) -> Dict[str, Any]:
    """Add a B-spline element from control points to a sketch.

    Parameters
    ----------
    project:
        The project dictionary.
    sketch_index:
        Index of the target sketch.
    points:
        List of control points, each ``[x, y]``.  Minimum 2 points.
    closed:
        If ``True``, the B-spline forms a closed loop.

    Returns
    -------
    Dict[str, Any]
        The newly created B-spline element.
    """
    _validate_project(project)
    sketch = _get_sketch(project, sketch_index)

    if sketch["closed"]:
        raise ValueError("Cannot add elements to a closed sketch")

    if not isinstance(points, (list, tuple)) or len(points) < 2:
        raise ValueError("B-spline requires at least 2 control points")

    validated_points: List[List[float]] = []
    for i, pt in enumerate(points):
        validated_points.append(_validate_point_2d(pt, f"points[{i}]"))

    element: Dict[str, Any] = {
        "id": _next_element_id(sketch),
        "type": "bspline",
        "poles": validated_points,
        "closed": bool(closed),
    }

    sketch["elements"].append(element)
    return element


def add_slot(
    project: Dict[str, Any],
    sketch_index: int,
    center1: Optional[List[float]] = None,
    center2: Optional[List[float]] = None,
    radius: float = 2.0,
) -> Dict[str, Any]:
    """Add a slot (obround) shape to a sketch.

    The slot consists of two semicircular arcs connected by two lines.

    Parameters
    ----------
    project:
        The project dictionary.
    sketch_index:
        Index of the target sketch.
    center1:
        Center of the first semicircle ``[x, y]``.  Defaults to ``[0, 0]``.
    center2:
        Center of the second semicircle ``[x, y]``.  Defaults to ``[10, 0]``.
    radius:
        Radius of the semicircular ends.  Must be positive.

    Returns
    -------
    Dict[str, Any]
        Summary containing arc and line element IDs.
    """
    _validate_project(project)
    sketch = _get_sketch(project, sketch_index)

    if sketch["closed"]:
        raise ValueError("Cannot add elements to a closed sketch")

    center1 = _validate_point_2d(center1 if center1 is not None else [0, 0], "center1")
    center2 = _validate_point_2d(center2 if center2 is not None else [10, 0], "center2")
    radius = float(radius)

    if radius <= 0:
        raise ValueError(f"Radius must be positive, got {radius}")
    if center1 == center2:
        raise ValueError("center1 and center2 must be different")

    # Direction vector from center1 to center2
    dx = center2[0] - center1[0]
    dy = center2[1] - center1[1]
    length = math.sqrt(dx * dx + dy * dy)
    nx = -dy / length  # perpendicular normal
    ny = dx / length

    # Four connection points
    p1_top = [center1[0] + nx * radius, center1[1] + ny * radius]
    p1_bot = [center1[0] - nx * radius, center1[1] - ny * radius]
    p2_top = [center2[0] + nx * radius, center2[1] + ny * radius]
    p2_bot = [center2[0] - nx * radius, center2[1] - ny * radius]

    # Angle of the direction vector
    base_angle = math.degrees(math.atan2(dy, dx))

    # Arc at center1 (from bottom to top, going "left")
    arc1: Dict[str, Any] = {
        "id": _next_element_id(sketch),
        "type": "arc",
        "center": list(center1),
        "radius": radius,
        "start_angle": base_angle + 90,
        "end_angle": base_angle + 270,
        "start_point": list(p1_top),
        "end_point": list(p1_bot),
    }
    sketch["elements"].append(arc1)

    # Top line from center1 to center2
    line_top: Dict[str, Any] = {
        "id": _next_element_id(sketch),
        "type": "line",
        "start": list(p1_top),
        "end": list(p2_top),
    }
    sketch["elements"].append(line_top)

    # Arc at center2 (from top to bottom, going "right")
    arc2: Dict[str, Any] = {
        "id": _next_element_id(sketch),
        "type": "arc",
        "center": list(center2),
        "radius": radius,
        "start_angle": base_angle - 90,
        "end_angle": base_angle + 90,
        "start_point": list(p2_bot),
        "end_point": list(p2_top),
    }
    sketch["elements"].append(arc2)

    # Bottom line from center2 to center1
    line_bot: Dict[str, Any] = {
        "id": _next_element_id(sketch),
        "type": "line",
        "start": list(p2_bot),
        "end": list(p1_bot),
    }
    sketch["elements"].append(line_bot)

    return {
        "type": "slot",
        "arc_ids": [arc1["id"], arc2["id"]],
        "line_ids": [line_top["id"], line_bot["id"]],
        "center1": center1,
        "center2": center2,
        "radius": radius,
    }


# ---------------------------------------------------------------------------
# Editing
# ---------------------------------------------------------------------------


def edit_element(
    project: Dict[str, Any],
    sketch_index: int,
    elem_id: int,
    **props: Any,
) -> Dict[str, Any]:
    """Modify properties of an existing sketch element.

    Parameters
    ----------
    project:
        The project dictionary.
    sketch_index:
        Index of the target sketch.
    elem_id:
        ID of the element to edit.
    **props:
        Key-value pairs of properties to update (e.g. ``start``, ``end``,
        ``center``, ``radius``).

    Returns
    -------
    Dict[str, Any]
        The updated element dictionary.

    Raises
    ------
    ValueError
        If the sketch is closed or no properties are provided.
    KeyError
        If the element ID is not found.
    """
    _validate_project(project)
    sketch = _get_sketch(project, sketch_index)

    if sketch["closed"]:
        raise ValueError("Cannot edit elements in a closed sketch")

    if not props:
        raise ValueError("At least one property must be provided to edit")

    for elem in sketch["elements"]:
        if elem["id"] == elem_id:
            # Validate point-like properties
            for key in ("start", "end", "center", "position"):
                if key in props:
                    props[key] = _validate_point_2d(props[key], key)
            if "radius" in props:
                props["radius"] = float(props["radius"])
                if props["radius"] <= 0:
                    raise ValueError(f"Radius must be positive, got {props['radius']}")
            elem.update(props)
            return elem

    raise KeyError(f"Element ID {elem_id} not found in sketch")


def remove_element(
    project: Dict[str, Any],
    sketch_index: int,
    elem_id: int,
) -> Dict[str, Any]:
    """Remove an element and all its associated constraints from a sketch.

    Parameters
    ----------
    project:
        The project dictionary.
    sketch_index:
        Index of the target sketch.
    elem_id:
        ID of the element to remove.

    Returns
    -------
    Dict[str, Any]
        Summary with removed element ID and list of removed constraint IDs.

    Raises
    ------
    ValueError
        If the sketch is closed.
    KeyError
        If the element ID is not found.
    """
    _validate_project(project)
    sketch = _get_sketch(project, sketch_index)

    if sketch["closed"]:
        raise ValueError("Cannot remove elements from a closed sketch")

    # Find and remove the element
    found = False
    for i, elem in enumerate(sketch["elements"]):
        if elem["id"] == elem_id:
            sketch["elements"].pop(i)
            found = True
            break

    if not found:
        raise KeyError(f"Element ID {elem_id} not found in sketch")

    # Remove constraints that reference this element
    removed_constraints: List[int] = []
    remaining: List[Dict[str, Any]] = []
    for c in sketch["constraints"]:
        if elem_id in c.get("elements", []):
            removed_constraints.append(c["id"])
        else:
            remaining.append(c)
    sketch["constraints"] = remaining

    return {
        "removed_element_id": elem_id,
        "removed_constraint_ids": removed_constraints,
    }


def remove_constraint(
    project: Dict[str, Any],
    sketch_index: int,
    constraint_id: int,
) -> Dict[str, Any]:
    """Remove a specific constraint from a sketch.

    Parameters
    ----------
    project:
        The project dictionary.
    sketch_index:
        Index of the target sketch.
    constraint_id:
        ID of the constraint to remove.

    Returns
    -------
    Dict[str, Any]
        The removed constraint dictionary.

    Raises
    ------
    ValueError
        If the sketch is closed.
    KeyError
        If the constraint ID is not found.
    """
    _validate_project(project)
    sketch = _get_sketch(project, sketch_index)

    if sketch["closed"]:
        raise ValueError("Cannot remove constraints from a closed sketch")

    for i, c in enumerate(sketch["constraints"]):
        if c["id"] == constraint_id:
            return sketch["constraints"].pop(i)

    raise KeyError(f"Constraint ID {constraint_id} not found in sketch")


def edit_constraint(
    project: Dict[str, Any],
    sketch_index: int,
    constraint_id: int,
    value: Optional[float] = None,
) -> Dict[str, Any]:
    """Change the value of an existing constraint.

    Parameters
    ----------
    project:
        The project dictionary.
    sketch_index:
        Index of the target sketch.
    constraint_id:
        ID of the constraint to edit.
    value:
        New numeric value for the constraint.

    Returns
    -------
    Dict[str, Any]
        The updated constraint dictionary.

    Raises
    ------
    ValueError
        If the sketch is closed or the constraint is not a valued type.
    KeyError
        If the constraint ID is not found.
    """
    _validate_project(project)
    sketch = _get_sketch(project, sketch_index)

    if sketch["closed"]:
        raise ValueError("Cannot edit constraints in a closed sketch")

    for c in sketch["constraints"]:
        if c["id"] == constraint_id:
            if c["type"] not in VALUED_CONSTRAINTS:
                raise ValueError(
                    f"Constraint type '{c['type']}' does not accept a numeric value"
                )
            if value is not None:
                value = float(value)
            c["value"] = value
            return c

    raise KeyError(f"Constraint ID {constraint_id} not found in sketch")


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------


def mirror_elements(
    project: Dict[str, Any],
    sketch_index: int,
    elem_ids: List[int],
    axis_elem_id: int,
) -> Dict[str, Any]:
    """Mirror sketch elements about an axis element.

    Creates mirrored copies of the specified elements and adds symmetric
    constraints linking originals to their mirrors.

    Parameters
    ----------
    project:
        The project dictionary.
    sketch_index:
        Index of the target sketch.
    elem_ids:
        List of element IDs to mirror.
    axis_elem_id:
        ID of the line element to use as mirror axis.

    Returns
    -------
    Dict[str, Any]
        Summary with original IDs, mirrored element IDs, and constraint IDs.
    """
    _validate_project(project)
    sketch = _get_sketch(project, sketch_index)

    if sketch["closed"]:
        raise ValueError("Cannot mirror elements in a closed sketch")

    existing_ids = {el["id"] for el in sketch["elements"]}
    if axis_elem_id not in existing_ids:
        raise ValueError(f"Axis element ID {axis_elem_id} not found in sketch")
    for eid in elem_ids:
        if eid not in existing_ids:
            raise ValueError(f"Element ID {eid} not found in sketch")

    mirrored_ids: List[int] = []
    constraint_ids: List[int] = []

    for eid in elem_ids:
        # Find original element and create a shallow copy
        original = next(el for el in sketch["elements"] if el["id"] == eid)
        mirrored = dict(original)
        mirrored["id"] = _next_element_id(sketch)
        mirrored["mirrored_from"] = eid
        sketch["elements"].append(mirrored)
        mirrored_ids.append(mirrored["id"])

        # Add symmetric constraint (original, mirror, axis)
        constraint: Dict[str, Any] = {
            "id": _next_constraint_id(sketch),
            "type": "symmetric",
            "elements": [eid, mirrored["id"], axis_elem_id],
            "value": None,
        }
        sketch["constraints"].append(constraint)
        constraint_ids.append(constraint["id"])

    return {
        "original_ids": list(elem_ids),
        "mirrored_ids": mirrored_ids,
        "constraint_ids": constraint_ids,
        "axis_elem_id": axis_elem_id,
    }


def offset_wire(
    project: Dict[str, Any],
    sketch_index: int,
    elem_ids: List[int],
    distance: float,
) -> Dict[str, Any]:
    """Offset a wire of elements by a given distance.

    Creates offset copies of the specified elements in the sketch.

    Parameters
    ----------
    project:
        The project dictionary.
    sketch_index:
        Index of the target sketch.
    elem_ids:
        List of element IDs forming the wire to offset.
    distance:
        Offset distance.  Positive offsets outward, negative inward.

    Returns
    -------
    Dict[str, Any]
        Summary with original IDs and new offset element IDs.
    """
    _validate_project(project)
    sketch = _get_sketch(project, sketch_index)

    if sketch["closed"]:
        raise ValueError("Cannot offset elements in a closed sketch")

    distance = float(distance)
    if distance == 0:
        raise ValueError("Offset distance must be non-zero")

    existing_ids = {el["id"] for el in sketch["elements"]}
    for eid in elem_ids:
        if eid not in existing_ids:
            raise ValueError(f"Element ID {eid} not found in sketch")

    offset_ids: List[int] = []
    for eid in elem_ids:
        original = next(el for el in sketch["elements"] if el["id"] == eid)
        offset_elem = dict(original)
        offset_elem["id"] = _next_element_id(sketch)
        offset_elem["offset_from"] = eid
        offset_elem["offset_distance"] = distance
        sketch["elements"].append(offset_elem)
        offset_ids.append(offset_elem["id"])

    return {
        "original_ids": list(elem_ids),
        "offset_ids": offset_ids,
        "distance": distance,
    }


def trim_element(
    project: Dict[str, Any],
    sketch_index: int,
    elem_id: int,
    keep_side: str = "start",
) -> Dict[str, Any]:
    """Trim an element at its intersection point.

    This is a simplified trim that marks the element with a trim point
    indicator and the side to keep.

    Parameters
    ----------
    project:
        The project dictionary.
    sketch_index:
        Index of the target sketch.
    elem_id:
        ID of the element to trim.
    keep_side:
        Which side to keep: ``"start"`` or ``"end"``.

    Returns
    -------
    Dict[str, Any]
        The updated element dictionary with trim metadata.
    """
    _validate_project(project)
    sketch = _get_sketch(project, sketch_index)

    if sketch["closed"]:
        raise ValueError("Cannot trim elements in a closed sketch")

    keep_side = keep_side.lower()
    if keep_side not in ("start", "end"):
        raise ValueError(f"keep_side must be 'start' or 'end', got '{keep_side}'")

    for elem in sketch["elements"]:
        if elem["id"] == elem_id:
            elem["trimmed"] = True
            elem["trim_keep_side"] = keep_side
            return elem

    raise KeyError(f"Element ID {elem_id} not found in sketch")


def extend_element(
    project: Dict[str, Any],
    sketch_index: int,
    elem_id: int,
    target_elem_id: int,
) -> Dict[str, Any]:
    """Extend an element to reach a target element.

    Marks the element with extension metadata referencing the target.

    Parameters
    ----------
    project:
        The project dictionary.
    sketch_index:
        Index of the target sketch.
    elem_id:
        ID of the element to extend.
    target_elem_id:
        ID of the target element to extend towards.

    Returns
    -------
    Dict[str, Any]
        The updated element dictionary with extension metadata.
    """
    _validate_project(project)
    sketch = _get_sketch(project, sketch_index)

    if sketch["closed"]:
        raise ValueError("Cannot extend elements in a closed sketch")

    existing_ids = {el["id"] for el in sketch["elements"]}
    if elem_id not in existing_ids:
        raise KeyError(f"Element ID {elem_id} not found in sketch")
    if target_elem_id not in existing_ids:
        raise KeyError(f"Target element ID {target_elem_id} not found in sketch")
    if elem_id == target_elem_id:
        raise ValueError("Element and target must be different")

    for elem in sketch["elements"]:
        if elem["id"] == elem_id:
            elem["extended"] = True
            elem["extend_target_id"] = target_elem_id
            return elem

    raise KeyError(f"Element ID {elem_id} not found in sketch")


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


def validate_sketch(
    project: Dict[str, Any],
    sketch_index: int,
) -> Dict[str, Any]:
    """Check sketch validity.

    Performs basic validation: ensures the sketch has elements and that
    all constraint element references are valid.

    Parameters
    ----------
    project:
        The project dictionary.
    sketch_index:
        Index of the target sketch.

    Returns
    -------
    Dict[str, Any]
        Validation result with ``valid`` flag and list of ``issues``.
    """
    _validate_project(project)
    sketch = _get_sketch(project, sketch_index)

    issues: List[str] = []
    elements = sketch.get("elements", [])
    constraints = sketch.get("constraints", [])

    if not elements:
        issues.append("Sketch has no elements")

    existing_ids = {el["id"] for el in elements}
    for c in constraints:
        for eid in c.get("elements", []):
            if eid not in existing_ids:
                issues.append(
                    f"Constraint {c['id']} references non-existent element {eid}"
                )

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "element_count": len(elements),
        "constraint_count": len(constraints),
    }


def solve_status(
    project: Dict[str, Any],
    sketch_index: int,
) -> Dict[str, Any]:
    """Return the constraint solving status of a sketch.

    Provides an estimate of the degrees of freedom (DOF) and whether the
    sketch is fully, under, or over constrained.

    Parameters
    ----------
    project:
        The project dictionary.
    sketch_index:
        Index of the target sketch.

    Returns
    -------
    Dict[str, Any]
        Status containing ``status``, ``element_count``,
        ``constraint_count``, and ``dof`` (estimated degrees of freedom).
    """
    _validate_project(project)
    sketch = _get_sketch(project, sketch_index)

    elements = sketch.get("elements", [])
    constraints = sketch.get("constraints", [])

    # Rough DOF estimation: each element contributes DOF based on type,
    # each constraint removes 1 DOF.
    dof_per_type = {
        "point": 2,
        "line": 4,
        "circle": 3,
        "arc": 5,
        "ellipse": 5,
        "bspline": 2,  # per pole, but simplified
    }

    total_dof = 0
    for el in elements:
        etype = el.get("type", "line")
        if etype == "bspline":
            total_dof += len(el.get("poles", [])) * 2
        else:
            total_dof += dof_per_type.get(etype, 4)

    total_dof -= len(constraints)

    if total_dof == 0:
        status = "fully_constrained"
    elif total_dof > 0:
        status = "under_constrained"
    else:
        status = "over_constrained"

    return {
        "status": status,
        "element_count": len(elements),
        "constraint_count": len(constraints),
        "dof": total_dof,
    }


def set_construction(
    project: Dict[str, Any],
    sketch_index: int,
    elem_id: int,
    flag: bool = True,
) -> Dict[str, Any]:
    """Toggle the construction geometry flag on an element.

    Construction geometry is used as reference and does not form part of
    the sketch profile.

    Parameters
    ----------
    project:
        The project dictionary.
    sketch_index:
        Index of the target sketch.
    elem_id:
        ID of the element.
    flag:
        ``True`` to mark as construction, ``False`` to unmark.

    Returns
    -------
    Dict[str, Any]
        The updated element dictionary.
    """
    _validate_project(project)
    sketch = _get_sketch(project, sketch_index)

    for elem in sketch["elements"]:
        if elem["id"] == elem_id:
            elem["construction"] = bool(flag)
            return elem

    raise KeyError(f"Element ID {elem_id} not found in sketch")


def project_external(
    project: Dict[str, Any],
    sketch_index: int,
    part_index: int,
    edge_ref: Optional[str] = None,
    mode: str = "projection",
) -> Dict[str, Any]:
    """Project external geometry into the sketch as a reference element.

    Parameters
    ----------
    project:
        The project dictionary.
    sketch_index:
        Index of the target sketch.
    part_index:
        Index of the body/part containing the external geometry.
    edge_ref:
        Optional edge reference identifier (e.g. ``"Edge1"``).
        If ``None``, the entire shape is projected.
    mode:
        External geometry mode: ``"projection"`` or ``"reference"``
        (FreeCAD 1.1).

    Returns
    -------
    Dict[str, Any]
        The newly created external reference element.
    """
    _validate_project(project)
    sketch = _get_sketch(project, sketch_index)

    if sketch["closed"]:
        raise ValueError("Cannot add elements to a closed sketch")

    valid_modes = {"projection", "reference"}
    if mode not in valid_modes:
        raise ValueError(
            f"Invalid mode '{mode}'. Must be one of: {', '.join(sorted(valid_modes))}"
        )

    element: Dict[str, Any] = {
        "id": _next_element_id(sketch),
        "type": "external_reference",
        "part_index": int(part_index),
        "edge_ref": edge_ref,
        "mode": mode,
        "construction": True,
    }

    sketch["elements"].append(element)
    return element


def intersection_external(
    project: Dict[str, Any],
    sketch_index: int,
    body_index: int,
) -> Dict[str, Any]:
    """Create external geometry from sketch-plane intersection with a body (FreeCAD 1.1).

    Generates external geometry elements at the intersection of the sketch
    plane with the specified body geometry.

    Parameters
    ----------
    project:
        The project dictionary.
    sketch_index:
        Index of the target sketch.
    body_index:
        Index of the body to intersect with the sketch plane.

    Returns
    -------
    Dict[str, Any]
        The newly created intersection reference element.
    """
    _validate_project(project)
    sketch = _get_sketch(project, sketch_index)

    if sketch["closed"]:
        raise ValueError("Cannot add elements to a closed sketch")

    element: Dict[str, Any] = {
        "id": _next_element_id(sketch),
        "type": "intersection_reference",
        "body_index": int(body_index),
        "construction": True,
    }

    sketch["elements"].append(element)
    return element


def add_external_from_face(
    project: Dict[str, Any],
    sketch_index: int,
    part_index: int,
    face_ref: str,
) -> Dict[str, Any]:
    """Create external geometry from a face selection (FreeCAD 1.1).

    Projects the boundary of the referenced face onto the sketch plane.

    Parameters
    ----------
    project:
        The project dictionary.
    sketch_index:
        Index of the target sketch.
    part_index:
        Index of the body/part containing the face.
    face_ref:
        Face reference identifier (e.g. ``"Face1"``).

    Returns
    -------
    Dict[str, Any]
        The newly created face reference element.
    """
    _validate_project(project)
    sketch = _get_sketch(project, sketch_index)

    if sketch["closed"]:
        raise ValueError("Cannot add elements to a closed sketch")

    element: Dict[str, Any] = {
        "id": _next_element_id(sketch),
        "type": "face_reference",
        "part_index": int(part_index),
        "face_ref": face_ref,
        "construction": True,
    }

    sketch["elements"].append(element)
    return element
