"""Session management for cli-anything-calibre."""

from __future__ import annotations

import copy
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


def _locked_save_json(path, data, **dump_kwargs) -> None:
    try:
        f = open(path, "r+")
    except FileNotFoundError:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        f = open(path, "w+")
    with f:
        locked = False
        try:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            locked = True
        except (ImportError, OSError):
            pass
        try:
            f.seek(0)
            f.truncate()
            json.dump(data, f, **dump_kwargs)
            f.flush()
        finally:
            if locked:
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)


class Session:
    MAX_UNDO = 50

    def __init__(self, session_path: str | None = None):
        self.library_path: str | None = None
        self.current_book_id: int | None = None
        self._undo_stack: list[dict[str, Any]] = []
        self._redo_stack: list[dict[str, Any]] = []
        self._modified = False
        if session_path is None:
            session_path = str(Path.home() / ".cli-anything-calibre" / "session.json")
        self.session_path = session_path

    def has_library(self) -> bool:
        return self.library_path is not None

    def require_library(self) -> str:
        if not self.library_path:
            raise RuntimeError("No library selected. Use 'library open <path>' first.")
        return self.library_path

    def open_library(self, library_path: str) -> None:
        self.library_path = os.path.abspath(library_path)
        self.current_book_id = None
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._modified = False

    def snapshot(self, description: str = "") -> None:
        state = {
            "library_path": self.library_path,
            "current_book_id": self.current_book_id,
            "description": description,
            "timestamp": datetime.now().isoformat(),
        }
        self._undo_stack.append(copy.deepcopy(state))
        if len(self._undo_stack) > self.MAX_UNDO:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self._modified = True

    def select_book(self, book_id: int | None) -> None:
        self.current_book_id = book_id
        self._modified = True

    def undo(self) -> str:
        if not self._undo_stack:
            raise RuntimeError("Nothing to undo.")
        current = {
            "library_path": self.library_path,
            "current_book_id": self.current_book_id,
            "description": "redo point",
            "timestamp": datetime.now().isoformat(),
        }
        self._redo_stack.append(current)
        state = self._undo_stack.pop()
        self.library_path = state["library_path"]
        self.current_book_id = state["current_book_id"]
        self._modified = True
        return state.get("description", "")

    def redo(self) -> str:
        if not self._redo_stack:
            raise RuntimeError("Nothing to redo.")
        current = {
            "library_path": self.library_path,
            "current_book_id": self.current_book_id,
            "description": "undo point",
            "timestamp": datetime.now().isoformat(),
        }
        self._undo_stack.append(current)
        state = self._redo_stack.pop()
        self.library_path = state["library_path"]
        self.current_book_id = state["current_book_id"]
        self._modified = True
        return state.get("description", "")

    def status(self) -> dict[str, Any]:
        return {
            "has_library": self.library_path is not None,
            "library_path": self.library_path,
            "current_book_id": self.current_book_id,
            "modified": self._modified,
            "undo_count": len(self._undo_stack),
            "redo_count": len(self._redo_stack),
        }

    def list_history(self) -> list[dict[str, Any]]:
        return [
            {
                "index": i,
                "description": state.get("description", ""),
                "timestamp": state.get("timestamp", ""),
            }
            for i, state in enumerate(reversed(self._undo_stack))
        ]

    def save(self) -> str:
        payload = {
            "library_path": self.library_path,
            "current_book_id": self.current_book_id,
            "history": self._undo_stack,
            "history_index": len(self._undo_stack) - 1,
            "saved_at": datetime.now().isoformat(),
        }
        _locked_save_json(self.session_path, payload, indent=2, sort_keys=True)
        self._modified = False
        return self.session_path
