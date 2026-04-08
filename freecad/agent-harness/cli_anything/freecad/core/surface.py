"""FreeCAD CLI - Surface workbench module.

Provides surface creation and manipulation functions including filling,
lofting through sections, extending, blending, sewing, and cutting.
All surfaces are stored in ``project["surfaces"]`` via
:func:`~cli_anything.freecad.core.document.ensure_collection`.
"""

from typing import Any, Dict, List, Optional

from cli_anything.freecad.core.document import ensure_collection

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _next_id(project: Dict[str, Any]) -> int:
    """Return the next available integer ID for surfaces."""
    items = project.get("surfaces", [])
    if not items:
        return 1
    return max(item["id"] for item in items) + 1


def _unique_name(project: Dict[str, Any], base: str) -> str:
    """Return a unique name derived from *base* inside ``project["surfaces"]``."""
    existing = {item["name"] for item in project.get("surfaces", [])}
    if base not in existing:
        return base
    counter = 2
    while f"{base}_{counter}" in existing:
        counter += 1
    return f"{base}_{counter}"


def _get_surface(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Return the surface at *index*, raising ``IndexError`` if out of range."""
    surfaces = project.get("surfaces", [])
    if not isinstance(index, int) or index < 0 or index >= len(surfaces):
        raise IndexError(
            f"Surface index {index} out of range (0..{len(surfaces) - 1})"
        )
    return surfaces[index]


def _validate_index_list(indices: Any, label: str, min_count: int = 1) -> List[int]:
    """Validate that *indices* is a list of non-negative integers."""
    if not isinstance(indices, (list, tuple)):
        raise ValueError(f"{label} must be a list of indices")
    if len(indices) < min_count:
        raise ValueError(f"{label} requires at least {min_count} index(es), got {len(indices)}")
    for i, v in enumerate(indices):
        if not isinstance(v, int) or v < 0:
            raise ValueError(f"{label}[{i}] must be a non-negative integer, got {v!r}")
    return list(indices)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def surface_filling(
    project: Dict[str, Any],
    edge_indices: List[int],
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a surface that fills a boundary defined by edges.

    The filling surface interpolates through the specified boundary
    edges, producing a smooth G1/G2 surface patch.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    edge_indices : list[int]
        Indices referencing boundary edges (from parts or sketches).
    name : str or None
        Label for the surface.  Auto-generated when *None*.

    Returns
    -------
    dict
        The newly created surface entry.

    Raises
    ------
    ValueError
        If *edge_indices* has fewer than 1 entry or contains invalid values.
    """
    refs = _validate_index_list(edge_indices, "edge_indices", min_count=1)
    surfaces = ensure_collection(project, "surfaces")

    if name is None:
        name = _unique_name(project, "Filling")

    surface: Dict[str, Any] = {
        "id": _next_id(project),
        "name": name,
        "type": "filling",
        "params": {},
        "source_refs": refs,
    }

    surfaces.append(surface)
    return surface


def surface_sections(
    project: Dict[str, Any],
    section_indices: List[int],
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a loft-like surface through cross-section profiles.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    section_indices : list[int]
        Indices referencing cross-section profiles (edges, wires, or
        sketches).  At least two sections are required.
    name : str or None
        Label for the surface.  Auto-generated when *None*.

    Returns
    -------
    dict
        The newly created surface entry.

    Raises
    ------
    ValueError
        If fewer than two sections are provided.
    """
    refs = _validate_index_list(section_indices, "section_indices", min_count=2)
    surfaces = ensure_collection(project, "surfaces")

    if name is None:
        name = _unique_name(project, "Sections")

    surface: Dict[str, Any] = {
        "id": _next_id(project),
        "name": name,
        "type": "sections",
        "params": {},
        "source_refs": refs,
    }

    surfaces.append(surface)
    return surface


def surface_extend(
    project: Dict[str, Any],
    surface_index: int,
    length: float = 10.0,
    direction: str = "normal",
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Extend an existing surface by *length* along *direction*.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    surface_index : int
        Index of the surface to extend.
    length : float
        Extension distance (default ``10``).
    direction : str
        Extension direction — ``"normal"`` (default), ``"u"``, or ``"v"``.
    name : str or None
        Label for the new surface.  Auto-generated when *None*.

    Returns
    -------
    dict
        The newly created extended surface entry.

    Raises
    ------
    IndexError
        If *surface_index* is out of range.
    ValueError
        If *length* is not positive or *direction* is invalid.
    """
    source = _get_surface(project, surface_index)

    if length <= 0:
        raise ValueError("length must be a positive number")

    valid_dirs = {"normal", "u", "v"}
    if direction not in valid_dirs:
        raise ValueError(f"direction must be one of {', '.join(sorted(valid_dirs))}, got '{direction}'")

    surfaces = ensure_collection(project, "surfaces")

    if name is None:
        name = _unique_name(project, f"{source['name']}_Extended")

    surface: Dict[str, Any] = {
        "id": _next_id(project),
        "name": name,
        "type": "extend",
        "params": {
            "length": float(length),
            "direction": direction,
            "source_surface_id": source["id"],
        },
        "source_refs": [surface_index],
    }

    surfaces.append(surface)
    return surface


def surface_blend_curve(
    project: Dict[str, Any],
    edge_index1: int,
    edge_index2: int,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a blend surface between two edges.

    The blend surface smoothly connects two boundary edges with
    tangency continuity.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    edge_index1 : int
        Index referencing the first boundary edge.
    edge_index2 : int
        Index referencing the second boundary edge.
    name : str or None
        Label for the surface.  Auto-generated when *None*.

    Returns
    -------
    dict
        The newly created surface entry.

    Raises
    ------
    ValueError
        If edge indices are equal or negative.
    """
    if not isinstance(edge_index1, int) or edge_index1 < 0:
        raise ValueError("edge_index1 must be a non-negative integer")
    if not isinstance(edge_index2, int) or edge_index2 < 0:
        raise ValueError("edge_index2 must be a non-negative integer")
    if edge_index1 == edge_index2:
        raise ValueError("edge_index1 and edge_index2 must differ")

    surfaces = ensure_collection(project, "surfaces")

    if name is None:
        name = _unique_name(project, "BlendCurve")

    surface: Dict[str, Any] = {
        "id": _next_id(project),
        "name": name,
        "type": "blend_curve",
        "params": {},
        "source_refs": [edge_index1, edge_index2],
    }

    surfaces.append(surface)
    return surface


def surface_sew(
    project: Dict[str, Any],
    surface_indices: List[int],
    tolerance: float = 0.01,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Sew multiple surfaces into a single shell.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    surface_indices : list[int]
        Indices of the surfaces to sew together.  At least two required.
    tolerance : float
        Sewing tolerance (default ``0.01``).
    name : str or None
        Label for the resulting surface.  Auto-generated when *None*.

    Returns
    -------
    dict
        The newly created sewn surface entry.

    Raises
    ------
    ValueError
        If fewer than two surfaces or tolerance is invalid.
    IndexError
        If any surface index is out of range.
    """
    if tolerance <= 0:
        raise ValueError("tolerance must be a positive number")

    refs = _validate_index_list(surface_indices, "surface_indices", min_count=2)

    # Validate that each referenced surface exists
    source_ids = []
    for idx in refs:
        s = _get_surface(project, idx)
        source_ids.append(s["id"])

    surfaces = ensure_collection(project, "surfaces")

    if name is None:
        name = _unique_name(project, "SewnSurface")

    surface: Dict[str, Any] = {
        "id": _next_id(project),
        "name": name,
        "type": "sew",
        "params": {
            "tolerance": float(tolerance),
            "source_surface_ids": source_ids,
        },
        "source_refs": refs,
    }

    surfaces.append(surface)
    return surface


def surface_cut(
    project: Dict[str, Any],
    surface_index: int,
    cutting_index: int,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Cut a surface with another surface or shape.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    surface_index : int
        Index of the surface to cut.
    cutting_index : int
        Index of the cutting surface or shape reference.
    name : str or None
        Label for the resulting surface.  Auto-generated when *None*.

    Returns
    -------
    dict
        The newly created cut surface entry.

    Raises
    ------
    IndexError
        If *surface_index* is out of range.
    ValueError
        If indices are equal.
    """
    source = _get_surface(project, surface_index)

    if surface_index == cutting_index:
        raise ValueError("surface_index and cutting_index must differ")

    surfaces = ensure_collection(project, "surfaces")

    if name is None:
        name = _unique_name(project, f"{source['name']}_Cut")

    surface: Dict[str, Any] = {
        "id": _next_id(project),
        "name": name,
        "type": "cut",
        "params": {
            "source_surface_id": source["id"],
            "cutting_index": cutting_index,
        },
        "source_refs": [surface_index, cutting_index],
    }

    surfaces.append(surface)
    return surface
