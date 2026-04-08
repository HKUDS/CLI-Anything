"""Project management for the CloudAnalyzer CLI harness.

A project tracks loaded point clouds, trajectories, QA results,
and operation history.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


def _default_project(name: str = "untitled") -> dict:
    """Return a fresh project structure."""
    return {
        "version": "1.0",
        "name": name,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "modified_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "clouds": [],
        "trajectories": [],
        "results": [],
        "history": [],
        "settings": {
            "default_voxel_size": 0.05,
        },
    }


def create_project(path: str, name: str = "untitled") -> dict:
    """Create a new project file."""
    project = _default_project(name)
    _save(path, project)
    return project


def load_project(path: str) -> dict:
    """Load a project from disk."""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Project file not found: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_project(path: str, project: dict) -> None:
    """Save the project to disk."""
    project["modified_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    _save(path, project)


def record_operation(project: dict, operation: str, details: dict[str, Any] | None = None) -> None:
    """Append an operation to the project history."""
    project["history"].append({
        "operation": operation,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "details": details or {},
    })


def add_result(project: dict, result_type: str, data: dict) -> None:
    """Store a QA result in the project."""
    project["results"].append({
        "type": result_type,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "data": data,
    })


def project_info(project: dict) -> dict:
    """Return a summary of the project state."""
    return {
        "name": project.get("name", "untitled"),
        "clouds": len(project.get("clouds", [])),
        "trajectories": len(project.get("trajectories", [])),
        "results": len(project.get("results", [])),
        "operations": len(project.get("history", [])),
        "created_at": project.get("created_at"),
        "modified_at": project.get("modified_at"),
    }


def _save(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
