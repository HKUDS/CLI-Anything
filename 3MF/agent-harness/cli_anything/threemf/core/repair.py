"""Mesh repair -- fix degenerate faces, duplicate vertices, and normals."""

from __future__ import annotations

from dataclasses import dataclass, replace

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
    5. Fix inconsistent winding and inward-pointing normals.
    6. Return the repaired mesh and a report dict.
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
    valid_faces = _nondegenerate_face_mask(triangles)
    degen_count = int(triangles.shape[0] - np.count_nonzero(valid_faces))
    triangles = triangles[valid_faces]
    triangle_attributes = _filter_triangle_attributes(
        mesh_data.triangle_attributes,
        valid_faces,
    )

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

    repaired = replace(
        mesh_data,
        vertices=vertices,
        triangles=triangles,
        triangle_attributes=triangle_attributes,
    )
    fixed = fix_normals(repaired)
    report["faces_reoriented"] = int(np.count_nonzero(
        np.any(fixed.triangles != repaired.triangles, axis=1),
    ))
    return fixed, report


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

    valid = _nondegenerate_face_mask(triangles)
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
    """Fix winding and orient closed shells at the material boundary.

    Returns a **new** ``MeshData`` with corrected triangle winding order.
    Separate solids point outward; nested cavity shells point inward.
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
    trimesh.repair.fix_winding(tm)

    # An aggregate volume cannot distinguish inverted solids from cavities.
    # Find closed shells without changing face order or discarding open faces.
    groups = trimesh.graph.connected_components(
        tm.face_adjacency, nodes=np.arange(len(tm.faces)), engine="networkx",
    )
    closed_shells = []
    for indices in groups:
        if len(indices) < 4:
            continue
        # Classification shells need only their own vertices. Keeping the
        # full model in each shell also makes cached bounds needlessly large.
        vertex_indices, local_faces = np.unique(tm.faces[indices], return_inverse=True)
        shell = trimesh.Trimesh(
            vertices=tm.vertices[vertex_indices], faces=local_faces.reshape(-1, 3), process=False,
        )
        if shell.is_watertight and shell.is_winding_consistent and shell.volume != 0:
            closed_shells.append((indices, shell))

    shell_bounds = np.array([shell.bounds for _, shell in closed_shells])
    shell_tree = (
        _bounds_tree(shell_bounds[:, 0], shell_bounds[:, 1], np.arange(len(closed_shells)))
        if closed_shells else None
    )
    # Reuse each immutable shell's triangle hierarchy across containment
    # pairs. This cache belongs only to this invocation of normal repair.
    boundaries = [None] * len(closed_shells)
    fixed_triangles = np.array(tm.faces)
    for index, (indices, shell) in enumerate(closed_shells):
        depth = 0
        for other_index in _enclosing_shell_indices(shell_bounds, shell_tree, index):
            _, enclosing = closed_shells[other_index]
            # A point classifies the whole connected shell only when the
            # boundaries are disjoint. Crossing a concave wall or touching
            # it must not turn an overlapping solid into a cavity.
            if not _encloses_point(enclosing.triangles, shell.triangles[0, 0]):
                continue
            for shell_index in (other_index, index):
                if boundaries[shell_index] is None:
                    boundaries[shell_index] = _triangle_boundary(closed_shells[shell_index][1].triangles)
            if not _shell_boundaries_intersect(boundaries[other_index], boundaries[index]):
                depth += 1

        if (shell.volume < 0) != (depth % 2 == 1):
            fixed_triangles[indices] = fixed_triangles[indices, ::-1]

    # Keep the original first vertex when expressing the corrected winding.
    # This also keeps the implicit object-level property fallback for p1;
    # reversing a face then only swaps its second and third properties.
    first_positions = np.argmax(
        fixed_triangles == mesh_data.triangles[:, :1], axis=1,
    )
    fixed_triangles = np.take_along_axis(
        fixed_triangles, (first_positions[:, None] + np.arange(3)) % 3, axis=1,
    )
    flipped = fixed_triangles[:, 1] != mesh_data.triangles[:, 1]
    triangle_attributes = (
        tuple(
            _reorient_triangle_properties(attrs) if flip else dict(attrs)
            for attrs, flip in zip(mesh_data.triangle_attributes, flipped)
        )
        if len(mesh_data.triangle_attributes) == fixed_triangles.shape[0]
        else ()
    )

    return replace(
        mesh_data,
        vertices=np.array(tm.vertices),
        triangles=fixed_triangles,
        triangle_attributes=triangle_attributes,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _shell_boundaries_intersect(
    first: np.ndarray | _TriangleBoundary, second: np.ndarray | _TriangleBoundary,
) -> bool:
    """Conservatively detect triangle intersection or contact between shells.

    Traverse cached triangle-bound hierarchies in a common scale. Bounds
    stay in their original coordinates so a shell can be reused with
    different enclosing shells without changing the cache. Disjoint subtrees
    are discarded without comparing every pair of faces. Overlapping leaves use the same
    separating-axis test, with near-contact counted as intersection. This
    only classifies containment; it does not alter geometry.
    """
    if not isinstance(first, _TriangleBoundary):
        first = _triangle_boundary(first)
    if not isinstance(second, _TriangleBoundary):
        second = _triangle_boundary(second)
    low = np.minimum(first.tree.low, second.tree.low)
    high = np.maximum(first.tree.high, second.tree.high)
    scale = float(np.max(high - low))
    if not np.isfinite(scale) or scale <= 0:
        return True
    if len(first.triangles) > len(second.triangles):
        first, second = second, first
    tolerance = 64 * np.finfo(float).eps
    pending = [(first.tree, second.tree)]
    while pending:
        left, right = pending.pop()
        left_low, left_high = (left.low - low) / scale, (left.high - low) / scale
        right_low, right_high = (right.low - low) / scale, (right.high - low) / scale
        if np.any(left_high < right_low - tolerance) or np.any(right_high < left_low - tolerance):
            continue
        if left.children or right.children:
            # Split the larger non-leaf; tree depth is logarithmic even
            # when many triangle centers coincide.
            if right.children and (not left.children or right.count >= left.count):
                pending.extend((left, child) for child in right.children)
            else:
                pending.extend((child, right) for child in left.children)
            continue
        for index in left.indices:
            first_low = (first.low[index] - low) / scale
            first_high = (first.high[index] - low) / scale
            candidates = right.indices[
                np.all((second.high[right.indices] - low) / scale >= first_low - tolerance, axis=1)
                & np.all((second.low[right.indices] - low) / scale <= first_high + tolerance, axis=1)
            ]
            if len(candidates) and _triangles_intersect(
                (first.triangles[index] - low) / scale,
                (second.triangles[candidates] - low) / scale,
                tolerance,
            ):
                return True
    return False


@dataclass
class _BoundsNode:
    low: np.ndarray
    high: np.ndarray
    count: int
    indices: np.ndarray | None = None
    children: tuple[_BoundsNode, ...] = ()


@dataclass
class _TriangleBoundary:
    triangles: np.ndarray
    low: np.ndarray
    high: np.ndarray
    tree: _BoundsNode


def _triangle_boundary(triangles: np.ndarray) -> _TriangleBoundary:
    low, high = triangles.min(axis=1), triangles.max(axis=1)
    return _TriangleBoundary(
        triangles, low, high, _bounds_tree(low, high, np.arange(len(triangles))),
    )


def _bounds_tree(low: np.ndarray, high: np.ndarray, indices: np.ndarray) -> _BoundsNode:
    """Partition bounds; every node encloses every object below it."""
    node = _BoundsNode(low[indices].min(axis=0), high[indices].max(axis=0), len(indices))
    if len(indices) <= 16:
        node.indices = indices
        return node
    centers = (low[indices] + high[indices]) * 0.5
    axis = int(np.argmax(np.ptp(centers, axis=0)))
    middle = len(indices) // 2
    indices = indices[np.argpartition(centers[:, axis], middle)]
    node.children = (
        _bounds_tree(low, high, indices[:middle]),
        _bounds_tree(low, high, indices[middle:]),
    )
    return node


def _enclosing_shell_indices(bounds: np.ndarray, tree: _BoundsNode, index: int):
    """Yield only shells whose bounds strictly contain the queried shell."""
    low, high = bounds[index]
    pending = [tree]
    while pending:
        node = pending.pop()
        # If even the union cannot enclose the query, no individual shell
        # in this subtree can do so. Test actual shell bounds at leaves.
        if np.any(node.low >= low) or np.any(node.high <= high):
            continue
        if node.children:
            pending.extend(node.children)
        else:
            candidates = node.indices[
                np.all(bounds[node.indices, 0] < low, axis=1)
                & np.all(high < bounds[node.indices, 1], axis=1)
            ]
            yield from candidates


def _triangles_intersect(triangle: np.ndarray, candidates: np.ndarray, tolerance: float) -> bool:
    """Test one triangle against a batch, including coplanar contact."""
    edges = np.roll(triangle, -1, axis=0) - triangle
    other_edges = np.roll(candidates, -1, axis=1) - candidates
    normal = np.cross(edges[0], edges[1])
    other_normals = np.cross(other_edges[:, 0], other_edges[:, 1])
    axes = np.concatenate([
        np.broadcast_to(normal, (len(candidates), 1, 3)),
        other_normals[:, None, :],
        np.cross(edges[None, :, None, :], other_edges[:, None, :, :]).reshape(-1, 9, 3),
        # Face normals and edge-cross-edge axes alone cannot separate
        # disjoint coplanar triangles: include their in-plane edge normals.
        np.broadcast_to(np.cross(normal, edges), (len(candidates), 3, 3)),
        np.cross(other_normals[:, None, :], other_edges),
    ], axis=1)
    degenerate = (
        ~np.any(other_normals, axis=1) if not np.any(normal)
        else np.zeros(len(candidates), dtype=bool)
    )
    if np.any(degenerate):
        # Two zero-area triangles are segments or points. Face-derived
        # axes can all vanish, so include their lower-dimensional SAT axes.
        direction = edges[np.argmax(np.linalg.norm(edges, axis=1))]
        other_directions = other_edges[
            np.arange(len(candidates)), np.argmax(np.linalg.norm(other_edges, axis=2), axis=1),
        ]
        pair_normals = np.cross(direction, other_directions)
        extra = np.concatenate([
            np.broadcast_to(direction, (len(candidates), 1, 3)),
            other_directions[:, None, :],
            pair_normals[:, None, :],
            np.cross(pair_normals, direction)[:, None, :],
            np.cross(pair_normals, other_directions)[:, None, :],
            np.broadcast_to(np.cross(direction, np.eye(3)), (len(candidates), 3, 3)),
            np.cross(other_directions[:, None, :], np.eye(3)),
            np.broadcast_to(np.eye(3), (len(candidates), 3, 3)),
        ], axis=1)
        extra[~degenerate] = 0
        axes = np.concatenate([axes, extra], axis=1)
    # These cross products have different dimensions (length squared or
    # cubed), so a contact-distance tolerance cannot decide whether they
    # are valid axes. Scale every nonzero axis before taking its norm to
    # retain separators from small facets without squaring tiny values.
    magnitudes = np.max(np.abs(axes), axis=2, keepdims=True)
    axes = np.divide(axes, magnitudes, out=np.zeros_like(axes), where=magnitudes > 0)
    lengths = np.linalg.norm(axes, axis=2, keepdims=True)
    axes = np.divide(axes, lengths, out=np.zeros_like(axes), where=lengths > 0)
    projected = np.einsum("td,nad->nat", triangle, axes)
    other_projected = np.einsum("ntd,nad->nat", candidates, axes)
    separated = (
        (projected.max(axis=2) < other_projected.min(axis=2) - tolerance)
        | (other_projected.max(axis=2) < projected.min(axis=2) - tolerance)
    )
    return bool(np.any(~np.any(separated, axis=1)))


def _encloses_point(triangles: np.ndarray, point: np.ndarray) -> bool:
    """Test a point against a closed shell without depending on its winding.

    The signed solid angles sum to +/-4*pi inside and zero outside. Work in
    chunks to bound temporary arrays for large meshes and normalize vectors
    before evaluating the angle to avoid products of cubed model dimensions.
    """
    angle = 0.0
    for start in range(0, len(triangles), 4096):
        vectors = triangles[start:start + 4096] - point
        lengths = np.linalg.norm(vectors, axis=2)
        if np.any(lengths == 0):
            return False
        directions = vectors / lengths[:, :, None]
        a, b, c = directions[:, 0], directions[:, 1], directions[:, 2]
        numerator = np.einsum("ij,ij->i", a, np.cross(b, c))
        denominator = (
            1.0 + np.einsum("ij,ij->i", a, b)
            + np.einsum("ij,ij->i", b, c)
            + np.einsum("ij,ij->i", c, a)
        )
        angle += float(np.sum(2.0 * np.arctan2(numerator, denominator)))
    return abs(angle) > 2.0 * np.pi


def _reorient_triangle_properties(attrs: dict[str, str]) -> dict[str, str]:
    """Swap per-vertex properties with v2/v3, preserving omitted defaults."""
    result = dict(attrs)
    for old, new in (("p2", "p3"), ("p3", "p2")):
        if old in attrs:
            result[new] = attrs[old]
        else:
            result.pop(new, None)
    return result


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


def _nondegenerate_face_mask(triangles: np.ndarray) -> np.ndarray:
    if triangles.shape[0] == 0:
        return np.zeros((0,), dtype=bool)
    v0, v1, v2 = triangles[:, 0], triangles[:, 1], triangles[:, 2]
    return (v0 != v1) & (v1 != v2) & (v0 != v2)


def _filter_triangle_attributes(
    triangle_attributes: tuple[dict[str, str], ...],
    mask: np.ndarray,
) -> tuple[dict[str, str], ...]:
    if not triangle_attributes:
        return ()
    return tuple(
        dict(attrs)
        for attrs, keep in zip(triangle_attributes, mask)
        if bool(keep)
    )


def _empty_report() -> dict:
    return {
        "vertices_merged": 0,
        "degenerate_faces_removed": 0,
        "unreferenced_vertices_removed": 0,
        "faces_reoriented": 0,
        "final_vertex_count": 0,
        "final_triangle_count": 0,
    }
