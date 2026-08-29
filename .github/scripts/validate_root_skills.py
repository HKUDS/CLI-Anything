#!/usr/bin/env python3
"""Validate that deep harness SKILL.md files are mirrored in repo-root skills/."""

from __future__ import annotations

import difflib
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _mirror_only_lines(expected: str, actual: str) -> list[str]:
    """Lines present in the root mirror but absent from the regenerated source.

    These are exactly what `sync_root_skills.py` would overwrite and destroy,
    because it regenerates the mirror from the harness source unconditionally.
    """
    diff = difflib.unified_diff(
        expected.splitlines(), actual.splitlines(), lineterm="", n=0
    )
    return [
        line[1:].strip()
        for line in diff
        if line.startswith("+") and not line.startswith("+++") and line[1:].strip()
    ]


def _load_sync_helpers():
    namespace: dict[str, object] = {"__file__": str(REPO_ROOT / ".github" / "scripts" / "sync_root_skills.py")}
    sync_script = REPO_ROOT / ".github" / "scripts" / "sync_root_skills.py"
    exec(sync_script.read_text(encoding="utf-8"), namespace)
    return namespace


def main() -> int:
    sync = _load_sync_helpers()
    discover_sources = sync["_discover_sources"]
    canonical_skill_id = sync["_canonical_skill_id"]
    rewrite_name_frontmatter = sync["_rewrite_name_frontmatter"]
    root_skills_dir = sync["ROOT_SKILLS_DIR"]

    # Drift where the mirror holds content the source lacks. Regenerating would
    # delete it, so these must be resolved by editing the source instead.
    clobber: list[tuple[Path, Path, list[str]]] = []
    # Drift the sync script can safely repair: the source moved ahead.
    stale: list[str] = []

    for source in discover_sources():
        skill_id = canonical_skill_id(source)
        target = root_skills_dir / skill_id / "SKILL.md"
        if not target.is_file():
            stale.append(
                f"Missing root skill for {source.relative_to(REPO_ROOT)}: expected {target.relative_to(REPO_ROOT)}"
            )
            continue

        source_content = source.read_text(encoding="utf-8")
        expected = rewrite_name_frontmatter(source_content, skill_id)
        actual = target.read_text(encoding="utf-8")
        if actual == expected:
            continue

        mirror_only = _mirror_only_lines(expected, actual)
        if mirror_only:
            clobber.append((source, target, mirror_only))
        else:
            stale.append(
                f"Out-of-sync root skill for {source.relative_to(REPO_ROOT)}: {target.relative_to(REPO_ROOT)}"
            )

    if not clobber and not stale:
        print("Root skills validation passed.")
        return 0

    print("Root skills validation failed:", file=sys.stderr)

    if clobber:
        print(
            "\nYou edited a GENERATED file. `skills/` is produced from the harness\n"
            "SKILL.md sources; running the sync script would DELETE these edits.",
            file=sys.stderr,
        )
        for source, target, mirror_only in clobber:
            print(f"\n- {target.relative_to(REPO_ROOT)}", file=sys.stderr)
            print(
                f"  contains content not present in {source.relative_to(REPO_ROOT)}:",
                file=sys.stderr,
            )
            for line in mirror_only[:10]:
                print(f"    + {line}", file=sys.stderr)
            if len(mirror_only) > 10:
                print(f"    … and {len(mirror_only) - 10} more line(s)", file=sys.stderr)
            print(
                f"  Fix: move the change into {source.relative_to(REPO_ROOT)},\n"
                f"       then run `python3 .github/scripts/sync_root_skills.py`.",
                file=sys.stderr,
            )

    if stale:
        print("\nThe following root skills are stale and can be regenerated:", file=sys.stderr)
        for error in stale:
            print(f"- {error}", file=sys.stderr)
        print(
            "Run `python3 .github/scripts/sync_root_skills.py` and commit the updated root skills.",
            file=sys.stderr,
        )

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
