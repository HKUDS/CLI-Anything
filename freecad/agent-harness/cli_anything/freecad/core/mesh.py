"""FreeCAD CLI - Mesh operations module.

Manages mesh import, export, tessellation from shapes, analysis, boolean
operations, decimation, remeshing, smoothing, repair, and conversion back
to solid shapes.  Meshes are stored in ``project["meshes"]`` via
:func:`~cli_anything.freecad.core.document.ensure_collection`.
"""

import os
from copy import deepcopy
from typing import Any, Dict, List, Optional, Set

from cli_anything.freecad.core.document import ensure_collection

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MESH_FORMATS: Set[str] = {"stl", "obj", "ply", "off", "3mf", "amf", "bms"}
MESH_BOOLEAN_OPS: Set[str] = {"union", "difference", "intersection"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _next_id(project: Dict[str, Any]) -> int:
    """Return the next available integer ID for meshes."""
    items = project.get("meshes", [])
    if not items:
        return 1
    return max(item["id"] for item in items) + 1


def _unique_name(project: Dict[str, Any], base: str) -> str:
    """Return a unique name derived from *base* inside ``project["meshes"]``."""
    existing = {item["name"] for item in project.get("meshes", [])}
    if base not in existing:
        return base
    counter = 2
    while f"{base}_{counter}" in existing:
        counter += 1
    return f"{base}_{counter}"


def _get_mesh(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Return the mesh at *index*, raising ``IndexError`` if out of range."""
    meshes = project.get("meshes", [])
    if not isinstance(index, int) or index < 0 or index >= len(meshes):
        raise IndexError(
            f"Mesh index {index} out of range (0..{len(meshes) - 1})"
        )
    return meshes[index]


def _validate_path(path: str, label: str = "path") -> str:
    """Validate that *path* is a non-empty string and return it normalised."""
    if not isinstance(path, str) or not path.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return path.strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def import_mesh(
    project: Dict[str, Any],
    path: str,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Import a mesh file and register it in ``project["meshes"]``.

    The actual file loading happens during macro generation; this function
    records the import intent and metadata.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    path : str
        Filesystem path to the mesh file.
    name : str or None
        Human-readable label.  Derived from filename when *None*.

    Returns
    -------
    dict
        The newly created mesh entry.

    Raises
    ------
    ValueError
        If *path* is empty.
    """
    path = _validate_path(path)
    meshes = ensure_collection(project, "meshes")

    ext = os.path.splitext(path)[1].lstrip(".").lower()
    if name is None:
        base = os.path.splitext(os.path.basename(path))[0]
        name = _unique_name(project, base)

    mesh: Dict[str, Any] = {
        "id": _next_id(project),
        "name": name,
        "source": path,
        "format": ext if ext else "unknown",
        "vertices_count": 0,
        "faces_count": 0,
        "operations_applied": [],
    }

    meshes.append(mesh)
    return mesh


def mesh_from_shape(
    project: Dict[str, Any],
    part_index: int,
    name: Optional[str] = None,
    max_length: Optional[float] = None,
    deviation: float = 0.1,
) -> Dict[str, Any]:
    """Tessellate a solid part into a triangular mesh.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    part_index : int
        Index of the source part in ``project["parts"]``.
    name : str or None
        Label for the new mesh.  Auto-generated when *None*.
    max_length : float or None
        Maximum edge length constraint.  *None* means no constraint.
    deviation : float
        Surface deviation tolerance (default ``0.1``).

    Returns
    -------
    dict
        The newly created mesh entry.

    Raises
    ------
    IndexError
        If *part_index* is out of range.
    ValueError
        If *deviation* is not positive.
    """
    parts = project.get("parts", [])
    if not isinstance(part_index, int) or part_index < 0 or part_index >= len(parts):
        raise IndexError(
            f"Part index {part_index} out of range (0..{len(parts) - 1})"
        )

    if deviation <= 0:
        raise ValueError("deviation must be a positive number")

    meshes = ensure_collection(project, "meshes")
    part = parts[part_index]

    if name is None:
        name = _unique_name(project, f"{part['name']}_Mesh")

    params: Dict[str, Any] = {"deviation": float(deviation)}
    if max_length is not None:
        if max_length <= 0:
            raise ValueError("max_length must be a positive number")
        params["max_length"] = float(max_length)

    mesh: Dict[str, Any] = {
        "id": _next_id(project),
        "name": name,
        "source": part_index,
        "format": "tessellated",
        "vertices_count": 0,
        "faces_count": 0,
        "operations_applied": [
            {"op": "tessellate", "params": params},
        ],
    }

    meshes.append(mesh)
    return mesh


def export_mesh(
    project: Dict[str, Any],
    mesh_index: int,
    path: str,
    format: str = "stl",
) -> Dict[str, Any]:
    """Record an export request for the mesh at *mesh_index*.

    The actual file writing is performed during macro generation; this
    function validates the arguments and returns export metadata.

    Parameters
    ----------
    project : dict
        The project state dictionary.
    mesh_index : int
        Index of the mesh to export.
    path : str
        Destination file path.
    format : str
        Output format (default ``"stl"``).

    Returns
    -------
    dict
        Export metadata including mesh id, path, and format.

    Raises
    ------
    IndexError
        If *mesh_index* is out of range.
    ValueError
        If *format* is unsupported or *path* is empty.
    """
    mesh = _get_mesh(project, mesh_index)
    path = _validate_path(path, "export path")

    fmt = format.lower()
    if fmt not in MESH_FORMATS:
        valid = ", ".join(sorted(MESH_FORMATS))
        raise ValueError(f"Unsupported mesh format '{fmt}'. Valid: {valid}")

    return {
        "mesh_id": mesh["id"],
        "mesh_name": mesh["name"],
        "path": path,
        "format": fmt,
    }


def mesh_info(project: Dict[str, Any], mesh_index: int) -> Dict[str, Any]:
    """Return a summary of the mesh at *mesh_index*.

    Parameters
    ----------
    project : dict
        The project state dictionary.
    mesh_index : int
        Index of the mesh.

    Returns
    -------
    dict
        Copy of the mesh entry.
    """
    mesh = _get_mesh(project, mesh_index)
    return deepcopy(mesh)


def analyze_mesh(project: Dict[str, Any], mesh_index: int) -> Dict[str, Any]:
    """Return stored analysis results for the mesh at *mesh_index*.

    Analysis covers vertex/face counts, bounding-box estimation, and
    volume/area placeholders.  Actual numerical analysis happens in the
    FreeCAD macro; this records the intent and returns current metadata.

    Parameters
    ----------
    project : dict
        The project state dictionary.
    mesh_index : int
        Index of the mesh.

    Returns
    -------
    dict
        Analysis result dictionary.
    """
    mesh = _get_mesh(project, mesh_index)
    return {
        "mesh_id": mesh["id"],
        "name": mesh["name"],
        "vertices_count": mesh["vertices_count"],
        "faces_count": mesh["faces_count"],
        "format": mesh["format"],
        "operations_applied": list(mesh["operations_applied"]),
        "analysis": "pending_macro_execution",
    }


def check_mesh(project: Dict[str, Any], mesh_index: int) -> Dict[str, Any]:
    """Check the mesh at *mesh_index* for common problems.

    Returns a diagnostic dictionary.  The actual checks (non-manifold
    edges, self-intersections, degenerate faces) are performed by the
    FreeCAD macro; this function records the request.

    Parameters
    ----------
    project : dict
        The project state dictionary.
    mesh_index : int
        Index of the mesh.

    Returns
    -------
    dict
        Diagnostic placeholder with mesh metadata.
    """
    mesh = _get_mesh(project, mesh_index)
    return {
        "mesh_id": mesh["id"],
        "name": mesh["name"],
        "checks": [
            "non_manifold_edges",
            "self_intersections",
            "degenerate_faces",
            "duplicate_faces",
            "duplicate_points",
            "orientation",
        ],
        "status": "pending_macro_execution",
    }


def mesh_boolean(
    project: Dict[str, Any],
    op: str,
    base_index: int,
    tool_index: int,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Perform a boolean operation between two meshes.

    Creates a new mesh entry representing the result.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    op : str
        One of ``"union"``, ``"difference"``, or ``"intersection"``.
    base_index : int
        Index of the base mesh.
    tool_index : int
        Index of the tool mesh.
    name : str or None
        Label for the result mesh.

    Returns
    -------
    dict
        The newly created result mesh entry.

    Raises
    ------
    ValueError
        If *op* is unknown or indices are equal.
    IndexError
        If either index is out of range.
    """
    if op not in MESH_BOOLEAN_OPS:
        valid = ", ".join(sorted(MESH_BOOLEAN_OPS))
        raise ValueError(f"Unknown mesh boolean op '{op}'. Valid: {valid}")

    if base_index == tool_index:
        raise ValueError("base_index and tool_index must differ")

    base_mesh = _get_mesh(project, base_index)
    tool_mesh = _get_mesh(project, tool_index)

    meshes = ensure_collection(project, "meshes")

    if name is None:
        name = _unique_name(project, f"MeshBool_{op.capitalize()}")

    result: Dict[str, Any] = {
        "id": _next_id(project),
        "name": name,
        "source": f"boolean:{op}",
        "format": "computed",
        "vertices_count": 0,
        "faces_count": 0,
        "operations_applied": [
            {
                "op": f"boolean_{op}",
                "params": {
                    "base_id": base_mesh["id"],
                    "tool_id": tool_mesh["id"],
                },
            },
        ],
    }

    meshes.append(result)
    return result


def decimate_mesh(
    project: Dict[str, Any],
    mesh_index: int,
    target_faces: int = 1000,
) -> Dict[str, Any]:
    """Decimate (simplify) the mesh at *mesh_index*.

    Records a decimation operation targeting *target_faces* triangles.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    mesh_index : int
        Index of the mesh to decimate.
    target_faces : int
        Target number of faces after decimation.

    Returns
    -------
    dict
        The updated mesh entry.

    Raises
    ------
    IndexError
        If *mesh_index* is out of range.
    ValueError
        If *target_faces* is not a positive integer.
    """
    if not isinstance(target_faces, int) or target_faces <= 0:
        raise ValueError("target_faces must be a positive integer")

    mesh = _get_mesh(project, mesh_index)
    mesh["operations_applied"].append({
        "op": "decimate",
        "params": {"target_faces": target_faces},
    })
    return mesh


def remesh_mesh(
    project: Dict[str, Any],
    mesh_index: int,
    target_length: float = 1.0,
) -> Dict[str, Any]:
    """Remesh the mesh at *mesh_index* with uniform edge lengths.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    mesh_index : int
        Index of the mesh to remesh.
    target_length : float
        Target edge length for the remeshed output.

    Returns
    -------
    dict
        The updated mesh entry.

    Raises
    ------
    IndexError
        If *mesh_index* is out of range.
    ValueError
        If *target_length* is not positive.
    """
    if target_length <= 0:
        raise ValueError("target_length must be a positive number")

    mesh = _get_mesh(project, mesh_index)
    mesh["operations_applied"].append({
        "op": "remesh",
        "params": {"target_length": float(target_length)},
    })
    return mesh


def smooth_mesh(
    project: Dict[str, Any],
    mesh_index: int,
    iterations: int = 3,
    factor: float = 0.5,
) -> Dict[str, Any]:
    """Apply Laplacian smoothing to the mesh at *mesh_index*.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    mesh_index : int
        Index of the mesh to smooth.
    iterations : int
        Number of smoothing passes (default ``3``).
    factor : float
        Smoothing intensity factor between 0 and 1 (default ``0.5``).

    Returns
    -------
    dict
        The updated mesh entry.

    Raises
    ------
    IndexError
        If *mesh_index* is out of range.
    ValueError
        If *iterations* or *factor* is invalid.
    """
    if not isinstance(iterations, int) or iterations <= 0:
        raise ValueError("iterations must be a positive integer")
    if not (0.0 < factor <= 1.0):
        raise ValueError("factor must be between 0 (exclusive) and 1 (inclusive)")

    mesh = _get_mesh(project, mesh_index)
    mesh["operations_applied"].append({
        "op": "smooth",
        "params": {"iterations": iterations, "factor": float(factor)},
    })
    return mesh


def repair_mesh(project: Dict[str, Any], mesh_index: int) -> Dict[str, Any]:
    """Record a repair operation for the mesh at *mesh_index*.

    Repair includes fixing degenerate faces, removing duplicates,
    harmonising normals, and filling small holes.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    mesh_index : int
        Index of the mesh to repair.

    Returns
    -------
    dict
        The updated mesh entry.
    """
    mesh = _get_mesh(project, mesh_index)
    mesh["operations_applied"].append({
        "op": "repair",
        "params": {},
    })
    return mesh


def fill_holes(
    project: Dict[str, Any],
    mesh_index: int,
    max_hole_size: int = 10,
) -> Dict[str, Any]:
    """Fill holes in the mesh at *mesh_index*.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    mesh_index : int
        Index of the mesh.
    max_hole_size : int
        Maximum number of edges bounding a hole to fill (default ``10``).

    Returns
    -------
    dict
        The updated mesh entry.

    Raises
    ------
    ValueError
        If *max_hole_size* is not a positive integer.
    """
    if not isinstance(max_hole_size, int) or max_hole_size <= 0:
        raise ValueError("max_hole_size must be a positive integer")

    mesh = _get_mesh(project, mesh_index)
    mesh["operations_applied"].append({
        "op": "fill_holes",
        "params": {"max_hole_size": max_hole_size},
    })
    return mesh


def flip_normals(project: Dict[str, Any], mesh_index: int) -> Dict[str, Any]:
    """Flip all face normals on the mesh at *mesh_index*.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    mesh_index : int
        Index of the mesh.

    Returns
    -------
    dict
        The updated mesh entry.
    """
    mesh = _get_mesh(project, mesh_index)
    mesh["operations_applied"].append({
        "op": "flip_normals",
        "params": {},
    })
    return mesh


def merge_meshes(
    project: Dict[str, Any],
    indices: List[int],
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Merge multiple meshes into a single mesh.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    indices : list[int]
        Indices of the meshes to merge.
    name : str or None
        Label for the merged mesh.

    Returns
    -------
    dict
        The newly created merged mesh entry.

    Raises
    ------
    ValueError
        If fewer than two indices are supplied or any index is invalid.
    """
    if not isinstance(indices, (list, tuple)) or len(indices) < 2:
        raise ValueError("At least two mesh indices are required for merging")

    source_ids = []
    for idx in indices:
        mesh = _get_mesh(project, idx)
        source_ids.append(mesh["id"])

    meshes = ensure_collection(project, "meshes")

    if name is None:
        name = _unique_name(project, "MergedMesh")

    result: Dict[str, Any] = {
        "id": _next_id(project),
        "name": name,
        "source": "merged",
        "format": "computed",
        "vertices_count": 0,
        "faces_count": 0,
        "operations_applied": [
            {"op": "merge", "params": {"source_ids": source_ids}},
        ],
    }

    meshes.append(result)
    return result


def split_mesh(project: Dict[str, Any], mesh_index: int) -> Dict[str, Any]:
    """Split a mesh into its disconnected components.

    Records the split operation.  The actual component separation is
    performed by the FreeCAD macro; this function returns metadata
    about the request.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    mesh_index : int
        Index of the mesh to split.

    Returns
    -------
    dict
        Metadata describing the split request.
    """
    mesh = _get_mesh(project, mesh_index)
    mesh["operations_applied"].append({
        "op": "split",
        "params": {},
    })
    return {
        "mesh_id": mesh["id"],
        "name": mesh["name"],
        "status": "split_pending_macro_execution",
    }


def mesh_to_shape(
    project: Dict[str, Any],
    mesh_index: int,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Convert a mesh to a solid shape and add it to ``project["parts"]``.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    mesh_index : int
        Index of the source mesh.
    name : str or None
        Label for the resulting part.

    Returns
    -------
    dict
        The newly created part entry in ``project["parts"]``.
    """
    mesh = _get_mesh(project, mesh_index)
    parts = ensure_collection(project, "parts")

    if name is None:
        base = f"{mesh['name']}_Solid"
        existing = {p["name"] for p in parts}
        if base in existing:
            counter = 2
            while f"{base}_{counter}" in existing:
                counter += 1
            base = f"{base}_{counter}"
        name = base

    # Compute next part id
    part_id = max((p["id"] for p in parts), default=0) + 1

    part: Dict[str, Any] = {
        "id": part_id,
        "name": name,
        "type": "mesh_to_shape",
        "params": {
            "source_mesh_id": mesh["id"],
        },
        "placement": {
            "position": [0.0, 0.0, 0.0],
            "rotation": [0.0, 0.0, 0.0],
        },
        "material_index": None,
        "visible": True,
    }

    parts.append(part)
    return part
