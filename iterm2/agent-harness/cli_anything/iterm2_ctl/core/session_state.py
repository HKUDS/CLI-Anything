"""Session state management for cli-anything-iterm2.

Stores the current context (window, tab, session) in a JSON file so
commands remain stateful across CLI invocations.
"""
import fcntl
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional


_DEFAULT_STATE_DIR = Path.home() / ".cli-anything-iterm2"
_DEFAULT_STATE_FILE = _DEFAULT_STATE_DIR / "session.json"


@dataclass
class SessionState:
    """Tracks the current iTerm2 context."""
    window_id: Optional[str] = None
    tab_id: Optional[str] = None
    session_id: Optional[str] = None
    # Metadata
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "SessionState":
        return cls(
            window_id=data.get("window_id"),
            tab_id=data.get("tab_id"),
            session_id=data.get("session_id"),
            notes=data.get("notes", ""),
        )

    def clear(self):
        self.window_id = None
        self.tab_id = None
        self.session_id = None
        self.notes = ""

    def summary(self) -> str:
        parts = []
        if self.window_id:
            parts.append(f"window={self.window_id}")
        if self.tab_id:
            parts.append(f"tab={self.tab_id}")
        if self.session_id:
            parts.append(f"session={self.session_id}")
        return ", ".join(parts) if parts else "no context set"


def default_state_path() -> Path:
    return _DEFAULT_STATE_FILE


def load_state(path: Optional[str] = None) -> SessionState:
    """Load session state from a JSON file.

    Returns an empty SessionState if the file does not exist.
    """
    p = Path(path) if path else _DEFAULT_STATE_FILE
    if not p.exists():
        return SessionState()
    try:
        with open(p, "r") as f:
            data = json.load(f)
        return SessionState.from_dict(data)
    except (json.JSONDecodeError, OSError):
        return SessionState()


def save_state(state: SessionState, path: Optional[str] = None) -> None:
    """Save session state to a JSON file with exclusive file locking."""
    p = Path(path) if path else _DEFAULT_STATE_FILE
    p.parent.mkdir(parents=True, exist_ok=True)

    data = state.to_dict()

    try:
        f = open(str(p), "r+")
    except FileNotFoundError:
        f = open(str(p), "w")

    with f:
        _locked = False
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            _locked = True
        except (ImportError, OSError):
            pass
        try:
            f.seek(0)
            f.truncate()
            json.dump(data, f, indent=2)
            f.flush()
        finally:
            if _locked:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def clear_state(path: Optional[str] = None) -> None:
    """Clear all session state."""
    save_state(SessionState(), path)
