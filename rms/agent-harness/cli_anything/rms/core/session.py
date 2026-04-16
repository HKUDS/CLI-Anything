"""Session state for RMS CLI."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def _locked_save_json(path, data, **dump_kwargs) -> None:
    """Atomically write JSON with exclusive file locking."""
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
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)


class Session:
    """RMS CLI session state."""

    def __init__(self, session_file: str = None):
        self.session_file = session_file or str(
            Path.home() / ".cli-anything-rms" / "session.json"
        )
        self.last_device_id = None
        self.history = []
        self.preferences = {}
        self.max_history = 50
        if os.path.exists(self.session_file):
            try:
                with open(self.session_file, "r") as f:
                    data = json.load(f)
                    self.last_device_id = data.get("last_device_id")
                    self.history = data.get("history", [])
                    self.preferences = data.get("preferences", {})
            except (json.JSONDecodeError, IOError):
                pass

    def set_last_device(self, device_id: str):
        self.last_device_id = device_id
        self._save()

    def save_history(self, command: str, result: dict):
        self.history.append({
            "command": command,
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
        self._save()

    def clear(self):
        self.last_device_id = None
        self.history = []
        self.preferences = {}
        self._save()

    def status(self):
        return {
            "last_device_id": self.last_device_id,
            "history_count": len(self.history),
            "preferences": self.preferences,
            "session_file": self.session_file,
        }

    def _save(self):
        _locked_save_json(
            self.session_file,
            {
                "last_device_id": self.last_device_id,
                "history": self.history,
                "preferences": self.preferences,
            },
            indent=2,
        )
