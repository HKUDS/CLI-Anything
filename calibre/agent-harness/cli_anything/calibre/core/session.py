"""Session management — persists library path and state between CLI invocations."""

import json
import os
from pathlib import Path
from typing import Any

_SESSION_DIR = Path.home() / ".cli-anything-calibre"
_SESSION_FILE = _SESSION_DIR / "session.json"


def _default_session() -> dict:
    return {
        "library_path": None,
        "last_command": None,
    }


def load_session() -> dict:
    """Load session from disk, creating defaults if missing."""
    _SESSION_DIR.mkdir(parents=True, exist_ok=True)
    if not _SESSION_FILE.exists():
        return _default_session()
    try:
        with open(_SESSION_FILE) as f:
            data = json.load(f)
        # Merge with defaults for forward-compatibility
        session = _default_session()
        session.update(data)
        return session
    except (json.JSONDecodeError, OSError):
        return _default_session()


def save_session(session: dict) -> None:
    """Persist session to disk."""
    _SESSION_DIR.mkdir(parents=True, exist_ok=True)
    with open(_SESSION_FILE, "w") as f:
        json.dump(session, f, indent=2)


def get_library_path(session: dict | None = None) -> str | None:
    """Return the active library path from session or CALIBRE_LIBRARY env var."""
    env_path = os.environ.get("CALIBRE_LIBRARY")
    if env_path:
        return env_path
    if session is None:
        session = load_session()
    return session.get("library_path")


def set_library_path(path: str, session: dict | None = None) -> dict:
    """Set the active library path and save session."""
    if session is None:
        session = load_session()
    resolved = str(Path(path).expanduser().resolve())
    session["library_path"] = resolved
    save_session(session)
    return session


def require_library(session: dict | None = None) -> str:
    """Return library path or raise RuntimeError with helpful message."""
    path = get_library_path(session)
    if not path:
        raise RuntimeError(
            "No Calibre library connected.\n"
            "Set one with: cli-anything-calibre library connect <path>\n"
            "Or set CALIBRE_LIBRARY environment variable."
        )
    if not Path(path).exists():
        raise RuntimeError(
            f"Library path does not exist: {path}\n"
            "Set a valid path with: cli-anything-calibre library connect <path>"
        )
    return path
