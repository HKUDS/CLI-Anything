"""Session state and undo/redo for EEZ Studio project editing."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from . import project as project_mod


SESSION_DIR = Path.home() / ".eez-studio-cli" / "sessions"
MAX_UNDO_DEPTH = 50


class Session:
    def __init__(self, session_id: str | None = None):
        self.session_id = session_id or f"session_{int(time.time())}"
        self.project_path: str | None = None
        self.project: dict[str, Any] | None = None
        self._undo_stack: list[dict[str, Any]] = []
        self._redo_stack: list[dict[str, Any]] = []
        self._modified = False

    @property
    def is_open(self) -> bool:
        return self.project is not None

    @property
    def is_modified(self) -> bool:
        return self._modified

    @property
    def name(self) -> str:
        if not self.project:
            return ""
        return project_mod.get_general(self.project).get("projectName") or ""

    def set_project(self, project: dict[str, Any], path: str | None = None) -> None:
        self.project = project
        self.project_path = os.path.abspath(path) if path else None
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._modified = False

    def open_project(self, path: str) -> None:
        self.set_project(project_mod.load_project(path), path)

    def save_project(self, path: str | None = None) -> dict[str, Any]:
        if self.project is None:
            raise RuntimeError("no project is open")
        target = path or self.project_path
        if not target:
            raise RuntimeError("no save path specified")
        result = project_mod.save_project(self.project, target)
        self.project_path = result["path"]
        self._modified = False
        return result

    def checkpoint(self) -> None:
        if self.project is None:
            raise RuntimeError("no project is open")
        self._undo_stack.append(project_mod.clone_project(self.project))
        if len(self._undo_stack) > MAX_UNDO_DEPTH:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self._modified = True

    def undo(self) -> bool:
        if self.project is None or not self._undo_stack:
            return False
        self._redo_stack.append(project_mod.clone_project(self.project))
        self.project = self._undo_stack.pop()
        self._modified = True
        return True

    def redo(self) -> bool:
        if self.project is None or not self._redo_stack:
            return False
        self._undo_stack.append(project_mod.clone_project(self.project))
        self.project = self._redo_stack.pop()
        self._modified = True
        return True

    def status(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "session_id": self.session_id,
            "project_open": self.is_open,
            "project_path": self.project_path,
            "modified": self._modified,
            "undo_available": len(self._undo_stack),
            "redo_available": len(self._redo_stack),
        }
        if self.project is not None:
            result.update(project_mod.project_info(self.project))
        return result

    def save_state(self) -> str:
        SESSION_DIR.mkdir(parents=True, exist_ok=True)
        state = self.status()
        state["timestamp"] = time.time()
        path = SESSION_DIR / f"{self.session_id}.json"
        project_mod._locked_save_json(path, state, indent=2, sort_keys=True)
        return str(path)

    @classmethod
    def list_states(cls) -> list[dict[str, Any]]:
        SESSION_DIR.mkdir(parents=True, exist_ok=True)
        states: list[dict[str, Any]] = []
        for path in SESSION_DIR.glob("*.json"):
            try:
                states.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
        states.sort(key=lambda item: item.get("timestamp", 0), reverse=True)
        return states
