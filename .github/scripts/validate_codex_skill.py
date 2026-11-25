#!/usr/bin/env python3
"""Validate that codex-skill/ vendored resources match their canonical sources."""

from __future__ import annotations

import sys
from pathlib import Path

namespace: dict[str, object] = {"__file__": str(Path(__file__).resolve())}
sync_script = Path(__file__).resolve().parent / "sync_codex_skill.py"
exec(sync_script.read_text(encoding="utf-8"), namespace)

REPO_ROOT = namespace["REPO_ROOT"]
SKILL_DIR = namespace["SKILL_DIR"]
_mapped_files = namespace["_mapped_files"]


def main() -> int:
    stale: list[str] = []
    missing: list[str] = []
    expected_dests: set[Path] = set()

    for source, dest in _mapped_files():
        expected_dests.add(dest)
        if not dest.is_file():
            missing.append(dest.relative_to(SKILL_DIR).as_posix())
            continue
        if source.read_bytes() != dest.read_bytes():
            stale.append(dest.relative_to(SKILL_DIR).as_posix())

    # Reverse check: no orphan files in the mirrored directories.
    orphans: list[str] = []
    for _, dest_rel in namespace["DIR_MAP"]:
        dest_dir = SKILL_DIR / dest_rel
        if not dest_dir.is_dir():
            continue
        for dest in sorted(dest_dir.rglob("*")):
            if dest.is_file() and dest not in expected_dests:
                orphans.append(dest.relative_to(SKILL_DIR).as_posix())

    if not missing and not stale and not orphans:
        print("Codex skill vendored resources validation passed.")
        return 0

    print("Codex skill vendored resources validation failed:", file=sys.stderr)
    for rel in missing:
        print(f"- missing: codex-skill/{rel}", file=sys.stderr)
    for rel in stale:
        print(f"- out of sync: codex-skill/{rel}", file=sys.stderr)
    for rel in orphans:
        print(f"- orphan (not in canonical source): codex-skill/{rel}", file=sys.stderr)
    print(
        "\nRun `python3 .github/scripts/sync_codex_skill.py` and commit the updated files.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
