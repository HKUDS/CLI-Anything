"""FreeCAD CLI - Draft 2D workbench module.

Provides creation, annotation, transformation, array, copy, and modification
functions for 2D drafting objects.  All objects are stored in
``project["draft_objects"]`` via
:func:`~cli_anything.freecad.core.document.ensure_collection`.
"""

from copy import deepcopy
from typing import Any, Dict, List, Optional, Union

from cli_anything.freecad.core.document import ensure_collection
from cli_anything.freecad.utils.compat import require_version, V1_1

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _next_id(project: Dict[str, Any]) -> int:
    """Return the next available integer ID for draft objects."""
    items = project.get("draft_objects", [])
    if not items:
        return 1
    return max(item["id"] for item in items) + 1


def _unique_name(project: Dict[str, Any], base: str) -> str:
    """Return a unique name derived from *base* inside ``project["draft_objects"]``."""
    existing = {item["name"] for item in project.get("draft_objects", [])}
    if base not in existing:
        return base
    counter = 2
    while f"{base}_{counter}" in existing:
        counter += 1
    return f"{base}_{counter}"


def _validate_vec3(value: Any, label: str) -> List[float]:
    """Validate that *value* is a list of exactly three numbers."""
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{label} must be a list of 3 numbers, got {type(value).__name__}")
    if len(value) != 3:
        raise ValueError(f"{label} must have exactly 3 elements, got {len(value)}")
    try:
        return [float(v) for v in value]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} elements must be numeric: {exc}") from exc


def _validate_vec2(value: Any, label: str) -> List[float]:
    """Validate that *value* is a list of exactly two numbers."""
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{label} must be a list of 2 numbers, got {type(value).__name__}")
    if len(value) != 2:
        raise ValueError(f"{label} must have exactly 2 elements, got {len(value)}")
    try:
        return [float(v) for v in value]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} elements must be numeric: {exc}") from exc


