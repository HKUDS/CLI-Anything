"""Lightweight session for multi-turn chat history."""

from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime


@contextmanager
def _locked_session_file(path):
    """Keep reads and read-modify-write transactions under the same lock."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    path = path + ".lock"
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    f = os.fdopen(fd, "r+", encoding="utf-8")
    with f:
        # The lock inode stays stable when the session data is replaced.
        if hasattr(os, "fchmod"):
            os.fchmod(f.fileno(), 0o600)
        else:
            os.chmod(path, 0o600)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            f.flush()
            f.seek(0)
            if os.name == "nt":
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
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
            self._refresh()

    def _load(self):
        try:
            os.chmod(self.session_file, 0o600)
            with open(self.session_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}
        self.messages = data.get("messages", [])
        self.history = data.get("history", [])

    def _refresh(self):
        with _locked_session_file(self.session_file):
            self._load()

    def add_exchange(self, prompt: str, answer: str, model: str = ""):
        with _locked_session_file(self.session_file):
            self._load()
            self.messages.append({"role": "user", "content": prompt})
            self.messages.append({"role": "assistant", "content": answer})
            self.history.append(
                {"prompt": prompt, "model": model, "timestamp": datetime.now().isoformat(timespec="seconds")}
            )
            if len(self.history) > self.max_history:
                self.history = self.history[-self.max_history:]
            self._save()

    def get_messages(self) -> list[dict]:
        self._refresh()
        return list(self.messages)

    def clear(self):
        with _locked_session_file(self.session_file):
            self.messages = []
            self.history = []
            self._save()

    def status(self) -> dict:
        self._refresh()
        return {
            "message_count": len(self.messages),
            "turns": len(self.messages) // 2,
            "session_file": self.session_file,
        }

    def _save(self):
        directory = os.path.dirname(os.path.abspath(self.session_file))
        fd, temporary = tempfile.mkstemp(prefix=".session-", suffix=".json", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(
                    {"messages": self.messages, "history": self.history},
                    f,
                    indent=2,
                    ensure_ascii=False,
                )
            os.replace(temporary, self.session_file)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
