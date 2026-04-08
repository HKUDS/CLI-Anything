"""
Session management for FreeCAD CLI harness.

Handles project state, undo/redo history, and session persistence
with atomic file locking for safe concurrent access.
"""

from __future__ import annotations

import copy
import json
import os
import time
from typing import Any, Dict, List, Optional


def _locked_save_json(path: str, data: Any, **dump_kwargs: Any) -> None:
    """Persist JSON data to *path* using atomic file locking.

    Opens with ``"r+"`` to avoid truncation before the lock is acquired.
    Falls back to ``"w"`` when the file does not yet exist.  On platforms
    that lack :mod:`fcntl` (Windows) the write proceeds without locking.
    """
    try:
        f = open(path, "r+")
    except FileNotFoundError:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        f = open(path, "w")

    with f:
        _locked = False
        try:
            import fcntl

            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            _locked = True
        except (ImportError, OSError):
            pass
        try:
            f.seek(0)
            f.truncate()
            json.dump(data, f, **dump_kwargs)
            f.flush()
        finally:
            if _locked:
                import fcntl as _fcntl

                _fcntl.flock(f.fileno(), _fcntl.LOCK_UN)


class Session:
    """Manages project state, undo/redo snapshots and persistence for a FreeCAD project."""

    MAX_UNDO: int = 50

    def __init__(self) -> None:
        self.project: Optional[Dict] = None
        self.project_path: Optional[str] = None
        self._undo_stack: List[Dict] = []
        self._redo_stack: List[Dict] = []
        self._modified: bool = False

    # -- project access --------------------------------------------------------

    def get_project(self) -> Dict:
        """Return the current project dict.

        Raises :class:`RuntimeError` if no project is loaded.
        """
        if self.project is None:
            raise RuntimeError("No project is currently loaded.")
        return self.project

    def set_project(self, project: Dict, path: Optional[str] = None) -> None:
        """Replace the current project, clearing all undo/redo history."""
        self.project = project
        if path is not None:
            self.project_path = path
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._modified = False

    # -- snapshot / undo / redo ------------------------------------------------

    def snapshot(self, description: str = "") -> None:
        """Save a deep copy of the current project state before a mutation.

        The redo stack is cleared on every new snapshot.  When the undo
        stack exceeds :attr:`MAX_UNDO`, the oldest entry is discarded
        (FIFO).
        """
        if self.project is None:
            return

        entry: Dict = {
            "timestamp": time.time(),
            "description": description,
            "state": copy.deepcopy(self.project),
        }
        self._undo_stack.append(entry)

        # FIFO limit
        if len(self._undo_stack) > self.MAX_UNDO:
            self._undo_stack.pop(0)

        self._redo_stack.clear()
        self._modified = True

    def undo(self) -> Optional[str]:
        """Restore the previous project state.

        Returns the snapshot description, or ``None`` if there is nothing
        to undo.
        """
        if not self._undo_stack:
            return None

        # Save current state onto redo stack before restoring.
        redo_entry: Dict = {
            "timestamp": time.time(),
            "description": self._undo_stack[-1].get("description", ""),
            "state": copy.deepcopy(self.project),
        }
        self._redo_stack.append(redo_entry)

        entry = self._undo_stack.pop()
        self.project = entry["state"]
        self._modified = True
        return entry.get("description", "")

    def redo(self) -> Optional[str]:
        """Restore the next project state after an undo.

        Returns the snapshot description, or ``None`` if there is nothing
        to redo.
        """
        if not self._redo_stack:
            return None

        # Save current state onto undo stack before restoring.
        undo_entry: Dict = {
            "timestamp": time.time(),
            "description": self._redo_stack[-1].get("description", ""),
            "state": copy.deepcopy(self.project),
        }
        self._undo_stack.append(undo_entry)

        entry = self._redo_stack.pop()
        self.project = entry["state"]
        self._modified = True
        return entry.get("description", "")

    # -- persistence -----------------------------------------------------------

    def save_session(self, path: Optional[str] = None) -> str:
        """Persist the current project to disk using atomic file locking.

        Parameters
        ----------
        path:
            Destination file path.  Falls back to :attr:`project_path`.

        Returns
        -------
        str
            The absolute path the project was saved to.

        Raises
        ------
        ValueError
            If no path is available.
        RuntimeError
            If no project is loaded.
        """
        save_path = path or self.project_path
        if save_path is None:
            raise ValueError("No save path specified and no project_path set.")
        if self.project is None:
            raise RuntimeError("No project is currently loaded.")

        save_path = os.path.abspath(save_path)
        _locked_save_json(save_path, self.project, indent=2, default=str)

        self.project_path = save_path
        self._modified = False
        return save_path

    # -- query helpers ---------------------------------------------------------

    def status(self) -> Dict:
        """Return a summary of the current session state."""
        return {
            "has_project": self.project is not None,
            "project_path": self.project_path,
            "modified": self._modified,
            "undo_depth": len(self._undo_stack),
            "redo_depth": len(self._redo_stack),
        }

    def list_history(self) -> List[Dict]:
        """Return the undo stack in reverse chronological order (newest first)."""
        return [
            {
                "index": i,
                "timestamp": entry["timestamp"],
                "description": entry.get("description", ""),
            }
            for i, entry in reversed(list(enumerate(self._undo_stack)))
        ]
