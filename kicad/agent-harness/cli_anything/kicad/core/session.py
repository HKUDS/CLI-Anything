"""Session management with undo/redo."""

import json, os, copy
from typing import Dict, Any, Optional, List
from datetime import datetime


def _locked_save_json(path, data, **dump_kwargs):
    try:
        f = open(path, "r+")
    except FileNotFoundError:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        f = open(path, "w")
    with f:
        try:
            import fcntl

            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        except:
            pass
        try:
            f.seek(0)
            f.truncate()
            json.dump(data, f, **dump_kwargs)
            f.flush()
        finally:
            try:
                import fcntl

                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            except:
                pass


class Session:
    MAX_UNDO = 50

    def __init__(self):
        self.project = None
        self.project_path = None
        self._undo_stack = []
        self._redo_stack = []
        self._modified = False

    def has_project(self):
        return self.project is not None

    def get_project(self):
        if self.project is None:
            raise RuntimeError("No project loaded.")
        return self.project

    def set_project(self, project, path=None):
        self.project = project
        self.project_path = path
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._modified = False

    def snapshot(self, description=""):
        if self.project is None:
            return
        self._undo_stack.append(
            {
                "project": copy.deepcopy(self.project),
                "description": description,
                "timestamp": datetime.now().isoformat(),
            }
        )
        if len(self._undo_stack) > self.MAX_UNDO:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self._modified = True

    def undo(self):
        if not self._undo_stack:
            raise RuntimeError("Nothing to undo.")
        self._redo_stack.append(
            {
                "project": copy.deepcopy(self.project),
                "description": "redo",
                "timestamp": datetime.now().isoformat(),
            }
        )
        state = self._undo_stack.pop()
        self.project = state["project"]
        self._modified = True
        return state.get("description", "")

    def redo(self):
        if not self._redo_stack:
            raise RuntimeError("Nothing to redo.")
        self._undo_stack.append(
            {
                "project": copy.deepcopy(self.project),
                "description": "undo",
                "timestamp": datetime.now().isoformat(),
            }
        )
        state = self._redo_stack.pop()
        self.project = state["project"]
        self._modified = True
        return state.get("description", "")

    def status(self):
        return {
            "has_project": self.project is not None,
            "project_path": self.project_path,
            "modified": self._modified,
            "undo_count": len(self._undo_stack),
            "redo_count": len(self._redo_stack),
            "project_name": self.project.get("name", "untitled")
            if self.project
            else None,
        }

    def save_session(self, path=None):
        if self.project is None:
            raise RuntimeError("No project to save.")
        save_path = path or self.project_path
        if not save_path:
            raise ValueError("No save path specified.")
        self.project["metadata"]["modified"] = datetime.now().isoformat()
        _locked_save_json(
            save_path, self.project, indent=2, sort_keys=True, default=str
        )
        self.project_path = save_path
        self._modified = False
        return save_path

    def list_history(self):
        return [
            {
                "index": i,
                "description": s.get("description", ""),
                "timestamp": s.get("timestamp", ""),
            }
            for i, s in enumerate(reversed(self._undo_stack))
        ]
