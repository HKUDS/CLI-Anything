"""Mesh repair -- fix degenerate faces, duplicate vertices, and normals."""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from cli_anything.threemf.core.parser import MeshData

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def repair_mesh(mesh_data: MeshData) -> tuple[MeshData, dict]:
    """Run the full repair pipeline on *mesh_data*.

    Returns ``(repaired_mesh, report)`` where *report* summarises the
    number of fixes applied at each step.

    Pipeline
    --------
    1. Merge duplicate vertices (rounded coordinate matching).
    2. Remap triangle indices to canonical vertices.
    3. Remove degenerate triangles (two or more identical indices).
    4. Remove unreferenced vertices and compact indices.
    5. Return the repaired mesh and a report dict.
    """

    _validate_mesh(mesh_data)

    vertices = mesh_data.vertices
    triangles = mesh_data.triangles

    # Handle empty mesh early
    if vertices.shape[0] == 0 or triangles.shape[0] == 0:
        return mesh_data, _empty_report()

    # Step 1+2 -- merge duplicates and remap triangles
    vertices, triangles, merge_count = merge_duplicate_vertices(
        vertices, triangles,
    )

    # Step 3 -- remove degenerate faces
    triangles, degen_count = remove_degenerate_faces(triangles)

    # Step 4 -- remove unreferenced vertices
    vertices, triangles, unref_count = remove_unreferenced_vertices(
        vertices, triangles,
    )

    report = {
        "vertices_merged": merge_count,
        "degenerate_faces_removed": degen_count,
        "unreferenced_vertices_removed": unref_count,
        "final_vertex_count": int(vertices.shape[0]),
        "final_triangle_count": int(triangles.shape[0]),
    }

    repaired = replace(mesh_data, vertices=vertices, triangles=triangles)
    return repaired, report


def merge_duplicate_vertices(
    vertices: np.ndarray,
    triangles: np.ndarray,
    decimals: int = 6,
) -> tuple[np.ndarray, np.ndarray, int]:
    """Merge vertices that share the same coordinates (after rounding).

    Returns ``(unique_vertices, remapped_triangles, merge_count)``
    where *merge_count* is the number of vertices removed.
    """

    if vertices.shape[0] == 0:
        return vertices, triangles, 0

    rounded = np.round(vertices, decimals=decimals)

    # Build a mapping from rounded coordinates to canonical index
    # Using a structured view for fast unique-row detection
    dtype = np.dtype([("x", rounded.dtype), ("y", rounded.dtype), ("z", rounded.dtype)])
    structured = np.ascontiguousarray(rounded).view(dtype).reshape(-1)

    _, canonical_idx, inverse = np.unique(
        structured, return_index=True, return_inverse=True,
    )

    unique_vertices = vertices[np.sort(canonical_idx)]

    # Build old-index -> new-index mapping (preserving sorted order of canonical)
    sorted_canonical = np.sort(canonical_idx)
    new_idx_map = np.full(vertices.shape[0], -1, dtype=np.intp)
    for new_i, old_i in enumerate(sorted_canonical):
        new_idx_map[old_i] = new_i

    # Remap each original index through inverse -> canonical -> new_sorted
    remap = new_idx_map[canonical_idx[inverse]]

    remapped_triangles = remap[triangles] if triangles.shape[0] > 0 else triangles

    merge_count = int(vertices.shape[0] - unique_vertices.shape[0])
    return unique_vertices, remapped_triangles, merge_count


def remove_degenerate_faces(
    triangles: np.ndarray,
) -> tuple[np.ndarray, int]:
    """Remove triangles where two or more vertex indices are identical.

    Returns ``(filtered_triangles, removed_count)``.
    """

    if triangles.shape[0] == 0:
        return triangles, 0

    v0, v1, v2 = triangles[:, 0], triangles[:, 1], triangles[:, 2]
    valid = (v0 != v1) & (v1 != v2) & (v0 != v2)

    filtered = triangles[valid]
    removed = int(triangles.shape[0] - filtered.shape[0])
    return filtered, removed


def remove_unreferenced_vertices(
    vertices: np.ndarray,
    triangles: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, int]:
    """Remove vertices not referenced by any triangle and compact indices.

    Returns ``(filtered_vertices, remapped_triangles, removed_count)``.
    """

    if vertices.shape[0] == 0:
        return vertices, triangles, 0

    if triangles.shape[0] == 0:
        # No triangles reference any vertex -- remove all
        empty_verts = np.empty((0, 3), dtype=vertices.dtype)
        empty_tris = np.empty((0, 3), dtype=triangles.dtype)
        return empty_verts, empty_tris, int(vertices.shape[0])

    referenced = np.unique(triangles.ravel())
    removed_count = int(vertices.shape[0] - referenced.shape[0])

    if removed_count == 0:
        return vertices, triangles, 0

    filtered_vertices = vertices[referenced]

    # Build old-index -> new-index mapping
    remap = np.full(vertices.shape[0], -1, dtype=np.intp)
    remap[referenced] = np.arange(referenced.shape[0], dtype=np.intp)

    remapped_triangles = remap[triangles]
    return filtered_vertices, remapped_triangles, removed_count


def fix_normals(mesh_data: MeshData) -> MeshData:
    """Fix face winding for consistent outward-pointing normals using trimesh.

    Returns a **new** ``MeshData`` with corrected triangle winding order.
    """

    _validate_mesh(mesh_data)

    if mesh_data.vertices.shape[0] == 0 or mesh_data.triangles.shape[0] == 0:
        return mesh_data

    try:
        import trimesh
    except ImportError as exc:
        raise ImportError(
            "trimesh is required for normal repair. "
            "Install with: pip install trimesh"
        ) from exc

    tm = trimesh.Trimesh(
        vertices=mesh_data.vertices.copy(),
        faces=mesh_data.triangles.copy(),
        process=False,
    )
    trimesh.repair.fix_normals(tm)

    return replace(
        mesh_data,
        vertices=np.array(tm.vertices),
        triangles=np.array(tm.faces),
    )


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


def _empty_report() -> dict:
    return {
        "vertices_merged": 0,
        "degenerate_faces_removed": 0,
        "unreferenced_vertices_removed": 0,
        "final_vertex_count": 0,
        "final_triangle_count": 0,
    }
