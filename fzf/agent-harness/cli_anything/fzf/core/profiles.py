"""Explicit, secret-free fzf profile files and deterministic composition."""

from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from cli_anything.fzf.core.errors import ValidationError
from cli_anything.fzf.core.validation import OptionValue, parse_option


PROFILE_SCHEMA = "cli-anything-fzf-profile/v1"


@contextmanager
def _exclusive_lock(path: Path) -> Iterator[None]:
    lock_path = path.with_name(f".{path.name}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock:
        try:
            import fcntl

            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        except (ImportError, OSError):
            pass
        yield


def validate_profile(data: object, *, source: str = "profile") -> dict:
    """Validate and normalize one profile document."""

    if not isinstance(data, dict):
        raise ValidationError("profile_invalid", "Profile must be a JSON object")
    allowed = {"schema_version", "name", "description", "options", "bindings"}
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ValidationError("profile_invalid", "Profile contains unknown fields", details={"fields": unknown})
    if data.get("schema_version") != PROFILE_SCHEMA:
        raise ValidationError("profile_invalid", f"Profile schema must be {PROFILE_SCHEMA}")
    name = data.get("name")
    if not isinstance(name, str) or not name.strip() or len(name) > 128:
        raise ValidationError("profile_invalid", "Profile name must be 1 to 128 characters")
    description = data.get("description", "")
    if not isinstance(description, str) or len(description) > 2048:
        raise ValidationError("profile_invalid", "Profile description must be a string up to 2048 characters")
    options = data.get("options", [])
    bindings = data.get("bindings", [])
    if not isinstance(options, list) or not all(isinstance(item, str) for item in options):
        raise ValidationError("profile_invalid", "Profile options must be a list of strings")
    if not isinstance(bindings, list) or not all(isinstance(item, str) for item in bindings):
        raise ValidationError("profile_invalid", "Profile bindings must be a list of strings")
    normalized_options = [parse_option(item, source=source) for item in options]
    normalized_bindings = [parse_option(f"bind={item}", source=source) for item in bindings]
    return {
        "schema_version": PROFILE_SCHEMA,
        "name": name,
        "description": description,
        "options": options,
        "bindings": bindings,
        "resolved_options": normalized_options + normalized_bindings,
    }


def load_profile(path_value: str) -> dict:
    """Load one explicit profile path without searching ambient config."""

    path = Path(path_value).expanduser().resolve(strict=False)
    if not path.is_file():
        raise ValidationError("profile_not_found", f"Profile does not exist: {path}")
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError("profile_invalid", f"Could not read profile {path}: {exc}") from exc
    result = validate_profile(data, source=str(path))
    result["path"] = str(path)
    return result


def compose_profiles(paths: list[str]) -> dict:
    """Compose profiles in order; later scalar options override earlier ones."""

    loaded = [load_profile(path) for path in paths]
    scalar: dict[str, OptionValue] = {}
    order: list[str] = []
    repeatable: list[OptionValue] = []
    for profile in loaded:
        for option in profile["resolved_options"]:
            if option.spec.get("repeatable", False):
                repeatable.append(option)
                continue
            if option.name not in scalar:
                order.append(option.name)
            scalar[option.name] = option
    resolved = [scalar[name] for name in order] + repeatable
    return {
        "profiles": [
            {"name": item["name"], "description": item["description"], "path": item["path"]}
            for item in loaded
        ],
        "resolved_options": resolved,
        "option_tokens": [option.argv_token() for option in resolved],
    }


def profile_output_path(path_value: str) -> Path:
    """Keep the lexical output path and refuse final-component symlinks."""

    requested = Path(path_value).expanduser()
    if requested.is_symlink():
        raise ValidationError("profile_path_unsafe", "Profile output path cannot be a symlink")
    return requested.absolute()


def write_profile(
    path_value: str,
    *,
    name: str,
    description: str,
    options: list[str],
    bindings: list[str],
    overwrite: bool = False,
) -> dict:
    """Atomically create or replace a profile with mode 0600."""

    path = profile_output_path(path_value)
    document = {
        "schema_version": PROFILE_SCHEMA,
        "name": name,
        "description": description,
        "options": options,
        "bindings": bindings,
    }
    validate_profile(document)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _exclusive_lock(path):
        if path.exists() and not overwrite:
            raise ValidationError("profile_exists", f"Profile already exists: {path}")
        fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(document, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            os.chmod(path, 0o600)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
    return {"path": str(path), "profile": document, "mode": "0600"}
