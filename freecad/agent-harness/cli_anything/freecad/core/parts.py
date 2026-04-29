"""FreeCAD CLI - 3D parts and primitives module.

Manages part creation, removal, transformation, and boolean operations
on a JSON-based project state. Each part carries its own placement
(position + rotation) and parameter set derived from FreeCAD primitives.
"""

import math
from copy import deepcopy
from typing import Any, Dict, List, Optional, Set, Union


# ---------------------------------------------------------------------------
# Primitive definitions (type -> default parameters)
# ---------------------------------------------------------------------------

PRIMITIVES: Dict[str, Dict[str, float]] = {
    "box": {
        "length": 10.0,
        "width": 10.0,
        "height": 10.0,
    },
    "cylinder": {
        "radius": 5.0,
        "height": 10.0,
        "angle": 360.0,
    },
    "sphere": {
        "radius": 5.0,
        "angle1": -90.0,
        "angle2": 90.0,
        "angle3": 360.0,
    },
    "cone": {
        "radius1": 5.0,
        "radius2": 2.5,
        "height": 10.0,
        "angle": 360.0,
    },
    "torus": {
        "radius1": 10.0,
        "radius2": 2.0,
        "angle1": -180.0,
        "angle2": 180.0,
        "angle3": 360.0,
    },
    "wedge": {
        "xmin": 0.0,
        "ymin": 0.0,
        "zmin": 0.0,
        "x2min": 2.0,
        "z2min": 2.0,
        "xmax": 10.0,
        "ymax": 10.0,
        "zmax": 10.0,
        "x2max": 8.0,
        "z2max": 8.0,
    },
    "helix": {
        "pitch": 5.0,
        "height": 20.0,
        "radius": 5.0,
        "angle": 0.0,
    },
    "spiral": {
        "growth": 1.0,
        "turns": 5.0,
        "radius": 5.0,
    },
    "thread": {
        "pitch": 1.5,
        "diameter": 10.0,
        "length": 20.0,
        "thread_type": 0.0,  # 0 = metric (encoded as float for consistency)
    },
    "plane": {
        "length": 10.0,
        "width": 10.0,
    },
    "polygon_3d": {
        "sides": 6.0,
        "radius": 5.0,
    },
}

BOOLEAN_OPS: Set[str] = {"cut", "fuse", "common"}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _next_id(project: Dict[str, Any], key: str = "parts") -> int:
    """Return the next available integer ID for *key* in *project*.

    Scans existing items under ``project[key]`` and returns one more than
    the current maximum ``id`` value, or ``1`` if the list is empty.
    """
    items = project.get(key, [])
    if not items:
        return 1
    return max(item["id"] for item in items) + 1


def _unique_name(
    project: Dict[str, Any], base: str, key: str = "parts"
) -> str:
    """Return a unique name derived from *base* inside ``project[key]``.

    If *base* is not yet taken the string is returned as-is; otherwise a
    numeric suffix is appended (e.g. ``Box_2``, ``Box_3``).
    """
    existing = {item["name"] for item in project.get(key, [])}
    if base not in existing:
        return base
    counter = 2
    while f"{base}_{counter}" in existing:
        counter += 1
    return f"{base}_{counter}"


def _validate_vec3(value: Any, label: str) -> List[float]:
    """Validate that *value* is a list of exactly three numbers.

    Returns the value normalised to a list of Python floats.

    Raises ``ValueError`` with a descriptive message on failure.
    """
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{label} must be a list of 3 numbers, got {type(value).__name__}")
    if len(value) != 3:
        raise ValueError(f"{label} must have exactly 3 elements, got {len(value)}")
    try:
        return [float(v) for v in value]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} elements must be numeric: {exc}") from exc


def _rotation_matrix(rotation: List[float]) -> List[List[float]]:
    """Return a simple XYZ Euler rotation matrix for *rotation* in degrees."""
    rx, ry, rz = [math.radians(float(v)) for v in rotation]
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)

    mx = [
        [1.0, 0.0, 0.0],
        [0.0, cx, -sx],
        [0.0, sx, cx],
    ]
    my = [
        [cy, 0.0, sy],
        [0.0, 1.0, 0.0],
        [-sy, 0.0, cy],
    ]
    mz = [
        [cz, -sz, 0.0],
        [sz, cz, 0.0],
        [0.0, 0.0, 1.0],
    ]

    def _matmul(a: List[List[float]], b: List[List[float]]) -> List[List[float]]:
        return [
            [
                sum(a[row][k] * b[k][col] for k in range(3))
                for col in range(3)
            ]
            for row in range(3)
        ]

    return _matmul(mz, _matmul(my, mx))


def _transform_point(point: List[float], rotation: List[float], translation: List[float]) -> List[float]:
    """Apply an XYZ Euler rotation and translation to a point."""
    matrix = _rotation_matrix(rotation)
    x, y, z = point
    tx, ty, tz = translation
    return [
        matrix[0][0] * x + matrix[0][1] * y + matrix[0][2] * z + tx,
        matrix[1][0] * x + matrix[1][1] * y + matrix[1][2] * z + ty,
        matrix[2][0] * x + matrix[2][1] * y + matrix[2][2] * z + tz,
    ]


