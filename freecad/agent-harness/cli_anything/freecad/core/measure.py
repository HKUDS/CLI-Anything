"""FreeCAD CLI - Measurement and geometry analysis module.

Computes measurements from part/body geometry stored in the JSON project
state.  For simple primitives (box, cylinder, sphere, cone, torus) the
module implements exact mathematical formulas.  More complex shapes store
measurement requests that are resolved via macro execution.
"""

import math
from typing import Any, Dict, List, Optional

from cli_anything.freecad.core.document import ensure_collection
from cli_anything.freecad.core.parts import PRIMITIVES, get_part


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


def _bbox_center(part: Dict[str, Any]) -> List[float]:
    """Estimate the bounding-box centre of a part from its position and params."""
    pos = _get_position(part)
    p = part["params"]
    t = part["type"]

    if t == "box":
        return [
            pos[0] + p["length"] / 2.0,
            pos[1] + p["width"] / 2.0,
            pos[2] + p["height"] / 2.0,
        ]
    elif t == "cylinder":
        r = p["radius"]
        return [
            pos[0] + r,
            pos[1] + r,
            pos[2] + p["height"] / 2.0,
        ]
    elif t == "sphere":
        r = p["radius"]
        return [pos[0] + r, pos[1] + r, pos[2] + r]
    elif t == "cone":
        r = max(p["radius1"], p["radius2"])
        return [
            pos[0] + r,
            pos[1] + r,
            pos[2] + p["height"] / 2.0,
        ]
    elif t == "torus":
        R = p["radius1"]
        r = p["radius2"]
        return [
            pos[0] + R + r,
            pos[1] + R + r,
            pos[2] + r,
        ]
    elif t == "wedge":
        return [
            pos[0] + (p["xmin"] + p["xmax"]) / 2.0,
            pos[1] + (p["ymin"] + p["ymax"]) / 2.0,
            pos[2] + (p["zmin"] + p["zmax"]) / 2.0,
        ]
    # Boolean or unknown — fall back to placement position
    return pos


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
    """Estimate the centre of mass (geometric centre for simple shapes).

    For uniform-density primitives the centre of mass coincides with the
    bounding-box centre.

    Returns
    -------
    dict
        Measurement record with ``center_of_mass`` ``[x, y, z]``.
    """
    part = get_part(project, index)
    com = _bbox_center(part)

    result_com: Dict[str, Any] = {
        "part_index": index,
        "center_of_mass": [round(v, 6) for v in com],
    }
    if additive:
        result_com["additive"] = True
    return _store_measurement(project, "center_of_mass", result_com)


def measure_bounding_box(
    project: Dict[str, Any], index: int,
    additive: bool = False,
) -> Dict[str, Any]:
    """Compute the axis-aligned bounding box of a part.

    The bounding box is derived from the part's position and primitive
    parameters.

    Returns
    -------
    dict
        Measurement record with ``min``, ``max``, and ``size`` vectors.
    """
    part = get_part(project, index)
    pos = _get_position(part)
    p = part["params"]
    t = part["type"]

    if t == "box":
        bb_min = pos[:]
        bb_max = [
            pos[0] + p["length"],
            pos[1] + p["width"],
            pos[2] + p["height"],
        ]
    elif t == "cylinder":
        r = p["radius"]
        bb_min = [pos[0] - r, pos[1] - r, pos[2]]
        bb_max = [pos[0] + r, pos[1] + r, pos[2] + p["height"]]
    elif t == "sphere":
        r = p["radius"]
        bb_min = [pos[0] - r, pos[1] - r, pos[2] - r]
        bb_max = [pos[0] + r, pos[1] + r, pos[2] + r]
    elif t == "cone":
        r = max(p["radius1"], p["radius2"])
        bb_min = [pos[0] - r, pos[1] - r, pos[2]]
        bb_max = [pos[0] + r, pos[1] + r, pos[2] + p["height"]]
    elif t == "torus":
        R, r = p["radius1"], p["radius2"]
        outer = R + r
        bb_min = [pos[0] - outer, pos[1] - outer, pos[2] - r]
        bb_max = [pos[0] + outer, pos[1] + outer, pos[2] + r]
    elif t == "wedge":
        bb_min = [
            pos[0] + p["xmin"],
            pos[1] + p["ymin"],
            pos[2] + p["zmin"],
        ]
        bb_max = [
            pos[0] + p["xmax"],
            pos[1] + p["ymax"],
            pos[2] + p["zmax"],
        ]
    else:
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
