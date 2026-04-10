"""Hole detection -- cross-section analysis to find cylindrical holes in meshes."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage

from cli_anything.threemf.core.parser import MeshData, ThreeMFData
from cli_anything.threemf.utils import threemf_backend as backend

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DetectedHole:
    """A cylindrical hole detected in a mesh."""

    hole_id: int
    center: tuple[float, float]  # (coord1, coord2) perpendicular to axis
    diameter: float
    axis_min: float  # extent along axis
    axis_max: float
    axis: int  # 0=X, 1=Y, 2=Z
    confidence: float  # 0.0-1.0
    vertex_count: int


@dataclass(frozen=True)
class InspectParams:
    """Parameters that control hole-detection behaviour."""

    num_planes: int = 20
    min_hole_diameter: float = 0.5
    min_confidence: float = 0.7
    axis: int = 0  # which axis to section perpendicular to


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_GROUP_DISTANCE_MM = 0.5  # max center-to-center distance to merge circles


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def inspect_mesh(
    mesh_data: MeshData,
    params: InspectParams | None = None,
) -> list[DetectedHole]:
    """Detect cylindrical holes via multi-plane cross-section analysis.

    Algorithm
    ---------
    1. Take cross-sections at ``num_planes`` evenly-spaced levels along *axis*.
    2. At each section call ``cross_section_circles()`` to find circular features.
    3. Group circles across planes by centre proximity (hierarchical clustering
       with a 0.5 mm distance threshold).
    4. For each group compute the average diameter, axis extent, and confidence.
    5. Filter by *min_hole_diameter* and *min_confidence*.
    6. Count vertices on each hole wall.
    7. Return a sorted list of ``DetectedHole`` (sorted by hole_id).
    """

    if params is None:
        params = InspectParams()

    _validate_mesh(mesh_data)

    vertices = mesh_data.vertices
    if vertices.shape[0] == 0:
        return []

    axis = params.axis

    # Step 1 -- basic axis range check
    perp_axes = _perpendicular_axes(axis)
    axis_vals = vertices[:, axis]
    axis_lo, axis_hi = float(np.min(axis_vals)), float(np.max(axis_vals))
    if axis_hi - axis_lo < 1e-9:
        return []

    # Step 2 -- collect circles via multi-plane cross-section
    raw_circles = backend.cross_section_circles(
        mesh_data, axis=axis, num_planes=params.num_planes,
    )
    all_circles = []
    for c in raw_circles:
        all_circles.append({
            "center": (float(c["center"][0]), float(c["center"][1])),
            "radius": float(c["radius"]),
            "fit_error": float(c.get("fit_error", 0.0)),
            "level": float(c["plane_value"]),
        })
    if not all_circles:
        return []

    # Step 3 -- group circles by centre proximity via hierarchical clustering
    groups = _group_circles(all_circles)

    # Step 4/5 -- build candidate holes, compute confidence, filter
    num_planes = params.num_planes
    holes: list[DetectedHole] = []
    hole_id = 0

    for group in groups:
        radii = np.array([c["radius"] for c in group])
        mean_radius = float(np.mean(radii))
        mean_diameter = mean_radius * 2.0

        if mean_diameter < params.min_hole_diameter:
            continue

        # Confidence = (planes_with_detection / total_planes) * (1 - mean_fit_error / radius)
        fit_errors = np.array([c["fit_error"] for c in group])
        mean_fit_error = float(np.mean(fit_errors))
        detection_ratio = len(group) / num_planes
        if mean_radius > 0:
            quality = 1.0 - mean_fit_error / mean_radius
        else:
            quality = 0.0
        confidence = float(np.clip(detection_ratio * quality, 0.0, 1.0))

        if confidence < params.min_confidence:
            continue

        # Axis extent
        group_levels = [c["level"] for c in group]
        axis_min = float(min(group_levels))
        axis_max = float(max(group_levels))

        # Centre (average across all detections)
        centres = np.array([c["center"] for c in group])
        avg_center = (float(np.mean(centres[:, 0])), float(np.mean(centres[:, 1])))

        # Step 6 -- count wall vertices
        vertex_count = _count_wall_vertices(
            vertices, avg_center, mean_radius, axis, perp_axes, axis_min, axis_max,
        )

        holes.append(DetectedHole(
            hole_id=hole_id,
            center=avg_center,
            diameter=round(mean_diameter, 4),
            axis_min=round(axis_min, 4),
            axis_max=round(axis_max, 4),
            axis=axis,
            confidence=round(confidence, 4),
            vertex_count=vertex_count,
        ))
        hole_id += 1

    holes.sort(key=lambda h: h.hole_id)
    return holes


def get_mesh_info(mesh_data: MeshData) -> dict:
    """Return mesh statistics using ``backend.compute_mesh_stats()``."""

    _validate_mesh(mesh_data)
    stats = backend.compute_mesh_stats(mesh_data)
    return {
        "object_id": mesh_data.object_id,
        "name": mesh_data.name,
        "num_vertices": int(mesh_data.vertices.shape[0]),
        "num_triangles": int(mesh_data.triangles.shape[0]),
        **stats,
    }


def compare_meshes(mesh_a: MeshData, mesh_b: MeshData) -> dict:
    """Compare two meshes and return a summary of differences.

    Returns a dict with keys: vertices, faces, volume, watertight — each a
    sub-dict with file1/file2/diff (matching the CLI display format).
    """

    _validate_mesh(mesh_a)
    _validate_mesh(mesh_b)

    stats_a = backend.compute_mesh_stats(mesh_a)
    stats_b = backend.compute_mesh_stats(mesh_b)

    vol_a = stats_a.get("volume_mm3") or 0.0
    vol_b = stats_b.get("volume_mm3") or 0.0

    return {
        "vertices": {
            "file1": int(mesh_a.vertices.shape[0]),
            "file2": int(mesh_b.vertices.shape[0]),
            "diff": int(mesh_b.vertices.shape[0]) - int(mesh_a.vertices.shape[0]),
        },
        "faces": {
            "file1": int(mesh_a.triangles.shape[0]),
            "file2": int(mesh_b.triangles.shape[0]),
            "diff": int(mesh_b.triangles.shape[0]) - int(mesh_a.triangles.shape[0]),
        },
        "volume": {
            "file1": float(vol_a),
            "file2": float(vol_b),
            "diff": float(vol_b - vol_a),
        },
        "watertight": {
            "file1": stats_a.get("watertight", False),
            "file2": stats_b.get("watertight", False),
        },
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _validate_mesh(mesh_data: MeshData) -> None:
    """Raise ``ValueError`` for clearly invalid mesh data."""
    if mesh_data is None:
        raise ValueError("mesh_data must not be None")
    if not isinstance(mesh_data.vertices, np.ndarray):
        raise ValueError("mesh_data.vertices must be a numpy ndarray")
    if not isinstance(mesh_data.triangles, np.ndarray):
        raise ValueError("mesh_data.triangles must be a numpy ndarray")
    if mesh_data.vertices.ndim != 2 or mesh_data.vertices.shape[1] != 3:
        raise ValueError("mesh_data.vertices must have shape (N, 3)")
    if mesh_data.triangles.ndim != 2 or mesh_data.triangles.shape[1] != 3:
        if mesh_data.triangles.shape[0] != 0:
            raise ValueError("mesh_data.triangles must have shape (M, 3)")


def _perpendicular_axes(axis: int) -> tuple[int, int]:
    """Return the two axes perpendicular to *axis*."""
    return {0: (1, 2), 1: (0, 2), 2: (0, 1)}[axis]


def _group_circles(circles: list[dict]) -> list[list[dict]]:
    """Group circles from different planes by centre proximity.

    Uses scipy hierarchical clustering with a distance threshold of
    ``_GROUP_DISTANCE_MM``.
    """

    if len(circles) == 1:
        return [circles]

    centres = np.array([c["center"] for c in circles])
    link = linkage(centres, method="single", metric="euclidean")
    labels = fcluster(link, t=_GROUP_DISTANCE_MM, criterion="distance")

    groups: dict[int, list[dict]] = {}
    for label, circle in zip(labels, circles):
        groups.setdefault(int(label), []).append(circle)

    return list(groups.values())


def _count_wall_vertices(
    vertices: np.ndarray,
    center: tuple[float, float],
    radius: float,
    axis: int,
    perp_axes: tuple[int, int],
    axis_min: float,
    axis_max: float,
    tolerance: float = 0.06,
) -> int:
    """Count vertices that lie on the cylindrical wall of a hole."""

    ax0, ax1 = perp_axes
    in_range = (vertices[:, axis] >= axis_min - tolerance) & (
        vertices[:, axis] <= axis_max + tolerance
    )
    subset = vertices[in_range]
    if subset.shape[0] == 0:
        return 0

    dx = subset[:, ax0] - center[0]
    dy = subset[:, ax1] - center[1]
    dist = np.sqrt(dx * dx + dy * dy)
    on_wall = np.abs(dist - radius) < tolerance
    return int(np.count_nonzero(on_wall))
