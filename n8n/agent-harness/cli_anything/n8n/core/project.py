"""Configuration management — load/save from JSON file + env vars."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


CONFIG_DIR = Path.home() / ".cli-anything" / "n8n"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULTS: dict[str, Any] = {
    "base_url": "",
    "api_key": "",
}


def load_config() -> dict[str, Any]:
    """Load config from file, overlaid with env vars."""
    cfg = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                cfg.update(json.load(f))
        except (json.JSONDecodeError, ValueError):
            pass  # Corrupted config — fall back to defaults + env vars
    if url := os.environ.get("N8N_BASE_URL"):
        cfg["base_url"] = url
    if key := os.environ.get("N8N_API_KEY"):
        cfg["api_key"] = key
    return cfg


def save_config(cfg: dict[str, Any]) -> Path:
    """Persist config to disk with restricted permissions."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(str(CONFIG_DIR), 0o700)
    except OSError:
        pass
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)
    try:
        os.chmod(str(CONFIG_FILE), 0o600)
    except OSError:
        pass
    return CONFIG_FILE


def get_connection(
    base_url: str | None = None,
    api_key: str | None = None,
) -> tuple[str, str]:
    """Resolve base_url and api_key from args > env > config file."""
    cfg = load_config()
    url = base_url or cfg["base_url"]
    if url and not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    key = api_key or cfg["api_key"]
    return url, key