def _bbox_from_points(points: List[List[float]]) -> Dict[str, Dict[str, float]]:
    """Build min/max/size/center dictionaries from transformed points."""
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    zs = [point[2] for point in points]
    min_corner = {"x": min(xs), "y": min(ys), "z": min(zs)}
    max_corner = {"x": max(xs), "y": max(ys), "z": max(zs)}
    return {
        "min": min_corner,
        "max": max_corner,
        "size": {
            axis: max_corner[axis] - min_corner[axis]
            for axis in ("x", "y", "z")
        },
        "center": {
            axis: (min_corner[axis] + max_corner[axis]) / 2.0
            for axis in ("x", "y", "z")
        },
    }


def _local_bounds(part_type: str, params: Dict[str, Any]) -> Optional[Dict[str, Dict[str, float]]]:
    """Return a primitive-local bounding box for supported part types."""
    if part_type == "box":
        return {
            "min": {"x": 0.0, "y": 0.0, "z": 0.0},
            "max": {
                "x": float(params["length"]),
                "y": float(params["width"]),
                "z": float(params["height"]),
            },
        }

    if part_type == "cylinder":
        radius = float(params["radius"])
        height = float(params["height"])
        return {
            "min": {"x": -radius, "y": -radius, "z": 0.0},
            "max": {"x": radius, "y": radius, "z": height},
        }

    if part_type == "sphere":
        radius = float(params["radius"])
        return {
            "min": {"x": -radius, "y": -radius, "z": -radius},
            "max": {"x": radius, "y": radius, "z": radius},
        }

    if part_type == "cone":
        radius = max(float(params["radius1"]), float(params["radius2"]))
        height = float(params["height"])
        return {
            "min": {"x": -radius, "y": -radius, "z": 0.0},
            "max": {"x": radius, "y": radius, "z": height},
        }

    if part_type == "torus":
        radius1 = float(params["radius1"])
        radius2 = float(params["radius2"])
        major = radius1 + radius2
        return {
            "min": {"x": -major, "y": -major, "z": -radius2},
            "max": {"x": major, "y": major, "z": radius2},
        }

    if part_type == "wedge":
        return {
            "min": {
                "x": min(float(params["xmin"]), float(params["x2min"])),
                "y": float(params["ymin"]),
                "z": min(float(params["zmin"]), float(params["z2min"])),
            },
            "max": {
                "x": max(float(params["xmax"]), float(params["x2max"])),
                "y": float(params["ymax"]),
                "z": max(float(params["zmax"]), float(params["z2max"])),
            },
        }

    if part_type == "plane":
        return {
            "min": {"x": 0.0, "y": 0.0, "z": 0.0},
            "max": {"x": float(params["length"]), "y": float(params["width"]), "z": 0.0},
        }

    if part_type == "polygon_3d":
        radius = float(params["radius"])
        return {
            "min": {"x": -radius, "y": -radius, "z": 0.0},
            "max": {"x": radius, "y": radius, "z": 0.0},
        }

    return None


def _world_bounds(part: Dict[str, Any]) -> Optional[Dict[str, Dict[str, float]]]:
    """Return a world-space bounding box for supported primitive parts."""
    local = _local_bounds(str(part.get("type", "")).lower(), part.get("params", {}))
    if local is None:
        return None

    min_corner = local["min"]
    max_corner = local["max"]
    corners = []
    for x in (min_corner["x"], max_corner["x"]):
        for y in (min_corner["y"], max_corner["y"]):
            for z in (min_corner["z"], max_corner["z"]):
                corners.append([x, y, z])

    placement = part.get("placement", {})
    position = _validate_vec3(placement.get("position", [0.0, 0.0, 0.0]), "position")
    rotation = _validate_vec3(placement.get("rotation", [0.0, 0.0, 0.0]), "rotation")
    return _bbox_from_points([_transform_point(point, rotation, position) for point in corners])


