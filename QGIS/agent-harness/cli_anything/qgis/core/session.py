"""Session state and command history for cli-anything-qgis."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


def _locked_save_json(path: str, data: dict, **dump_kwargs) -> None:
    """Atomically write JSON with exclusive file locking."""
    try:
        handle = open(path, "r+", encoding="utf-8")
    except FileNotFoundError:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        handle = open(path, "w", encoding="utf-8")

    with handle:
        locked = False
        try:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            locked = True
        except (ImportError, OSError):
            pass

        try:
            handle.seek(0)
            handle.truncate()
            json.dump(data, handle, **dump_kwargs)
            handle.flush()
        finally:
            if locked:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@dataclass
class HistoryEntry:
    """A single CLI command execution."""

    command: str
    args: dict
    timestamp: str = ""
    result: dict | None = None

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "command": self.command,
            "args": self.args,
            "timestamp": self.timestamp,
            "result": self.result,
        }

    @classmethod
    def from_dict(cls, value: dict) -> "HistoryEntry":
        return cls(
            command=value["command"],
            args=value.get("args", {}),
            timestamp=value.get("timestamp", ""),
            result=value.get("result"),
        )


class Session:
    """Tracks the current project path and command history."""

    def __init__(self, session_file: str | None = None):
        self.current_project_path = ""
        self._history: list[HistoryEntry] = []
        self._session_file = session_file
        if session_file:
            self._load(session_file)

    @property
    def history_count(self) -> int:
        return len(self._history)

    @property
    def active_project_name(self) -> str:
        if not self.current_project_path:
            return ""
        return Path(self.current_project_path).name

    def set_project_path(self, path: str | None) -> None:
        normalized = str(path or "")
        if normalized == self.current_project_path:
            return
        self.current_project_path = normalized
        self._auto_save()

    def clear_project(self) -> None:
        if not self.current_project_path:
            return
        self.current_project_path = ""
        self._auto_save()

    def record(self, command: str, args: dict, result: dict | None = None) -> None:
        self._history.append(HistoryEntry(command=command, args=args, result=result))
        self._auto_save()

    def history(self, limit: int = 20) -> list[dict]:
        entries = self._history[-limit:] if limit else self._history
        return [entry.to_dict() for entry in entries]

    def status(self, *, modified: bool = False) -> dict:
        return {
            "current_project_path": self.current_project_path or None,
            "project_name": self.active_project_name or None,
            "modified": modified,
            "history_count": self.history_count,
        }

    def save(self, path: str) -> None:
        data = {
            "current_project_path": self.current_project_path,
            "history": [entry.to_dict() for entry in self._history],
        }
        _locked_save_json(path, data, indent=2, sort_keys=True)

    def _auto_save(self) -> None:
        if self._session_file:
            self.save(self._session_file)

    def _load(self, path: str) -> None:
        session_path = Path(path)
        if not session_path.exists():
            return
        try:
            data = json.loads(session_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        self.current_project_path = str(data.get("current_project_path", "") or "")
        self._history = [HistoryEntry.from_dict(entry) for entry in data.get("history", [])]
