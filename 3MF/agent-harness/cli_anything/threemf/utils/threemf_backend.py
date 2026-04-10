"""Geometry utilities -- trimesh / numpy integration for 3MF mesh analysis.

All public functions are **pure**: they return new data structures and never
mutate their inputs.  This aligns with the frozen dataclasses used in
:mod:`cli_anything.threemf.core.parser`.
"""

from __future__ import annotations

from typing import Any

import numpy as np

try:
    import trimesh
except ImportError as _exc:  # pragma: no cover
    raise ImportError(
        "trimesh is required for geometry utilities.  "
        "Install it with:  pip install trimesh"
    ) from _exc

from cli_anything.threemf.core.parser import MeshData


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------

def mesh_to_trimesh(mesh_data: MeshData) -> trimesh.Trimesh:
    """Convert a :class:`MeshData` to a :class:`trimesh.Trimesh`.

    Parameters
    ----------
    mesh_data:
        Source mesh (frozen dataclass, never mutated).

    Returns
    -------
    trimesh.Trimesh
        A new Trimesh object.  The input arrays are copied so that the
        original ``MeshData`` is unaffected by any downstream mutations
        performed by trimesh internals.
    """
    return trimesh.Trimesh(
        vertices=np.array(mesh_data.vertices, dtype=np.float64, copy=True),
        faces=np.array(mesh_data.triangles, dtype=np.int32, copy=True),
        process=False,
    )


def trimesh_to_mesh(
    tm: trimesh.Trimesh,
    object_id: str,
    name: str,
) -> MeshData:
    """Convert a :class:`trimesh.Trimesh` back to a :class:`MeshData`.

    Parameters
    ----------
    tm:
        Source trimesh object.
    object_id:
        The ``<object id="...">`` attribute to assign.
    name:
        The ``<object name="...">`` attribute to assign.

    Returns
    -------
    MeshData
        A new frozen dataclass.
    """
    return MeshData(
        object_id=object_id,
        name=name,
        vertices=np.array(tm.vertices, dtype=np.float64, copy=True),
        triangles=np.array(tm.faces, dtype=np.int32, copy=True),
    )


# ---------------------------------------------------------------------------
# Mesh statistics
# ---------------------------------------------------------------------------

def compute_mesh_stats(mesh_data: MeshData) -> dict[str, Any]:
    """Compute summary statistics for a mesh.

    Returns
    -------
    dict
        Keys:

        - ``vertex_count`` (int)
        - ``face_count`` (int)
        - ``bounding_box`` -- dict with ``min`` and ``max`` (each a list
          of three floats) plus ``size`` (list of three floats).
        - ``watertight`` (bool)
        - ``volume_mm3`` (float | None) -- ``None`` when mesh is not
          watertight.
        - ``surface_area_mm2`` (float)
    """
    if mesh_data.vertices.shape[0] == 0 or mesh_data.triangles.shape[0] == 0:
        return {
            "vertex_count": int(mesh_data.vertices.shape[0]),
            "face_count": int(mesh_data.triangles.shape[0]),
            "bounding_box": {"min": [0.0, 0.0, 0.0],
                             "max": [0.0, 0.0, 0.0],
                             "size": [0.0, 0.0, 0.0]},
            "watertight": False,
            "volume_mm3": None,
            "surface_area_mm2": 0.0,
        }

    tm = mesh_to_trimesh(mesh_data)

    bb_min = tm.bounds[0].tolist()
    bb_max = tm.bounds[1].tolist()
    bb_size = (tm.bounds[1] - tm.bounds[0]).tolist()

    watertight = bool(tm.is_watertight)
    volume: float | None = float(tm.volume) if watertight else None
    surface_area = float(tm.area)

    return {
        "vertex_count": int(mesh_data.vertices.shape[0]),
        "face_count": int(mesh_data.triangles.shape[0]),
        "bounding_box": {
            "min": bb_min,
            "max": bb_max,
            "size": bb_size,
        },
        "watertight": watertight,
        "volume_mm3": volume,
        "surface_area_mm2": surface_area,
    }


# ---------------------------------------------------------------------------
# Circle fitting (algebraic / Kasa method)
# ---------------------------------------------------------------------------

