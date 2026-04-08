"""Project management for the CloudCompare CLI harness.

A 'project' is a JSON file tracking:
- Loaded clouds and meshes (input file paths, labels)
- Active working files (current state after operations)
- Session settings (export format, global shift, etc.)
- Operation history for undo/redo
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Optional

try:
    import fcntl as _fcntl
    _HAS_FCNTL = True
except ImportError:
    _HAS_FCNTL = False


# ── JSON locking helper ──────────────────────────────────────────────────────

def _locked_save_json(path: str, data: dict, **dump_kwargs) -> None:
    """Atomically write JSON with exclusive file locking."""
    path = os.path.abspath(path)
    try:
        f = open(path, "r+")            # no truncation on open
    except FileNotFoundError:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        f = open(path, "w")             # first save — file doesn't exist yet
    with f:
        _locked = False
        try:
            if _HAS_FCNTL:
                _fcntl.flock(f.fileno(), _fcntl.LOCK_EX)
                _locked = True
        except OSError:
            pass                        # unsupported FS — proceed unlocked
        try:
            f.seek(0)
            f.truncate()
            json.dump(data, f, indent=2, **dump_kwargs)
            f.flush()
        finally:
            if _locked:
                _fcntl.flock(f.fileno(), _fcntl.LOCK_UN)


# ── Project data model ───────────────────────────────────────────────────────

def _default_project(name: str = "untitled") -> dict:
    """Return a fresh project structure."""
    return {
        "version": "1.0",
        "name": name,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "modified_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "clouds": [],      # list of cloud entries
        "meshes": [],      # list of mesh entries
        "settings": {
            "cloud_export_format": "LAS",
            "cloud_export_ext": "las",
            "mesh_export_format": "OBJ",
            "mesh_export_ext": "obj",
            "global_shift": None,      # [x, y, z] or null
            "no_timestamp": True,
        },
        "history": [],     # operation history for undo
    }


def _cloud_entry(path: str, label: Optional[str] = None) -> dict:
    """Create a cloud entry dict."""
    path = os.path.abspath(path)
    return {
        "path": path,
        "label": label or Path(path).stem,
        "loaded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "scalar_fields": [],
        "has_normals": False,
        "has_rgb": False,
    }


def _mesh_entry(path: str, label: Optional[str] = None) -> dict:
    """Create a mesh entry dict."""
    path = os.path.abspath(path)
    return {
        "path": path,
        "label": label or Path(path).stem,
        "loaded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


# ── Public API ────────────────────────────────────────────────────────────────

def create_project(output_path: str, name: Optional[str] = None) -> dict:
    """Create a new empty project and save it to disk.

    Args:
        output_path: Where to save the .json project file.
        name: Human-readable project name.

    Returns:
        The project dict.
    """
    output_path = os.path.abspath(output_path)
    if name is None:
        name = Path(output_path).stem
    proj = _default_project(name)
    _locked_save_json(output_path, proj)
    return proj


def load_project(path: str) -> dict:
    """Load a project from disk.

    Args:
        path: Path to the .json project file.

    Returns:
        The project dict.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If the file is not a valid project JSON.
    """
    path = os.path.abspath(path)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Project file not found: {path}")

    with open(path) as f:
        data = json.load(f)

    if "version" not in data or "clouds" not in data:
        raise ValueError(f"Not a valid CloudCompare CLI project: {path}")

    return data


def save_project(project: dict, path: str) -> None:
    """Save project to disk.

    Args:
        project: Project dict.
        path: Destination .json file path.
    """
    project["modified_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    _locked_save_json(path, project)


def add_cloud(project: dict, cloud_path: str, label: Optional[str] = None) -> dict:
    """Add a cloud to the project's cloud list.

    Args:
        project: Project dict (modified in place).
        cloud_path: Path to the cloud file.
        label: Optional label.

    Returns:
        The new cloud entry.
    """
    if not os.path.exists(cloud_path):
        raise FileNotFoundError(f"Cloud file not found: {cloud_path}")

    entry = _cloud_entry(cloud_path, label)
    project["clouds"].append(entry)
    return entry


def add_mesh(project: dict, mesh_path: str, label: Optional[str] = None) -> dict:
    """Add a mesh to the project's mesh list.

    Args:
        project: Project dict (modified in place).
        mesh_path: Path to the mesh file.
        label: Optional label.

    Returns:
        The new mesh entry.
    """
    if not os.path.exists(mesh_path):
        raise FileNotFoundError(f"Mesh file not found: {mesh_path}")

    entry = _mesh_entry(mesh_path, label)
    project["meshes"].append(entry)
    return entry


def remove_cloud(project: dict, index: int) -> dict:
    """Remove a cloud by index.

    Args:
        project: Project dict (modified in place).
        index: 0-based index of the cloud to remove.

    Returns:
        The removed cloud entry.
    """
    if index < 0 or index >= len(project["clouds"]):
        raise IndexError(f"No cloud at index {index} (project has {len(project['clouds'])} clouds)")
    return project["clouds"].pop(index)


def remove_mesh(project: dict, index: int) -> dict:
    """Remove a mesh by index.

    Args:
        project: Project dict (modified in place).
        index: 0-based index of the mesh to remove.

    Returns:
        The removed mesh entry.
    """
    if index < 0 or index >= len(project["meshes"]):
        raise IndexError(f"No mesh at index {index} (project has {len(project['meshes'])} meshes)")
    return project["meshes"].pop(index)


def get_cloud(project: dict, index: int) -> dict:
    """Get a cloud entry by index.

    Args:
        project: Project dict.
        index: 0-based index.

    Returns:
        The cloud entry dict.
    """
    clouds = project.get("clouds", [])
    if index < 0 or index >= len(clouds):
        raise IndexError(f"No cloud at index {index}")
    return clouds[index]


def get_mesh(project: dict, index: int) -> dict:
    """Get a mesh entry by index."""
    meshes = project.get("meshes", [])
    if index < 0 or index >= len(meshes):
        raise IndexError(f"No mesh at index {index}")
    return meshes[index]


def project_info(project: dict) -> dict:
    """Return a summary dict of the project state."""
    return {
        "name": project.get("name", "unnamed"),
        "version": project.get("version", "?"),
        "created_at": project.get("created_at", ""),
        "modified_at": project.get("modified_at", ""),
        "cloud_count": len(project.get("clouds", [])),
        "mesh_count": len(project.get("meshes", [])),
        "history_depth": len(project.get("history", [])),
        "settings": project.get("settings", {}),
        "clouds": [
            {"index": i, "label": c["label"], "path": c["path"]}
            for i, c in enumerate(project.get("clouds", []))
        ],
        "meshes": [
            {"index": i, "label": m["label"], "path": m["path"]}
            for i, m in enumerate(project.get("meshes", []))
        ],
    }


def record_operation(project: dict, operation: str, inputs: list[str], outputs: list[str], params: dict) -> None:
    """Record an operation in the project history.

    Args:
        project: Project dict (modified in place).
        operation: Operation name (e.g., 'subsample').
        inputs: List of input file paths.
        outputs: List of output file paths.
        params: Operation parameters dict.
    """
    entry = {
        "operation": operation,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "inputs": inputs,
        "outputs": outputs,
        "params": params,
    }
    project.setdefault("history", []).append(entry)
