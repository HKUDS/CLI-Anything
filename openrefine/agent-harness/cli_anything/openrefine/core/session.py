from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_SESSION = Path.home() / ".cli-anything-openrefine" / "session.json"


@dataclass
class SessionState:
    base_url: str = "http://127.0.0.1:3333"
    project_id: str | None = None
    project_name: str | None = None
    last_export: str | None = None
    history: list[dict[str, Any]] = field(default_factory=list)
    future: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_url": self.base_url,
            "project_id": self.project_id,
            "project_name": self.project_name,
            "last_export": self.last_export,
            "history": self.history,
            "future": self.future,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionState":
        return cls(
            base_url=str(data.get("base_url") or "http://127.0.0.1:3333"),
            project_id=data.get("project_id"),
            project_name=data.get("project_name"),
            last_export=data.get("last_export"),
            history=list(data.get("history") or []),
            future=list(data.get("future") or []),
        )


class SessionStore:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else DEFAULT_SESSION

    def load(self) -> SessionState:
        if not self.path.exists():
            return SessionState()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Session file is not a JSON object: {self.path}")
        return SessionState.from_dict(data)

    def save(self, state: SessionState) -> Path:
        _locked_save_json(self.path, state.to_dict(), indent=2, sort_keys=True)
        return self.path

    def effective_base_url(self, requested_base_url: str | None = None) -> str:
        if requested_base_url:
            return requested_base_url
        try:
            return self.load().base_url
        except FileNotFoundError:
            return SessionState().base_url

    def record(self, state: SessionState, action: str, payload: dict[str, Any]) -> None:
        state.history.append({"action": action, "payload": payload})
        state.future.clear()

    def undo(self, state: SessionState) -> dict[str, Any]:
        if not state.history:
            raise ValueError("No local session action to undo")
        item = state.history.pop()
        state.future.append(item)
        return item

    def redo(self, state: SessionState) -> dict[str, Any]:
        if not state.future:
            raise ValueError("No local session action to redo")
        item = state.future.pop()
        state.history.append(item)
        return item


def _locked_save_json(path: Path, data: dict[str, Any], **dump_kwargs: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        handle = path.open("r+", encoding="utf-8")
    except FileNotFoundError:
        handle = path.open("w+", encoding="utf-8")
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
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        finally:
            if locked:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
