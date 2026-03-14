"""Session management — undo/redo and command history for AnyGen CLI."""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class HistoryEntry:
    command: str
    args: dict
    timestamp: str = ""
    result: dict | None = None

    def __post_init__(self):
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
    def from_dict(cls, d: dict) -> "HistoryEntry":
        return cls(
            command=d["command"],
            args=d.get("args", {}),
            timestamp=d.get("timestamp", ""),
            result=d.get("result"),
        )


class Session:
    """Manages command history and undo/redo for the AnyGen CLI REPL."""

    def __init__(self, session_file: str | None = None):
        self._history: list[HistoryEntry] = []
        self._redo_stack: list[HistoryEntry] = []
        self._session_file = session_file

        if session_file:
            self._load(session_file)

    def record(self, command: str, args: dict, result: dict | None = None):
        entry = HistoryEntry(command=command, args=args, result=result)
        self._history.append(entry)
        self._redo_stack.clear()
        self._auto_save()

    def undo(self) -> HistoryEntry | None:
        if not self._history:
            return None
        entry = self._history.pop()
        self._redo_stack.append(entry)
        self._auto_save()
        return entry

    def redo(self) -> HistoryEntry | None:
        if not self._redo_stack:
            return None
        entry = self._redo_stack.pop()
        self._history.append(entry)
        self._auto_save()
        return entry

    def history(self, limit: int = 20) -> list[dict]:
        entries = self._history[-limit:] if limit else self._history
        return [e.to_dict() for e in entries]

    @property
    def history_count(self) -> int:
        return len(self._history)

    @property
    def can_undo(self) -> bool:
        return len(self._history) > 0

    @property
    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    def status(self) -> dict:
        return {
            "history_count": self.history_count,
            "can_undo": self.can_undo,
            "can_redo": self.can_redo,
            "redo_count": len(self._redo_stack),
        }

    def _auto_save(self):
        if self._session_file:
            self.save(self._session_file)

    def save(self, path: str):
        data = {
            "history": [e.to_dict() for e in self._history],
            "redo_stack": [e.to_dict() for e in self._redo_stack],
        }
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        try:
            f = open(path, "r+")
        except FileNotFoundError:
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
                json.dump(data, f, indent=2, default=str)
            finally:
                if _locked:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def _load(self, path: str):
        p = Path(path)
        if not p.exists():
            return
        try:
            with open(p) as f:
                data = json.load(f)
            self._history = [HistoryEntry.from_dict(e) for e in data.get("history", [])]
            self._redo_stack = [HistoryEntry.from_dict(e) for e in data.get("redo_stack", [])]
        except (json.JSONDecodeError, IOError, KeyError):
            pass
