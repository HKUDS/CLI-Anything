#!/usr/bin/env python3
"""Validate registry.json against the registry schema documented in CONTRIBUTING.md.

Usage:
    python3 .github/scripts/validate_registry.py            # report only (exit 0)
    python3 .github/scripts/validate_registry.py --strict   # fail on problems (exit 1)

Not wired into CI yet: it reports pre-existing deviations from the documented
schema (entries that predate the field table), so it stays non-blocking until
those entries are normalised.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = REPO_ROOT / "registry.json"

REQUIRED = (
    "name",
    "display_name",
    "version",
    "description",
    "requires",
    "homepage",
    "source_url",
    "install_cmd",
    "entry_point",
    "skill_md",
    "category",
    "contributors",
)
URL_RE = re.compile(r"^https?://")
SUBDIR_RE = re.compile(r"subdirectory=([^#&\s]+)")


def _url_ok(value: object) -> bool:
    return isinstance(value, str) and bool(URL_RE.match(value))


def check_entry(entry: dict, index: int) -> list[str]:
    label = entry.get("name") or f"<entry #{index}>"
    out: list[str] = []

    missing = [f for f in REQUIRED if f not in entry]
    if missing:
        out.append(f"missing required field(s): {', '.join(missing)}")

    unexpected = [k for k in entry if k not in REQUIRED]
    if unexpected:
        out.append(f"unexpected field(s): {', '.join(sorted(unexpected))}")

    contributors = entry.get("contributors")
    if not isinstance(contributors, list) or not contributors:
        out.append("contributors must be a non-empty array")
    else:
        for i, person in enumerate(contributors):
            if (
                not isinstance(person, dict)
                or not person.get("name")
                or not _url_ok(person.get("url"))
            ):
                out.append(f"contributors[{i}] must be {{name, url}} with an http(s) url")

    if not _url_ok(entry.get("homepage")):
        out.append(f"homepage {entry.get('homepage')!r} is not an http(s) URL")

    if entry.get("source_url") is None:
        install_cmd = str(entry.get("install_cmd") or "")
        # Non-Python harnesses (npm / cargo / ...) install from elsewhere, so the
        # monorepo subdirectory rule only applies to this-repo installs.
        if "github.com/HKUDS/CLI-Anything" in install_cmd:
            match = SUBDIR_RE.search(install_cmd)
            if not match:
                out.append("in-repo entry: install_cmd has no #subdirectory=...")
            elif not (REPO_ROOT / match.group(1)).is_dir():
                out.append(f"in-repo entry: subdirectory {match.group(1)!r} does not exist")

        skill_md = entry.get("skill_md")
        if isinstance(skill_md, str) and not _url_ok(skill_md):
            if not (REPO_ROOT / skill_md).is_file():
                out.append(f"skill_md {skill_md!r} does not exist")
    elif not _url_ok(entry.get("source_url")):
        out.append(f"source_url {entry.get('source_url')!r} is not an http(s) URL or null")

    return [f"{label}: {o}" for o in out]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--strict", action="store_true", help="exit 1 when problems are found")
    args = ap.parse_args()

    if not REGISTRY.is_file():
        print(f"registry not found: {REGISTRY}", file=sys.stderr)
        return 1

    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    entries = data.get("clis") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        print("registry.json must be an object with a 'clis' array", file=sys.stderr)
        return 1

    errors: list[str] = []
    seen: dict[str, int] = {}
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"<entry #{i}>: must be an object")
            continue
        name = entry.get("name")
        if isinstance(name, str):
            if name in seen:
                errors.append(f"{name}: duplicate name (also entry #{seen[name]})")
            seen[name] = i
        errors.extend(check_entry(entry, i))

    if errors:
        print(f"registry.json: {len(errors)} problem(s) in {len(entries)} entries:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        if args.strict:
            return 1
        print("\n(re-run with --strict to make this fail the build)", file=sys.stderr)
        return 0

    print(f"registry.json validation passed ({len(entries)} entries).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