def fit_circle_least_squares(
    points_2d: np.ndarray,
) -> tuple[float, float, float, float]:
    """Fit a circle to 2D points using the algebraic (Kasa) method.

    The Kasa method minimises the algebraic distance by solving the
    over-determined system::

        A @ [a, b, c]^T = d

    where ``x^2 + y^2 + a*x + b*y + c = 0`` describes the circle.
    The centre is ``(-a/2, -b/2)`` and the radius is
    ``sqrt(a^2/4 + b^2/4 - c)``.

    Parameters
    ----------
    points_2d:
        (N, 2) array of 2D coordinates.  At least 3 points are required.

    Returns
    -------
    tuple
        ``(center_x, center_y, radius, fit_error)`` where *fit_error* is
        the RMS deviation of point distances from the fitted circle.

    Raises
    ------
    ValueError
        If fewer than 3 points are provided.
    """
    if points_2d.ndim != 2 or points_2d.shape[1] != 2:
        raise ValueError(
            f"points_2d must be (N, 2); got shape {points_2d.shape}"
        )
    n = points_2d.shape[0]
    if n < 3:
        raise ValueError(
            f"At least 3 points are required for circle fitting; got {n}"
        )

    x = points_2d[:, 0]
    y = points_2d[:, 1]

    # Build the linear system:  A @ [a, b, c]^T = d
    #   where  x^2 + y^2 + a*x + b*y + c = 0
    A = np.column_stack([x, y, np.ones(n)])
    d = -(x ** 2 + y ** 2)

    # Least-squares solve
    result, *_ = np.linalg.lstsq(A, d, rcond=None)
    a, b, c = result

    cx = -a / 2.0
    cy = -b / 2.0
    r_sq = (a ** 2 + b ** 2) / 4.0 - c
    if r_sq < 0:
        # Degenerate case -- points are collinear or nearly so
        radius = 0.0
        fit_error = float("inf")
        return (cx, cy, radius, fit_error)

    radius = float(np.sqrt(r_sq))

    # RMS fit error
    distances = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    fit_error = float(np.sqrt(np.mean((distances - radius) ** 2)))

    return (cx, cy, radius, fit_error)


# ---------------------------------------------------------------------------
# Cross-section analysis
# ---------------------------------------------------------------------------

def _axis_plane_normal(axis: int) -> np.ndarray:
    """Return a unit normal vector for the given axis index (0=X, 1=Y, 2=Z)."""
    normal = np.zeros(3, dtype=np.float64)
    normal[axis] = 1.0
    return normal


def _project_to_2d(
    points_3d: np.ndarray,
    axis: int,
) -> np.ndarray:
    """Project 3D points onto the 2D plane perpendicular to *axis*.

    For axis=0 (X), returns columns (Y, Z).
    For axis=1 (Y), returns columns (X, Z).
    For axis=2 (Z), returns columns (X, Y).
    """
    other_axes = [i for i in range(3) if i != axis]
    return points_3d[:, other_axes]


def cross_section_circles(
    mesh_data: MeshData,
    axis: int = 0,
    num_planes: int = 20,
) -> list[dict[str, Any]]:
    """Take cross-sections and detect circular entities.

    The mesh is sliced at *num_planes* evenly-spaced planes perpendicular
    to the given axis.  For each resulting contour, a circle is fitted using
    :func:`fit_circle_least_squares`.  Only results with a reasonable fit
    error (< 5 % of radius) are included.

    Parameters
    ----------
    mesh_data:
        Source mesh.
    axis:
        Axis perpendicular to the slicing planes (0=X, 1=Y, 2=Z).
        Default ``0`` (X-axis) since most 3D-printed holes run along X.
    num_planes:
        Number of evenly-spaced slicing planes.

    Returns
    -------
    list[dict]
        Each dict contains:

        - ``center`` -- (2,) list of centre coordinates in the 2D plane.
        - ``radius`` -- fitted radius.
        - ``diameter`` -- 2 * radius.
        - ``plane_value`` -- coordinate along the slicing axis.
        - ``num_points`` -- number of contour points used for fitting.
        - ``fit_error`` -- RMS distance error of the fit.
    """
    if mesh_data.vertices.shape[0] == 0 or mesh_data.triangles.shape[0] == 0:
        return []

    if axis not in (0, 1, 2):
        raise ValueError(f"axis must be 0, 1 or 2; got {axis}")

    if num_planes < 1:
        raise ValueError(f"num_planes must be >= 1; got {num_planes}")

    tm = mesh_to_trimesh(mesh_data)
    normal = _axis_plane_normal(axis)

    # Determine slicing range along the chosen axis
    axis_min = float(tm.bounds[0][axis])
    axis_max = float(tm.bounds[1][axis])
    span = axis_max - axis_min

    if span < 1e-12:
        return []

    # Inset slightly to avoid degenerate boundary slices
    margin = span * 0.02
    plane_values = np.linspace(axis_min + margin, axis_max - margin, num_planes)

    results: list[dict[str, Any]] = []

    for pv in plane_values:
        origin = np.zeros(3, dtype=np.float64)
        origin[axis] = pv

        try:
            section = tm.section(plane_origin=origin, plane_normal=normal)
        except Exception:
            continue

        if section is None:
            continue

        # section is a Path3D; extract discrete points from each entity
        try:
            discrete = section.discrete
        except Exception:
            continue

        for path_points in discrete:
            pts_3d = np.asarray(path_points, dtype=np.float64)
            if pts_3d.ndim != 2 or pts_3d.shape[0] < 5:
                # Need a reasonable number of points for a good circle fit
                continue

            pts_2d = _project_to_2d(pts_3d, axis)

            try:
                cx, cy, radius, fit_error = fit_circle_least_squares(pts_2d)
            except ValueError:
                continue

            if radius < 1e-9:
                continue

            relative_error = fit_error / radius
            if relative_error > 0.05:
                # Not circular enough -- skip
                continue

            results.append({
                "center": [float(cx), float(cy)],
                "radius": float(radius),
                "diameter": float(radius * 2.0),
                "plane_value": float(pv),
                "num_points": int(pts_2d.shape[0]),
                "fit_error": float(fit_error),
            })

    return results


