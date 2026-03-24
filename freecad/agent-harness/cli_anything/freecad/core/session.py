"""FreeCAD Session management.

Manages the state of the current FreeCAD project as a JSON object,
which can be used to generate FreeCAD Python scripts.
"""

import os
import json
import copy
from typing import Dict, List, Optional, Any


class Session:
    """Stateful session for a FreeCAD project."""

    def __init__(self, project_path: Optional[str] = None):
        self.project_path = project_path
        self.data: Dict[str, Any] = self._initial_state()
        self.history: List[Dict[str, Any]] = []
        self.redo_stack: List[Dict[str, Any]] = []

        if project_path and os.path.exists(project_path):
            self.load(project_path)

    def _initial_state(self) -> Dict[str, Any]:
        """Create the initial project state."""
        return {
            "name": "Untitled",
            "units": "mm",
            "objects": [],  # List of objects: sketches, bodies, parts
            "metadata": {
                "created_by": "cli-anything-freecad",
                "version": "1.0"
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
        """Save the current state to history for undo."""
        self.history.append(copy.deepcopy(self.data))
        # Limit history size
        if len(self.history) > 50:
            self.history.pop(0)
        self.redo_stack = []

    def undo(self) -> bool:
        """Undo the last change."""
        if not self.history:
            return False
        
        self.redo_stack.append(copy.deepcopy(self.data))
        self.data = self.history.pop()
        return True

    def redo(self) -> bool:
        """Redo the last undone change."""
        if not self.redo_stack:
            return False
        
        self.history.append(copy.deepcopy(self.data))
        self.data = self.redo_stack.pop()
        return True

    def add_object(self, obj_type: str, params: Dict[str, Any]) -> str:
        """Add a new object to the project."""
        self.commit()
        
        obj_id = f"{obj_type}_{len(self.data['objects'])}"
        obj = {
            "id": obj_id,
            "type": obj_type,
            "params": params
        }
        self.data["objects"].append(obj)
        return obj_id

    def get_objects(self, type_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get objects in the project, optionally filtered by type."""
        if type_filter:
            return [obj for obj in self.data["objects"] if obj["type"] == type_filter]
        return self.data["objects"]
