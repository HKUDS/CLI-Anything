"""Run history and persisted patch/session state."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATE_DIR = Path.home() / ".cli-anything-litellm"
SESSION_FILE = STATE_DIR / "session.json"


@dataclass
class RunEntry:
    command: str
    args: dict[str, Any]
    result: dict[str, Any]
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "args": self.args,
            "result": self.result,
            "timestamp": self.timestamp,
        }


class SessionStore:
    def __init__(self, path: Path | None = None):
        self.path = path or SESSION_FILE
        self.state = {"history": [], "last_patch": None, "last_run": None}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            self.state = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, PermissionError):
            self.state = {"history": [], "last_patch": None, "last_run": None}

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.state, indent=2, sort_keys=True), encoding="utf-8")
        except (OSError, PermissionError):
            pass

    def record(self, command: str, args: dict[str, Any], result: dict[str, Any]) -> None:
        self.state.setdefault("history", []).append(RunEntry(command, args, result).to_dict())
        self.state["last_run"] = result
        self.save()

    def set_last_patch(self, patch_info: dict[str, Any]) -> None:
        self.state["last_patch"] = patch_info
        self.save()

    def history(self, limit: int = 20) -> list[dict[str, Any]]:
        return self.state.get("history", [])[-limit:]

    def status(self) -> dict[str, Any]:
        return {
            "history_count": len(self.state.get("history", [])),
            "has_last_patch": self.state.get("last_patch") is not None,
            "has_last_run": self.state.get("last_run") is not None,
        }

    def clear(self) -> None:
        self.state = {"history": [], "last_patch": None, "last_run": None}
        self.save()


def workspace_session_file(workspace: str | Path) -> Path:
    return Path(workspace).resolve() / ".litellm" / "session.json"
