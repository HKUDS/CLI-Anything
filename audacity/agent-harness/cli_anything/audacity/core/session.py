"""Audacity CLI - Session management with undo/redo.

Same pattern as GIMP/Blender CLIs: maintains project state with a
snapshot-based undo/redo stack using deep copy.
"""

import json
import os
import copy
from typing import Dict, Any, Optional, List
from datetime import datetime
from cli_anything.utils.io import locked_save_json


class Session:
    """Manages project state with undo/redo history."""

    MAX_UNDO = 50

    def __init__(self):
        self.project: Optional[Dict[str, Any]] = None
        self.project_path: Optional[str] = None
        self._undo_stack: List[Dict[str, Any]] = []
        self._redo_stack: List[Dict[str, Any]] = []
        self._modified: bool = False

    def has_project(self) -> bool:
        return self.project is not None

    def get_project(self) -> Dict[str, Any]:
        if self.project is None:
            raise RuntimeError(
                "No project loaded. Use 'project new' or 'project open' first."
            )
        return self.project

    def set_project(self, project: Dict[str, Any], path: Optional[str] = None) -> None:
        self.project = project
        self.project_path = path
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._modified = False

    def snapshot(self, description: str = "") -> None:
        """Save current state to undo stack before a mutation."""
        if self.project is None:
            return
        state = {
            "project": copy.deepcopy(self.project),
            "description": description,
            "timestamp": datetime.now().isoformat(),
        }
        self._undo_stack.append(state)
        if len(self._undo_stack) > self.MAX_UNDO:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self._modified = True

    def undo(self) -> Optional[str]:
        """Undo the last operation. Returns description of undone action."""
        if not self._undo_stack:
            raise RuntimeError("Nothing to undo.")
        if self.project is None:
            raise RuntimeError("No project loaded.")

        # Save current state to redo stack
        self._redo_stack.append({
            "project": copy.deepcopy(self.project),
            "description": "redo point",
            "timestamp": datetime.now().isoformat(),
        })

        # Restore previous state
        state = self._undo_stack.pop()
        self.project = state["project"]
        self._modified = True
        return state.get("description", "")

    def redo(self) -> Optional[str]:
        """Redo the last undone operation."""
        if not self._redo_stack:
            raise RuntimeError("Nothing to redo.")
        if self.project is None:
            raise RuntimeError("No project loaded.")

        # Save current state to undo stack
        self._undo_stack.append({
            "project": copy.deepcopy(self.project),
            "description": "undo point",
            "timestamp": datetime.now().isoformat(),
        })

        # Restore redo state
        state = self._redo_stack.pop()
        self.project = state["project"]
        self._modified = True
        return state.get("description", "")

    def status(self) -> Dict[str, Any]:
        """Get session status."""
        return {
            "has_project": self.project is not None,
            "project_path": self.project_path,
            "modified": self._modified,
            "undo_count": len(self._undo_stack),
            "redo_count": len(self._redo_stack),
            "project_name": (
                self.project.get("name", "untitled") if self.project else None
            ),
        }

    def save_session(self, path: Optional[str] = None) -> str:
        """Save the session state to disk."""
        if self.project is None:
            raise RuntimeError("No project to save.")

        save_path = path or self.project_path
        if not save_path:
            raise ValueError("No save path specified.")

        # Save project
        self.project["metadata"]["modified"] = datetime.now().isoformat()
        os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
        locked_save_json(save_path, self.project, indent=2, default=str)

        self.project_path = save_path
        self._modified = False
        return save_path

    def list_history(self) -> List[Dict[str, str]]:
        """List undo history."""
        result = []
        for i, state in enumerate(reversed(self._undo_stack)):
            result.append({
                "index": i,
                "description": state.get("description", ""),
                "timestamp": state.get("timestamp", ""),
            })
        return result
