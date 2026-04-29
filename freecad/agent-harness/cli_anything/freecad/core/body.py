"""
PartDesign body module for the FreeCAD CLI harness.

Provides creation of PartDesign bodies and additive/subtractive features
such as pad, pocket, fillet, chamfer, and revolution.
"""

from typing import Any, Dict, List, Optional, Union


# ---------------------------------------------------------------------------
# Valid constants
# ---------------------------------------------------------------------------

VALID_FEATURE_TYPES = {
    "pad", "pocket", "fillet", "chamfer", "revolution",
    "additive_loft", "additive_pipe", "additive_helix",
    "additive_box", "additive_cylinder", "additive_sphere",
    "additive_cone", "additive_torus", "additive_wedge",
    "groove", "subtractive_loft", "subtractive_pipe", "subtractive_helix",
    "subtractive_box", "subtractive_cylinder", "subtractive_sphere",
    "subtractive_cone", "subtractive_torus", "subtractive_wedge",
    "draft", "thickness",
    "linear_pattern", "polar_pattern", "mirrored", "multi_transform",
    "hole", "datum_plane", "datum_line", "datum_point", "shape_binder",
    "local_coordinate_system",
}
VALID_REVOLUTION_AXES = {"X", "Y", "Z"}
VALID_PATTERN_PLANES = {"XY", "XZ", "YZ"}
VALID_THREAD_STANDARDS = {"metric", "BSW", "BSF", "BSP", "NPT"}
VALID_ATTACHMENT_MODES = {
    "flat_face", "normal_to_edge", "translate", "object_xyz",
    "concentric", "tangent_plane", "inertial_cs",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _next_id(project: Dict[str, Any], collection_key: str = "bodies") -> int:
    """Generate the next unique ID for a collection."""
    items = project.get(collection_key, [])
    existing_ids = [item.get("id", 0) for item in items]
    return max(existing_ids, default=-1) + 1


def _unique_name(project: Dict[str, Any], base_name: str, collection_key: str = "bodies") -> str:
    """Generate a unique name within a collection."""
    items = project.get(collection_key, [])
    existing_names = {item.get("name", "") for item in items}
    if base_name not in existing_names:
        return base_name
    counter = 1
    while f"{base_name}.{counter:03d}" in existing_names:
        counter += 1
    return f"{base_name}.{counter:03d}"


def _next_feature_id(body: Dict[str, Any]) -> int:
    """Generate the next unique feature ID within a body."""
    features = body.get("features", [])
    existing_ids = [f.get("id", 0) for f in features]
    return max(existing_ids, default=-1) + 1


def _validate_project(project: Dict[str, Any]) -> None:
    """Raise ``ValueError`` if *project* is not a valid dict with required collections."""
    if not isinstance(project, dict):
        raise ValueError("Project must be a dictionary")
    if "bodies" not in project:
        raise ValueError("Project is missing 'bodies' collection")
    if not isinstance(project["bodies"], list):
        raise ValueError("Project 'bodies' must be a list")


def _get_body(project: Dict[str, Any], body_index: int) -> Dict[str, Any]:
    """Return body at *body_index* or raise ``IndexError``."""
    bodies = project["bodies"]
    if body_index < 0 or body_index >= len(bodies):
        raise IndexError(
            f"Body index {body_index} out of range (0-{len(bodies) - 1})"
        )
    return bodies[body_index]


def _validate_sketch_index(project: Dict[str, Any], sketch_index: int) -> Dict[str, Any]:
    """Validate that a sketch index exists and return the sketch."""
    sketches = project.get("sketches", [])
    if not isinstance(sketches, list):
        raise ValueError("Project 'sketches' must be a list")
    if sketch_index < 0 or sketch_index >= len(sketches):
        raise IndexError(
            f"Sketch index {sketch_index} out of range (0-{len(sketches) - 1})"
        )
    return sketches[sketch_index]


def _validate_vec3(value: Optional[List[float]], label: str) -> Optional[List[float]]:
    """Validate and normalize a 3-component vector."""
    if value is None:
        return None
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f"{label} must be a list of 3 numbers")
    return [float(component) for component in value]


