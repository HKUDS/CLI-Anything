"""FreeCAD CLI - TechDraw module.

Manages technical drawing pages, views (standard, projection, section,
detail), dimensions, annotations, leaders, centerlines, hatches, and
PDF/SVG export on a JSON-based project state.
"""

from copy import deepcopy
from typing import Any, Dict, List, Optional, Set

from .document import ensure_collection
from cli_anything.freecad.utils.compat import require_version, V1_1


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_DIM_TYPES: Set[str] = {"length", "distance", "radius", "diameter", "angle"}

_COLLECTION_KEY = "techdraw_pages"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _next_id(project: Dict[str, Any]) -> int:
    """Return the next available integer ID for TechDraw pages."""
    items = project.get(_COLLECTION_KEY, [])
    if not items:
        return 1
    return max(item["id"] for item in items) + 1


def _unique_name(project: Dict[str, Any], base: str) -> str:
    """Return a unique name derived from *base* inside the pages list."""
    existing = {item["name"] for item in project.get(_COLLECTION_KEY, [])}
    if base not in existing:
        return base
    counter = 2
    while f"{base}_{counter}" in existing:
        counter += 1
    return f"{base}_{counter}"


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


def _get_page(project: Dict[str, Any], page_index: int) -> Dict[str, Any]:
    """Internal accessor with bounds checking."""
    items = ensure_collection(project, _COLLECTION_KEY)
    if not isinstance(page_index, int) or page_index < 0 or page_index >= len(items):
        raise IndexError(
            f"Page index {page_index} out of range (0..{len(items) - 1})"
        )
    return items[page_index]


def _get_view(
    project: Dict[str, Any], page_index: int, view_index: int
) -> Dict[str, Any]:
    """Internal accessor for a view within a page."""
    page = _get_page(project, page_index)
    views = page["views"]
    if not isinstance(view_index, int) or view_index < 0 or view_index >= len(views):
        raise IndexError(
            f"View index {view_index} out of range (0..{len(views) - 1})"
        )
    return views[view_index]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def new_page(
    project: Dict[str, Any],
    name: Optional[str] = None,
    template: str = "A4_LandscapeTD",
) -> Dict[str, Any]:
    """Create a new TechDraw page and append it to the project.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    name : str or None
        Human-readable label. Auto-generated when *None*.
    template : str
        Drawing template name (e.g. ``"A4_LandscapeTD"``, ``"A3_LandscapeTD"``).

    Returns
    -------
    dict
        The newly created page dictionary.
    """
    items = ensure_collection(project, _COLLECTION_KEY)

    if name is None:
        name = _unique_name(project, "Page")

    page: Dict[str, Any] = {
        "id": _next_id(project),
        "name": name,
        "template": template,
        "views": [],
        "dimensions": [],
        "annotations": [],
    }

    items.append(page)
    return page


def set_template(
    project: Dict[str, Any],
    page_index: int,
    template: str,
) -> Dict[str, Any]:
    """Change the template of an existing page.

    Returns the updated page dictionary.
    """
    if not isinstance(template, str) or not template.strip():
        raise ValueError("Template must be a non-empty string")

    page = _get_page(project, page_index)
    page["template"] = template.strip()
    return page