def _get_draft(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Return the draft object at *index*, raising ``IndexError`` if out of range."""
    objs = project.get("draft_objects", [])
    if not isinstance(index, int) or index < 0 or index >= len(objs):
        raise IndexError(
            f"Draft object index {index} out of range (0..{len(objs) - 1})"
        )
    return objs[index]


def _make_draft(
    project: Dict[str, Any],
    obj_type: str,
    name: Optional[str],
    properties: Dict[str, Any],
    position: Optional[List[float]] = None,
    rotation: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Create a draft object, append it, and return it."""
    objs = ensure_collection(project, "draft_objects")

    if name is None:
        name = _unique_name(project, obj_type.capitalize())

    pos = _validate_vec3(position, "position") if position is not None else [0.0, 0.0, 0.0]
    rot = _validate_vec3(rotation, "rotation") if rotation is not None else [0.0, 0.0, 0.0]

    draft_obj: Dict[str, Any] = {
        "id": _next_id(project),
        "name": name,
        "type": obj_type,
        "properties": properties,
        "placement": {
            "position": pos,
            "rotation": rot,
        },
        "visible": True,
    }

    objs.append(draft_obj)
    return draft_obj


# ---------------------------------------------------------------------------
# Creation functions (10)
# ---------------------------------------------------------------------------


def draft_wire(
    project: Dict[str, Any],
    points: List[List[float]],
    closed: bool = False,
    name: Optional[str] = None,
    position: Optional[List[float]] = None,
    rotation: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Create a polyline (wire) from a list of 3D points.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    points : list[list[float]]
        Ordered list of ``[x, y, z]`` vertices.
    closed : bool
        Whether to close the wire (default ``False``).
    name : str or None
        Label for the object.
    position, rotation : list[float] or None
        Placement overrides.

    Returns
    -------
    dict
        The newly created draft object.
    """
    if not isinstance(points, (list, tuple)) or len(points) < 2:
        raise ValueError("wire requires at least 2 points")
    validated = [_validate_vec3(p, f"points[{i}]") for i, p in enumerate(points)]
    return _make_draft(project, "wire", name, {
        "points": validated,
        "closed": bool(closed),
    }, position, rotation)


def draft_rectangle(
    project: Dict[str, Any],
    length: float = 10.0,
    height: float = 10.0,
    name: Optional[str] = None,
    position: Optional[List[float]] = None,
    rotation: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Create a 2D rectangle.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    length : float
        X-dimension (default ``10``).
    height : float
        Y-dimension (default ``10``).

    Returns
    -------
    dict
        The newly created draft object.
    """
    if length <= 0 or height <= 0:
        raise ValueError("length and height must be positive numbers")
    return _make_draft(project, "rectangle", name, {
        "length": float(length),
        "height": float(height),
    }, position, rotation)


def draft_circle(
    project: Dict[str, Any],
    radius: float = 5.0,
    name: Optional[str] = None,
    position: Optional[List[float]] = None,
    rotation: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Create a 2D circle.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    radius : float
        Circle radius (default ``5``).

    Returns
    -------
    dict
        The newly created draft object.
    """
    if radius <= 0:
        raise ValueError("radius must be a positive number")
    return _make_draft(project, "circle", name, {
        "radius": float(radius),
    }, position, rotation)


def draft_ellipse(
    project: Dict[str, Any],
    major_radius: float = 10.0,
    minor_radius: float = 5.0,
    name: Optional[str] = None,
    position: Optional[List[float]] = None,
    rotation: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Create a 2D ellipse.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    major_radius : float
        Semi-major axis (default ``10``).
    minor_radius : float
        Semi-minor axis (default ``5``).

    Returns
    -------
    dict
        The newly created draft object.
    """
    if major_radius <= 0 or minor_radius <= 0:
        raise ValueError("major_radius and minor_radius must be positive")
    if minor_radius > major_radius:
        raise ValueError("minor_radius must not exceed major_radius")
    return _make_draft(project, "ellipse", name, {
        "major_radius": float(major_radius),
        "minor_radius": float(minor_radius),
    }, position, rotation)


def draft_polygon(
    project: Dict[str, Any],
    sides: int = 6,
    radius: float = 5.0,
    name: Optional[str] = None,
    position: Optional[List[float]] = None,
    rotation: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Create a regular polygon.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    sides : int
        Number of sides (default ``6``).  Must be >= 3.
    radius : float
        Circumscribed radius (default ``5``).

    Returns
    -------
    dict
        The newly created draft object.
    """
    if not isinstance(sides, int) or sides < 3:
        raise ValueError("sides must be an integer >= 3")
    if radius <= 0:
        raise ValueError("radius must be a positive number")
    return _make_draft(project, "polygon", name, {
        "sides": sides,
        "radius": float(radius),
    }, position, rotation)


def draft_bspline(
    project: Dict[str, Any],
    points: List[List[float]],
    closed: bool = False,
    name: Optional[str] = None,
    position: Optional[List[float]] = None,
    rotation: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Create a B-spline curve through a list of points.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    points : list[list[float]]
        Control / through-points (minimum 2).
    closed : bool
        Whether to close the spline (default ``False``).

    Returns
    -------
    dict
        The newly created draft object.
    """
    if not isinstance(points, (list, tuple)) or len(points) < 2:
        raise ValueError("bspline requires at least 2 points")
    validated = [_validate_vec3(p, f"points[{i}]") for i, p in enumerate(points)]
    return _make_draft(project, "bspline", name, {
        "points": validated,
        "closed": bool(closed),
    }, position, rotation)


def draft_bezier(
    project: Dict[str, Any],
    points: List[List[float]],
    name: Optional[str] = None,
    position: Optional[List[float]] = None,
    rotation: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Create a Bezier curve from control points.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    points : list[list[float]]
        Control points (minimum 2).

    Returns
    -------
    dict
        The newly created draft object.
    """
    if not isinstance(points, (list, tuple)) or len(points) < 2:
        raise ValueError("bezier requires at least 2 control points")
    validated = [_validate_vec3(p, f"points[{i}]") for i, p in enumerate(points)]
    return _make_draft(project, "bezier", name, {
        "points": validated,
    }, position, rotation)


def draft_point(
    project: Dict[str, Any],
    point: Optional[List[float]] = None,
    name: Optional[str] = None,
    position: Optional[List[float]] = None,
    rotation: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Create a single draft point.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    point : list[float] or None
        ``[x, y, z]`` coordinate.  Defaults to ``[0, 0, 0]``.

    Returns
    -------
    dict
        The newly created draft object.
    """
    pt = _validate_vec3(point, "point") if point is not None else [0.0, 0.0, 0.0]
    return _make_draft(project, "point", name, {
        "point": pt,
    }, position, rotation)


def draft_text(
    project: Dict[str, Any],
    text: str,
    name: Optional[str] = None,
    position: Optional[List[float]] = None,
    rotation: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Create a draft text annotation.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    text : str
        The text content to display.

    Returns
    -------
    dict
        The newly created draft object.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must be a non-empty string")
    return _make_draft(project, "text", name, {
        "text": text.strip(),
    }, position, rotation)


def draft_shapestring(
    project: Dict[str, Any],
    text: str,
    font_file: str,
    size: float = 10.0,
    font_path_relative: bool = False,
    name: Optional[str] = None,
    position: Optional[List[float]] = None,
    rotation: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Create a ShapeString (text extruded into wire outlines).

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    text : str
        The text content.
    font_file : str
        Path to the TrueType font file.
    size : float
        Font height (default ``10``).
    font_path_relative : bool
        Whether *font_file* is a relative path (default ``False``).

    Returns
    -------
    dict
        The newly created draft object.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must be a non-empty string")
    if not isinstance(font_file, str) or not font_file.strip():
        raise ValueError("font_file must be a non-empty string")
    if size <= 0:
        raise ValueError("size must be a positive number")
    return _make_draft(project, "shapestring", name, {
        "text": text.strip(),
        "font_file": font_file.strip(),
        "size": float(size),
        "font_path_relative": bool(font_path_relative),
    }, position, rotation)


# ---------------------------------------------------------------------------
# Annotation functions (3)
# ---------------------------------------------------------------------------


def draft_dimension(
    project: Dict[str, Any],
    start: List[float],
    end: List[float],
    dim_line: Optional[List[float]] = None,
    name: Optional[str] = None,
    position: Optional[List[float]] = None,
    rotation: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Create a linear dimension annotation.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    start : list[float]
        ``[x, y, z]`` start point.
    end : list[float]
        ``[x, y, z]`` end point.
    dim_line : list[float] or None
        Point through which the dimension line passes.

    Returns
    -------
    dict
        The newly created draft object.
    """
    s = _validate_vec3(start, "start")
    e = _validate_vec3(end, "end")
    dl = _validate_vec3(dim_line, "dim_line") if dim_line is not None else [0.0, 0.0, 0.0]
    return _make_draft(project, "dimension", name, {
        "start": s,
        "end": e,
        "dim_line": dl,
    }, position, rotation)


def draft_label(
    project: Dict[str, Any],
    target_point: List[float],
    text: str = "",
    name: Optional[str] = None,
    position: Optional[List[float]] = None,
    rotation: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Create a label annotation pointing to *target_point*.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    target_point : list[float]
        ``[x, y, z]`` point the label arrow targets.
    text : str
        Label text content.

    Returns
    -------
    dict
        The newly created draft object.
    """
    tp = _validate_vec3(target_point, "target_point")
    return _make_draft(project, "label", name, {
        "target_point": tp,
        "text": text,
    }, position, rotation)


def draft_hatch(
    project: Dict[str, Any],
    target_index: int,
    pattern: str = "ANSI31",
    scale: float = 1.0,
    name: Optional[str] = None,
    position: Optional[List[float]] = None,
    rotation: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Apply a hatch pattern to a draft object face.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    target_index : int
        Index of the draft object to hatch.
    pattern : str
        Hatch pattern name (default ``"ANSI31"``).
    scale : float
        Pattern scale factor (default ``1``).

    Returns
    -------
    dict
        The newly created draft object.
    """
    _get_draft(project, target_index)  # validate
    if scale <= 0:
        raise ValueError("scale must be a positive number")
    return _make_draft(project, "hatch", name, {
        "target_index": target_index,
        "pattern": pattern,
        "scale": float(scale),
    }, position, rotation)


# ---------------------------------------------------------------------------
# Transform functions (5)
# ---------------------------------------------------------------------------


def draft_move(
    project: Dict[str, Any],
    index: int,
    vector: List[float],
    copy: bool = False,
) -> Dict[str, Any]:
    """Move a draft object by *vector*, optionally creating a copy.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    index : int
        Index of the draft object.
    vector : list[float]
        ``[dx, dy, dz]`` translation vector.
    copy : bool
        If ``True`` create a moved copy instead of modifying in-place.

    Returns
    -------
    dict
        The moved (or copied) draft object.
    """
    obj = _get_draft(project, index)
    vec = _validate_vec3(vector, "vector")

    if copy:
        new_obj = deepcopy(obj)
        new_obj["id"] = _next_id(project)
        new_obj["name"] = _unique_name(project, f"{obj['name']}_Copy")
        pos = new_obj["placement"]["position"]
        new_obj["placement"]["position"] = [pos[i] + vec[i] for i in range(3)]
        ensure_collection(project, "draft_objects").append(new_obj)
        return new_obj

    pos = obj["placement"]["position"]
    obj["placement"]["position"] = [pos[i] + vec[i] for i in range(3)]
    return obj


def draft_rotate(
    project: Dict[str, Any],
    index: int,
    angle: float,
    axis: Optional[List[float]] = None,
    center: Optional[List[float]] = None,
    copy: bool = False,
) -> Dict[str, Any]:
    """Rotate a draft object by *angle* degrees around *axis*.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    index : int
        Index of the draft object.
    angle : float
        Rotation angle in degrees.
    axis : list[float] or None
        Rotation axis (default Z-axis ``[0, 0, 1]``).
    center : list[float] or None
        Center of rotation (default origin).
    copy : bool
        If ``True`` create a rotated copy.

    Returns
    -------
    dict
        The rotated (or copied) draft object.
    """
    obj = _get_draft(project, index)
    ax = _validate_vec3(axis, "axis") if axis is not None else [0.0, 0.0, 1.0]
    ctr = _validate_vec3(center, "center") if center is not None else [0.0, 0.0, 0.0]

    if copy:
        new_obj = deepcopy(obj)
        new_obj["id"] = _next_id(project)
        new_obj["name"] = _unique_name(project, f"{obj['name']}_Copy")
        rot = new_obj["placement"]["rotation"]
        new_obj["placement"]["rotation"] = [rot[0], rot[1], rot[2] + float(angle)]
        ensure_collection(project, "draft_objects").append(new_obj)
        return new_obj

    obj["placement"]["rotation"] = [
        obj["placement"]["rotation"][0],
        obj["placement"]["rotation"][1],
        obj["placement"]["rotation"][2] + float(angle),
    ]
    return obj


def draft_scale(
    project: Dict[str, Any],
    index: int,
    scale: Union[float, List[float]] = 2.0,
    center: Optional[List[float]] = None,
    copy: bool = False,
) -> Dict[str, Any]:
    """Scale a draft object.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    index : int
        Index of the draft object.
    scale : float or list[float]
        Uniform scale factor, or ``[sx, sy, sz]`` anisotropic scale.
    center : list[float] or None
        Center of scaling (default origin).
    copy : bool
        If ``True`` create a scaled copy.

    Returns
    -------
    dict
        The scaled (or copied) draft object.
    """
    obj = _get_draft(project, index)
    ctr = _validate_vec3(center, "center") if center is not None else [0.0, 0.0, 0.0]

    if isinstance(scale, (int, float)):
        if scale == 0:
            raise ValueError("scale must be non-zero")
        scale_vec = [float(scale)] * 3
    else:
        scale_vec = _validate_vec3(scale, "scale")
        if any(s == 0 for s in scale_vec):
            raise ValueError("scale components must be non-zero")

    if copy:
        new_obj = deepcopy(obj)
        new_obj["id"] = _next_id(project)
        new_obj["name"] = _unique_name(project, f"{obj['name']}_Scaled")
        new_obj["properties"]["_scale"] = scale_vec
        new_obj["properties"]["_scale_center"] = ctr
        ensure_collection(project, "draft_objects").append(new_obj)
        return new_obj

    obj["properties"]["_scale"] = scale_vec
    obj["properties"]["_scale_center"] = ctr
    return obj


def draft_mirror(
    project: Dict[str, Any],
    index: int,
    point: Optional[List[float]] = None,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a mirrored copy of a draft object.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    index : int
        Index of the draft object to mirror.
    point : list[float] or None
        Mirror reference point (default origin).
    name : str or None
        Label for the mirrored copy.

    Returns
    -------
    dict
        The newly created mirrored draft object.
    """
    obj = _get_draft(project, index)
    pt = _validate_vec3(point, "point") if point is not None else [0.0, 0.0, 0.0]

    new_obj = deepcopy(obj)
    new_obj["id"] = _next_id(project)
    if name is None:
        name = _unique_name(project, f"{obj['name']}_Mirror")
    new_obj["name"] = name
    new_obj["properties"]["_mirror_point"] = pt

    ensure_collection(project, "draft_objects").append(new_obj)
    return new_obj


def draft_offset(
    project: Dict[str, Any],
    index: int,
    distance: float = 1.0,
    copy: bool = True,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Offset a draft object by *distance*.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    index : int
        Index of the draft object.
    distance : float
        Offset distance (default ``1``).
    copy : bool
        If ``True`` (default) create an offset copy.
    name : str or None
        Label for the offset copy.

    Returns
    -------
    dict
        The offset draft object.
    """
    obj = _get_draft(project, index)
    if distance == 0:
        raise ValueError("distance must be non-zero")

    if copy:
        new_obj = deepcopy(obj)
        new_obj["id"] = _next_id(project)
        if name is None:
            name = _unique_name(project, f"{obj['name']}_Offset")
        new_obj["name"] = name
        new_obj["properties"]["_offset_distance"] = float(distance)
        ensure_collection(project, "draft_objects").append(new_obj)
        return new_obj

    obj["properties"]["_offset_distance"] = float(distance)
    return obj


# ---------------------------------------------------------------------------
# Array functions (3)
# ---------------------------------------------------------------------------


def draft_array_linear(
    project: Dict[str, Any],
    index: int,
    x_count: int = 2,
    y_count: int = 1,
    x_interval: float = 20.0,
    y_interval: float = 20.0,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a linear (rectangular) array of a draft object.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    index : int
        Index of the source draft object.
    x_count : int
        Number of copies along X (default ``2``).
    y_count : int
        Number of copies along Y (default ``1``).
    x_interval : float
        Spacing along X (default ``20``).
    y_interval : float
        Spacing along Y (default ``20``).

    Returns
    -------
    dict
        The newly created array draft object.
    """
    obj = _get_draft(project, index)
    if x_count < 1 or y_count < 1:
        raise ValueError("x_count and y_count must be >= 1")
    return _make_draft(project, "array_linear", name, {
        "source_id": obj["id"],
        "x_count": int(x_count),
        "y_count": int(y_count),
        "x_interval": float(x_interval),
        "y_interval": float(y_interval),
    })


def draft_array_polar(
    project: Dict[str, Any],
    index: int,
    count: int = 6,
    angle: float = 360.0,
    center: Optional[List[float]] = None,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a polar (circular) array of a draft object.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    index : int
        Index of the source draft object.
    count : int
        Number of copies (default ``6``).
    angle : float
        Total sweep angle in degrees (default ``360``).
    center : list[float] or None
        Center of the array (default origin).

    Returns
    -------
    dict
        The newly created array draft object.
    """
    obj = _get_draft(project, index)
    if count < 2:
        raise ValueError("count must be >= 2")
    ctr = _validate_vec3(center, "center") if center is not None else [0.0, 0.0, 0.0]
    return _make_draft(project, "array_polar", name, {
        "source_id": obj["id"],
        "count": int(count),
        "angle": float(angle),
        "center": ctr,
    })


def draft_array_path(
    project: Dict[str, Any],
    index: int,
    path_index: int,
    count: int = 4,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Create an array of a draft object along a path.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    index : int
        Index of the source draft object.
    path_index : int
        Index of the path draft object (wire, bspline, etc.).
    count : int
        Number of copies along the path (default ``4``).

    Returns
    -------
    dict
        The newly created array draft object.
    """
    obj = _get_draft(project, index)
    path_obj = _get_draft(project, path_index)
    if count < 2:
        raise ValueError("count must be >= 2")
    return _make_draft(project, "array_path", name, {
        "source_id": obj["id"],
        "path_id": path_obj["id"],
        "count": int(count),
    })


# ---------------------------------------------------------------------------
# Copy functions (2)
# ---------------------------------------------------------------------------


def draft_copy(
    project: Dict[str, Any],
    index: int,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a simple copy of a draft object.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    index : int
        Index of the draft object to copy.
    name : str or None
        Label for the copy.

    Returns
    -------
    dict
        The newly created copy.
    """
    obj = _get_draft(project, index)
    new_obj = deepcopy(obj)
    new_obj["id"] = _next_id(project)
    if name is None:
        name = _unique_name(project, f"{obj['name']}_Copy")
    new_obj["name"] = name

    ensure_collection(project, "draft_objects").append(new_obj)
    return new_obj


def draft_clone(
    project: Dict[str, Any],
    index: int,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a clone (linked copy) of a draft object.

    Unlike :func:`draft_copy`, a clone maintains a parametric reference
    to the source object.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    index : int
        Index of the source draft object.
    name : str or None
        Label for the clone.

    Returns
    -------
    dict
        The newly created clone draft object.
    """
    obj = _get_draft(project, index)
    if name is None:
        name = _unique_name(project, f"{obj['name']}_Clone")
    return _make_draft(project, "clone", name, {
        "source_id": obj["id"],
    })


# ---------------------------------------------------------------------------
# Modify functions (7)
# ---------------------------------------------------------------------------


def draft_upgrade(
    project: Dict[str, Any],
    index: int,
) -> Dict[str, Any]:
    """Upgrade a draft object (e.g. wires -> face).

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    index : int
        Index of the draft object to upgrade.

    Returns
    -------
    dict
        The updated draft object.
    """
    obj = _get_draft(project, index)
    obj["properties"]["_upgraded"] = True
    return obj


def draft_downgrade(
    project: Dict[str, Any],
    index: int,
) -> Dict[str, Any]:
    """Downgrade a draft object (e.g. face -> wires).

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    index : int
        Index of the draft object to downgrade.

    Returns
    -------
    dict
        The updated draft object.
    """
    obj = _get_draft(project, index)
    obj["properties"]["_downgraded"] = True
    return obj


def draft_trim(
    project: Dict[str, Any],
    index: int,
    point: List[float],
) -> Dict[str, Any]:
    """Trim a draft object at the given point.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    index : int
        Index of the draft object to trim.
    point : list[float]
        ``[x, y, z]`` trim location.

    Returns
    -------
    dict
        The updated draft object.
    """
    obj = _get_draft(project, index)
    pt = _validate_vec3(point, "point")
    obj["properties"]["_trim_point"] = pt
    return obj


def draft_join(
    project: Dict[str, Any],
    indices: List[int],
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Join multiple draft wires into one.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    indices : list[int]
        Indices of the draft objects to join.
    name : str or None
        Label for the joined result.

    Returns
    -------
    dict
        The newly created joined draft object.

    Raises
    ------
    ValueError
        If fewer than two indices are provided.
    """
    if not isinstance(indices, (list, tuple)) or len(indices) < 2:
        raise ValueError("At least two draft object indices are required for join")
    source_ids = []
    for idx in indices:
        obj = _get_draft(project, idx)
        source_ids.append(obj["id"])
    return _make_draft(project, "join", name, {
        "source_ids": source_ids,
    })


def draft_extrude(
    project: Dict[str, Any],
    index: int,
    vector: Optional[List[float]] = None,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Extrude a 2D draft object into a 3D solid along *vector*.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    index : int
        Index of the draft object to extrude.
    vector : list[float] or None
        Extrusion direction and magnitude (default ``[0, 0, 10]``).
    name : str or None
        Label for the extruded result.

    Returns
    -------
    dict
        The newly created extrusion draft object.
    """
    obj = _get_draft(project, index)
    vec = _validate_vec3(vector, "vector") if vector is not None else [0.0, 0.0, 10.0]
    return _make_draft(project, "extrude", name, {
        "source_id": obj["id"],
        "vector": vec,
    })


def draft_fillet_2d(
    project: Dict[str, Any],
    index: int,
    radius: float = 1.0,
    edges: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """Apply a 2D fillet (rounding) to the vertices of a draft object.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    index : int
        Index of the draft object.
    radius : float
        Fillet radius (default ``1``).
    edges : list[int] or None
        When provided, fillet only these edge indices instead of all vertices.

    Returns
    -------
    dict
        The updated draft object.
    """
    if radius <= 0:
        raise ValueError("radius must be a positive number")
    obj = _get_draft(project, index)
    obj["properties"]["_fillet_radius"] = float(radius)
    if edges is not None:
        require_version(V1_1, "edge-selective 2D fillet")
        obj["properties"]["_fillet_edges"] = list(edges)
    return obj


def draft_to_sketch(
    project: Dict[str, Any],
    index: int,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Convert a draft object to a sketch in ``project["sketches"]``.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    index : int
        Index of the draft object to convert.
    name : str or None
        Label for the resulting sketch.

    Returns
    -------
    dict
        The newly created sketch entry.
    """
    obj = _get_draft(project, index)
    sketches = ensure_collection(project, "sketches")

    if name is None:
        base = f"{obj['name']}_Sketch"
        existing = {s["name"] for s in sketches}
        if base in existing:
            counter = 2
            while f"{base}_{counter}" in existing:
                counter += 1
            base = f"{base}_{counter}"
        name = base

    sketch_id = max((s["id"] for s in sketches), default=0) + 1

    sketch: Dict[str, Any] = {
        "id": sketch_id,
        "name": name,
        "type": "from_draft",
        "source_draft_id": obj["id"],
        "elements": [],
        "constraints": [],
    }

    sketches.append(sketch)
    return sketch


# ---------------------------------------------------------------------------
# Manage functions (3)
# ---------------------------------------------------------------------------


def list_draft_objects(project: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return all draft objects in the project.

    Parameters
    ----------
    project : dict
        The project state dictionary.

    Returns
    -------
    list[dict]
        List of draft object dictionaries.
    """
    return project.get("draft_objects", [])


def get_draft_object(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Return the draft object at *index* without removing it.

    Parameters
    ----------
    project : dict
        The project state dictionary.
    index : int
        Index of the draft object.

    Returns
    -------
    dict
        The draft object dictionary.
    """
    return _get_draft(project, index)


def remove_draft_object(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Remove and return the draft object at *index*.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    index : int
        Index of the draft object to remove.

    Returns
    -------
    dict
        The removed draft object.
    """
    objs = project.get("draft_objects", [])
    if not isinstance(index, int) or index < 0 or index >= len(objs):
        raise IndexError(
            f"Draft object index {index} out of range (0..{len(objs) - 1})"
        )
    return objs.pop(index)
