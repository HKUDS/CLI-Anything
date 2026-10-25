"""Workspace ("project") files: which voxtype config is managed, per-run
transcription overrides, the config mutation history and transcription log."""

import json
import os
import time
from typing import Optional

WORKSPACE_FORMAT = "cli-anything-voxtype/workspace-v1"

# Global voxtype flags a workspace may pin for every transcription.
# key -> (cli flag, takes_value)
OVERRIDE_FLAGS = {
    "model": ("--model", True),
    "engine": ("--engine", True),
    "language": ("--language", True),
    "translate": ("--translate", False),
    "threads": ("--threads", True),
    "initial_prompt": ("--initial-prompt", True),
    "vad": ("--vad", False),
    "vad_threshold": ("--vad-threshold", True),
    "vad_backend": ("--vad-backend", True),
    "spoken_punctuation": ("--spoken-punctuation", False),
    "filter_fillers": ("--filter-fillers", False),
    "flash_attention": ("--flash-attention", False),
}


def create_workspace(name: str = "voxtype-workspace", config_path: Optional[str] = None) -> dict:
    return {
        "format": WORKSPACE_FORMAT,
        "name": name,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "config_path": os.path.abspath(config_path) if config_path else None,
        "overrides": {},
        "history": [],
        "redo": [],
        "transcriptions": [],
    }


def validate_workspace(ws: dict) -> dict:
    if not isinstance(ws, dict) or ws.get("format") != WORKSPACE_FORMAT:
        raise ValueError(f"Not a voxtype workspace file (expected format {WORKSPACE_FORMAT!r})")
    for key, default in (("overrides", {}), ("history", []), ("redo", []), ("transcriptions", [])):
        ws.setdefault(key, type(default)())
    ws.setdefault("config_path", None)
    return ws


def load_workspace(path: str) -> dict:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Workspace not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Workspace is not valid JSON: {path} ({e})") from e
    return validate_workspace(data)


def set_override(ws: dict, key: str, value) -> dict:
    if key not in OVERRIDE_FLAGS:
        raise ValueError(f"Unknown override '{key}'. Valid: {', '.join(sorted(OVERRIDE_FLAGS))}")
    _, takes_value = OVERRIDE_FLAGS[key]
    if takes_value:
        if value is None or str(value) == "":
            raise ValueError(f"Override '{key}' needs a value")
        ws["overrides"][key] = str(value)
    else:
        ws["overrides"][key] = _parse_bool(value)
    return ws["overrides"]


def remove_override(ws: dict, key: str) -> dict:
    ws["overrides"].pop(key, None)
    return ws["overrides"]


def override_flags(overrides: dict) -> list[str]:
    """Translate a workspace's overrides into voxtype global CLI flags."""
    flags: list[str] = []
    for key in sorted(overrides):
        if key not in OVERRIDE_FLAGS:
            continue
        flag, takes_value = OVERRIDE_FLAGS[key]
        value = overrides[key]
        if takes_value:
            flags += [flag, str(value)]
        elif value:
            flags.append(flag)
    return flags


def workspace_info(ws: dict, path: Optional[str] = None) -> dict:
    return {
        "name": ws.get("name"),
        "path": os.path.abspath(path) if path else None,
        "config_path": ws.get("config_path"),
        "overrides": dict(ws.get("overrides", {})),
        "history_depth": len(ws.get("history", [])),
        "redo_depth": len(ws.get("redo", [])),
        "transcriptions": len(ws.get("transcriptions", [])),
    }


def _parse_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return True
    s = str(value).strip().lower()
    if s in ("1", "true", "yes", "on", ""):
        return True
    if s in ("0", "false", "no", "off"):
        return False
    raise ValueError(f"Expected a boolean, got {value!r}")
