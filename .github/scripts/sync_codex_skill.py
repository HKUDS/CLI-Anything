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
            if source.is_dir():
                raise SystemExit(
                    f"unsupported subdirectory in mirrored source dir: {source}"
                )
            if source.is_file():
                pairs.append((source, dest_dir / source.name))
    return pairs


# Parents of fixed-file destinations, scanned recursively for orphans left
# behind when a FILE_MAP destination is renamed or removed. Only files are
# managed here; directory mirrors are handled via DIR_MAP. Any file under
# these parents that is neither a mapped destination nor explicitly
# allowlisted in UNMANAGED_FILES is treated as a stale resource and removed
# by sync — add new non-vendored files to UNMANAGED_FILES before placing
# them here.
FIXED_PARENTS: list[str] = ["references", "references/docs", "scripts"]
UNMANAGED_FILES: set[str] = {"scripts/install.sh", "scripts/install.ps1"}


def _dir_map_dests() -> set[Path]:
    return {SKILL_DIR / dest_rel for _, dest_rel in DIR_MAP}


def _fixed_orphans() -> list[Path]:
    expected = {dest for _, dest in _mapped_files()}
    dir_map_dests = _dir_map_dests()
    orphans: dict[Path, None] = {}
    for parent_rel in FIXED_PARENTS:
        parent = SKILL_DIR / parent_rel
        if not parent.is_dir():
            continue
        for entry in sorted(parent.rglob("*")):
            if entry.is_dir() and not entry.is_symlink():
                continue
            if any(entry.is_relative_to(dest) for dest in dir_map_dests):
                continue
            if entry.relative_to(SKILL_DIR).as_posix() in UNMANAGED_FILES:
                continue
            if entry not in expected:
                orphans.setdefault(entry, None)
    return list(orphans)


def _clear_conflicting(dest: Path) -> None:
    """Remove entries that conflict with the regular file/dir layout sync
    needs, so the documented repair command can restore the mirror without
    manual deletion.

    Ancestors are cleared top-down and symlinks are never followed, so a
    symlinked ancestor cannot redirect removals outside codex-skill/.
    """
    current = SKILL_DIR
    for part in dest.relative_to(SKILL_DIR).parts:
        current = current / part
        if current.is_symlink():
            current.unlink()
        elif current.is_dir():
            continue
        elif current.exists():
            current.unlink()
        else:
            return
    if dest.is_dir():
        shutil.rmtree(dest)


def sync() -> None:
    mapped = list(_mapped_files())
    for source, dest in mapped:
        if not source.is_file():
            raise SystemExit(f"canonical source missing: {source}")
        _clear_conflicting(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)

    # Remove vendored files in the mirrored directories whose canonical
    # source was deleted or renamed. Cleanup is scoped to DIR_MAP
    # destinations; FILE_MAP destinations are fixed paths and cannot
    # accumulate orphans.
    expected = {dest for _, dest in mapped}
    for _, dest_rel in DIR_MAP:
        dest_dir = SKILL_DIR / dest_rel
        if not dest_dir.is_dir():
            continue
        for existing in sorted(dest_dir.rglob("*")):
            if existing.is_symlink() or (
                existing.is_file() and existing not in expected
            ):
                existing.unlink()
        # Prune now-empty nested directories left behind by cleanup.
        for nested in sorted(
            (d for d in dest_dir.rglob("*") if d.is_dir()),
            key=lambda d: len(d.parts),
            reverse=True,
        ):
            if not any(nested.iterdir()):
                nested.rmdir()

    # Remove stale fixed resources left behind by FILE_MAP renames/removals.
    for orphan in _fixed_orphans():
        orphan.unlink()
    dir_map_dests = _dir_map_dests()
    fixed_dirs = [SKILL_DIR / rel for rel in FIXED_PARENTS]
    for nested in sorted(
        (
            d
            for parent in fixed_dirs
            if parent.is_dir()
            for d in parent.rglob("*")
            if d.is_dir() and not any(d.is_relative_to(dest) for dest in dir_map_dests)
        ),
        key=lambda d: len(d.parts),
        reverse=True,
    ):
        if nested.is_dir() and not any(nested.iterdir()):
            nested.rmdir()


if __name__ == "__main__":
    sync()
    print(f"Synced {len(_mapped_files())} vendored resources into codex-skill/.")
