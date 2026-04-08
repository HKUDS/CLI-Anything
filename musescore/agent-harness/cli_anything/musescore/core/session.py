"""Session management with undo/redo and JSON persistence.

Maintains in-memory state for the currently open project, with
undo/redo stacks and safe file locking for concurrent access.
"""

import copy
import json
import os

try:
    import fcntl
except ImportError:
    fcntl = None  # Windows — file locking unavailable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Session:
    """Stateful session for the MuseScore CLI."""

    project_path: str | None = None
    project_data: dict | None = None
    modified: bool = False
    undo_stack: list[dict] = field(default_factory=list)
    redo_stack: list[dict] = field(default_factory=list)
    history: list[str] = field(default_factory=list)

    def has_project(self) -> bool:
        return self.project_data is not None

    def get_project(self) -> dict:
        if self.project_data is None:
            raise RuntimeError("No project is open. Use 'project open' first.")
        return self.project_data

    def set_project(self, data: dict, path: str | None = None):
        self.project_data = data
        self.project_path = path
        self.modified = False
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.history.clear()

    def is_modified(self) -> bool:
        return self.modified

    def snapshot(self, description: str):
        """Save current state to undo stack before a modification."""
        if self.project_data is not None:
            self.undo_stack.append({
                "description": description,
                "data": copy.deepcopy(self.project_data),
                "path": self.project_path,
            })
            self.redo_stack.clear()
            self.history.append(description)
            self.modified = True

    def undo(self) -> str:
        """Undo the last operation."""
        if not self.undo_stack:
            raise RuntimeError("Nothing to undo.")
        entry = self.undo_stack.pop()
        self.redo_stack.append({
            "description": entry["description"],
            "data": copy.deepcopy(self.project_data),
            "path": self.project_path,
        })
        self.project_data = entry["data"]
        self.project_path = entry.get("path", self.project_path)
        self.modified = True
        return entry["description"]

    def redo(self) -> str:
        """Redo the last undone operation."""
        if not self.redo_stack:
            raise RuntimeError("Nothing to redo.")
        entry = self.redo_stack.pop()
        self.undo_stack.append({
            "description": entry["description"],
            "data": copy.deepcopy(self.project_data),
            "path": self.project_path,
        })
        self.project_data = entry["data"]
        self.project_path = entry.get("path", self.project_path)
        self.modified = True
        return entry["description"]

    def list_history(self) -> list[str]:
        return list(self.history)

    def status(self) -> dict:
        return {
            "project_path": self.project_path or "(none)",
            "modified": self.modified,
            "undo_depth": len(self.undo_stack),
            "redo_depth": len(self.redo_stack),
            "history_length": len(self.history),
        }

    def save_session(self, path: str | None = None) -> str:
        """Save session state to a JSON file with file locking."""
        save_path = path or self.project_path
        if not save_path:
            raise RuntimeError("No save path specified.")

        session_file = str(save_path) + ".session.json"
        data = {
            "project_path": self.project_path,
            "modified": self.modified,
            "history": self.history,
        }
        _locked_save_json(session_file, data)
        return session_file


def _locked_save_json(path: str, data: Any):
    """Save JSON data with file locking where available.

    Uses fcntl.flock on Unix (r+ mode to avoid truncation before lock).
    Falls back to plain write on Windows where fcntl is unavailable.
    """
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    if fcntl is not None:
        # Unix: lock-safe write
        if not os.path.exists(path):
            with open(path, "w") as f:
                f.write("{}")
        with open(path, "r+") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.seek(0)
                f.truncate()
                json.dump(data, f, indent=2, default=str)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    else:
        # Windows: plain write (session state is not concurrent-critical)
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)


# ── Singleton ─────────────────────────────────────────────────────────

_session: Session | None = None


def get_session() -> Session:
    """Get or create the global session singleton."""
    global _session
    if _session is None:
        _session = Session()
    return _session