def add_view(
    project: Dict[str, Any],
    page_index: int,
    source_index: int,
    direction: Optional[List[float]] = None,
    scale: float = 1.0,
    position: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Add a standard view of a part/body to a TechDraw page.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    page_index : int
        Index of the target page.
    source_index : int
        Index of the source object in ``project["parts"]``.
    direction : list[float] or None
        View projection direction ``[x, y, z]``. Defaults to ``[0, 0, 1]``.
    scale : float
        View scale factor.
    position : list[float] or None
        Position on the page ``[x, y]``. Defaults to ``[0, 0]``.

    Returns
    -------
    dict
        The newly created view entry.
    """
    page = _get_page(project, page_index)

    if direction is not None:
        direction = _validate_vec3(direction, "direction")
    else:
        direction = [0.0, 0.0, 1.0]

    if position is not None:
        position = _validate_vec2(position, "position")
    else:
        position = [0.0, 0.0]

    view: Dict[str, Any] = {
        "type": "standard",
        "source_index": source_index,
        "direction": direction,
        "scale": float(scale),
        "position": position,
    }

    page["views"].append(view)
    return view


def add_projection_group(
    project: Dict[str, Any],
    page_index: int,
    source_index: int,
    directions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Add a projection group (front, right, top, etc.) to a page.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    page_index : int
        Index of the target page.
    source_index : int
        Index of the source object in ``project["parts"]``.
    directions : list[str] or None
        Projection names. Defaults to ``["front", "right", "top"]``.

    Returns
    -------
    dict
        The projection group view entry.
    """
    page = _get_page(project, page_index)

    if directions is None:
        directions = ["front", "right", "top"]

    group: Dict[str, Any] = {
        "type": "projection_group",
        "source_index": source_index,
        "directions": list(directions),
        "scale": 1.0,
        "position": [0.0, 0.0],
    }

    page["views"].append(group)
    return group


def add_section_view(
    project: Dict[str, Any],
    page_index: int,
    view_index: int,
    section_normal: Optional[List[float]] = None,
    section_origin: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Add a section view derived from an existing view.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    page_index : int
        Index of the target page.
    view_index : int
        Index of the parent view within the page.
    section_normal : list[float] or None
        Normal vector of the section plane. Defaults to ``[1, 0, 0]``.
    section_origin : list[float] or None
        Origin point of the section plane. Defaults to ``[0, 0, 0]``.

    Returns
    -------
    dict
        The section view entry.
    """
    page = _get_page(project, page_index)
    # Validate parent view exists
    _get_view(project, page_index, view_index)

    if section_normal is not None:
        section_normal = _validate_vec3(section_normal, "section_normal")
    else:
        section_normal = [1.0, 0.0, 0.0]

    if section_origin is not None:
        section_origin = _validate_vec3(section_origin, "section_origin")
    else:
        section_origin = [0.0, 0.0, 0.0]

    section: Dict[str, Any] = {
        "type": "section",
        "parent_view_index": view_index,
        "section_normal": section_normal,
        "section_origin": section_origin,
        "scale": 1.0,
        "position": [0.0, 0.0],
    }

    page["views"].append(section)
    return section


def add_detail_view(
    project: Dict[str, Any],
    page_index: int,
    view_index: int,
    center: Optional[List[float]] = None,
    radius: float = 20.0,
) -> Dict[str, Any]:
    """Add a detail (magnified) view of part of an existing view.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    page_index : int
        Index of the target page.
    view_index : int
        Index of the parent view within the page.
    center : list[float] or None
        Center of the detail circle ``[x, y]``. Defaults to ``[0, 0]``.
    radius : float
        Radius of the detail circle.

    Returns
    -------
    dict
        The detail view entry.
    """
    page = _get_page(project, page_index)
    _get_view(project, page_index, view_index)

    if center is not None:
        center = _validate_vec2(center, "center")
    else:
        center = [0.0, 0.0]

    detail: Dict[str, Any] = {
        "type": "detail",
        "parent_view_index": view_index,
        "center": center,
        "radius": float(radius),
        "scale": 2.0,
        "position": [0.0, 0.0],
    }

    page["views"].append(detail)
    return detail


def add_dimension(
    project: Dict[str, Any],
    page_index: int,
    view_index: int,
    dim_type: str,
    references: List[Any],
    value: Optional[float] = None,
) -> Dict[str, Any]:
    """Add a dimension annotation to a page.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    page_index : int
        Index of the target page.
    view_index : int
        Index of the view the dimension references.
    dim_type : str
        One of ``"length"``, ``"distance"``, ``"radius"``,
        ``"diameter"``, ``"angle"``.
    references : list
        Geometry references (edges, vertices) for the dimension.
    value : float or None
        Explicit override value. When *None* the value is derived from
        the referenced geometry during macro execution.

    Returns
    -------
    dict
        The dimension entry.

    Raises
    ------
    ValueError
        If *dim_type* is unknown.
    """
    if dim_type not in VALID_DIM_TYPES:
        valid = ", ".join(sorted(VALID_DIM_TYPES))
        raise ValueError(f"Unknown dim_type '{dim_type}'. Valid: {valid}")

    page = _get_page(project, page_index)
    _get_view(project, page_index, view_index)

    dimension: Dict[str, Any] = {
        "type": dim_type,
        "view_index": view_index,
        "references": list(references),
        "value": float(value) if value is not None else None,
    }

    page["dimensions"].append(dimension)
    return dimension


def add_annotation(
    project: Dict[str, Any],
    page_index: int,
    text: str,
    position: Optional[List[float]] = None,
    area_mode: bool = False,
    shape_validation: bool = True,
) -> Dict[str, Any]:
    """Add a text annotation to a page.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    page_index : int
        Index of the target page.
    text : str
        Annotation text content.
    position : list[float] or None
        Position on the page ``[x, y]``. Defaults to ``[0, 0]``.
    area_mode : bool
        When ``True``, computes area accounting for face holes (default ``False``).
    shape_validation : bool
        Enables shape validation (default ``True``).

    Returns the annotation entry.
    """
    page = _get_page(project, page_index)

    if position is not None:
        position = _validate_vec2(position, "position")
    else:
        position = [0.0, 0.0]

    if area_mode:
        require_version(V1_1, "area mode annotations")

    annotation: Dict[str, Any] = {
        "type": "annotation",
        "text": str(text),
        "position": position,
        "area_mode": bool(area_mode),
        "shape_validation": bool(shape_validation),
    }

    page["annotations"].append(annotation)
    return annotation


def add_leader(
    project: Dict[str, Any],
    page_index: int,
    points: List[List[float]],
    text: str = "",
) -> Dict[str, Any]:
    """Add a leader line with optional text to a page.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    page_index : int
        Index of the target page.
    points : list[list[float]]
        List of ``[x, y]`` waypoints for the leader line.
    text : str
        Optional text label at the end of the leader.

    Returns
    -------
    dict
        The leader entry.
    """
    page = _get_page(project, page_index)

    validated_points: List[List[float]] = []
    for i, pt in enumerate(points):
        validated_points.append(_validate_vec2(pt, f"points[{i}]"))

    leader: Dict[str, Any] = {
        "type": "leader",
        "points": validated_points,
        "text": str(text),
    }

    page["annotations"].append(leader)
    return leader


def add_centerline(
    project: Dict[str, Any],
    page_index: int,
    view_index: int,
    references: List[Any],
) -> Dict[str, Any]:
    """Add a centerline to a view on a page.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    page_index : int
        Index of the target page.
    view_index : int
        Index of the view within the page.
    references : list
        Geometry references (edges, faces) that define the centerline.

    Returns
    -------
    dict
        The centerline entry.
    """
    page = _get_page(project, page_index)
    _get_view(project, page_index, view_index)

    centerline: Dict[str, Any] = {
        "type": "centerline",
        "view_index": view_index,
        "references": list(references),
    }

    page["annotations"].append(centerline)
    return centerline


def add_hatch(
    project: Dict[str, Any],
    page_index: int,
    view_index: int,
    pattern: str = "steel",
    scale: float = 1.0,
) -> Dict[str, Any]:
    """Add a hatch pattern to a view on a page.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    page_index : int
        Index of the target page.
    view_index : int
        Index of the view within the page.
    pattern : str
        Hatch pattern name (e.g. ``"steel"``, ``"aluminum"``).
    scale : float
        Pattern scale factor.

    Returns
    -------
    dict
        The hatch entry.
    """
    page = _get_page(project, page_index)
    _get_view(project, page_index, view_index)

    hatch: Dict[str, Any] = {
        "type": "hatch",
        "view_index": view_index,
        "pattern": str(pattern),
        "scale": float(scale),
    }

    page["annotations"].append(hatch)
    return hatch


def export_page_pdf(
    project: Dict[str, Any],
    page_index: int,
    path: str,
) -> Dict[str, Any]:
    """Record metadata for exporting a page to PDF.

    The actual export is performed by the generated FreeCAD macro.

    Returns
    -------
    dict
        Export metadata including page name and output path.
    """
    if not isinstance(path, str) or not path.strip():
        raise ValueError("Path must be a non-empty string")

    page = _get_page(project, page_index)

    return {
        "action": "export_pdf",
        "page_name": page["name"],
        "page_index": page_index,
        "path": path.strip(),
        "format": "pdf",
    }


def export_page_svg(
    project: Dict[str, Any],
    page_index: int,
    path: str,
) -> Dict[str, Any]:
    """Record metadata for exporting a page to SVG.

    The actual export is performed by the generated FreeCAD macro.

    Returns
    -------
    dict
        Export metadata including page name and output path.
    """
    if not isinstance(path, str) or not path.strip():
        raise ValueError("Path must be a non-empty string")

    page = _get_page(project, page_index)

    return {
        "action": "export_svg",
        "page_name": page["name"],
        "page_index": page_index,
        "path": path.strip(),
        "format": "svg",
    }


def list_views(
    project: Dict[str, Any],
    page_index: int,
) -> List[Dict[str, Any]]:
    """Return all views on a page."""
    page = _get_page(project, page_index)
    return page["views"]


def get_view(
    project: Dict[str, Any],
    page_index: int,
    view_index: int,
) -> Dict[str, Any]:
    """Return a specific view from a page.

    Raises ``IndexError`` when either index is out of range.
    """
    return _get_view(project, page_index, view_index)
