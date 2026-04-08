"""Session management for the CloudCompare CLI harness.

A session wraps a project file path and provides:
- Convenience methods for common workflows
- Undo/redo via operation history
- Status reporting
"""

import json
import os
from pathlib import Path
from typing import Optional

from cli_anything.cloudcompare.core.project import (
    add_cloud,
    add_mesh,
    create_project,
    get_cloud,
    get_mesh,
    load_project,
    project_info,
    record_operation,
    remove_cloud,
    remove_mesh,
    save_project,
)


class Session:
    """Stateful session wrapping a CloudCompare CLI project."""

    def __init__(self, project_path: str):
        """Initialize session with a project file.

        Args:
            project_path: Path to the .json project file.
                          Created if it doesn't exist.
        """
        self.project_path = os.path.abspath(project_path)
        if os.path.exists(self.project_path):
            self.project = load_project(self.project_path)
        else:
            self.project = create_project(self.project_path)
        self._dirty = False

    @property
    def name(self) -> str:
        return self.project.get("name", "unnamed")

    @property
    def cloud_count(self) -> int:
        return len(self.project.get("clouds", []))

    @property
    def mesh_count(self) -> int:
        return len(self.project.get("meshes", []))

    @property
    def is_modified(self) -> bool:
        return self._dirty

    def add_cloud(self, path: str, label: Optional[str] = None) -> dict:
        """Add a cloud to the session."""
        entry = add_cloud(self.project, path, label)
        self._dirty = True
        return entry

    def add_mesh(self, path: str, label: Optional[str] = None) -> dict:
        """Add a mesh to the session."""
        entry = add_mesh(self.project, path, label)
        self._dirty = True
        return entry

    def remove_cloud(self, index: int) -> dict:
        """Remove a cloud by index."""
        entry = remove_cloud(self.project, index)
        self._dirty = True
        return entry

    def remove_mesh(self, index: int) -> dict:
        """Remove a mesh by index."""
        entry = remove_mesh(self.project, index)
        self._dirty = True
        return entry

    def get_cloud(self, index: int) -> dict:
        """Get a cloud entry."""
        return get_cloud(self.project, index)

    def get_mesh(self, index: int) -> dict:
        """Get a mesh entry."""
        return get_mesh(self.project, index)

    def record(self, operation: str, inputs: list, outputs: list, params: dict) -> None:
        """Record an operation in history."""
        record_operation(self.project, operation, inputs, outputs, params)
        self._dirty = True

    def save(self) -> None:
        """Persist the project to disk."""
        save_project(self.project, self.project_path)
        self._dirty = False

    def info(self) -> dict:
        """Return project info dict."""
        return project_info(self.project)

    def history(self, last_n: int = 10) -> list:
        """Return recent operation history.

        Args:
            last_n: How many recent operations to return.
        """
        hist = self.project.get("history", [])
        return hist[-last_n:] if last_n else hist

    def undo_last(self) -> Optional[dict]:
        """Remove the last history entry (soft undo — removes record, not files).

        Returns:
            The removed history entry, or None if history is empty.
        """
        hist = self.project.get("history", [])
        if not hist:
            return None
        removed = hist.pop()
        self._dirty = True
        return removed

    def set_export_format(
        self,
        cloud_fmt: Optional[str] = None,
        cloud_ext: Optional[str] = None,
        mesh_fmt: Optional[str] = None,
        mesh_ext: Optional[str] = None,
    ) -> None:
        """Update export format settings.

        Args:
            cloud_fmt: CloudCompare format string (e.g., 'LAS', 'PLY', 'ASC').
            cloud_ext: File extension (e.g., 'las', 'ply', 'xyz').
            mesh_fmt: Mesh format string.
            mesh_ext: Mesh file extension.
        """
        settings = self.project.setdefault("settings", {})
        if cloud_fmt:
            settings["cloud_export_format"] = cloud_fmt.upper()
        if cloud_ext:
            settings["cloud_export_ext"] = cloud_ext.lower()
        if mesh_fmt:
            settings["mesh_export_format"] = mesh_fmt.upper()
        if mesh_ext:
            settings["mesh_export_ext"] = mesh_ext.lower()
        self._dirty = True

    def get_settings(self) -> dict:
        """Return current session settings."""
        return self.project.get("settings", {})

    def status(self) -> dict:
        """Return a concise status dict."""
        return {
            "project": self.project_path,
            "name": self.name,
            "clouds": self.cloud_count,
            "meshes": self.mesh_count,
            "modified": self._dirty,
            "history_depth": len(self.project.get("history", [])),
        }

    def __repr__(self) -> str:
        return f"Session({self.project_path!r}, clouds={self.cloud_count}, meshes={self.mesh_count})"
