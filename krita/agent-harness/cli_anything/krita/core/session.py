"""
Session management for Krita CLI harness.

Handles undo/redo history and session state persistence with
atomic file locking for safe concurrent access.
"""

import copy
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple


def _locked_save_json(path: str, data: Any, **dump_kwargs: Any) -> None:
    """Persist JSON data to *path* using atomic file locking."""
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
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)


class Session:
    """Manages undo/redo snapshots and session persistence for a Krita project."""

    def __init__(self, session_path: Optional[str] = None) -> None:
        self._snapshots: List[Tuple[float, str, Dict]] = []
        self._current: int = -1
        self._session_path: Optional[str] = session_path

        if session_path and os.path.isfile(session_path):
            self.load(session_path)

    # -- snapshot / undo / redo -----------------------------------------------

    def snapshot(self, project: Dict, label: str = "") -> None:
        """Save a deep-copied snapshot of *project* for later undo.

        If the current position is not at the end of the history (i.e. the
        user has undone some steps), all redo states beyond the current
        position are discarded before the new snapshot is appended.
        """
        # Discard any redo states beyond the current position.
        if self._current < len(self._snapshots) - 1:
            self._snapshots = self._snapshots[: self._current + 1]

        entry = (time.time(), label, copy.deepcopy(project))
        self._snapshots.append(entry)
        self._current = len(self._snapshots) - 1

    def undo(self) -> Optional[Dict]:
        """Move one step back in history and return the restored project state.

        Returns ``None`` if there is nothing to undo.
        """
        if not self.can_undo():
            return None
        self._current -= 1
        return copy.deepcopy(self._snapshots[self._current][2])

    def redo(self) -> Optional[Dict]:
        """Move one step forward in history and return the restored project state.

        Returns ``None`` if there is nothing to redo.
        """
        if not self.can_redo():
            return None
        self._current += 1
        return copy.deepcopy(self._snapshots[self._current][2])

    # -- query helpers --------------------------------------------------------

    def can_undo(self) -> bool:
        return self._current > 0

    def can_redo(self) -> bool:
        return self._current < len(self._snapshots) - 1

    def current_index(self) -> int:
        """Return the current position in the snapshot history."""
        return self._current

    def history(self) -> List[Dict[str, Any]]:
        """Return a list of snapshot metadata (timestamp + label)."""
        return [
            {"index": i, "timestamp": ts, "label": lbl}
            for i, (ts, lbl, _state) in enumerate(self._snapshots)
        ]

    # -- persistence ----------------------------------------------------------

    def save(self, path: Optional[str] = None) -> None:
        """Persist the full session (snapshots + current index) to disk."""
        path = path or self._session_path
        if path is None:
            raise ValueError("No session path specified.")

        data = {
            "current": self._current,
            "snapshots": [
                {"timestamp": ts, "label": lbl, "state": state}
                for ts, lbl, state in self._snapshots
            ],
        }
        _locked_save_json(path, data, indent=2, default=str)
        self._session_path = path

    def load(self, path: str) -> None:
        """Load session state from a JSON file on disk."""
        with open(path, "r") as f:
            data = json.load(f)

        self._snapshots = [
            (s["timestamp"], s["label"], s["state"])
            for s in data.get("snapshots", [])
        ]
        self._current = data.get("current", len(self._snapshots) - 1)
        self._session_path = path

    def clear(self) -> None:
        """Discard all snapshots and reset the session."""
        self._snapshots = []
        self._current = -1
