"""Project discovery and config helpers for eth2-quickstart."""

from __future__ import annotations

import os
import re
from pathlib import Path

REPO_ENV_VAR = "ETH2QS_REPO_ROOT"
WRAPPER_RELATIVE_PATH = Path("scripts") / "eth2qs.sh"


def find_repo_root(explicit_root: str | None = None, cwd: str | None = None) -> Path:
    candidates: list[Path] = []

    if explicit_root:
        candidates.append(Path(explicit_root).expanduser())

    env_root = os.environ.get(REPO_ENV_VAR)
    if env_root:
        candidates.append(Path(env_root).expanduser())

    start = Path(cwd).resolve() if cwd else Path.cwd().resolve()
    candidates.append(start)
    candidates.extend(start.parents)

    for candidate in candidates:
        resolved = candidate.resolve()
        if (resolved / WRAPPER_RELATIVE_PATH).is_file():
            return resolved

    raise RuntimeError(
        "Could not locate an eth2-quickstart checkout. "
        "Use --repo-root or set ETH2QS_REPO_ROOT."
    )


def wrapper_path(repo_root: Path) -> Path:
    return repo_root / WRAPPER_RELATIVE_PATH


def user_config_path(repo_root: Path) -> Path:
    return repo_root / "config" / "user_config.env"


def ensure_user_config(repo_root: Path) -> Path:
    config_path = user_config_path(repo_root)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if not config_path.exists():
        config_path.write_text(
            "# Managed by cli-anything-eth2-quickstart\n",
            encoding="utf-8",
        )
    return config_path


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def upsert_user_config(repo_root: Path, updates: dict[str, str]) -> Path:
    config_path = ensure_user_config(repo_root)
    existing = config_path.read_text(encoding="utf-8")

    for key, value in updates.items():
        line = f"export {key}={shell_quote(value)}"
        pattern = re.compile(rf"^export {re.escape(key)}=.*$", re.MULTILINE)
        if pattern.search(existing):
            existing = pattern.sub(line, existing)
        else:
            if existing and not existing.endswith("\n"):
                existing += "\n"
            existing += line + "\n"

    config_path.write_text(existing, encoding="utf-8")
    return config_path