def _normalize_feature_placement(
    position: Optional[List[float]] = None,
    rotation: Optional[List[float]] = None,
) -> Optional[Dict[str, List[float]]]:
    """Normalize optional position/rotation into a placement payload."""
    pos = _validate_vec3(position, "position")
    rot = _validate_vec3(rotation, "rotation")
    if pos is None and rot is None:
        return None
    return {
        "position": pos or [0.0, 0.0, 0.0],
        "rotation": rot or [0.0, 0.0, 0.0],
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_body(
    project: Dict[str, Any],
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new PartDesign body.

    Parameters
    ----------
    project:
        The project dictionary.
    name:
        Optional body name.  Auto-generated if ``None``.

    Returns
    -------
    Dict[str, Any]
        The newly created body dictionary.
    """
    _validate_project(project)

    base_name = name if name else "Body"
    body_name = _unique_name(project, base_name)

    body: Dict[str, Any] = {
        "id": _next_id(project),
        "name": body_name,
        "features": [],
        "base_sketch_index": None,
    }

    project["bodies"].append(body)
    return body


def pad(
    project: Dict[str, Any],
    body_index: int,
    sketch_index: int,
    length: float = 10.0,
    symmetric: bool = False,
    reversed: bool = False,
) -> Dict[str, Any]:
    """Add a pad (extrusion) feature to a body based on a sketch.

    Parameters
    ----------
    project:
        The project dictionary.
    body_index:
        Index of the target body.
    sketch_index:
        Index of the sketch to extrude.
    length:
        Extrusion length.  Must be positive.
    symmetric:
        If ``True``, extrude symmetrically in both directions
        (half the length each way).
    reversed:
        If ``True``, extrude in the opposite direction.

    Returns
    -------
    Dict[str, Any]
        The newly created pad feature dictionary.
    """
    _validate_project(project)
    body = _get_body(project, body_index)
    sketch = _validate_sketch_index(project, sketch_index)

    length = float(length)
    if length <= 0:
        raise ValueError(f"Pad length must be positive, got {length}")

    # Set base sketch if this is the first feature
    if body["base_sketch_index"] is None:
        body["base_sketch_index"] = sketch_index

    feature: Dict[str, Any] = {
        "id": _next_feature_id(body),
        "type": "pad",
        "sketch_index": sketch_index,
        "sketch_name": sketch.get("name", f"Sketch {sketch_index}"),
        "length": length,
        "symmetric": bool(symmetric),
        "reversed": bool(reversed),
    }

    body["features"].append(feature)
    return feature


def pocket(
    project: Dict[str, Any],
    body_index: int,
    sketch_index: int,
    length: float = 5.0,
    symmetric: bool = False,
    reversed: bool = False,
) -> Dict[str, Any]:
    """Add a pocket (cut extrusion) feature to a body based on a sketch.

    Parameters
    ----------
    project:
        The project dictionary.
    body_index:
        Index of the target body.
    sketch_index:
        Index of the sketch defining the pocket profile.
    length:
        Cut depth.  Must be positive.
    symmetric:
        If ``True``, cut symmetrically in both directions.
    reversed:
        If ``True``, cut in the opposite direction.

    Returns
    -------
    Dict[str, Any]
        The newly created pocket feature dictionary.
    """
    _validate_project(project)
    body = _get_body(project, body_index)
    sketch = _validate_sketch_index(project, sketch_index)

    length = float(length)
    if length <= 0:
        raise ValueError(f"Pocket length must be positive, got {length}")

    feature: Dict[str, Any] = {
        "id": _next_feature_id(body),
        "type": "pocket",
        "sketch_index": sketch_index,
        "sketch_name": sketch.get("name", f"Sketch {sketch_index}"),
        "length": length,
        "symmetric": bool(symmetric),
        "reversed": bool(reversed),
    }

    body["features"].append(feature)
    return feature


def fillet(
    project: Dict[str, Any],
    body_index: int,
    radius: float = 1.0,
    edges: Union[str, List[int]] = "all",
) -> Dict[str, Any]:
    """Add a fillet (rounded edge) feature to a body.

    Parameters
    ----------
    project:
        The project dictionary.
    body_index:
        Index of the target body.
    radius:
        Fillet radius.  Must be positive.
    edges:
        ``"all"`` to fillet every edge, or a list of edge indices.

    Returns
    -------
    Dict[str, Any]
        The newly created fillet feature dictionary.
    """
    _validate_project(project)
    body = _get_body(project, body_index)

    radius = float(radius)
    if radius <= 0:
        raise ValueError(f"Fillet radius must be positive, got {radius}")

    if edges != "all":
        if not isinstance(edges, (list, tuple)):
            raise ValueError("Edges must be 'all' or a list of edge indices")
        for idx in edges:
            if not isinstance(idx, int) or idx < 0:
                raise ValueError(f"Edge index must be a non-negative integer, got {idx!r}")
        edges = list(edges)

    if not body["features"]:
        raise ValueError("Cannot add fillet to a body with no existing features")

    feature: Dict[str, Any] = {
        "id": _next_feature_id(body),
        "type": "fillet",
        "radius": radius,
        "edges": edges,
    }

    body["features"].append(feature)
    return feature


def chamfer(
    project: Dict[str, Any],
    body_index: int,
    size: float = 1.0,
    edges: Union[str, List[int]] = "all",
) -> Dict[str, Any]:
    """Add a chamfer (beveled edge) feature to a body.

    Parameters
    ----------
    project:
        The project dictionary.
    body_index:
        Index of the target body.
    size:
        Chamfer size (distance).  Must be positive.
    edges:
        ``"all"`` to chamfer every edge, or a list of edge indices.

    Returns
    -------
    Dict[str, Any]
        The newly created chamfer feature dictionary.
    """
    _validate_project(project)
    body = _get_body(project, body_index)

    size = float(size)
    if size <= 0:
        raise ValueError(f"Chamfer size must be positive, got {size}")

    if edges != "all":
        if not isinstance(edges, (list, tuple)):
            raise ValueError("Edges must be 'all' or a list of edge indices")
        for idx in edges:
            if not isinstance(idx, int) or idx < 0:
                raise ValueError(f"Edge index must be a non-negative integer, got {idx!r}")
        edges = list(edges)

    if not body["features"]:
        raise ValueError("Cannot add chamfer to a body with no existing features")

    feature: Dict[str, Any] = {
        "id": _next_feature_id(body),
        "type": "chamfer",
        "size": size,
        "edges": edges,
    }

    body["features"].append(feature)
    return feature


def revolution(
    project: Dict[str, Any],
    body_index: int,
    sketch_index: int,
    angle: float = 360.0,
    axis: str = "Z",
    reversed: bool = False,
) -> Dict[str, Any]:
    """Add a revolution feature to a body based on a sketch.

    Parameters
    ----------
    project:
        The project dictionary.
    body_index:
        Index of the target body.
    sketch_index:
        Index of the sketch to revolve.
    angle:
        Revolution angle in degrees (0 exclusive, 360 inclusive).
    axis:
        Revolution axis: ``"X"``, ``"Y"``, or ``"Z"``.
    reversed:
        If ``True``, revolve in the opposite direction.

    Returns
    -------
    Dict[str, Any]
        The newly created revolution feature dictionary.
    """
    _validate_project(project)
    body = _get_body(project, body_index)
    sketch = _validate_sketch_index(project, sketch_index)

    angle = float(angle)
    if angle <= 0 or angle > 360:
        raise ValueError(f"Revolution angle must be in (0, 360], got {angle}")

    axis = axis.upper()
    if axis not in VALID_REVOLUTION_AXES:
        raise ValueError(
            f"Invalid revolution axis '{axis}'. Must be one of: {', '.join(sorted(VALID_REVOLUTION_AXES))}"
        )

    # Set base sketch if this is the first feature
    if body["base_sketch_index"] is None:
        body["base_sketch_index"] = sketch_index

    feature: Dict[str, Any] = {
        "id": _next_feature_id(body),
        "type": "revolution",
        "sketch_index": sketch_index,
        "sketch_name": sketch.get("name", f"Sketch {sketch_index}"),
        "angle": angle,
        "axis": axis,
        "reversed": bool(reversed),
    }

    body["features"].append(feature)
    return feature


def list_bodies(project: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return a summary list of all bodies in the project.

    Parameters
    ----------
    project:
        The project dictionary.

    Returns
    -------
    List[Dict[str, Any]]
        List of body summaries with index, id, name, feature count,
        and base sketch index.
    """
    _validate_project(project)

    result: List[Dict[str, Any]] = []
    for i, body in enumerate(project["bodies"]):
        result.append({
            "index": i,
            "id": body.get("id", i),
            "name": body.get("name", f"Body {i}"),
            "feature_count": len(body.get("features", [])),
            "base_sketch_index": body.get("base_sketch_index"),
        })
    return result


def get_body(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Return the full body dictionary at the given index.

    Parameters
    ----------
    project:
        The project dictionary.
    index:
        Body index.

    Returns
    -------
    Dict[str, Any]
        The complete body dictionary.
    """
    _validate_project(project)
    return _get_body(project, index)


# ---------------------------------------------------------------------------
# Additive Features
# ---------------------------------------------------------------------------


def additive_loft(
    project: Dict[str, Any],
    body_index: int,
    sketch_indices: List[int],
    solid: bool = True,
    ruled: bool = False,
) -> Dict[str, Any]:
    """Add a loft feature between two or more sketches.

    Parameters
    ----------
    project:
        The project dictionary.
    body_index:
        Index of the target body.
    sketch_indices:
        List of sketch indices defining loft cross-sections.  Minimum 2.
    solid:
        If ``True``, create a solid loft.
    ruled:
        If ``True``, use ruled surfaces between sections.

    Returns
    -------
    Dict[str, Any]
        The newly created additive loft feature dictionary.
    """
    _validate_project(project)
    body = _get_body(project, body_index)

    if not isinstance(sketch_indices, (list, tuple)) or len(sketch_indices) < 2:
        raise ValueError("Loft requires at least 2 sketch indices")

    sketch_names: List[str] = []
    for si in sketch_indices:
        sk = _validate_sketch_index(project, si)
        sketch_names.append(sk.get("name", f"Sketch {si}"))

    if body["base_sketch_index"] is None:
        body["base_sketch_index"] = sketch_indices[0]

    feature: Dict[str, Any] = {
        "id": _next_feature_id(body),
        "type": "additive_loft",
        "sketch_indices": list(sketch_indices),
        "sketch_names": sketch_names,
        "solid": bool(solid),
        "ruled": bool(ruled),
    }

    body["features"].append(feature)
    return feature


def additive_pipe(
    project: Dict[str, Any],
    body_index: int,
    profile_sketch_index: int,
    path_sketch_index: int,
) -> Dict[str, Any]:
    """Add a pipe (sweep) feature along a path sketch.

    Parameters
    ----------
    project:
        The project dictionary.
    body_index:
        Index of the target body.
    profile_sketch_index:
        Index of the sketch defining the sweep profile.
    path_sketch_index:
        Index of the sketch defining the sweep path.

    Returns
    -------
    Dict[str, Any]
        The newly created additive pipe feature dictionary.
    """
    _validate_project(project)
    body = _get_body(project, body_index)

    profile = _validate_sketch_index(project, profile_sketch_index)
    path = _validate_sketch_index(project, path_sketch_index)

    if body["base_sketch_index"] is None:
        body["base_sketch_index"] = profile_sketch_index

    feature: Dict[str, Any] = {
        "id": _next_feature_id(body),
        "type": "additive_pipe",
        "profile_sketch_index": profile_sketch_index,
        "profile_sketch_name": profile.get("name", f"Sketch {profile_sketch_index}"),
        "path_sketch_index": path_sketch_index,
        "path_sketch_name": path.get("name", f"Sketch {path_sketch_index}"),
    }

    body["features"].append(feature)
    return feature


def additive_helix(
    project: Dict[str, Any],
    body_index: int,
    sketch_index: int,
    pitch: float = 5.0,
    height: float = 20.0,
    turns: Optional[float] = None,
) -> Dict[str, Any]:
    """Add a helix extrusion feature.

    Parameters
    ----------
    project:
        The project dictionary.
    body_index:
        Index of the target body.
    sketch_index:
        Index of the sketch to extrude along the helix.
    pitch:
        Distance between helix turns.  Must be positive.
    height:
        Total helix height.  Must be positive.
    turns:
        Number of turns.  If provided, overrides height
        (``height = turns * pitch``).

    Returns
    -------
    Dict[str, Any]
        The newly created additive helix feature dictionary.
    """
    _validate_project(project)
    body = _get_body(project, body_index)
    sketch = _validate_sketch_index(project, sketch_index)

    pitch = float(pitch)
    if pitch <= 0:
        raise ValueError(f"Pitch must be positive, got {pitch}")

    if turns is not None:
        turns = float(turns)
        if turns <= 0:
            raise ValueError(f"Turns must be positive, got {turns}")
        height = turns * pitch
    else:
        height = float(height)
        if height <= 0:
            raise ValueError(f"Height must be positive, got {height}")
        turns = height / pitch

    if body["base_sketch_index"] is None:
        body["base_sketch_index"] = sketch_index

    feature: Dict[str, Any] = {
        "id": _next_feature_id(body),
        "type": "additive_helix",
        "sketch_index": sketch_index,
        "sketch_name": sketch.get("name", f"Sketch {sketch_index}"),
        "pitch": pitch,
        "height": height,
        "turns": turns,
    }

    body["features"].append(feature)
    return feature


def _additive_primitive(
    project: Dict[str, Any],
    body_index: int,
    primitive_type: str,
    params: Dict[str, Any],
    position: Optional[List[float]] = None,
    rotation: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Internal helper to add an additive primitive feature."""
    _validate_project(project)
    body = _get_body(project, body_index)

    feature: Dict[str, Any] = {
        "id": _next_feature_id(body),
        "type": f"additive_{primitive_type}",
    }
    feature.update(params)
    placement = _normalize_feature_placement(position=position, rotation=rotation)
    if placement is not None:
        feature["placement"] = placement

    body["features"].append(feature)
    return feature


def additive_box(
    project: Dict[str, Any],
    body_index: int,
    length: float = 10.0,
    width: float = 10.0,
    height: float = 10.0,
    position: Optional[List[float]] = None,
    rotation: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Add an additive box primitive to a body.

    Parameters
    ----------
    project:
        The project dictionary.
    body_index:
        Index of the target body.
    length:
        Box length (X).  Must be positive.
    width:
        Box width (Y).  Must be positive.
    height:
        Box height (Z).  Must be positive.

    Returns
    -------
    Dict[str, Any]
        The newly created additive box feature dictionary.
    """
    length, width, height = float(length), float(width), float(height)
    for name, val in [("length", length), ("width", width), ("height", height)]:
        if val <= 0:
            raise ValueError(f"Box {name} must be positive, got {val}")
    return _additive_primitive(
        project,
        body_index,
        "box",
        {"length": length, "width": width, "height": height},
        position=position,
        rotation=rotation,
    )


def additive_cylinder(
    project: Dict[str, Any],
    body_index: int,
    radius: float = 5.0,
    height: float = 10.0,
    position: Optional[List[float]] = None,
    rotation: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Add an additive cylinder primitive to a body.

    Parameters
    ----------
    project:
        The project dictionary.
    body_index:
        Index of the target body.
    radius:
        Cylinder radius.  Must be positive.
    height:
        Cylinder height.  Must be positive.

    Returns
    -------
    Dict[str, Any]
        The newly created additive cylinder feature dictionary.
    """
    radius, height = float(radius), float(height)
    if radius <= 0:
        raise ValueError(f"Cylinder radius must be positive, got {radius}")
    if height <= 0:
        raise ValueError(f"Cylinder height must be positive, got {height}")
    return _additive_primitive(
        project,
        body_index,
        "cylinder",
        {"radius": radius, "height": height},
        position=position,
        rotation=rotation,
    )


def additive_sphere(
    project: Dict[str, Any],
    body_index: int,
    radius: float = 5.0,
    position: Optional[List[float]] = None,
    rotation: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Add an additive sphere primitive to a body.

    Parameters
    ----------
    project:
        The project dictionary.
    body_index:
        Index of the target body.
    radius:
        Sphere radius.  Must be positive.

    Returns
    -------
    Dict[str, Any]
        The newly created additive sphere feature dictionary.
    """
    radius = float(radius)
    if radius <= 0:
        raise ValueError(f"Sphere radius must be positive, got {radius}")
    return _additive_primitive(
        project,
        body_index,
        "sphere",
        {"radius": radius},
        position=position,
        rotation=rotation,
    )


def additive_cone(
    project: Dict[str, Any],
    body_index: int,
    radius1: float = 5.0,
    radius2: float = 0.0,
    height: float = 10.0,
    position: Optional[List[float]] = None,
    rotation: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Add an additive cone primitive to a body.

    Parameters
    ----------
    project:
        The project dictionary.
    body_index:
        Index of the target body.
    radius1:
        Bottom radius.  Must be non-negative.
    radius2:
        Top radius.  Must be non-negative.
    height:
        Cone height.  Must be positive.

    Returns
    -------
    Dict[str, Any]
        The newly created additive cone feature dictionary.
    """
    radius1, radius2, height = float(radius1), float(radius2), float(height)
    if radius1 < 0:
        raise ValueError(f"Cone radius1 must be non-negative, got {radius1}")
    if radius2 < 0:
        raise ValueError(f"Cone radius2 must be non-negative, got {radius2}")
    if height <= 0:
        raise ValueError(f"Cone height must be positive, got {height}")
    return _additive_primitive(
        project,
        body_index,
        "cone",
        {"radius1": radius1, "radius2": radius2, "height": height},
        position=position,
        rotation=rotation,
    )


def additive_torus(
    project: Dict[str, Any],
    body_index: int,
    radius1: float = 10.0,
    radius2: float = 2.0,
    position: Optional[List[float]] = None,
    rotation: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Add an additive torus primitive to a body.

    Parameters
    ----------
    project:
        The project dictionary.
    body_index:
        Index of the target body.
    radius1:
        Major radius (center of tube to center of torus).  Must be positive.
    radius2:
        Minor radius (tube radius).  Must be positive.

    Returns
    -------
    Dict[str, Any]
        The newly created additive torus feature dictionary.
    """
    radius1, radius2 = float(radius1), float(radius2)
    if radius1 <= 0:
        raise ValueError(f"Torus major radius must be positive, got {radius1}")
    if radius2 <= 0:
        raise ValueError(f"Torus minor radius must be positive, got {radius2}")
    return _additive_primitive(
        project,
        body_index,
        "torus",
        {"radius1": radius1, "radius2": radius2},
        position=position,
        rotation=rotation,
    )


def additive_wedge(
    project: Dict[str, Any],
    body_index: int,
    xmin: float = 0.0,
    xmax: float = 10.0,
    ymin: float = 0.0,
    ymax: float = 10.0,
    zmin: float = 0.0,
    zmax: float = 10.0,
    x2min: float = 2.0,
    x2max: float = 8.0,
    z2min: float = 2.0,
    z2max: float = 8.0,
    position: Optional[List[float]] = None,
    rotation: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Add an additive wedge primitive to a body.

    Parameters
    ----------
    project:
        The project dictionary.
    body_index:
        Index of the target body.
    xmin, xmax, ymin, ymax, zmin, zmax:
        Bounding box extents.
    x2min, x2max, z2min, z2max:
        Top face extents (for the tapered wedge shape).

    Returns
    -------
    Dict[str, Any]
        The newly created additive wedge feature dictionary.
    """
    return _additive_primitive(
        project,
        body_index,
        "wedge",
        {
            "xmin": float(xmin),
            "xmax": float(xmax),
            "ymin": float(ymin),
            "ymax": float(ymax),
            "zmin": float(zmin),
            "zmax": float(zmax),
            "x2min": float(x2min),
            "x2max": float(x2max),
            "z2min": float(z2min),
            "z2max": float(z2max),
        },
        position=position,
        rotation=rotation,
    )


# ---------------------------------------------------------------------------
# Subtractive Features
# ---------------------------------------------------------------------------


def groove(
    project: Dict[str, Any],
    body_index: int,
    sketch_index: int,
    angle: float = 360.0,
    axis: str = "Z",
    reversed: bool = False,
) -> Dict[str, Any]:
    """Add a groove (subtractive revolution) feature to a body.

    Parameters
    ----------
    project:
        The project dictionary.
    body_index:
        Index of the target body.
    sketch_index:
        Index of the sketch to revolve as a cut.
    angle:
        Revolution angle in degrees (0 exclusive, 360 inclusive).
    axis:
        Revolution axis: ``"X"``, ``"Y"``, or ``"Z"``.
    reversed:
        If ``True``, revolve in the opposite direction.

    Returns
    -------
    Dict[str, Any]
        The newly created groove feature dictionary.
    """
    _validate_project(project)
    body = _get_body(project, body_index)
    sketch = _validate_sketch_index(project, sketch_index)

    angle = float(angle)
    if angle <= 0 or angle > 360:
        raise ValueError(f"Groove angle must be in (0, 360], got {angle}")

    axis = axis.upper()
    if axis not in VALID_REVOLUTION_AXES:
        raise ValueError(
            f"Invalid groove axis '{axis}'. Must be one of: {', '.join(sorted(VALID_REVOLUTION_AXES))}"
        )

    if not body["features"]:
        raise ValueError("Cannot add groove to a body with no existing features")

    feature: Dict[str, Any] = {
        "id": _next_feature_id(body),
        "type": "groove",
        "sketch_index": sketch_index,
        "sketch_name": sketch.get("name", f"Sketch {sketch_index}"),
        "angle": angle,
        "axis": axis,
        "reversed": bool(reversed),
    }

    body["features"].append(feature)
    return feature


def subtractive_loft(
    project: Dict[str, Any],
    body_index: int,
    sketch_indices: List[int],
    solid: bool = True,
    ruled: bool = False,
) -> Dict[str, Any]:
    """Add a subtractive loft feature between two or more sketches.

    Parameters
    ----------
    project:
        The project dictionary.
    body_index:
        Index of the target body.
    sketch_indices:
        List of sketch indices defining loft cross-sections.  Minimum 2.
    solid:
        If ``True``, create a solid loft cut.
    ruled:
        If ``True``, use ruled surfaces between sections.

    Returns
    -------
    Dict[str, Any]
        The newly created subtractive loft feature dictionary.
    """
    _validate_project(project)
    body = _get_body(project, body_index)

    if not isinstance(sketch_indices, (list, tuple)) or len(sketch_indices) < 2:
        raise ValueError("Loft requires at least 2 sketch indices")

    if not body["features"]:
        raise ValueError("Cannot add subtractive loft to a body with no existing features")

    sketch_names: List[str] = []
    for si in sketch_indices:
        sk = _validate_sketch_index(project, si)
        sketch_names.append(sk.get("name", f"Sketch {si}"))

    feature: Dict[str, Any] = {
        "id": _next_feature_id(body),
        "type": "subtractive_loft",
        "sketch_indices": list(sketch_indices),
        "sketch_names": sketch_names,
        "solid": bool(solid),
        "ruled": bool(ruled),
    }

    body["features"].append(feature)
    return feature


def subtractive_pipe(
    project: Dict[str, Any],
    body_index: int,
    profile_sketch_index: int,
    path_sketch_index: int,
) -> Dict[str, Any]:
    """Add a subtractive pipe (sweep cut) feature along a path sketch.

    Parameters
    ----------
    project:
        The project dictionary.
    body_index:
        Index of the target body.
    profile_sketch_index:
        Index of the sketch defining the cut profile.
    path_sketch_index:
        Index of the sketch defining the sweep path.

    Returns
    -------
    Dict[str, Any]
        The newly created subtractive pipe feature dictionary.
    """
    _validate_project(project)
    body = _get_body(project, body_index)

    if not body["features"]:
        raise ValueError("Cannot add subtractive pipe to a body with no existing features")

    profile = _validate_sketch_index(project, profile_sketch_index)
    path = _validate_sketch_index(project, path_sketch_index)

    feature: Dict[str, Any] = {
        "id": _next_feature_id(body),
        "type": "subtractive_pipe",
        "profile_sketch_index": profile_sketch_index,
        "profile_sketch_name": profile.get("name", f"Sketch {profile_sketch_index}"),
        "path_sketch_index": path_sketch_index,
        "path_sketch_name": path.get("name", f"Sketch {path_sketch_index}"),
    }

    body["features"].append(feature)
    return feature


def subtractive_helix(
    project: Dict[str, Any],
    body_index: int,
    sketch_index: int,
    pitch: float = 5.0,
    height: float = 20.0,
    turns: Optional[float] = None,
) -> Dict[str, Any]:
    """Add a subtractive helix feature.

    Parameters
    ----------
    project:
        The project dictionary.
    body_index:
        Index of the target body.
    sketch_index:
        Index of the sketch to extrude along the helix as a cut.
    pitch:
        Distance between helix turns.  Must be positive.
    height:
        Total helix height.  Must be positive.
    turns:
        Number of turns.  If provided, overrides height.

    Returns
    -------
    Dict[str, Any]
        The newly created subtractive helix feature dictionary.
    """
    _validate_project(project)
    body = _get_body(project, body_index)
    sketch = _validate_sketch_index(project, sketch_index)

    if not body["features"]:
        raise ValueError("Cannot add subtractive helix to a body with no existing features")

    pitch = float(pitch)
    if pitch <= 0:
        raise ValueError(f"Pitch must be positive, got {pitch}")

    if turns is not None:
        turns = float(turns)
        if turns <= 0:
            raise ValueError(f"Turns must be positive, got {turns}")
        height = turns * pitch
    else:
        height = float(height)
        if height <= 0:
            raise ValueError(f"Height must be positive, got {height}")
        turns = height / pitch

    feature: Dict[str, Any] = {
        "id": _next_feature_id(body),
        "type": "subtractive_helix",
        "sketch_index": sketch_index,
        "sketch_name": sketch.get("name", f"Sketch {sketch_index}"),
        "pitch": pitch,
        "height": height,
        "turns": turns,
    }

    body["features"].append(feature)
    return feature


def _subtractive_primitive(
    project: Dict[str, Any],
    body_index: int,
    primitive_type: str,
    params: Dict[str, Any],
    position: Optional[List[float]] = None,
    rotation: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Internal helper to add a subtractive primitive feature."""
    _validate_project(project)
    body = _get_body(project, body_index)

    if not body["features"]:
        raise ValueError(
            f"Cannot add subtractive {primitive_type} to a body with no existing features"
        )

    feature: Dict[str, Any] = {
        "id": _next_feature_id(body),
        "type": f"subtractive_{primitive_type}",
    }
    feature.update(params)
    placement = _normalize_feature_placement(position=position, rotation=rotation)
    if placement is not None:
        feature["placement"] = placement

    body["features"].append(feature)
    return feature


def subtractive_box(
    project: Dict[str, Any],
    body_index: int,
    length: float = 10.0,
    width: float = 10.0,
    height: float = 10.0,
    position: Optional[List[float]] = None,
    rotation: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Add a subtractive box primitive to a body.

    Parameters
    ----------
    project:
        The project dictionary.
    body_index:
        Index of the target body.
    length:
        Box length (X).  Must be positive.
    width:
        Box width (Y).  Must be positive.
    height:
        Box height (Z).  Must be positive.

    Returns
    -------
    Dict[str, Any]
        The newly created subtractive box feature dictionary.
    """
    length, width, height = float(length), float(width), float(height)
    for name, val in [("length", length), ("width", width), ("height", height)]:
        if val <= 0:
            raise ValueError(f"Box {name} must be positive, got {val}")
    return _subtractive_primitive(
        project,
        body_index,
        "box",
        {"length": length, "width": width, "height": height},
        position=position,
        rotation=rotation,
    )


def subtractive_cylinder(
    project: Dict[str, Any],
    body_index: int,
    radius: float = 5.0,
    height: float = 10.0,
    position: Optional[List[float]] = None,
    rotation: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Add a subtractive cylinder primitive to a body.

    Parameters
    ----------
    project:
        The project dictionary.
    body_index:
        Index of the target body.
    radius:
        Cylinder radius.  Must be positive.
    height:
        Cylinder height.  Must be positive.

    Returns
    -------
    Dict[str, Any]
        The newly created subtractive cylinder feature dictionary.
    """
    radius, height = float(radius), float(height)
    if radius <= 0:
        raise ValueError(f"Cylinder radius must be positive, got {radius}")
    if height <= 0:
        raise ValueError(f"Cylinder height must be positive, got {height}")
    return _subtractive_primitive(
        project,
        body_index,
        "cylinder",
        {"radius": radius, "height": height},
        position=position,
        rotation=rotation,
    )


def subtractive_sphere(
    project: Dict[str, Any],
    body_index: int,
    radius: float = 5.0,
    position: Optional[List[float]] = None,
    rotation: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Add a subtractive sphere primitive to a body.

    Parameters
    ----------
    project:
        The project dictionary.
    body_index:
        Index of the target body.
    radius:
        Sphere radius.  Must be positive.

    Returns
    -------
    Dict[str, Any]
        The newly created subtractive sphere feature dictionary.
    """
    radius = float(radius)
    if radius <= 0:
        raise ValueError(f"Sphere radius must be positive, got {radius}")
    return _subtractive_primitive(
        project,
        body_index,
        "sphere",
        {"radius": radius},
        position=position,
        rotation=rotation,
    )


def subtractive_cone(
    project: Dict[str, Any],
    body_index: int,
    radius1: float = 5.0,
    radius2: float = 0.0,
    height: float = 10.0,
    position: Optional[List[float]] = None,
    rotation: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Add a subtractive cone primitive to a body.

    Parameters
    ----------
    project:
        The project dictionary.
    body_index:
        Index of the target body.
    radius1:
        Bottom radius.  Must be non-negative.
    radius2:
        Top radius.  Must be non-negative.
    height:
        Cone height.  Must be positive.

    Returns
    -------
    Dict[str, Any]
        The newly created subtractive cone feature dictionary.
    """
    radius1, radius2, height = float(radius1), float(radius2), float(height)
    if radius1 < 0:
        raise ValueError(f"Cone radius1 must be non-negative, got {radius1}")
    if radius2 < 0:
        raise ValueError(f"Cone radius2 must be non-negative, got {radius2}")
    if height <= 0:
        raise ValueError(f"Cone height must be positive, got {height}")
    return _subtractive_primitive(
        project,
        body_index,
        "cone",
        {"radius1": radius1, "radius2": radius2, "height": height},
        position=position,
        rotation=rotation,
    )


def subtractive_torus(
    project: Dict[str, Any],
    body_index: int,
    radius1: float = 10.0,
    radius2: float = 2.0,
    position: Optional[List[float]] = None,
    rotation: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Add a subtractive torus primitive to a body.

    Parameters
    ----------
    project:
        The project dictionary.
    body_index:
        Index of the target body.
    radius1:
        Major radius.  Must be positive.
    radius2:
        Minor radius.  Must be positive.

    Returns
    -------
    Dict[str, Any]
        The newly created subtractive torus feature dictionary.
    """
    radius1, radius2 = float(radius1), float(radius2)
    if radius1 <= 0:
        raise ValueError(f"Torus major radius must be positive, got {radius1}")
    if radius2 <= 0:
        raise ValueError(f"Torus minor radius must be positive, got {radius2}")
    return _subtractive_primitive(
        project,
        body_index,
        "torus",
        {"radius1": radius1, "radius2": radius2},
        position=position,
        rotation=rotation,
    )


def subtractive_wedge(
    project: Dict[str, Any],
    body_index: int,
    xmin: float = 0.0,
    xmax: float = 10.0,
    ymin: float = 0.0,
    ymax: float = 10.0,
    zmin: float = 0.0,
    zmax: float = 10.0,
    x2min: float = 2.0,
    x2max: float = 8.0,
    z2min: float = 2.0,
    z2max: float = 8.0,
    position: Optional[List[float]] = None,
    rotation: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Add a subtractive wedge primitive to a body.

    Parameters
    ----------
    project:
        The project dictionary.
    body_index:
        Index of the target body.
    xmin, xmax, ymin, ymax, zmin, zmax:
        Bounding box extents.
    x2min, x2max, z2min, z2max:
        Top face extents.

    Returns
    -------
    Dict[str, Any]
        The newly created subtractive wedge feature dictionary.
    """
    return _subtractive_primitive(
        project,
        body_index,
        "wedge",
        {
            "xmin": float(xmin),
            "xmax": float(xmax),
            "ymin": float(ymin),
            "ymax": float(ymax),
            "zmin": float(zmin),
            "zmax": float(zmax),
            "x2min": float(x2min),
            "x2max": float(x2max),
            "z2min": float(z2min),
            "z2max": float(z2max),
        },
        position=position,
        rotation=rotation,
    )


# ---------------------------------------------------------------------------
# Dress-up Features
# ---------------------------------------------------------------------------


def draft_feature(
    project: Dict[str, Any],
    body_index: int,
    angle: float,
    faces: Union[str, List[int]] = "all",
    pull_direction: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Add a draft (taper) feature to a body.

    Parameters
    ----------
    project:
        The project dictionary.
    body_index:
        Index of the target body.
    angle:
        Draft angle in degrees.  Must be positive.
    faces:
        ``"all"`` to draft every face, or a list of face indices.
    pull_direction:
        Pull direction vector ``[x, y, z]``.  Defaults to ``[0, 0, 1]``.

    Returns
    -------
    Dict[str, Any]
        The newly created draft feature dictionary.
    """
    _validate_project(project)
    body = _get_body(project, body_index)

    if not body["features"]:
        raise ValueError("Cannot add draft to a body with no existing features")

    angle = float(angle)
    if angle <= 0:
        raise ValueError(f"Draft angle must be positive, got {angle}")

    if pull_direction is None:
        pull_direction = [0, 0, 1]
    if not isinstance(pull_direction, (list, tuple)) or len(pull_direction) != 3:
        raise ValueError("pull_direction must be a list of 3 numbers")
    pull_direction = [float(v) for v in pull_direction]

    if faces != "all":
        if not isinstance(faces, (list, tuple)):
            raise ValueError("Faces must be 'all' or a list of face indices")
        faces = list(faces)

    feature: Dict[str, Any] = {
        "id": _next_feature_id(body),
        "type": "draft",
        "angle": angle,
        "faces": faces,
        "pull_direction": pull_direction,
    }

    body["features"].append(feature)
    return feature


def thickness_feature(
    project: Dict[str, Any],
    body_index: int,
    thickness: float,
    faces: Union[str, List[int]] = "all",
    join: str = "arc",
) -> Dict[str, Any]:
    """Add a thickness (shell) feature to a body.

    Hollows out the solid, leaving walls of the specified thickness.

    Parameters
    ----------
    project:
        The project dictionary.
    body_index:
        Index of the target body.
    thickness:
        Wall thickness.  Must be positive.
    faces:
        ``"all"`` to shell all faces, or a list of face indices to
        remove (open faces).
    join:
        Join type for corners: ``"arc"``, ``"tangent"``, or
        ``"intersection"``.

    Returns
    -------
    Dict[str, Any]
        The newly created thickness feature dictionary.
    """
    _validate_project(project)
    body = _get_body(project, body_index)

    if not body["features"]:
        raise ValueError("Cannot add thickness to a body with no existing features")

    thickness = float(thickness)
    if thickness <= 0:
        raise ValueError(f"Thickness must be positive, got {thickness}")

    valid_joins = {"arc", "tangent", "intersection"}
    join = join.lower()
    if join not in valid_joins:
        raise ValueError(
            f"Invalid join type '{join}'. Must be one of: {', '.join(sorted(valid_joins))}"
        )

    if faces != "all":
        if not isinstance(faces, (list, tuple)):
            raise ValueError("Faces must be 'all' or a list of face indices")
        faces = list(faces)

    feature: Dict[str, Any] = {
        "id": _next_feature_id(body),
        "type": "thickness",
        "thickness": thickness,
        "faces": faces,
        "join": join,
    }

    body["features"].append(feature)
    return feature


# ---------------------------------------------------------------------------
# Pattern Features
# ---------------------------------------------------------------------------


def linear_pattern(
    project: Dict[str, Any],
    body_index: int,
    direction: Optional[List[float]] = None,
    length: float = 50.0,
    occurrences: int = 3,
) -> Dict[str, Any]:
    """Add a linear pattern feature to a body.

    Repeats the last feature along a direction.

    Parameters
    ----------
    project:
        The project dictionary.
    body_index:
        Index of the target body.
    direction:
        Pattern direction vector ``[x, y, z]``.  Defaults to ``[1, 0, 0]``.
    length:
        Total pattern length.  Must be positive.
    occurrences:
        Number of occurrences (including the original).  Must be >= 2.

    Returns
    -------
    Dict[str, Any]
        The newly created linear pattern feature dictionary.
    """
    _validate_project(project)
    body = _get_body(project, body_index)

    if not body["features"]:
        raise ValueError("Cannot add linear pattern to a body with no existing features")

    if direction is None:
        direction = [1, 0, 0]
    if not isinstance(direction, (list, tuple)) or len(direction) != 3:
        raise ValueError("Direction must be a list of 3 numbers")
    direction = [float(v) for v in direction]

    length = float(length)
    if length <= 0:
        raise ValueError(f"Pattern length must be positive, got {length}")

    occurrences = int(occurrences)
    if occurrences < 2:
        raise ValueError(f"Occurrences must be at least 2, got {occurrences}")

    feature: Dict[str, Any] = {
        "id": _next_feature_id(body),
        "type": "linear_pattern",
        "direction": direction,
        "length": length,
        "occurrences": occurrences,
    }

    body["features"].append(feature)
    return feature


def polar_pattern(
    project: Dict[str, Any],
    body_index: int,
    axis: str = "Z",
    angle: float = 360.0,
    occurrences: int = 6,
) -> Dict[str, Any]:
    """Add a polar (circular) pattern feature to a body.

    Parameters
    ----------
    project:
        The project dictionary.
    body_index:
        Index of the target body.
    axis:
        Rotation axis: ``"X"``, ``"Y"``, or ``"Z"``.
    angle:
        Total angular span in degrees.  Must be in (0, 360].
    occurrences:
        Number of occurrences (including the original).  Must be >= 2.

    Returns
    -------
    Dict[str, Any]
        The newly created polar pattern feature dictionary.
    """
    _validate_project(project)
    body = _get_body(project, body_index)

    if not body["features"]:
        raise ValueError("Cannot add polar pattern to a body with no existing features")

    axis = axis.upper()
    if axis not in VALID_REVOLUTION_AXES:
        raise ValueError(
            f"Invalid axis '{axis}'. Must be one of: {', '.join(sorted(VALID_REVOLUTION_AXES))}"
        )

    angle = float(angle)
    if angle <= 0 or angle > 360:
        raise ValueError(f"Pattern angle must be in (0, 360], got {angle}")

    occurrences = int(occurrences)
    if occurrences < 2:
        raise ValueError(f"Occurrences must be at least 2, got {occurrences}")

    feature: Dict[str, Any] = {
        "id": _next_feature_id(body),
        "type": "polar_pattern",
        "axis": axis,
        "angle": angle,
        "occurrences": occurrences,
    }

    body["features"].append(feature)
    return feature


def mirrored_feature(
    project: Dict[str, Any],
    body_index: int,
    plane: str = "XY",
) -> Dict[str, Any]:
    """Add a mirrored feature to a body.

    Mirrors the last feature across the specified plane.

    Parameters
    ----------
    project:
        The project dictionary.
    body_index:
        Index of the target body.
    plane:
        Mirror plane: ``"XY"``, ``"XZ"``, or ``"YZ"``.

    Returns
    -------
    Dict[str, Any]
        The newly created mirrored feature dictionary.
    """
    _validate_project(project)
    body = _get_body(project, body_index)

    if not body["features"]:
        raise ValueError("Cannot add mirror to a body with no existing features")

    plane = plane.upper()
    if plane not in VALID_PATTERN_PLANES:
        raise ValueError(
            f"Invalid mirror plane '{plane}'. Must be one of: {', '.join(sorted(VALID_PATTERN_PLANES))}"
        )

    feature: Dict[str, Any] = {
        "id": _next_feature_id(body),
        "type": "mirrored",
        "plane": plane,
    }

    body["features"].append(feature)
    return feature


def multi_transform(
    project: Dict[str, Any],
    body_index: int,
    transformations: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Add a multi-transform feature combining multiple pattern operations.

    Parameters
    ----------
    project:
        The project dictionary.
    body_index:
        Index of the target body.
    transformations:
        List of transformation dictionaries, each describing a pattern
        operation (e.g. ``{"type": "linear_pattern", "direction": [1,0,0],
        "length": 50, "occurrences": 3}``).

    Returns
    -------
    Dict[str, Any]
        The newly created multi-transform feature dictionary.
    """
    _validate_project(project)
    body = _get_body(project, body_index)

    if not body["features"]:
        raise ValueError("Cannot add multi-transform to a body with no existing features")

    if not isinstance(transformations, (list, tuple)) or len(transformations) == 0:
        raise ValueError("Transformations must be a non-empty list of pattern dicts")

    feature: Dict[str, Any] = {
        "id": _next_feature_id(body),
        "type": "multi_transform",
        "transformations": list(transformations),
    }

    body["features"].append(feature)
    return feature


# ---------------------------------------------------------------------------
# Other Features
# ---------------------------------------------------------------------------


def hole_feature(
    project: Dict[str, Any],
    body_index: int,
    sketch_index: int,
    diameter: float = 5.0,
    depth: float = 10.0,
    threaded: bool = False,
    thread_pitch: Optional[float] = None,
    thread_standard: str = "metric",
    tapered: bool = False,
    taper_angle: Optional[float] = None,
) -> Dict[str, Any]:
    """Add a hole feature to a body based on a sketch with point positions.

    Parameters
    ----------
    project:
        The project dictionary.
    body_index:
        Index of the target body.
    sketch_index:
        Index of the sketch containing hole center points.
    diameter:
        Hole diameter.  Must be positive.
    depth:
        Hole depth.  Must be positive.
    threaded:
        If ``True``, create a threaded hole.
    thread_pitch:
        Thread pitch (only used when *threaded* is ``True``).

    Returns
    -------
    Dict[str, Any]
        The newly created hole feature dictionary.
    """
    _validate_project(project)
    body = _get_body(project, body_index)
    sketch = _validate_sketch_index(project, sketch_index)

    if not body["features"]:
        raise ValueError("Cannot add hole to a body with no existing features")

    diameter = float(diameter)
    if diameter <= 0:
        raise ValueError(f"Hole diameter must be positive, got {diameter}")

    depth = float(depth)
    if depth <= 0:
        raise ValueError(f"Hole depth must be positive, got {depth}")

    if thread_standard not in VALID_THREAD_STANDARDS:
        raise ValueError(f"Invalid thread_standard '{thread_standard}'. Valid: {sorted(VALID_THREAD_STANDARDS)}")

    if tapered and taper_angle is None:
        if thread_standard == "NPT":
            taper_angle = 1.7899  # ASME B1.20.1
        elif thread_standard == "BSP":
            taper_angle = 1.7899  # ISO 7-1

    feature: Dict[str, Any] = {
        "id": _next_feature_id(body),
        "type": "hole",
        "sketch_index": sketch_index,
        "sketch_name": sketch.get("name", f"Sketch {sketch_index}"),
        "diameter": diameter,
        "depth": depth,
        "threaded": bool(threaded),
        "thread_standard": thread_standard,
        "tapered": bool(tapered),
        "taper_angle": taper_angle,
    }

    if threaded and thread_pitch is not None:
        thread_pitch = float(thread_pitch)
        if thread_pitch <= 0:
            raise ValueError(f"Thread pitch must be positive, got {thread_pitch}")
        feature["thread_pitch"] = thread_pitch

    body["features"].append(feature)
    return feature


def datum_plane(
    project: Dict[str, Any],
    body_index: int,
    offset: float = 0.0,
    reference: str = "XY",
    attachment_mode: Optional[str] = None,
    attachment_refs: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Add a datum plane to a body.

    Parameters
    ----------
    project:
        The project dictionary.
    body_index:
        Index of the target body.
    offset:
        Offset distance from the reference plane.
    reference:
        Reference plane: ``"XY"``, ``"XZ"``, or ``"YZ"``.

    Returns
    -------
    Dict[str, Any]
        The newly created datum plane feature dictionary.
    """
    _validate_project(project)
    body = _get_body(project, body_index)

    reference = reference.upper()
    if reference not in VALID_PATTERN_PLANES:
        raise ValueError(
            f"Invalid reference plane '{reference}'. "
            f"Must be one of: {', '.join(sorted(VALID_PATTERN_PLANES))}"
        )

    feature: Dict[str, Any] = {
        "id": _next_feature_id(body),
        "type": "datum_plane",
        "offset": float(offset),
        "reference": reference,
    }

    if attachment_mode is not None:
        if attachment_mode not in VALID_ATTACHMENT_MODES:
            raise ValueError(f"Invalid attachment_mode '{attachment_mode}'. Valid: {sorted(VALID_ATTACHMENT_MODES)}")
        feature["attachment_mode"] = attachment_mode
    if attachment_refs is not None:
        feature["attachment_refs"] = attachment_refs

    body["features"].append(feature)
    return feature


def datum_line(
    project: Dict[str, Any],
    body_index: int,
    point: Optional[List[float]] = None,
    direction: Optional[List[float]] = None,
    attachment_mode: Optional[str] = None,
    attachment_refs: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Add a datum line to a body.

    Parameters
    ----------
    project:
        The project dictionary.
    body_index:
        Index of the target body.
    point:
        Base point ``[x, y, z]``.  Defaults to ``[0, 0, 0]``.
    direction:
        Direction vector ``[x, y, z]``.  Defaults to ``[0, 0, 1]``.

    Returns
    -------
    Dict[str, Any]
        The newly created datum line feature dictionary.
    """
    _validate_project(project)
    body = _get_body(project, body_index)

    if point is None:
        point = [0, 0, 0]
    if not isinstance(point, (list, tuple)) or len(point) != 3:
        raise ValueError("Point must be a list of 3 numbers")
    point = [float(v) for v in point]

    if direction is None:
        direction = [0, 0, 1]
    if not isinstance(direction, (list, tuple)) or len(direction) != 3:
        raise ValueError("Direction must be a list of 3 numbers")
    direction = [float(v) for v in direction]

    feature: Dict[str, Any] = {
        "id": _next_feature_id(body),
        "type": "datum_line",
        "point": point,
        "direction": direction,
    }

    if attachment_mode is not None:
        if attachment_mode not in VALID_ATTACHMENT_MODES:
            raise ValueError(f"Invalid attachment_mode '{attachment_mode}'. Valid: {sorted(VALID_ATTACHMENT_MODES)}")
        feature["attachment_mode"] = attachment_mode
    if attachment_refs is not None:
        feature["attachment_refs"] = attachment_refs

    body["features"].append(feature)
    return feature


def datum_point(
    project: Dict[str, Any],
    body_index: int,
    position: Optional[List[float]] = None,
    attachment_mode: Optional[str] = None,
    attachment_refs: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Add a datum point to a body.

    Parameters
    ----------
    project:
        The project dictionary.
    body_index:
        Index of the target body.
    position:
        Point position ``[x, y, z]``.  Defaults to ``[0, 0, 0]``.

    Returns
    -------
    Dict[str, Any]
        The newly created datum point feature dictionary.
    """
    _validate_project(project)
    body = _get_body(project, body_index)

    if position is None:
        position = [0, 0, 0]
    if not isinstance(position, (list, tuple)) or len(position) != 3:
        raise ValueError("Position must be a list of 3 numbers")
    position = [float(v) for v in position]

    feature: Dict[str, Any] = {
        "id": _next_feature_id(body),
        "type": "datum_point",
        "position": position,
    }

    if attachment_mode is not None:
        if attachment_mode not in VALID_ATTACHMENT_MODES:
            raise ValueError(f"Invalid attachment_mode '{attachment_mode}'. Valid: {sorted(VALID_ATTACHMENT_MODES)}")
        feature["attachment_mode"] = attachment_mode
    if attachment_refs is not None:
        feature["attachment_refs"] = attachment_refs

    body["features"].append(feature)
    return feature


def local_coordinate_system(
    project: Dict[str, Any],
    body_index: int,
    position: Optional[List[float]] = None,
    x_axis: Optional[List[float]] = None,
    y_axis: Optional[List[float]] = None,
    z_axis: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Add a local coordinate system to a body (FreeCAD 1.1).

    Replaces the legacy Origin object with a fully configurable
    coordinate system that supports cross-workbench attachment.
    """
    bodies = project.get("bodies", [])
    if body_index < 0 or body_index >= len(bodies):
        raise IndexError(f"Body index {body_index} out of range (0..{len(bodies) - 1}).")
    body = bodies[body_index]
    feature: Dict[str, Any] = {
        "type": "local_coordinate_system",
        "position": position or [0.0, 0.0, 0.0],
        "x_axis": x_axis or [1.0, 0.0, 0.0],
        "y_axis": y_axis or [0.0, 1.0, 0.0],
        "z_axis": z_axis or [0.0, 0.0, 1.0],
    }
    body.setdefault("features", []).append(feature)
    return feature


def shape_binder(
    project: Dict[str, Any],
    body_index: int,
    source_body_index: int,
    feature_ref: Optional[str] = None,
) -> Dict[str, Any]:
    """Add a shape binder referencing geometry from another body.

    Parameters
    ----------
    project:
        The project dictionary.
    body_index:
        Index of the target body.
    source_body_index:
        Index of the source body containing the geometry to bind.
    feature_ref:
        Optional feature reference identifier in the source body
        (e.g. ``"Pad"``).  If ``None``, binds the entire shape.

    Returns
    -------
    Dict[str, Any]
        The newly created shape binder feature dictionary.
    """
    _validate_project(project)
    body = _get_body(project, body_index)
    _get_body(project, source_body_index)  # validate source exists

    if body_index == source_body_index:
        raise ValueError("Shape binder source and target bodies must be different")

    feature: Dict[str, Any] = {
        "id": _next_feature_id(body),
        "type": "shape_binder",
        "source_body_index": source_body_index,
        "feature_ref": feature_ref,
    }

    body["features"].append(feature)
    return feature


def toggle_freeze(
    project: Dict[str, Any],
    body_index: int,
    feature_index: int,
) -> Dict[str, Any]:
    """Toggle the frozen state of a feature in a body (FreeCAD 1.1).

    Frozen features are excluded from recomputation.
    """
    bodies = project.get("bodies", [])
    if body_index < 0 or body_index >= len(bodies):
        raise IndexError(f"Body index {body_index} out of range (0..{len(bodies) - 1}).")
    body = bodies[body_index]
    features = body.get("features", [])
    if feature_index < 0 or feature_index >= len(features):
        raise IndexError(f"Feature index {feature_index} out of range (0..{len(features) - 1}).")
    feat = features[feature_index]
    feat["frozen"] = not feat.get("frozen", False)
    return feat
