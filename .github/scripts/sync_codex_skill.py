#!/usr/bin/env python3
"""Sync codex-skill/ vendored resources from their canonical sources.

`npx skills add` copies the `codex-skill/` directory verbatim, so the
methodology resources that `SKILL.md` points at must exist inside the
directory itself. The canonical sources live in `cli-anything-plugin/`
and `docs/`; this script copies them into the vendored mirror.
"""

from __future__ import annotations

import shutil
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = REPO_ROOT / "codex-skill"
PLUGIN_DIR = REPO_ROOT / "cli-anything-plugin"

# (source relative to repo root, destination relative to codex-skill/)
FILE_MAP: list[tuple[str, str]] = [
    ("cli-anything-plugin/HARNESS.md", "references/HARNESS.md"),
    ("docs/PREVIEW_PROTOCOL.md", "references/docs/PREVIEW_PROTOCOL.md"),
    ("cli-anything-plugin/repl_skin.py", "scripts/repl_skin.py"),
    ("cli-anything-plugin/preview_bundle.py", "scripts/preview_bundle.py"),
    ("cli-anything-plugin/skill_generator.py", "scripts/skill_generator.py"),
]

# Whole directories mirrored file-by-file, matching the wildcard copies in
# codex-skill/scripts/install.sh and install.ps1.
DIR_MAP: list[tuple[str, str]] = [
    ("cli-anything-plugin/commands", "references/commands"),
    ("cli-anything-plugin/guides", "references/guides"),
    ("cli-anything-plugin/templates", "scripts/templates"),
]


def _mapped_files() -> list[tuple[Path, Path]]:
    pairs: list[tuple[Path, Path]] = []
    for source_rel, dest_rel in FILE_MAP:
        pairs.append((REPO_ROOT / source_rel, SKILL_DIR / dest_rel))
    for source_rel, dest_rel in DIR_MAP:
        source_dir = REPO_ROOT / source_rel
        dest_dir = SKILL_DIR / dest_rel
        for source in sorted(source_dir.iterdir()):
            if source.is_file():
                pairs.append((source, dest_dir / source.name))
    return pairs


def sync() -> None:
    for source, dest in _mapped_files():
        if not source.is_file():
            raise SystemExit(f"canonical source missing: {source}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)


if __name__ == "__main__":
    sync()
    print(f"Synced {len(_mapped_files())} vendored resources into codex-skill/.")