def _anchor_value(bounds: Dict[str, Dict[str, float]], axis: str, anchor: str) -> float:
    """Resolve an axis anchor string against a bounds payload."""
    aliases = {
        "min": "min",
        "max": "max",
        "center": "center",
        "left": "min",
        "right": "max",
        "bottom": "min",
        "top": "max",
        "front": "min",
        "back": "max",
        "mid": "center",
    }
    normalized = aliases.get(anchor.lower())
    if normalized is None:
        raise ValueError(f"Unknown anchor '{anchor}'. Valid: min, center, max")
    return float(bounds[normalized][axis])


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def add_part(
    project: Dict[str, Any],
    part_type: str = "box",
    name: Optional[str] = None,
    position: Optional[List[float]] = None,
    rotation: Optional[List[float]] = None,
    params: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Create a new primitive part and append it to ``project["parts"]``.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary. Must contain a ``"parts"``
        list (created automatically if missing).
    part_type : str
        One of the keys in :data:`PRIMITIVES`.
    name : str or None
        Human-readable label. When *None* a unique name is derived from
        *part_type* (e.g. ``"Box"``, ``"Cylinder_2"``).
    position : list[float] or None
        ``[x, y, z]`` translation. Defaults to ``[0, 0, 0]``.
    rotation : list[float] or None
        ``[x, y, z]`` Euler rotation in degrees. Defaults to ``[0, 0, 0]``.
    params : dict or None
        Parameter overrides merged on top of the primitive defaults.

    Returns
    -------
    dict
        The newly created part dictionary.

    Raises
    ------
    ValueError
        If *part_type* is unknown or vector arguments are invalid.
    """
    # Validate part type
    if part_type not in PRIMITIVES:
        valid = ", ".join(sorted(PRIMITIVES))
        raise ValueError(f"Unknown part_type '{part_type}'. Valid types: {valid}")

    # Ensure the parts list exists
    if "parts" not in project:
        project["parts"] = []

    # Validate / default placement vectors
    pos = _validate_vec3(position, "position") if position is not None else [0.0, 0.0, 0.0]
    rot = _validate_vec3(rotation, "rotation") if rotation is not None else [0.0, 0.0, 0.0]

    # Merge parameters
    merged_params = deepcopy(PRIMITIVES[part_type])
    if params:
        unknown = set(params) - set(merged_params)
        if unknown:
            raise ValueError(
                f"Unknown parameter(s) for '{part_type}': {', '.join(sorted(unknown))}. "
                f"Valid: {', '.join(sorted(merged_params))}"
            )
        for k, v in params.items():
            try:
                merged_params[k] = float(v)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Parameter '{k}' must be numeric: {exc}") from exc

    # Build the name
    if name is None:
        base = part_type.capitalize()
        name = _unique_name(project, base)

    part: Dict[str, Any] = {
        "id": _next_id(project),
        "name": name,
        "type": part_type,
        "params": merged_params,
        "placement": {
            "position": pos,
            "rotation": rot,
        },
        "material_index": None,
        "visible": True,
    }

    project["parts"].append(part)
    return part


def remove_part(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Remove and return the part at *index* in ``project["parts"]``.

    Raises ``IndexError`` when the index is out of range.
    """
    parts = project.get("parts", [])
    if not isinstance(index, int) or index < 0 or index >= len(parts):
        raise IndexError(
            f"Part index {index} out of range (0..{len(parts) - 1})"
        )
    return parts.pop(index)


def list_parts(project: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return all parts in the project."""
    return project.get("parts", [])


def get_part(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Return the part at *index* without removing it.

    Raises ``IndexError`` when the index is out of range.
    """
    parts = project.get("parts", [])
    if not isinstance(index, int) or index < 0 or index >= len(parts):
        raise IndexError(
            f"Part index {index} out of range (0..{len(parts) - 1})"
        )
    return parts[index]


def transform_part(
    project: Dict[str, Any],
    index: int,
    position: Optional[List[float]] = None,
    rotation: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Update the placement of the part at *index*.

    Only the supplied vectors are changed; the other is left untouched.

    Returns the updated part dictionary.
    """
    part = get_part(project, index)

    if position is not None:
        part["placement"]["position"] = _validate_vec3(position, "position")
    if rotation is not None:
        part["placement"]["rotation"] = _validate_vec3(rotation, "rotation")

    return part


def boolean_op(
    project: Dict[str, Any],
    op: str,
    base_index: int,
    tool_index: int,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Perform a boolean operation between two parts.

    Creates a new part of ``type=op`` that references the *base* and *tool*
    parts by their IDs. Both source parts are marked ``visible=False``.

    Parameters
    ----------
    op : str
        One of ``"cut"``, ``"fuse"``, or ``"common"``.
    base_index : int
        Index of the base (kept) shape in ``project["parts"]``.
    tool_index : int
        Index of the tool shape in ``project["parts"]``.
    name : str or None
        Label for the result. Auto-generated when *None*.

    Returns
    -------
    dict
        The newly created boolean-result part.

    Raises
    ------
    ValueError
        If *op* is unknown or indices are equal.
    IndexError
        If either index is out of range.
    """
    if op not in BOOLEAN_OPS:
        valid = ", ".join(sorted(BOOLEAN_OPS))
        raise ValueError(f"Unknown boolean op '{op}'. Valid: {valid}")

    if base_index == tool_index:
        raise ValueError("base_index and tool_index must differ")

    base_part = get_part(project, base_index)
    tool_part = get_part(project, tool_index)

    # Mark operands as hidden
    base_part["visible"] = False
    tool_part["visible"] = False

    # Ensure the parts list exists
    if "parts" not in project:
        project["parts"] = []

    if name is None:
        base_name = op.capitalize()
        name = _unique_name(project, base_name)

    result: Dict[str, Any] = {
        "id": _next_id(project),
        "name": name,
        "type": op,
        "params": {
            "base_id": base_part["id"],
            "tool_id": tool_part["id"],
        },
        "placement": {
            "position": [0.0, 0.0, 0.0],
            "rotation": [0.0, 0.0, 0.0],
        },
        "material_index": None,
        "visible": True,
    }

    project["parts"].append(result)
    return result


# ---------------------------------------------------------------------------
# Extended operations
# ---------------------------------------------------------------------------

def copy_part(
    project: Dict[str, Any],
    index: int,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Deep-copy the part at *index* and append the copy to the project.

    The copy receives a new unique ``id`` and (optionally) a new *name*.
    All other attributes — parameters, placement, material — are duplicated.

    Returns the newly created part dictionary.
    """
    source = get_part(project, index)
    new_part: Dict[str, Any] = deepcopy(source)
    new_part["id"] = _next_id(project)

    if name is None:
        base = f"{source['name']}_copy"
        name = _unique_name(project, base)
    new_part["name"] = name

    project["parts"].append(new_part)
    return new_part


def mirror_part(
    project: Dict[str, Any],
    index: int,
    plane: str = "XY",
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a mirrored copy of the part at *index*.

    Parameters
    ----------
    plane : str
        Mirror plane — one of ``"XY"``, ``"XZ"``, or ``"YZ"``.
    name : str or None
        Label for the result. Auto-generated when *None*.

    Returns the newly created mirror part.
    """
    valid_planes = {"XY", "XZ", "YZ"}
    if plane not in valid_planes:
        raise ValueError(
            f"Unknown mirror plane '{plane}'. Valid: {', '.join(sorted(valid_planes))}"
        )

    source = get_part(project, index)

    if "parts" not in project:
        project["parts"] = []

    if name is None:
        base = f"{source['name']}_mirror"
        name = _unique_name(project, base)

    result: Dict[str, Any] = {
        "id": _next_id(project),
        "name": name,
        "type": "mirror",
        "params": {
            "original_id": source["id"],
            "mirror_plane": plane,
        },
        "placement": deepcopy(source["placement"]),
        "material_index": source.get("material_index"),
        "visible": True,
    }

    project["parts"].append(result)
    return result


def scale_part(
    project: Dict[str, Any],
    index: int,
    factor: Union[float, List[float]],
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a uniformly (or non-uniformly) scaled copy of a part.

    Parameters
    ----------
    factor : float or list[float]
        A single number for uniform scaling, or ``[sx, sy, sz]`` for
        per-axis scaling.
    """
    source = get_part(project, index)

    if isinstance(factor, (list, tuple)):
        scale_vec = _validate_vec3(factor, "factor")
    else:
        try:
            sf = float(factor)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"factor must be numeric: {exc}") from exc
        scale_vec = [sf, sf, sf]

    if "parts" not in project:
        project["parts"] = []

    if name is None:
        base = f"{source['name']}_scaled"
        name = _unique_name(project, base)

    result: Dict[str, Any] = {
        "id": _next_id(project),
        "name": name,
        "type": "scale",
        "params": {
            "original_id": source["id"],
            "scale": scale_vec,
        },
        "placement": deepcopy(source["placement"]),
        "material_index": source.get("material_index"),
        "visible": True,
    }

    project["parts"].append(result)
    return result


def offset_shape(
    project: Dict[str, Any],
    index: int,
    distance: float,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Create an offset shell of the part at *index*.

    Parameters
    ----------
    distance : float
        Offset distance. Positive grows outward, negative shrinks inward.
    """
    source = get_part(project, index)

    try:
        dist = float(distance)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"distance must be numeric: {exc}") from exc

    if "parts" not in project:
        project["parts"] = []

    if name is None:
        base = f"{source['name']}_offset"
        name = _unique_name(project, base)

    result: Dict[str, Any] = {
        "id": _next_id(project),
        "name": name,
        "type": "offset",
        "params": {
            "original_id": source["id"],
            "distance": dist,
        },
        "placement": deepcopy(source["placement"]),
        "material_index": source.get("material_index"),
        "visible": True,
    }

    project["parts"].append(result)
    return result


def thickness_part(
    project: Dict[str, Any],
    index: int,
    thickness: float,
    faces: str = "all",
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Hollow a solid by applying a wall *thickness*.

    Parameters
    ----------
    thickness : float
        Wall thickness value.
    faces : str
        Which faces to open — ``"all"`` or a comma-separated list of
        face indices (e.g. ``"0,2,5"``).
    """
    source = get_part(project, index)

    try:
        thick = float(thickness)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"thickness must be numeric: {exc}") from exc

    if "parts" not in project:
        project["parts"] = []

    if name is None:
        base = f"{source['name']}_thickness"
        name = _unique_name(project, base)

    result: Dict[str, Any] = {
        "id": _next_id(project),
        "name": name,
        "type": "thickness",
        "params": {
            "original_id": source["id"],
            "thickness": thick,
            "faces": faces,
        },
        "placement": deepcopy(source["placement"]),
        "material_index": source.get("material_index"),
        "visible": True,
    }

    project["parts"].append(result)
    return result


def compound_parts(
    project: Dict[str, Any],
    indices: List[int],
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Group several parts into a compound.

    The source parts are marked ``visible=False``; the compound is
    visible and stores references to its children by ID.

    Parameters
    ----------
    indices : list[int]
        Indices of the parts to group.
    """
    if not indices:
        raise ValueError("indices must be a non-empty list")

    child_ids: List[int] = []
    for idx in indices:
        part = get_part(project, idx)
        part["visible"] = False
        child_ids.append(part["id"])

    if "parts" not in project:
        project["parts"] = []

    if name is None:
        base = "Compound"
        name = _unique_name(project, base)

    result: Dict[str, Any] = {
        "id": _next_id(project),
        "name": name,
        "type": "compound",
        "params": {
            "compound_children": child_ids,
        },
        "placement": {
            "position": [0.0, 0.0, 0.0],
            "rotation": [0.0, 0.0, 0.0],
        },
        "material_index": None,
        "visible": True,
    }

    project["parts"].append(result)
    return result


def explode_compound(
    project: Dict[str, Any],
    index: int,
) -> List[Dict[str, Any]]:
    """Break a compound back into its individual child parts.

    The compound part is marked ``visible=False`` and each child part
    is restored to ``visible=True``.

    Returns the list of (now visible) child part dictionaries.
    """
    compound = get_part(project, index)
    if compound.get("type") != "compound":
        raise ValueError(
            f"Part at index {index} is not a compound (type='{compound.get('type')}')"
        )

    compound["visible"] = False

    child_ids = set(compound["params"].get("compound_children", []))
    restored: List[Dict[str, Any]] = []
    for part in project.get("parts", []):
        if part["id"] in child_ids:
            part["visible"] = True
            restored.append(part)

    return restored


def fillet_3d(
    project: Dict[str, Any],
    index: int,
    radius: float,
    edges: str = "all",
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Apply a Part-level 3-D fillet to the part at *index*.

    Parameters
    ----------
    radius : float
        Fillet radius.
    edges : str
        Which edges to fillet — ``"all"`` or a comma-separated list of
        edge indices.
    """
    source = get_part(project, index)

    try:
        rad = float(radius)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"radius must be numeric: {exc}") from exc

    if "parts" not in project:
        project["parts"] = []

    if name is None:
        base = f"{source['name']}_fillet3d"
        name = _unique_name(project, base)

    result: Dict[str, Any] = {
        "id": _next_id(project),
        "name": name,
        "type": "fillet_3d",
        "params": {
            "original_id": source["id"],
            "radius": rad,
            "edges": edges,
        },
        "placement": deepcopy(source["placement"]),
        "material_index": source.get("material_index"),
        "visible": True,
    }

    project["parts"].append(result)
    return result


def chamfer_3d(
    project: Dict[str, Any],
    index: int,
    size: float,
    edges: str = "all",
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Apply a Part-level 3-D chamfer to the part at *index*.

    Parameters
    ----------
    size : float
        Chamfer size (distance).
    edges : str
        Which edges to chamfer — ``"all"`` or a comma-separated list of
        edge indices.
    """
    source = get_part(project, index)

    try:
        sz = float(size)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"size must be numeric: {exc}") from exc

    if "parts" not in project:
        project["parts"] = []

    if name is None:
        base = f"{source['name']}_chamfer3d"
        name = _unique_name(project, base)

    result: Dict[str, Any] = {
        "id": _next_id(project),
        "name": name,
        "type": "chamfer_3d",
        "params": {
            "original_id": source["id"],
            "size": sz,
            "edges": edges,
        },
        "placement": deepcopy(source["placement"]),
        "material_index": source.get("material_index"),
        "visible": True,
    }

    project["parts"].append(result)
    return result


def loft_parts(
    project: Dict[str, Any],
    section_indices: List[int],
    solid: bool = True,
    ruled: bool = False,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Loft through a series of cross-section parts.

    Parameters
    ----------
    section_indices : list[int]
        Ordered indices of the profile/section parts.
    solid : bool
        Whether to create a solid (True) or a shell (False).
    ruled : bool
        Whether to use ruled surfaces between sections.
    """
    if len(section_indices) < 2:
        raise ValueError("loft requires at least 2 section indices")

    section_ids: List[int] = []
    for idx in section_indices:
        part = get_part(project, idx)
        section_ids.append(part["id"])

    if "parts" not in project:
        project["parts"] = []

    if name is None:
        base = "Loft"
        name = _unique_name(project, base)

    result: Dict[str, Any] = {
        "id": _next_id(project),
        "name": name,
        "type": "loft",
        "params": {
            "section_ids": section_ids,
            "solid": solid,
            "ruled": ruled,
        },
        "placement": {
            "position": [0.0, 0.0, 0.0],
            "rotation": [0.0, 0.0, 0.0],
        },
        "material_index": None,
        "visible": True,
    }

    project["parts"].append(result)
    return result


def sweep_part(
    project: Dict[str, Any],
    profile_index: int,
    path_index: int,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Sweep a profile shape along a path shape.

    Parameters
    ----------
    profile_index : int
        Index of the profile (cross-section) part.
    path_index : int
        Index of the path (spine) part.
    """
    profile = get_part(project, profile_index)
    path = get_part(project, path_index)

    if "parts" not in project:
        project["parts"] = []

    if name is None:
        base = "Sweep"
        name = _unique_name(project, base)

    result: Dict[str, Any] = {
        "id": _next_id(project),
        "name": name,
        "type": "sweep",
        "params": {
            "profile_id": profile["id"],
            "path_id": path["id"],
        },
        "placement": {
            "position": [0.0, 0.0, 0.0],
            "rotation": [0.0, 0.0, 0.0],
        },
        "material_index": None,
        "visible": True,
    }

    project["parts"].append(result)
    return result


def revolve_part(
    project: Dict[str, Any],
    index: int,
    axis: str = "Z",
    angle: float = 360.0,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Revolve the part at *index* around an axis.

    Parameters
    ----------
    axis : str
        Axis of revolution — ``"X"``, ``"Y"``, or ``"Z"``.
    angle : float
        Revolution angle in degrees (default 360 for a full revolution).
    """
    valid_axes = {"X", "Y", "Z"}
    if axis not in valid_axes:
        raise ValueError(
            f"Unknown axis '{axis}'. Valid: {', '.join(sorted(valid_axes))}"
        )

    source = get_part(project, index)

    try:
        ang = float(angle)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"angle must be numeric: {exc}") from exc

    if "parts" not in project:
        project["parts"] = []

    if name is None:
        base = f"{source['name']}_revolve"
        name = _unique_name(project, base)

    result: Dict[str, Any] = {
        "id": _next_id(project),
        "name": name,
        "type": "revolve",
        "params": {
            "original_id": source["id"],
            "axis": axis,
            "angle": ang,
        },
        "placement": deepcopy(source["placement"]),
        "material_index": source.get("material_index"),
        "visible": True,
    }

    project["parts"].append(result)
    return result


def extrude_part(
    project: Dict[str, Any],
    index: int,
    direction: Optional[List[float]] = None,
    length: float = 10.0,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Extrude the part at *index* along a direction vector.

    Parameters
    ----------
    direction : list[float] or None
        ``[dx, dy, dz]`` unit direction. Defaults to ``[0, 0, 1]``.
    length : float
        Extrusion length.
    """
    source = get_part(project, index)

    dir_vec = _validate_vec3(direction, "direction") if direction is not None else [0.0, 0.0, 1.0]

    try:
        lng = float(length)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"length must be numeric: {exc}") from exc

    if "parts" not in project:
        project["parts"] = []

    if name is None:
        base = f"{source['name']}_extrude"
        name = _unique_name(project, base)

    result: Dict[str, Any] = {
        "id": _next_id(project),
        "name": name,
        "type": "extrude",
        "params": {
            "original_id": source["id"],
            "direction": dir_vec,
            "length": lng,
        },
        "placement": deepcopy(source["placement"]),
        "material_index": source.get("material_index"),
        "visible": True,
    }

    project["parts"].append(result)
    return result


def section_part(
    project: Dict[str, Any],
    index: int,
    plane: str = "XY",
    offset: float = 0.0,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a cross-section of the part at *index*.

    Parameters
    ----------
    plane : str
        Cutting plane — ``"XY"``, ``"XZ"``, or ``"YZ"``.
    offset : float
        Distance to shift the cutting plane along its normal.
    """
    valid_planes = {"XY", "XZ", "YZ"}
    if plane not in valid_planes:
        raise ValueError(
            f"Unknown section plane '{plane}'. Valid: {', '.join(sorted(valid_planes))}"
        )

    source = get_part(project, index)

    try:
        off = float(offset)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"offset must be numeric: {exc}") from exc

    if "parts" not in project:
        project["parts"] = []

    if name is None:
        base = f"{source['name']}_section"
        name = _unique_name(project, base)

    result: Dict[str, Any] = {
        "id": _next_id(project),
        "name": name,
        "type": "section",
        "params": {
            "original_id": source["id"],
            "plane": plane,
            "offset": off,
        },
        "placement": deepcopy(source["placement"]),
        "material_index": source.get("material_index"),
        "visible": True,
    }

    project["parts"].append(result)
    return result


def slice_part(
    project: Dict[str, Any],
    index: int,
    plane: str = "XY",
    offset: float = 0.0,
) -> Dict[str, Any]:
    """Slice the part at *index* into two halves along a plane.

    The original part is marked ``visible=False`` and two new parts are
    created — one for each side of the cutting plane.

    Returns a dict with keys ``"positive"`` and ``"negative"``, each
    holding the newly created part dictionary, plus ``"positive_index"``
    and ``"negative_index"`` with their list positions.
    """
    valid_planes = {"XY", "XZ", "YZ"}
    if plane not in valid_planes:
        raise ValueError(
            f"Unknown slice plane '{plane}'. Valid: {', '.join(sorted(valid_planes))}"
        )

    source = get_part(project, index)

    try:
        off = float(offset)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"offset must be numeric: {exc}") from exc

    source["visible"] = False

    if "parts" not in project:
        project["parts"] = []

    pos_name = _unique_name(project, f"{source['name']}_slice_pos")
    pos_part: Dict[str, Any] = {
        "id": _next_id(project),
        "name": pos_name,
        "type": "slice",
        "params": {
            "original_id": source["id"],
            "plane": plane,
            "offset": off,
            "side": "positive",
        },
        "placement": deepcopy(source["placement"]),
        "material_index": source.get("material_index"),
        "visible": True,
    }
    project["parts"].append(pos_part)
    pos_index = len(project["parts"]) - 1

    neg_name = _unique_name(project, f"{source['name']}_slice_neg")
    neg_part: Dict[str, Any] = {
        "id": _next_id(project),
        "name": neg_name,
        "type": "slice",
        "params": {
            "original_id": source["id"],
            "plane": plane,
            "offset": off,
            "side": "negative",
        },
        "placement": deepcopy(source["placement"]),
        "material_index": source.get("material_index"),
        "visible": True,
    }
    project["parts"].append(neg_part)
    neg_index = len(project["parts"]) - 1

    return {
        "positive": pos_part,
        "negative": neg_part,
        "positive_index": pos_index,
        "negative_index": neg_index,
    }


# ---------------------------------------------------------------------------
# Additional geometry creators
# ---------------------------------------------------------------------------

def add_line_3d(
    project: Dict[str, Any],
    start: Optional[List[float]] = None,
    end: Optional[List[float]] = None,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Add a 3-D line (edge) between two points.

    Parameters
    ----------
    start : list[float] or None
        ``[x, y, z]`` start point. Defaults to ``[0, 0, 0]``.
    end : list[float] or None
        ``[x, y, z]`` end point. Defaults to ``[10, 0, 0]``.

    Returns the newly created part.
    """
    s = _validate_vec3(start, "start") if start is not None else [0.0, 0.0, 0.0]
    e = _validate_vec3(end, "end") if end is not None else [10.0, 0.0, 0.0]

    if "parts" not in project:
        project["parts"] = []

    if name is None:
        base = "Line3D"
        name = _unique_name(project, base)

    part: Dict[str, Any] = {
        "id": _next_id(project),
        "name": name,
        "type": "line_3d",
        "params": {
            "start": s,
            "end": e,
        },
        "placement": {
            "position": [0.0, 0.0, 0.0],
            "rotation": [0.0, 0.0, 0.0],
        },
        "material_index": None,
        "visible": True,
    }

    project["parts"].append(part)
    return part


def add_wire(
    project: Dict[str, Any],
    points: List[List[float]],
    closed: bool = False,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Add a wire (polyline) from a list of ``[x, y, z]`` points.

    Parameters
    ----------
    points : list[list[float]]
        Ordered vertices. Must contain at least 2 points.
    closed : bool
        If *True* the wire forms a closed loop.

    Returns the newly created part.
    """
    if not isinstance(points, (list, tuple)) or len(points) < 2:
        raise ValueError("points must be a list of at least 2 [x,y,z] vertices")

    validated: List[List[float]] = []
    for i, pt in enumerate(points):
        validated.append(_validate_vec3(pt, f"points[{i}]"))

    if "parts" not in project:
        project["parts"] = []

    if name is None:
        base = "Wire"
        name = _unique_name(project, base)

    part: Dict[str, Any] = {
        "id": _next_id(project),
        "name": name,
        "type": "wire",
        "params": {
            "points": validated,
            "closed": closed,
        },
        "placement": {
            "position": [0.0, 0.0, 0.0],
            "rotation": [0.0, 0.0, 0.0],
        },
        "material_index": None,
        "visible": True,
    }

    project["parts"].append(part)
    return part


def add_polygon_3d(
    project: Dict[str, Any],
    center: Optional[List[float]] = None,
    sides: int = 6,
    radius: float = 5.0,
    normal: Optional[List[float]] = None,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Add a regular polygon in 3-D space.

    Parameters
    ----------
    center : list[float] or None
        ``[x, y, z]`` center point. Defaults to ``[0, 0, 0]``.
    sides : int
        Number of sides (>= 3).
    radius : float
        Circumscribed-circle radius.
    normal : list[float] or None
        ``[nx, ny, nz]`` plane normal. Defaults to ``[0, 0, 1]``.

    Returns the newly created part.
    """
    c = _validate_vec3(center, "center") if center is not None else [0.0, 0.0, 0.0]
    n = _validate_vec3(normal, "normal") if normal is not None else [0.0, 0.0, 1.0]

    if not isinstance(sides, int) or sides < 3:
        raise ValueError(f"sides must be an integer >= 3, got {sides}")

    try:
        rad = float(radius)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"radius must be numeric: {exc}") from exc

    if "parts" not in project:
        project["parts"] = []

    if name is None:
        base = "Polygon3D"
        name = _unique_name(project, base)

    part: Dict[str, Any] = {
        "id": _next_id(project),
        "name": name,
        "type": "polygon_3d",
        "params": {
            "center": c,
            "sides": float(sides),
            "radius": rad,
            "normal": n,
        },
        "placement": {
            "position": [0.0, 0.0, 0.0],
            "rotation": [0.0, 0.0, 0.0],
        },
        "material_index": None,
        "visible": True,
    }

    project["parts"].append(part)
    return part


# ---------------------------------------------------------------------------
# Part info query
# ---------------------------------------------------------------------------

def _estimate_geometry(part_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Compute estimated volume, surface area, and bounding box from params.

    Returns a dict with keys ``volume``, ``area``, and ``bounding_box``
    (each may be *None* when computation is not applicable).
    """
    volume: Optional[float] = None
    area: Optional[float] = None
    bbox: Optional[Dict[str, float]] = None

    if part_type == "box":
        l, w, h = params["length"], params["width"], params["height"]
        volume = l * w * h
        area = 2.0 * (l * w + w * h + l * h)
        bbox = {"x": l, "y": w, "z": h}

    elif part_type == "cylinder":
        r, h = params["radius"], params["height"]
        volume = math.pi * r * r * h
        area = 2.0 * math.pi * r * (r + h)
        bbox = {"x": 2 * r, "y": 2 * r, "z": h}

    elif part_type == "sphere":
        r = params["radius"]
        volume = (4.0 / 3.0) * math.pi * r ** 3
        area = 4.0 * math.pi * r ** 2
        bbox = {"x": 2 * r, "y": 2 * r, "z": 2 * r}

    elif part_type == "cone":
        r1, r2, h = params["radius1"], params["radius2"], params["height"]
        volume = math.pi * h / 3.0 * (r1 ** 2 + r1 * r2 + r2 ** 2)
        # Lateral + two caps
        slant = math.sqrt(h ** 2 + (r1 - r2) ** 2)
        area = (
            math.pi * (r1 + r2) * slant
            + math.pi * r1 ** 2
            + math.pi * r2 ** 2
        )
        rmax = max(r1, r2)
        bbox = {"x": 2 * rmax, "y": 2 * rmax, "z": h}

    elif part_type == "torus":
        R, r = params["radius1"], params["radius2"]
        volume = 2.0 * math.pi ** 2 * R * r ** 2
        area = 4.0 * math.pi ** 2 * R * r
        bbox = {"x": 2 * (R + r), "y": 2 * (R + r), "z": 2 * r}

    return {
        "volume": volume,
        "area": area,
        "bounding_box": bbox,
    }


def part_bounds(
    project: Dict[str, Any],
    index: int,
) -> Dict[str, Any]:
    """Return local and world bounding-box data for a part."""
    part = get_part(project, index)
    local = _local_bounds(str(part["type"]).lower(), part.get("params", {}))
    world = _world_bounds(part)
    return {
        "id": part["id"],
        "name": part["name"],
        "type": part["type"],
        "local_bounding_box": local,
        "world_bounding_box": world,
    }


def align_part(
    project: Dict[str, Any],
    index: int,
    target_index: int,
    *,
    x: Optional[str] = None,
    to_x: Optional[str] = None,
    dx: float = 0.0,
    y: Optional[str] = None,
    to_y: Optional[str] = None,
    dy: float = 0.0,
    z: Optional[str] = None,
    to_z: Optional[str] = None,
    dz: float = 0.0,
) -> Dict[str, Any]:
    """Move a part so selected bbox anchors match another part's anchors."""
    part = get_part(project, index)
    target = get_part(project, target_index)
    source_bounds = _world_bounds(part)
    target_bounds = _world_bounds(target)
    if source_bounds is None:
        raise ValueError(
            f"Part #{index} ({part['name']}) does not support bounding-box alignment for type '{part['type']}'"
        )
    if target_bounds is None:
        raise ValueError(
            f"Target part #{target_index} ({target['name']}) does not support bounding-box alignment for type '{target['type']}'"
        )

    updates = {
        "x": (x, to_x, float(dx)),
        "y": (y, to_y, float(dy)),
        "z": (z, to_z, float(dz)),
    }
    if not any(source_anchor or target_anchor for source_anchor, target_anchor, _ in updates.values()):
        raise ValueError("At least one axis alignment must be specified")

    position = _validate_vec3(part["placement"]["position"], "position")
    delta = [0.0, 0.0, 0.0]
    axis_to_index = {"x": 0, "y": 1, "z": 2}

    for axis, (source_anchor, target_anchor, offset) in updates.items():
        if source_anchor is None and target_anchor is None:
            continue
        if source_anchor is None or target_anchor is None:
            raise ValueError(f"Axis '{axis}' requires both source and target anchors")
        shift = (
            _anchor_value(target_bounds, axis, target_anchor)
            + offset
            - _anchor_value(source_bounds, axis, source_anchor)
        )
        delta[axis_to_index[axis]] = shift
        position[axis_to_index[axis]] += shift

    part["placement"]["position"] = position
    updated_bounds = _world_bounds(part)
    return {
        "part_index": index,
        "target_index": target_index,
        "part_name": part["name"],
        "target_name": target["name"],
        "delta": {"x": delta[0], "y": delta[1], "z": delta[2]},
        "placement": deepcopy(part["placement"]),
        "world_bounding_box": updated_bounds,
    }


def part_info(
    project: Dict[str, Any],
    index: int,
) -> Dict[str, Any]:
    """Return detailed information about the part at *index*.

    The returned dictionary includes:

    - ``type`` — the part type string.
    - ``params`` — a copy of the part's parameter dict.
    - ``placement`` — position and rotation.
    - ``material_index`` — index into the materials list (or *None*).
    - ``visible`` — visibility flag.
    - ``volume`` — estimated volume (or *None* if not computable).
    - ``area`` — estimated surface area (or *None*).
    - ``bounding_box`` — estimated axis-aligned bounding box ``{x, y, z}``
      (or *None*).
    """
    part = get_part(project, index)
    geo = _estimate_geometry(part["type"], part.get("params", {}))
    world = _world_bounds(part)

    return {
        "id": part["id"],
        "name": part["name"],
        "type": part["type"],
        "params": deepcopy(part["params"]),
        "placement": deepcopy(part["placement"]),
        "material_index": part.get("material_index"),
        "visible": part.get("visible", True),
        "volume": geo["volume"],
        "area": geo["area"],
        "bounding_box": geo["bounding_box"],
        "world_bounding_box": world,
    }
