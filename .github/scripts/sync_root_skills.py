#!/usr/bin/env python3
"""Sync repo-root skills/ from harness-local SKILL.md files."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ROOT_SKILLS_DIR = REPO_ROOT / "skills"


def _canonical_skill_id(source: Path) -> str:
    rel = source.relative_to(REPO_ROOT)
    parts = rel.parts
    if "cli_anything" in parts:
        package_index = parts.index("cli_anything") + 1
        if package_index < len(parts):
            package_name = parts[package_index]
            return f"cli-anything-{package_name.replace('_', '-')}"

    software_dir = parts[0]
    return f"cli-anything-{software_dir.replace('_', '-')}"


def _rewrite_name_frontmatter(content: str, skill_id: str) -> str:
    if not content.startswith("---\n"):
        return content

    parts = content.split("---\n", 2)
    if len(parts) < 3:
        return content

    _, frontmatter, body = parts
    lines = frontmatter.splitlines(keepends=True)
    rewritten: list[str] = []
    replaced = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if not replaced and line.startswith("name:"):
            rewritten.append(f'name: "{skill_id}"\n')
            replaced = True
            i += 1
            while i < len(lines) and (lines[i].startswith(" ") or lines[i].startswith("\t")):
                i += 1
            continue
        rewritten.append(line)
        i += 1

    if not replaced:
        rewritten.insert(0, f'name: "{skill_id}"\n')

    frontmatter = "".join(rewritten)
    return f"---\n{frontmatter}---\n{body}"


def _discover_sources() -> list[Path]:
    sources: list[Path] = []
    sources.extend(sorted(REPO_ROOT.glob("*/agent-harness/cli_anything/*/skills/SKILL.md")))
    sources.extend(sorted(REPO_ROOT.glob("*/agent-harness/cli_anything/*/SKILL.md")))
    return [path for path in sources if path.is_file()]


def main() -> int:
    sources = _discover_sources()
    ROOT_SKILLS_DIR.mkdir(parents=True, exist_ok=True)

    written = 0
    for source in sources:
        skill_id = _canonical_skill_id(source)
        target = ROOT_SKILLS_DIR / skill_id / "SKILL.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        content = source.read_text(encoding="utf-8")
        expected = _rewrite_name_frontmatter(content, skill_id)

        if target.is_file() and target.read_text(encoding="utf-8") == expected:
            continue

        # Overwriting is destructive: the mirror may hold edits the source lacks.
        # Say so, so the loss is never silent. validate_root_skills.py refuses
        # in that direction before CI ever reaches here.
        action = "overwrite" if target.is_file() else "create"
        print(f"{action}: {target.relative_to(REPO_ROOT)} <- {source.relative_to(REPO_ROOT)}")
        target.write_text(expected, encoding="utf-8")
        written += 1

    print(f"Synced {written} root skill(s); {len(sources) - written} already up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
