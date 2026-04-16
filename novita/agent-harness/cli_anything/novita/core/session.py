"""Lightweight session for chat history management."""

from __future__ import annotations

import json
import os
from datetime import datetime
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


class ChatSession:
    """Lightweight session for chat history management."""

    def __init__(self, session_file: str = None):
        self.session_file = session_file or str(
            Path.home() / ".cli-anything-novita" / "session.json"
        )
        self.messages = []
        self.history = []
        self.max_history = 50
        self.modified = False
        if os.path.exists(self.session_file):
            try:
                with open(self.session_file, "r") as f:
                    data = json.load(f)
                    self.messages = data.get("messages", [])
                    self.history = data.get("history", [])
            except (json.JSONDecodeError, IOError):
                self.messages = []

    def add_user_message(self, content: str):
        self.messages.append({"role": "user", "content": content})
        self.modified = True
        self._save()

    def add_assistant_message(self, content: str):
        self.messages.append({"role": "assistant", "content": content})
        self.modified = True
        self._save()

    def get_messages(self):
        return self.messages.copy()

    def clear(self):
        self.messages = []
        self.history = []
        self.modified = True
        self._save()

    def status(self):
        return {
            "message_count": len(self.messages),
            "history_count": len(self.history),
            "modified": self.modified,
            "session_file": self.session_file,
        }

    def _save(self):
        _locked_save_json(
            self.session_file,
            {"messages": self.messages, "history": self.history},
            indent=2,
        )
        self.modified = False

    def save_history(self, command: str, result: dict):
        self.history.append(
            {"command": command, "result": result, "timestamp": str(datetime.now())}
        )
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history :]
        self._save()
