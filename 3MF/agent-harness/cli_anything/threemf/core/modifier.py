"""Hole resizing -- radial vertex scaling to change hole diameters."""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from cli_anything.threemf.core.parser import MeshData, ThreeMFData
from cli_anything.threemf.core.inspector import (
    DetectedHole,
    inspect_mesh,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_WALL_RADIUS_TOLERANCE = 0.06  # mm -- proven in earlier 3MF editing session


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resize_holes(
    threemf_data: ThreeMFData,
    hole_ids: list[int],
    target_diameter: float,
    mesh_index: int = 0,
) -> tuple[ThreeMFData, list[dict]]:
    """Resize specified holes to *target_diameter* and return a **new** ``ThreeMFData``.

    Returns
    -------
    tuple
        ``(new_data, changes)`` where *changes* is a list of per-hole dicts
        with keys: hole_id, old_diameter, new_diameter, vertices_moved.

    Raises
    ------
    ValueError
        If *threemf_data* is ``None``, *mesh_index* is out of range,
        *target_diameter* is non-positive, or any *hole_id* is unknown.
    """

    _validate_resize_inputs(threemf_data, hole_ids, target_diameter, mesh_index)

    mesh = threemf_data.meshes[mesh_index]
    detected_holes = inspect_mesh(mesh)

    detected_ids = {h.hole_id for h in detected_holes}
    unknown = set(hole_ids) - detected_ids
    if unknown:
        raise ValueError(
            f"Unknown hole_ids: {sorted(unknown)}. "
            f"Detected hole_ids: {sorted(detected_ids)}"
        )

    target_holes = [h for h in detected_holes if h.hole_id in hole_ids]

    current_mesh = mesh
    reports: list[dict] = []

    for hole in target_holes:
        current_mesh, report = resize_single_hole(current_mesh, hole, target_diameter)
        reports.append(report)

    # Build new meshes tuple with the modified mesh
    new_meshes = tuple(
        current_mesh if i == mesh_index else m
        for i, m in enumerate(threemf_data.meshes)
    )

    return replace(threemf_data, meshes=new_meshes), reports


def resize_single_hole(
    mesh_data: MeshData,
    hole: DetectedHole,
    target_diameter: float,
) -> tuple[MeshData, dict]:
    """Resize a single hole and return ``(new_mesh, change_report)``.

    The change_report contains::

        {
            "hole_id": int,
            "old_diameter": float,
            "new_diameter": float,
            "vertices_moved": int,
        }

    Wall-vertex detection strategy (proven approach)
    -------------------------------------------------
    * Compute distance from hole axis for every vertex.
    * Select vertices whose radial distance is within ``_WALL_RADIUS_TOLERANCE``
      of the current hole radius **and** whose axial coordinate falls within
      the hole extent (with tolerance).
    * Scale those vertices radially to ``target_diameter / 2``.
    """

    if mesh_data is None:
        raise ValueError("mesh_data must not be None")
    if target_diameter <= 0:
        raise ValueError(f"target_diameter must be positive, got {target_diameter}")

    old_radius = hole.diameter / 2.0
    new_radius = target_diameter / 2.0

    perp = _perpendicular_axes(hole.axis)
    wall_mask = _find_wall_vertices(
        mesh_data.vertices,
        hole.center,
        old_radius,
        hole.axis,
        perp,
        hole.axis_min,
        hole.axis_max,
    )

    vertices_moved = int(np.count_nonzero(wall_mask))

    if vertices_moved == 0:
        return mesh_data, _make_report(hole, target_diameter, 0)

    new_vertices = _scale_wall_radially(
        mesh_data.vertices, wall_mask, hole.center, perp, new_radius,
    )

    new_mesh = replace(mesh_data, vertices=new_vertices)
    return new_mesh, _make_report(hole, target_diameter, vertices_moved)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _validate_resize_inputs(
    threemf_data: ThreeMFData,
    hole_ids: list[int],
    target_diameter: float,
    mesh_index: int,
) -> None:
    if threemf_data is None:
        raise ValueError("threemf_data must not be None")
    if not threemf_data.meshes:
        raise ValueError("threemf_data contains no meshes")
    if mesh_index < 0 or mesh_index >= len(threemf_data.meshes):
        raise ValueError(
            f"mesh_index {mesh_index} out of range "
            f"(0..{len(threemf_data.meshes) - 1})"
        )
    if target_diameter <= 0:
        raise ValueError(f"target_diameter must be positive, got {target_diameter}")
    if not hole_ids:
        raise ValueError("hole_ids must not be empty")


def _perpendicular_axes(axis: int) -> tuple[int, int]:
    """Return the two axes perpendicular to *axis*."""
    return {0: (1, 2), 1: (0, 2), 2: (0, 1)}[axis]


def _find_wall_vertices(
    vertices: np.ndarray,
    center: tuple[float, float],
    radius: float,
    axis: int,
    perp: tuple[int, int],
    axis_min: float,
    axis_max: float,
    tolerance: float = _WALL_RADIUS_TOLERANCE,
) -> np.ndarray:
    """Return a boolean mask of vertices on the cylindrical wall."""

    ax0, ax1 = perp
    in_range = (vertices[:, axis] >= axis_min - tolerance) & (
        vertices[:, axis] <= axis_max + tolerance
    )
    dx = vertices[:, ax0] - center[0]
    dy = vertices[:, ax1] - center[1]
    dist = np.sqrt(dx * dx + dy * dy)
    on_wall = np.abs(dist - radius) < tolerance
    return in_range & on_wall


def _scale_wall_radially(
    vertices: np.ndarray,
    mask: np.ndarray,
    center: tuple[float, float],
    perp: tuple[int, int],
    new_radius: float,
) -> np.ndarray:
    """Scale wall vertices to *new_radius*. Returns a **new** vertex array."""

    new_verts = vertices.copy()
    ax0, ax1 = perp

    dx = new_verts[mask, ax0] - center[0]
    dy = new_verts[mask, ax1] - center[1]
    dist = np.sqrt(dx * dx + dy * dy)

    # Avoid division by zero for vertices exactly at the centre
    safe_dist = np.where(dist > 1e-12, dist, 1.0)
    scale = new_radius / safe_dist

    new_verts[mask, ax0] = center[0] + dx * scale
    new_verts[mask, ax1] = center[1] + dy * scale

    return new_verts


def _make_report(hole: DetectedHole, target_diameter: float, vertices_moved: int) -> dict:
    return {
        "hole_id": hole.hole_id,
        "old_diameter": hole.diameter,
        "new_diameter": round(target_diameter, 4),
        "vertices_moved": vertices_moved,
    }
