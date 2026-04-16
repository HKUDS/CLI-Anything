"""FreeCAD CLI - Import module.

Provides functions for importing geometry files in various formats into
the project state.  Depending on the format, imported geometry is added
to ``project["parts"]``, ``project["meshes"]``, or
``project["draft_objects"]``.

Named ``import_mod`` to avoid collision with the Python ``import`` keyword.
"""

import os
from typing import Any, Dict, Optional, Set

from cli_anything.freecad.core.document import ensure_collection

# ---------------------------------------------------------------------------
# Format classification
# ---------------------------------------------------------------------------

#: Formats that produce solid/BREP parts.
PART_FORMATS: Set[str] = {"step", "stp", "iges", "igs", "brep", "brp"}

#: Formats that produce triangle meshes.
MESH_FORMATS: Set[str] = {"stl", "obj", "ply", "off", "3mf", "amf", "gltf", "glb"}

#: Formats that produce 2D draft / mixed objects.
DRAFT_FORMATS: Set[str] = {"dxf", "svg"}

#: Extension -> canonical format name mapping.
EXT_MAP: Dict[str, str] = {
    ".step": "step",
    ".stp": "step",
    ".iges": "iges",
    ".igs": "iges",
    ".stl": "stl",
    ".obj": "obj",
    ".dxf": "dxf",
    ".svg": "svg",
    ".brep": "brep",
    ".brp": "brep",
    ".3mf": "3mf",
    ".ply": "ply",
    ".off": "off",
    ".gltf": "gltf",
    ".glb": "gltf",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_path(path: str, label: str = "path") -> str:
    """Validate that *path* is a non-empty string and return it stripped."""
    if not isinstance(path, str) or not path.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return path.strip()


def _detect_format(path: str) -> str:
    """Detect the canonical format from a file extension.

    Returns
    -------
    str
        The canonical format key (e.g. ``"step"``, ``"stl"``).

    Raises
    ------
    ValueError
        If the extension is not recognised.
    """
    ext = os.path.splitext(path)[1].lower()
    if ext not in EXT_MAP:
        raise ValueError(
            f"Cannot detect format from extension '{ext}'. "
            f"Supported extensions: {', '.join(sorted(EXT_MAP))}"
        )
    return EXT_MAP[ext]


def _next_part_id(project: Dict[str, Any]) -> int:
    """Return the next available integer ID for parts."""
    items = project.get("parts", [])
    if not items:
        return 1
    return max(item["id"] for item in items) + 1


def _next_mesh_id(project: Dict[str, Any]) -> int:
    """Return the next available integer ID for meshes."""
    items = project.get("meshes", [])
    if not items:
        return 1
    return max(item["id"] for item in items) + 1


def _next_draft_id(project: Dict[str, Any]) -> int:
    """Return the next available integer ID for draft objects."""
    items = project.get("draft_objects", [])
    if not items:
        return 1
    return max(item["id"] for item in items) + 1


def _unique_name(project: Dict[str, Any], base: str, key: str) -> str:
    """Return a unique name derived from *base* inside ``project[key]``."""
    existing = {item["name"] for item in project.get(key, [])}
    if base not in existing:
        return base
    counter = 2
    while f"{base}_{counter}" in existing:
        counter += 1
    return f"{base}_{counter}"


def _default_name(path: str, name: Optional[str], project: Dict[str, Any], key: str) -> str:
    """Derive a name from *path* if *name* is None, then make it unique."""
    if name is not None:
        return name
    base = os.path.splitext(os.path.basename(path))[0]
    return _unique_name(project, base, key)


# ---------------------------------------------------------------------------
# Internal import builders
# ---------------------------------------------------------------------------


def _import_as_part(
    project: Dict[str, Any],
    path: str,
    fmt: str,
    name: Optional[str] = None,
    import_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create an imported part entry in ``project["parts"]``."""
    parts = ensure_collection(project, "parts")
    label = _default_name(path, name, project, "parts")

    part: Dict[str, Any] = {
        "id": _next_part_id(project),
        "name": label,
        "type": "imported",
        "params": {
            "source_path": path,
            "source_format": fmt,
            "import_params": import_params or {},
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


def _import_as_mesh(
    project: Dict[str, Any],
    path: str,
    fmt: str,
    name: Optional[str] = None,
    import_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create an imported mesh entry in ``project["meshes"]``."""
    meshes = ensure_collection(project, "meshes")
    label = _default_name(path, name, project, "meshes")

    mesh: Dict[str, Any] = {
        "id": _next_mesh_id(project),
        "name": label,
        "source": path,
        "format": fmt,
        "vertices_count": 0,
        "faces_count": 0,
        "operations_applied": [],
    }

    meshes.append(mesh)
    return mesh


def _import_as_draft(
    project: Dict[str, Any],
    path: str,
    fmt: str,
    name: Optional[str] = None,
    import_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create an imported draft object entry in ``project["draft_objects"]``."""
    objs = ensure_collection(project, "draft_objects")
    label = _default_name(path, name, project, "draft_objects")

    draft_obj: Dict[str, Any] = {
        "id": _next_draft_id(project),
        "name": label,
        "type": "imported",
        "properties": {
            "source_path": path,
            "source_format": fmt,
            "import_params": import_params or {},
        },
        "placement": {
            "position": [0.0, 0.0, 0.0],
            "rotation": [0.0, 0.0, 0.0],
        },
        "visible": True,
    }

    objs.append(draft_obj)
    return draft_obj


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def import_file(
    project: Dict[str, Any],
    path: str,
    format: Optional[str] = None,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Import a file, auto-detecting the format from its extension.

    Depending on the detected format the imported geometry is placed in
    ``project["parts"]``, ``project["meshes"]``, or
    ``project["draft_objects"]``.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    path : str
        Filesystem path to the file.
    format : str or None
        Explicit format override.  When *None* the format is detected
        from the file extension.
    name : str or None
        Label for the imported object.  Derived from filename when *None*.

    Returns
    -------
    dict
        The newly created import entry.

    Raises
    ------
    ValueError
        If the format cannot be detected or is unsupported.
    """
    path = _validate_path(path)
    fmt = format.lower() if format else _detect_format(path)

    if fmt in PART_FORMATS or fmt in {"step", "iges", "brep"}:
        return _import_as_part(project, path, fmt, name)
    elif fmt in MESH_FORMATS:
        return _import_as_mesh(project, path, fmt, name)
    elif fmt in DRAFT_FORMATS:
        return _import_as_draft(project, path, fmt, name)
    else:
        raise ValueError(
            f"Unsupported format '{fmt}'. Supported: "
            f"{', '.join(sorted(PART_FORMATS | MESH_FORMATS | DRAFT_FORMATS))}"
        )


def import_step(
    project: Dict[str, Any],
    path: str,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Import a STEP file into ``project["parts"]``.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    path : str
        Path to the STEP file.
    name : str or None
        Label for the imported part.

    Returns
    -------
    dict
        The newly created part entry.
    """
    path = _validate_path(path)
    return _import_as_part(project, path, "step", name)


def import_iges(
    project: Dict[str, Any],
    path: str,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Import an IGES file into ``project["parts"]``.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    path : str
        Path to the IGES file.
    name : str or None
        Label for the imported part.

    Returns
    -------
    dict
        The newly created part entry.
    """
    path = _validate_path(path)
    return _import_as_part(project, path, "iges", name)


def import_stl(
    project: Dict[str, Any],
    path: str,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Import an STL file into ``project["meshes"]``.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    path : str
        Path to the STL file.
    name : str or None
        Label for the imported mesh.

    Returns
    -------
    dict
        The newly created mesh entry.
    """
    path = _validate_path(path)
    return _import_as_mesh(project, path, "stl", name)


def import_obj(
    project: Dict[str, Any],
    path: str,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Import an OBJ file into ``project["meshes"]``.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    path : str
        Path to the OBJ file.
    name : str or None
        Label for the imported mesh.

    Returns
    -------
    dict
        The newly created mesh entry.
    """
    path = _validate_path(path)
    return _import_as_mesh(project, path, "obj", name)


def import_dxf(
    project: Dict[str, Any],
    path: str,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Import a DXF file into ``project["draft_objects"]`` or ``project["parts"]``.

    DXF files primarily contain 2D geometry and are imported as draft
    objects by default.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    path : str
        Path to the DXF file.
    name : str or None
        Label for the imported object.

    Returns
    -------
    dict
        The newly created draft object entry.
    """
    path = _validate_path(path)
    return _import_as_draft(project, path, "dxf", name)


def import_svg(
    project: Dict[str, Any],
    path: str,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Import an SVG file into ``project["draft_objects"]``.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    path : str
        Path to the SVG file.
    name : str or None
        Label for the imported object.

    Returns
    -------
    dict
        The newly created draft object entry.
    """
    path = _validate_path(path)
    return _import_as_draft(project, path, "svg", name)


def import_brep(
    project: Dict[str, Any],
    path: str,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Import a BREP file into ``project["parts"]``.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    path : str
        Path to the BREP file.
    name : str or None
        Label for the imported part.

    Returns
    -------
    dict
        The newly created part entry.
    """
    path = _validate_path(path)
    return _import_as_part(project, path, "brep", name)


def import_3mf(
    project: Dict[str, Any],
    path: str,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Import a 3MF file into ``project["meshes"]``.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    path : str
        Path to the 3MF file.
    name : str or None
        Label for the imported mesh.

    Returns
    -------
    dict
        The newly created mesh entry.
    """
    path = _validate_path(path)
    return _import_as_mesh(project, path, "3mf", name)


def import_ply(
    project: Dict[str, Any],
    path: str,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Import a PLY file into ``project["meshes"]``.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    path : str
        Path to the PLY file.
    name : str or None
        Label for the imported mesh.

    Returns
    -------
    dict
        The newly created mesh entry.
    """
    path = _validate_path(path)
    return _import_as_mesh(project, path, "ply", name)


def import_off(
    project: Dict[str, Any],
    path: str,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Import an OFF file into ``project["meshes"]``.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    path : str
        Path to the OFF file.
    name : str or None
        Label for the imported mesh.

    Returns
    -------
    dict
        The newly created mesh entry.
    """
    path = _validate_path(path)
    return _import_as_mesh(project, path, "off", name)


def import_gltf(
    project: Dict[str, Any],
    path: str,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Import a glTF/GLB file into ``project["meshes"]``.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    path : str
        Path to the glTF or GLB file.
    name : str or None
        Label for the imported mesh.

    Returns
    -------
    dict
        The newly created mesh entry.
    """
    path = _validate_path(path)
    return _import_as_mesh(project, path, "gltf", name)


def import_info(path: str) -> Dict[str, Any]:
    """Preview file metadata without modifying any project.

    Returns information about the file including size, detected format,
    and estimated object count.  Does **not** require a project dict.

    Parameters
    ----------
    path : str
        Filesystem path to the file.

    Returns
    -------
    dict
        Metadata dictionary with keys ``path``, ``format``,
        ``size_bytes``, ``exists``, and ``estimated_objects``.

    Raises
    ------
    ValueError
        If *path* is empty or the format is unrecognised.
    """
    path = _validate_path(path)
    fmt = _detect_format(path)

    exists = os.path.isfile(path)
    size = os.path.getsize(path) if exists else 0

    # Classify destination
    if fmt in PART_FORMATS:
        target = "parts"
    elif fmt in MESH_FORMATS:
        target = "meshes"
    elif fmt in DRAFT_FORMATS:
        target = "draft_objects"
    else:
        target = "unknown"

    return {
        "path": path,
        "format": fmt,
        "size_bytes": size,
        "exists": exists,
        "estimated_objects": 1,
        "target_collection": target,
    }
