"""Config domain: every read and write goes through `voxtype config ...`, so the
real validator (types, ranges, compiled-feature gates) and comment-preserving
editor are always used. This module adds undo bookkeeping and dry-run."""

import os
import shutil
import tempfile
import time
from typing import Optional

from cli_anything.voxtype.utils import voxtype_backend as backend


def value_to_cli(value) -> str:
    """Render a JSON value the way `voxtype config set` expects it."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return repr(round(value, 6))
    if value is None:
        raise ValueError("None cannot be set; use unset")
    return str(value)


def get_all(config_path: Optional[str] = None) -> dict:
    """Every allowlisted key with its effective value."""
    return backend.run_json(["config", "get", "--json"], config_path)


def get_key(key: str, config_path: Optional[str] = None) -> dict:
    """{'key', 'value' (effective), 'file_value' (literal in file or None)}."""
    return backend.run_json(["config", "get", key, "--json"], config_path)


def schema(config_path: Optional[str] = None, section: Optional[str] = None,
           search: Optional[str] = None) -> dict:
    data = backend.run_json(["config", "schema", "--json"], config_path)
    keys = data.get("keys", [])
    if section:
        keys = [k for k in keys if (k.get("section") or "").lower() == section.lower()]
    if search:
        s = search.lower()
        keys = [k for k in keys if s in k["key"].lower() or s in (k.get("label") or "").lower()
                or s in (k.get("description") or "").lower()]
    data["keys"] = keys
    return data


def sections(config_path: Optional[str] = None) -> list[dict]:
    keys = schema(config_path)["keys"]
    out: dict[str, int] = {}
    for k in keys:
        out[k.get("section") or "Other"] = out.get(k.get("section") or "Other", 0) + 1
    return [{"section": s, "keys": n} for s, n in out.items()]


def resolved_path(config_path: Optional[str] = None) -> str:
    """The file voxtype reads/writes for this invocation."""
    if config_path:
        return os.path.abspath(config_path)
    return backend.run_json(["config", "schema", "--json"])["config_path"]


def replacements(config_path: Optional[str] = None) -> dict:
    return backend.run_json(["config", "schema", "--json"], config_path).get("replacements", {}) or {}


def _parse_set_output(stdout: str) -> dict:
    return {"restart_required": "Restart voxtype to apply" in stdout,
            "message": stdout.strip().splitlines()[0] if stdout.strip() else ""}


def set_key(key: str, value: str, config_path: Optional[str] = None,
            dry_run: bool = False) -> dict:
    """Set KEY=VALUE via voxtype. Returns the undo entry plus the new state.

    With dry_run the change is applied to a scratch copy of the config, so
    voxtype still validates it but the real file is untouched.
    """
    target = resolved_path(config_path)
    before = get_key(key, target) if not key.startswith("text.replacements.") else _replacement_state(key, target)
    with _maybe_scratch(target, dry_run) as path:
        proc = backend.run(["config", "set", key, str(value)], path)
        after = get_key(key, path) if not key.startswith("text.replacements.") else _replacement_state(key, path)
    info = _parse_set_output(proc.stdout)
    return {
        "op": "set",
        "key": key,
        "old": before.get("file_value"),
        "new": after.get("file_value"),
        "value": after.get("value"),
        "config_path": target,
        "restart_required": info["restart_required"],
        "dry_run": dry_run,
        "ts": time.time(),
    }


def unset_key(key: str, config_path: Optional[str] = None, dry_run: bool = False) -> dict:
    target = resolved_path(config_path)
    before = get_key(key, target) if not key.startswith("text.replacements.") else _replacement_state(key, target)
    with _maybe_scratch(target, dry_run) as path:
        proc = backend.run(["config", "unset", key], path)
        after = get_key(key, path) if not key.startswith("text.replacements.") else _replacement_state(key, path)
    info = _parse_set_output(proc.stdout)
    return {
        "op": "unset",
        "key": key,
        "old": before.get("file_value"),
        "new": None,
        "value": after.get("value"),
        "config_path": target,
        "restart_required": info["restart_required"],
        "dry_run": dry_run,
        "ts": time.time(),
    }


def restore(key: str, file_value, config_path: Optional[str] = None) -> dict:
    """Put KEY back to a literal file value (None = absent)."""
    if file_value is None:
        return unset_key(key, config_path)
    return set_key(key, value_to_cli(file_value), config_path)


def undo_entry(entry: dict, config_path: Optional[str] = None) -> dict:
    return restore(entry["key"], entry.get("old"), config_path or entry.get("config_path"))


def redo_entry(entry: dict, config_path: Optional[str] = None) -> dict:
    path = config_path or entry.get("config_path")
    if entry["op"] == "unset":
        return unset_key(entry["key"], path)
    return restore(entry["key"], entry.get("new"), path)


def diff_against_defaults(config_path: Optional[str] = None) -> list[dict]:
    """Keys literally present in the config file, with their effective value."""
    data = schema(config_path)
    out = [{"key": k["key"], "file_value": k.get("file_value"), "value": k.get("value"),
            "section": k.get("section")}
           for k in data["keys"] if k.get("file_value") is not None]
    for spoken, written in sorted((data.get("replacements") or {}).items()):
        out.append({"key": f"text.replacements.{spoken}", "file_value": written,
                    "value": written, "section": "Text"})
    return out


def _replacement_state(key: str, config_path: str) -> dict:
    spoken = key[len("text.replacements."):]
    val = replacements(config_path).get(spoken)
    return {"key": key, "value": val, "file_value": val}


class _maybe_scratch:
    """Context manager yielding either the real config path or a scratch copy."""

    def __init__(self, path: str, dry_run: bool):
        self.path = path
        self.dry_run = dry_run
        self._dir = None

    def __enter__(self) -> str:
        if not self.dry_run:
            return self.path
        self._dir = tempfile.mkdtemp(prefix="cli-anything-voxtype-dry-")
        scratch = os.path.join(self._dir, "config.toml")
        if os.path.exists(self.path):
            shutil.copy2(self.path, scratch)
        return scratch

    def __exit__(self, *exc):
        if self._dir:
            shutil.rmtree(self._dir, ignore_errors=True)
        return False
