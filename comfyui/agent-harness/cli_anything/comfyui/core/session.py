"""ComfyUI Session management — state persistence and history."""

import os
import json
import copy
from typing import Dict, List, Optional, Any


class Session:
    """Stateful session for ComfyUI workflow management."""

    def __init__(self, project_path: Optional[str] = None):
        self.project_path = project_path
        self.data: Dict[str, Any] = self._initial_state()
        self.history: List[Dict[str, Any]] = []
        self.redo_stack: List[Dict[str, Any]] = []

        if project_path and os.path.exists(project_path):
            self.load(project_path)

    def _initial_state(self) -> Dict[str, Any]:
        """Create the initial session state."""
        return {
            "workflow": {},
            "variables": {},
            "server": {
                "base_url": "http://localhost:8188"
            }
        }

    def save(self, path: Optional[str] = None) -> str:
        """Save the session state to a JSON file."""
        save_path = path or self.project_path
        if not save_path:
            raise ValueError("No project path provided to save.")

        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

        self.project_path = save_path
        return save_path

    def load(self, path: str):
        """Load session state from a JSON file."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"Project file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

        self.project_path = path
        self.history = []
        self.redo_stack = []

    def commit(self):
        """Save current state to history for undo."""
        self.history.append(copy.deepcopy(self.data))
        if len(self.history) > 50:
            self.history.pop(0)
        self.redo_stack = []

    def undo(self) -> bool:
        """Undo last change."""
        if not self.history:
            return False
        self.redo_stack.append(copy.deepcopy(self.data))
        self.data = self.history.pop()
        return True

    def redo(self) -> bool:
        """Redo last undone change."""
        if not self.redo_stack:
            return False
        self.history.append(copy.deepcopy(self.data))
        self.data = self.redo_stack.pop()
        return True
