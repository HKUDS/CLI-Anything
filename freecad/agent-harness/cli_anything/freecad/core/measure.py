"""FreeCAD CLI - Measurement and geometry analysis module.

Computes measurements from part/body geometry stored in the JSON project
state.  For simple primitives (box, cylinder, sphere, cone, torus) the
module implements exact mathematical formulas.  More complex shapes store
measurement requests that are resolved via macro execution.
"""

import math
from typing import Any, Dict, List, Optional

from cli_anything.freecad.core.document import ensure_collection
from cli_anything.freecad.core.parts import (
    PRIMITIVES,
    _rotation_matrix,
    get_part,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _next_measurement_id(project: Dict[str, Any]) -> int:
    """Return the next available integer ID for measurements."""
    items = project.get("measurements", [])
    if not items:
        return 1
    return max(item["id"] for item in items) + 1


def _store_measurement(
    project: Dict[str, Any],
    kind: str,
    result: Dict[str, Any],
) -> Dict[str, Any]:
    """Wrap *result* in a measurement record and append to the project."""
    measurements = ensure_collection(project, "measurements")
    record: Dict[str, Any] = {
        "id": _next_measurement_id(project),
        "kind": kind,
        **result,
    }
    measurements.append(record)
    return record


def _get_position(part: Dict[str, Any]) -> List[float]:
    """Return the placement position of a part as ``[x, y, z]``."""
    return list(part["placement"]["position"])


def _local_bbox_center(part: Dict[str, Any]) -> List[float]:
    """Return the bounding-box centre in the part frame, before placement.

    A box and a wedge start at a corner, a cylinder and a cone are centred
    on +Z with the base at the origin, and a sphere and a torus are centred
    on the origin. Unknown parts have no local offset.
    """
    p = part["params"]
    t = part["type"]

    if t == "box":
        return [
            p["length"] / 2.0,
            p["width"] / 2.0,
            p["height"] / 2.0,
        ]
    elif t == "cylinder":
        return [0.0, 0.0, p["height"] / 2.0]
    elif t == "sphere":
        return [0.0, 0.0, 0.0]
    elif t == "cone":
        return [0.0, 0.0, p["height"] / 2.0]
    elif t == "torus":
        return [0.0, 0.0, 0.0]
    elif t == "wedge":
        return [
            (p["xmin"] + p["xmax"]) / 2.0,
            (p["ymin"] + p["ymax"]) / 2.0,
            (p["zmin"] + p["zmax"]) / 2.0,
        ]
    return [0.0, 0.0, 0.0]


def _rotation_to_matrix(rotation: Any) -> List[List[float]]:
    """Normalize a placement rotation to one 3x3 matrix.

    The forms are exactly those ``_gen_placements`` emits to FreeCAD:

    * list or tuple ``[rx, ry, rz]`` degrees becomes
      ``FreeCAD.Rotation(rz, ry, rx)`` (``Rz(rz) @ Ry(ry) @ Rx(rx)``).
    * dict ``{"axis": {"x", "y", "z"}, "angle": degrees}`` becomes
      ``FreeCAD.Rotation(Vector(axis), angle)``. Missing axis components
      default to ``x=0``, ``y=0``, ``z=1``. A zero-length axis falls back
      to +Z, matching FreeCAD.
    * dict ``{"yaw", "pitch", "roll"}`` degrees becomes
      ``FreeCAD.Rotation(yaw, pitch, roll)``, which is list
      ``[roll, pitch, yaw]``.
    * any other dict, including ``{}``, is the identity.
    * any other type raises ``TypeError``. ``_gen_placements`` rejects
      JSON null, numbers, bools, and strings as well.
    """
    if isinstance(rotation, (list, tuple)):
        rx = float(rotation[0]) if len(rotation) > 0 else 0.0
        ry = float(rotation[1]) if len(rotation) > 1 else 0.0
        rz = float(rotation[2]) if len(rotation) > 2 else 0.0
        return _rotation_matrix([rx, ry, rz])
    if isinstance(rotation, dict):
        if "axis" in rotation and "angle" in rotation:
            return _axis_angle_matrix(rotation["axis"], rotation["angle"])
        if any(key in rotation for key in ("yaw", "pitch", "roll")):
            yaw = float(rotation.get("yaw", 0.0))
            pitch = float(rotation.get("pitch", 0.0))
            roll = float(rotation.get("roll", 0.0))
            return _rotation_matrix([roll, pitch, yaw])
        return _rotation_matrix([0.0, 0.0, 0.0])
    raise TypeError(
        "rotation must be a list, tuple, or dict, "
        f"not {type(rotation).__name__}"
    )


def _axis_angle_matrix(axis: Any, angle_deg: Any) -> List[List[float]]:
    """Rodrigues matrix for FreeCAD's degree axis-angle constructor."""
    if not isinstance(axis, dict):
        raise TypeError("placement rotation axis must be a dict with x, y, z")
    ax = float(axis.get("x", 0.0))
    ay = float(axis.get("y", 0.0))
    az = float(axis.get("z", 1.0))
    theta = math.radians(float(angle_deg))
    length = math.hypot(ax, ay, az)
    if length == 0.0:
        ax, ay, az = 0.0, 0.0, 1.0
    else:
        ax /= length
        ay /= length
        az /= length
    cosine = math.cos(theta)
    sine = math.sin(theta)
    complement = 1.0 - cosine
    return [
        [
            cosine + complement * ax * ax,
            complement * ax * ay - sine * az,
            complement * ax * az + sine * ay,
        ],
        [
            complement * ay * ax + sine * az,
            cosine + complement * ay * ay,
            complement * ay * az - sine * ax,
        ],
        [
            complement * az * ax - sine * ay,
            complement * az * ay + sine * ax,
            cosine + complement * az * az,
        ],
    ]


def _part_rotation_matrix(part: Dict[str, Any]) -> List[List[float]]:
    """Rotation matrix for a part placement. Missing rotation is identity."""
    rotation = part.get("placement", {}).get("rotation", [0.0, 0.0, 0.0])
    return _rotation_to_matrix(rotation)


def _apply_rotation(
    point: List[float],
    matrix: List[List[float]],
    translation: List[float],
) -> List[float]:
    """Apply a placement matrix and translation to a local point."""
    x, y, z = (float(v) for v in point)
    tx, ty, tz = translation
    return [
        matrix[0][0] * x + matrix[0][1] * y + matrix[0][2] * z + tx,
        matrix[1][0] * x + matrix[1][1] * y + matrix[1][2] * z + ty,
        matrix[2][0] * x + matrix[2][1] * y + matrix[2][2] * z + tz,
    ]


def _bbox_center(part: Dict[str, Any]) -> List[float]:
    """Return the centre of the part's world axis-aligned bounds.

    The midpoint is taken from the same min/max as ``measure_bounding_box``.
    A symmetric solid's midpoint is the rotated local centre. An
    unequal-radius cone is not: its end disks set asymmetric extrema, so
    rotating the local ``height / 2`` point is not the world-bounds centre.
    """
    bounds = _part_world_aabb(part)
    if bounds is None:
        pos = _get_position(part)
        return _apply_rotation([0.0, 0.0, 0.0], _part_rotation_matrix(part), pos)
    bb_min, bb_max = bounds
    return [(bb_min[i] + bb_max[i]) / 2.0 for i in range(3)]


def _uniform_center_of_mass(part: Dict[str, Any]) -> List[float]:
    """Centre of mass of a uniform-density primitive in world coordinates.

    Local offsets use the same part frames as ``_local_bbox_center``. A
    conical frustum is the one primitive whose centroid is not the
    bounding-box centre. Measured from the radius1 face along +Z:

        z = H * (R1**2 + 2*R1*R2 + 3*R2**2) / (4 * (R1**2 + R1*R2 + R2**2))

    A zero-radius cone (both radii 0) falls back to the segment midpoint.
    Revolution angles are ignored, matching ``_compute_volume``.

    The local offset is rotated by ``_rotation_to_matrix``, which accepts
    every placement form ``_gen_placements`` emits, then the placement
    position is added.
    """
    pos = _get_position(part)
    if part["type"] == "cone":
        p = part["params"]
        r1 = float(p["radius1"])
        r2 = float(p["radius2"])
        height = float(p["height"])
        denom = r1 * r1 + r1 * r2 + r2 * r2
        if denom == 0.0:
            z_offset = height / 2.0
        else:
            z_offset = height * (r1 * r1 + 2.0 * r1 * r2 + 3.0 * r2 * r2) / (4.0 * denom)
        local = [0.0, 0.0, z_offset]
    else:
        local = _local_bbox_center(part)

    return _apply_rotation(local, _part_rotation_matrix(part), pos)


# ---------------------------------------------------------------------------
# Volume / area formulas
# ---------------------------------------------------------------------------

def _compute_volume(part: Dict[str, Any]) -> Optional[float]:
    """Compute volume from primitive parameters. Returns *None* for unknowns."""
    p = part["params"]
    t = part["type"]

    if t == "box":
        return p["length"] * p["width"] * p["height"]
    elif t == "cylinder":
        return math.pi * p["radius"] ** 2 * p["height"]
    elif t == "sphere":
        return (4.0 / 3.0) * math.pi * p["radius"] ** 3
    elif t == "cone":
        r1, r2, h = p["radius1"], p["radius2"], p["height"]
        return (1.0 / 3.0) * math.pi * h * (r1 ** 2 + r1 * r2 + r2 ** 2)
    elif t == "torus":
        R, r = p["radius1"], p["radius2"]
        return 2.0 * math.pi ** 2 * R * r ** 2
    elif t == "wedge":
        # Approximate as bounding box (exact wedge needs more info)
        dx = p["xmax"] - p["xmin"]
        dy = p["ymax"] - p["ymin"]
        dz = p["zmax"] - p["zmin"]
        return dx * dy * dz
    return None


def _compute_area(part: Dict[str, Any]) -> Optional[float]:
    """Compute surface area from primitive parameters. Returns *None* for unknowns."""
    p = part["params"]
    t = part["type"]

    if t == "box":
        l, w, h = p["length"], p["width"], p["height"]
        return 2.0 * (l * w + w * h + l * h)
    elif t == "cylinder":
        r, h = p["radius"], p["height"]
        return 2.0 * math.pi * r * (r + h)
    elif t == "sphere":
        return 4.0 * math.pi * p["radius"] ** 2
    elif t == "cone":
        r1, r2, h = p["radius1"], p["radius2"], p["height"]
        slant = math.sqrt((r1 - r2) ** 2 + h ** 2)
        return (
            math.pi * r1 ** 2
            + math.pi * r2 ** 2
            + math.pi * (r1 + r2) * slant
        )
    elif t == "torus":
        R, r = p["radius1"], p["radius2"]
        return 4.0 * math.pi ** 2 * R * r
    elif t == "wedge":
        dx = p["xmax"] - p["xmin"]
        dy = p["ymax"] - p["ymin"]
        dz = p["zmax"] - p["zmin"]
        return 2.0 * (dx * dy + dy * dz + dx * dz)
    return None


# ---------------------------------------------------------------------------
# Inertia helpers
# ---------------------------------------------------------------------------

def _compute_inertia(part: Dict[str, Any]) -> Optional[Dict[str, float]]:
    """Estimate principal moments of inertia (Ixx, Iyy, Izz) assuming unit density."""
    p = part["params"]
    t = part["type"]
    vol = _compute_volume(part)
    if vol is None:
        return None
    m = vol  # unit density

    if t == "box":
        l, w, h = p["length"], p["width"], p["height"]
        return {
            "Ixx": m * (w ** 2 + h ** 2) / 12.0,
            "Iyy": m * (l ** 2 + h ** 2) / 12.0,
            "Izz": m * (l ** 2 + w ** 2) / 12.0,
        }
    elif t == "cylinder":
        r, h = p["radius"], p["height"]
        return {
            "Ixx": m * (3.0 * r ** 2 + h ** 2) / 12.0,
            "Iyy": m * (3.0 * r ** 2 + h ** 2) / 12.0,
            "Izz": m * r ** 2 / 2.0,
        }
    elif t == "sphere":
        r = p["radius"]
        I = 2.0 * m * r ** 2 / 5.0
        return {"Ixx": I, "Iyy": I, "Izz": I}
    elif t == "cone":
        r1, r2, h = p["radius1"], p["radius2"], p["height"]
        # Approximate using average radius
        r_avg = (r1 + r2) / 2.0
        return {
            "Ixx": m * (3.0 * r_avg ** 2 + h ** 2) / 12.0,
            "Iyy": m * (3.0 * r_avg ** 2 + h ** 2) / 12.0,
            "Izz": m * r_avg ** 2 / 2.0,
        }
    elif t == "torus":
        R, r = p["radius1"], p["radius2"]
        Ixx = m * (5.0 * r ** 2 + 4.0 * R ** 2) / 8.0
        return {
            "Ixx": Ixx,
            "Iyy": Ixx,
            "Izz": m * (3.0 * r ** 2 + 4.0 * R ** 2) / 4.0,
        }
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def measure_distance(
    project: Dict[str, Any], index1: int, index2: int,
    additive: bool = False,
) -> Dict[str, Any]:
    """Measure the Euclidean distance between two parts (bounding-box centres).

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    index1 : int
        Index of the first part in ``project["parts"]``.
    index2 : int
        Index of the second part in ``project["parts"]``.

    Returns
    -------
    dict
        Measurement record with ``distance`` value and axis deltas.
    """
    part1 = get_part(project, index1)
    part2 = get_part(project, index2)

    c1 = _bbox_center(part1)
    c2 = _bbox_center(part2)

    dx = c2[0] - c1[0]
    dy = c2[1] - c1[1]
    dz = c2[2] - c1[2]
    dist = math.sqrt(dx ** 2 + dy ** 2 + dz ** 2)

    result: Dict[str, Any] = {
        "part1_index": index1,
        "part2_index": index2,
        "distance": round(dist, 6),
        "delta": [round(dx, 6), round(dy, 6), round(dz, 6)],
    }
    if additive:
        result["additive"] = True
    return _store_measurement(project, "distance", result)


def measure_length(
    project: Dict[str, Any], index: int, edge_ref: Optional[str] = None,
    additive: bool = False,
) -> Dict[str, Any]:
    """Estimate the length of a part edge.

    For primitives without an explicit *edge_ref*, the longest dimension
    is returned as an estimate.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    index : int
        Index of the part in ``project["parts"]``.
    edge_ref : str or None
        Optional edge reference (e.g. ``"Edge1"``).  When supplied the
        measurement is stored as a deferred request.

    Returns
    -------
    dict
        Measurement record with ``length`` value.
    """
    part = get_part(project, index)
    p = part["params"]
    t = part["type"]
    length: Optional[float] = None

    if edge_ref is not None:
        # Deferred — requires macro execution
        result_deferred: Dict[str, Any] = {
            "part_index": index,
            "edge_ref": edge_ref,
            "length": None,
            "deferred": True,
        }
        if additive:
            result_deferred["additive"] = True
        return _store_measurement(project, "length", result_deferred)

    if t == "box":
        length = max(p["length"], p["width"], p["height"])
    elif t == "cylinder":
        length = p["height"]
    elif t == "sphere":
        length = 2.0 * p["radius"]
    elif t == "cone":
        length = p["height"]
    elif t == "torus":
        length = 2.0 * math.pi * p["radius1"]
    elif t == "wedge":
        length = max(
            p["xmax"] - p["xmin"],
            p["ymax"] - p["ymin"],
            p["zmax"] - p["zmin"],
        )

    result_len: Dict[str, Any] = {
        "part_index": index,
        "edge_ref": edge_ref,
        "length": round(length, 6) if length is not None else None,
        "deferred": length is None,
    }
    if additive:
        result_len["additive"] = True
    return _store_measurement(project, "length", result_len)


def measure_angle(
    project: Dict[str, Any], index1: int, index2: int,
    additive: bool = False,
) -> Dict[str, Any]:
    """Measure the angle between two parts based on their centre vectors from the origin.

    The angle is computed between the vectors from the world origin to
    each part's bounding-box centre.  Returns 0.0 when either vector is
    zero-length.

    Returns
    -------
    dict
        Measurement record with ``angle_deg`` value.
    """
    part1 = get_part(project, index1)
    part2 = get_part(project, index2)

    c1 = _bbox_center(part1)
    c2 = _bbox_center(part2)

    mag1 = math.sqrt(sum(v ** 2 for v in c1))
    mag2 = math.sqrt(sum(v ** 2 for v in c2))

    if mag1 == 0.0 or mag2 == 0.0:
        angle_deg = 0.0
    else:
        dot = sum(a * b for a, b in zip(c1, c2))
        cos_val = max(-1.0, min(1.0, dot / (mag1 * mag2)))
        angle_deg = math.degrees(math.acos(cos_val))

    result_angle: Dict[str, Any] = {
        "part1_index": index1,
        "part2_index": index2,
        "angle_deg": round(angle_deg, 6),
    }
    if additive:
        result_angle["additive"] = True
    return _store_measurement(project, "angle", result_angle)


def measure_area(project: Dict[str, Any], index: int, additive: bool = False) -> Dict[str, Any]:
    """Estimate the surface area of a part from its primitive parameters.

    Returns
    -------
    dict
        Measurement record with ``area`` value (or *None* for unsupported types).
    """
    part = get_part(project, index)
    area = _compute_area(part)

    result_area: Dict[str, Any] = {
        "part_index": index,
        "area": round(area, 6) if area is not None else None,
        "deferred": area is None,
    }
    if additive:
        result_area["additive"] = True
    return _store_measurement(project, "area", result_area)


def measure_volume(project: Dict[str, Any], index: int, additive: bool = False) -> Dict[str, Any]:
    """Estimate the volume of a part from its primitive parameters.

    Formulas used:
    - box: V = l * w * h
    - cylinder: V = pi * r^2 * h
    - sphere: V = 4/3 * pi * r^3
    - cone: V = 1/3 * pi * h * (r1^2 + r1*r2 + r2^2)
    - torus: V = 2 * pi^2 * R * r^2

    Returns
    -------
    dict
        Measurement record with ``volume`` value (or *None* for unsupported types).
    """
    part = get_part(project, index)
    volume = _compute_volume(part)

    result_vol: Dict[str, Any] = {
        "part_index": index,
        "volume": round(volume, 6) if volume is not None else None,
        "deferred": volume is None,
    }
    if additive:
        result_vol["additive"] = True
    return _store_measurement(project, "volume", result_vol)


def measure_radius(project: Dict[str, Any], index: int, additive: bool = False) -> Dict[str, Any]:
    """Return the radius of a cylindrical, spherical, or toroidal part.

    For cones, the larger of ``radius1`` / ``radius2`` is returned.

    Returns
    -------
    dict
        Measurement record with ``radius`` value.

    Raises
    ------
    ValueError
        If the part type has no meaningful radius.
    """
    part = get_part(project, index)
    p = part["params"]
    t = part["type"]

    if t == "cylinder":
        radius = p["radius"]
    elif t == "sphere":
        radius = p["radius"]
    elif t == "cone":
        radius = max(p["radius1"], p["radius2"])
    elif t == "torus":
        radius = p["radius2"]
    else:
        raise ValueError(
            f"Part type '{t}' has no meaningful radius. "
            f"Supported: cylinder, sphere, cone, torus"
        )

    result_rad: Dict[str, Any] = {
        "part_index": index,
        "radius": round(radius, 6),
    }
    if additive:
        result_rad["additive"] = True
    return _store_measurement(project, "radius", result_rad)


def measure_diameter(project: Dict[str, Any], index: int, additive: bool = False) -> Dict[str, Any]:
    """Return the diameter of a cylindrical, spherical, or toroidal part.

    Returns
    -------
    dict
        Measurement record with ``diameter`` value.

    Raises
    ------
    ValueError
        If the part type has no meaningful diameter.
    """
    part = get_part(project, index)
    p = part["params"]
    t = part["type"]

    if t == "cylinder":
        diameter = 2.0 * p["radius"]
    elif t == "sphere":
        diameter = 2.0 * p["radius"]
    elif t == "cone":
        diameter = 2.0 * max(p["radius1"], p["radius2"])
    elif t == "torus":
        diameter = 2.0 * p["radius2"]
    else:
        raise ValueError(
            f"Part type '{t}' has no meaningful diameter. "
            f"Supported: cylinder, sphere, cone, torus"
        )

    result_dia: Dict[str, Any] = {
        "part_index": index,
        "diameter": round(diameter, 6),
    }
    if additive:
        result_dia["additive"] = True
    return _store_measurement(project, "diameter", result_dia)


def measure_position(project: Dict[str, Any], index: int, additive: bool = False) -> Dict[str, Any]:
    """Return the placement position of a part.

    Returns
    -------
    dict
        Measurement record with ``position`` ``[x, y, z]``.
    """
    part = get_part(project, index)
    pos = _get_position(part)

    result_pos: Dict[str, Any] = {
        "part_index": index,
        "position": pos,
    }
    if additive:
        result_pos["additive"] = True
    return _store_measurement(project, "position", result_pos)


def measure_center_of_mass(
    project: Dict[str, Any], index: int,
    additive: bool = False,
) -> Dict[str, Any]:
    """Estimate the centre of mass of a uniform-density part.

    Sphere, cylinder, box, wedge, and torus centroids coincide with the
    bounding-box centre. A cone does not: its centroid lies on the axis,
    at the solid-frustum position measured from the radius1 face.

    Returns
    -------
    dict
        Measurement record with ``center_of_mass`` ``[x, y, z]``.
    """
    part = get_part(project, index)
    com = _uniform_center_of_mass(part)

    result_com: Dict[str, Any] = {
        "part_index": index,
        "center_of_mass": [round(v, 6) for v in com],
    }
    if additive:
        result_com["additive"] = True
    return _store_measurement(project, "center_of_mass", result_com)


def _curved_local_support(
    part_type: str,
    params: Dict[str, Any],
    direction: List[float],
) -> float:
    """Support of a curved primitive along a local direction.

    Sphere, cylinder, cone, and torus are solids of revolution about
    local +Z. The value is the maximum of direction dot point over the solid.
    ``direction`` does not need to be a unit vector. A cone is the convex
    hull of the radius1 disk at ``z = 0`` and the radius2 disk at
    ``z = height``.
    """
    ux = float(direction[0])
    uy = float(direction[1])
    uz = float(direction[2])
    radial = math.hypot(ux, uy)
    if part_type == "sphere":
        return float(params["radius"]) * math.hypot(ux, uy, uz)
    if part_type == "cylinder":
        axial = float(params["height"]) * uz if uz > 0.0 else 0.0
        return float(params["radius"]) * radial + axial
    if part_type == "cone":
        base = float(params["radius1"]) * radial
        cap = float(params["radius2"]) * radial + float(params["height"]) * uz
        return max(base, cap)
    if part_type == "torus":
        major = float(params["radius1"])
        minor = float(params["radius2"])
        return major * radial + minor * math.hypot(ux, uy, uz)
    raise ValueError(f"not a curved primitive: {part_type}")


def _curved_support_aabb(part: Dict[str, Any]) -> tuple:
    """World axis-aligned bounds from curved-primitive support extents.

    World axis ``i`` is row ``i`` of the placement rotation. The max is the
    support of that row and the min is the negated support of the opposite
    row, then the placement position is added. The local box corners are
    not rotated: they lie outside the solid.
    """
    pos = _get_position(part)
    matrix = _part_rotation_matrix(part)
    part_type = part["type"]
    params = part["params"]
    bb_min: List[float] = []
    bb_max: List[float] = []
    for axis in range(3):
        row = matrix[axis]
        opposite = [-component for component in row]
        bb_max.append(pos[axis] + _curved_local_support(part_type, params, row))
        bb_min.append(
            pos[axis] - _curved_local_support(part_type, params, opposite)
        )
    return bb_min, bb_max

def _rotated_aabb(
    part: Dict[str, Any],
    local_min: List[float],
    local_max: List[float],
) -> tuple:
    """Axis-aligned bounds of a local box after the placement rotation.

    Corners are rotated about the placement, then the world-axis min and
    max are taken. An identity rotation leaves the translated local box
    unchanged.
    """
    pos = _get_position(part)
    matrix = _part_rotation_matrix(part)
    corners = [
        _apply_rotation([x, y, z], matrix, pos)
        for x in (local_min[0], local_max[0])
        for y in (local_min[1], local_max[1])
        for z in (local_min[2], local_max[2])
    ]
    bb_min = [min(corner[axis] for corner in corners) for axis in range(3)]
    bb_max = [max(corner[axis] for corner in corners) for axis in range(3)]
    return bb_min, bb_max


def _part_world_aabb(part: Dict[str, Any]) -> Optional[tuple]:
    """World min/max shared by bounding-box and centre measurements.

    Sphere, cylinder, cone, and torus use support extents. Box and wedge
    rotate the corners of the local parameter box. Other parts have no
    analytic bounds.
    """
    part_type = part["type"]
    params = part["params"]
    if part_type in ("sphere", "cylinder", "cone", "torus"):
        return _curved_support_aabb(part)
    if part_type == "box":
        return _rotated_aabb(
            part,
            [0.0, 0.0, 0.0],
            [float(params["length"]), float(params["width"]), float(params["height"])],
        )
    if part_type == "wedge":
        return _rotated_aabb(
            part,
            [float(params["xmin"]), float(params["ymin"]), float(params["zmin"])],
            [float(params["xmax"]), float(params["ymax"]), float(params["zmax"])],
        )
    return None


def measure_bounding_box(
    project: Dict[str, Any], index: int,
    additive: bool = False,
) -> Dict[str, Any]:
    """Compute the axis-aligned bounding box of a part.

    Box and wedge bounds rotate the corners of the local box. Sphere,
    cylinder, cone, and torus bounds are support extents of the solid in
    the placement frame, so a non-axis-aligned rotation does not inflate
    the box to those corners.

    Returns
    -------
    dict
        Measurement record with ``min``, ``max``, and ``size`` vectors.
    """
    part = get_part(project, index)
    bounds = _part_world_aabb(part)
    if bounds is None:
        # Unknown / boolean — deferred
        result_bb_def: Dict[str, Any] = {
            "part_index": index,
            "min": None,
            "max": None,
            "size": None,
            "deferred": True,
        }
        if additive:
            result_bb_def["additive"] = True
        return _store_measurement(project, "bounding_box", result_bb_def)

    bb_min, bb_max = bounds
    size = [bb_max[i] - bb_min[i] for i in range(3)]

    result_bb: Dict[str, Any] = {
        "part_index": index,
        "min": [round(v, 6) for v in bb_min],
        "max": [round(v, 6) for v in bb_max],
        "size": [round(v, 6) for v in size],
        "deferred": False,
    }
    if additive:
        result_bb["additive"] = True
    return _store_measurement(project, "bounding_box", result_bb)


def measure_inertia(project: Dict[str, Any], index: int, additive: bool = False) -> Dict[str, Any]:
    """Estimate the principal moments of inertia (unit density).

    Returns
    -------
    dict
        Measurement record with ``Ixx``, ``Iyy``, ``Izz`` values.
    """
    part = get_part(project, index)
    inertia = _compute_inertia(part)

    if inertia is not None:
        inertia = {k: round(v, 6) for k, v in inertia.items()}

    result_inertia: Dict[str, Any] = {
        "part_index": index,
        "inertia": inertia,
        "deferred": inertia is None,
    }
    if additive:
        result_inertia["additive"] = True
    return _store_measurement(project, "inertia", result_inertia)


def check_geometry(
    project: Dict[str, Any],
    index: int,
    include_valid: bool = False,
    skip_objects: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """Perform basic geometry validation on a part.

    Checks that all numeric parameters are positive and that the part
    type is a known primitive.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    index : int
        Index of the part in ``project["parts"]``.
    include_valid : bool
        When ``True``, also reports valid shape entries in ``valid_entries``
        (default ``False``).
    skip_objects : list[int] or None
        When provided, excludes these part indices from the check.  If the
        requested *index* is in the skip list the result is returned
        immediately with ``"skipped": True``.

    Returns
    -------
    dict
        Record with ``valid`` boolean and list of ``issues``.
    """
    if skip_objects is not None and index in skip_objects:
        return _store_measurement(project, "geometry_check", {
            "part_index": index,
            "valid": True,
            "issues": [],
            "skipped": True,
        })

    part = get_part(project, index)
    issues: List[str] = []
    valid_entries: List[str] = []

    t = part["type"]
    if t not in PRIMITIVES:
        issues.append(f"Unknown primitive type '{t}'")
    else:
        p = part["params"]
        defaults = PRIMITIVES[t]
        for key in defaults:
            if key in p:
                val = p[key]
                # Angle parameters may be negative (e.g. angle1 on sphere/torus)
                if "angle" not in key and val <= 0:
                    issues.append(f"Parameter '{key}' must be positive, got {val}")
                elif include_valid:
                    valid_entries.append(f"Parameter '{key}' = {val}")
            else:
                issues.append(f"Missing expected parameter '{key}'")

    # Validate placement exists
    placement = part.get("placement")
    if placement is None:
        issues.append("Missing 'placement' on part")
    else:
        if "position" not in placement:
            issues.append("Missing 'position' in placement")
        elif include_valid:
            valid_entries.append("Placement 'position' present")
        if "rotation" not in placement:
            issues.append("Missing 'rotation' in placement")
        elif include_valid:
            valid_entries.append("Placement 'rotation' present")

    result: Dict[str, Any] = {
        "part_index": index,
        "valid": len(issues) == 0,
        "issues": issues,
    }
    if include_valid:
        result["valid_entries"] = valid_entries
    if skip_objects is not None:
        result["skipped"] = False

    return _store_measurement(project, "geometry_check", result)