# ---------------------------------------------------------------------------
# Cylinder detection and vertex manipulation
# ---------------------------------------------------------------------------

def find_cylinder_vertices(
    vertices: np.ndarray,
    center_yz: np.ndarray,
    axis: int,
    radius: float,
    tolerance: float,
) -> np.ndarray:
    """Find vertex indices that lie on a cylindrical surface.

    A vertex is considered to be on the cylinder when its distance from the
    cylinder axis (measured in the 2D plane perpendicular to *axis*) is
    within *tolerance* of *radius*.

    Parameters
    ----------
    vertices:
        (N, 3) array of vertex positions.
    center_yz:
        (2,) array -- centre of the cylinder in the plane perpendicular to
        *axis*.  For axis=0 this is (center_y, center_z); for axis=1 it is
        (center_x, center_z); for axis=2 it is (center_x, center_y).
    axis:
        Cylinder axis direction (0=X, 1=Y, 2=Z).
    radius:
        Nominal radius of the cylinder.
    tolerance:
        Maximum allowed deviation from *radius*.

    Returns
    -------
    np.ndarray
        1-D int array of matching vertex indices.
    """
    if vertices.shape[0] == 0:
        return np.array([], dtype=np.intp)

    if axis not in (0, 1, 2):
        raise ValueError(f"axis must be 0, 1 or 2; got {axis}")

    center_yz = np.asarray(center_yz, dtype=np.float64).ravel()
    if center_yz.shape[0] != 2:
        raise ValueError(
            f"center_yz must have 2 elements; got {center_yz.shape[0]}"
        )

    other_axes = [i for i in range(3) if i != axis]
    pts_2d = vertices[:, other_axes]

    distances = np.sqrt(
        (pts_2d[:, 0] - center_yz[0]) ** 2
        + (pts_2d[:, 1] - center_yz[1]) ** 2
    )

    mask = np.abs(distances - radius) <= tolerance
    return np.nonzero(mask)[0].astype(np.intp)


def scale_vertices_radially(
    vertices: np.ndarray,
    indices: np.ndarray,
    center: np.ndarray,
    axis: int,
    new_radius: float,
) -> np.ndarray:
    """Scale selected vertices to a new radius, preserving angular position.

    Only the two coordinates perpendicular to *axis* are modified; the
    coordinate along *axis* is left unchanged.

    Parameters
    ----------
    vertices:
        (N, 3) vertex array.  **Never mutated** -- a copy is returned.
    indices:
        1-D array of vertex indices to scale.
    center:
        (2,) centre of the cylinder in the perpendicular plane.
    axis:
        Cylinder axis (0=X, 1=Y, 2=Z).
    new_radius:
        Target radius.

    Returns
    -------
    np.ndarray
        A **new** (N, 3) array with the selected vertices moved to
        *new_radius*.
    """
    if axis not in (0, 1, 2):
        raise ValueError(f"axis must be 0, 1 or 2; got {axis}")

    center = np.asarray(center, dtype=np.float64).ravel()
    if center.shape[0] != 2:
        raise ValueError(f"center must have 2 elements; got {center.shape[0]}")

    # Always work on a copy
    result = np.array(vertices, dtype=np.float64, copy=True)

    if indices.shape[0] == 0:
        return result

    other_axes = [i for i in range(3) if i != axis]
    ax_u, ax_v = other_axes

    # Extract the 2D positions of selected vertices relative to centre
    du = result[indices, ax_u] - center[0]
    dv = result[indices, ax_v] - center[1]
    current_radius = np.sqrt(du ** 2 + dv ** 2)

    # Avoid division by zero for vertices exactly at the centre
    safe_mask = current_radius > 1e-12
    scale = np.ones_like(current_radius)
    scale[safe_mask] = new_radius / current_radius[safe_mask]

    result[indices, ax_u] = center[0] + du * scale
    result[indices, ax_v] = center[1] + dv * scale

    return result
