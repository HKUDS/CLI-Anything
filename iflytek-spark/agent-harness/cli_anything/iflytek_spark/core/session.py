"""Lightweight session for multi-turn chat history."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path


def _locked_save_json(path, data, **dump_kwargs) -> None:
    """Write JSON with an exclusive file lock where the platform supports it."""
    try:
        f = open(path, "r+", encoding="utf-8")
    except FileNotFoundError:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        f = open(path, "w", encoding="utf-8")
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
    """Keeps the conversation so ``chat`` can continue across invocations.

    Only final answers are stored; reasoning is dropped from the history, as
    the Spark-X2.5 chat template expects for earlier turns.
    """

    def __init__(self, session_file: str):
        self.session_file = session_file
        self.messages: list[dict] = []
        self.history: list[dict] = []
        self.max_history = 50
        if os.path.exists(self.session_file):
            try:
                with open(self.session_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.messages = data.get("messages", [])
                self.history = data.get("history", [])
            except (json.JSONDecodeError, IOError):
                self.messages = []
                self.history = []

    def add_exchange(self, prompt: str, answer: str, model: str = ""):
        self.messages.append({"role": "user", "content": prompt})
        self.messages.append({"role": "assistant", "content": answer})
        self.history.append(
            {"prompt": prompt, "model": model, "timestamp": datetime.now().isoformat(timespec="seconds")}
        )
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
        self._save()

    def get_messages(self) -> list[dict]:
        return list(self.messages)

    def clear(self):
        self.messages = []
        self.history = []
        self._save()

    def status(self) -> dict:
        return {
            "message_count": len(self.messages),
            "turns": len(self.messages) // 2,
            "session_file": self.session_file,
        }

    def _save(self):
        _locked_save_json(
            self.session_file,
            {"messages": self.messages, "history": self.history},
            indent=2,
            ensure_ascii=False,
        )
