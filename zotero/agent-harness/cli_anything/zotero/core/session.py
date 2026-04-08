from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


COMMAND_HISTORY_LIMIT = 50
STATE_DIR_ENV = "CLI_ANYTHING_ZOTERO_STATE_DIR"
APP_NAME = "cli-anything-zotero"


def session_state_dir() -> Path:
    override = os.environ.get(STATE_DIR_ENV, "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".config" / APP_NAME


def session_state_path() -> Path:
    return session_state_dir() / "session.json"


def default_session_state() -> dict[str, Any]:
    return {"current_library": None, "current_collection": None, "current_item": None, "command_history": []}


def load_session_state() -> dict[str, Any]:
    path = session_state_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default_session_state()
    history = [item for item in data.get("command_history", []) if isinstance(item, str)]
    return {
        "current_library": data.get("current_library"),
        "current_collection": data.get("current_collection"),
        "current_item": data.get("current_item"),
        "command_history": history[-COMMAND_HISTORY_LIMIT:],
    }


def locked_save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        handle = open(path, "r+", encoding="utf-8")
    except FileNotFoundError:
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
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.flush()
        finally:
            if locked:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def save_session_state(session: dict[str, Any]) -> None:
    locked_save_json(
        session_state_path(),
        {
            "current_library": session.get("current_library"),
            "current_collection": session.get("current_collection"),
            "current_item": session.get("current_item"),
            "command_history": list(session.get("command_history", []))[-COMMAND_HISTORY_LIMIT:],
        },
    )


def append_command_history(command_line: str) -> None:
    command_line = command_line.strip()
    if not command_line:
        return
    session = load_session_state()
    history = list(session.get("command_history", []))
    history.append(command_line)
    session["command_history"] = history[-COMMAND_HISTORY_LIMIT:]
    save_session_state(session)


def build_session_payload(session: dict[str, Any]) -> dict[str, Any]:
    history = list(session.get("command_history", []))
    return {
        "current_library": session.get("current_library"),
        "current_collection": session.get("current_collection"),
        "current_item": session.get("current_item"),
        "state_path": str(session_state_path()),
        "history_count": len(history),
    }


def expand_repl_aliases_with_state(argv: list[str], session: dict[str, Any]) -> list[str]:
    aliases = {"@library": session.get("current_library"), "@collection": session.get("current_collection"), "@item": session.get("current_item")}
    expanded: list[str] = []
    for token in argv:
        if token in aliases and aliases[token]:
            expanded.append(str(aliases[token]))
        else:
            expanded.append(token)
    return expanded
