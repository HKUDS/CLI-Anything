"""Database connection and utility functions for CC Switch CLI."""

import os
import sqlite3
import json
from pathlib import Path
from typing import Optional


def get_cc_switch_dir() -> Path:
    """Get the CC Switch config directory."""
    home = Path(os.environ.get("CCSWITCH_HOME", os.path.expanduser("~")))
    return home / ".cc-switch"


def get_db_path() -> Path:
    """Get the SQLite database path."""
    return get_cc_switch_dir() / "cc-switch.db"


def get_config_path() -> Path:
    """Get the main app config JSON path."""
    return get_cc_switch_dir() / "config.json"


def get_settings_path() -> Path:
    """Get the settings JSON path."""
    return get_cc_switch_dir() / "settings.json"


def connect_db(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Connect to the CC Switch SQLite database."""
    path = db_path or get_db_path()
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def load_config(config_path: Optional[Path] = None) -> dict:
    """Load the main CC Switch config.json."""
    path = config_path or get_config_path()
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        content = f.read().strip()
        if not content:
            return {}
        return json.loads(content)


def save_config(data: dict, config_path: Optional[Path] = None) -> None:
    """Save the main CC Switch config.json."""
    path = config_path or get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_settings() -> dict:
    """Load CC Switch settings.json (UI preferences)."""
    path = get_settings_path()
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


VALID_APP_TYPES = ("claude", "codex", "gemini", "opencode", "openclaw", "hermes")
