"""The repo's root-skill CI gate, as it applies to a newly added harness.

``.github/workflows/check-root-skills.yml`` runs ``validate_root_skills.py`` on
every PR that touches ``*/agent-harness/**``. That script compares each
harness-local ``SKILL.md`` with its generated mirror under ``skills/``, so a new
harness is only shippable when the mirror matches byte for byte after the
front-matter ``name:`` rewrite — which is exactly what the OrcaRouter harness
adds.

These tests pin both halves: the comparison rules the new harness must satisfy,
and the drift direction the script has to refuse so a later sync cannot destroy
mirror-only content.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


VALIDATE = _load("validate_root_skills", SCRIPTS / "validate_root_skills.py")
SYNC = _load("sync_root_skills", SCRIPTS / "sync_root_skills.py")

REPO_ROOT = VALIDATE.REPO_ROOT

SKILL_SOURCE = """---
name: orcarouter
description: OrcaRouter harness skill
---

# OrcaRouter

Two authentication choices: an API key or OAuth 2.0 + PKCE.
"""


def test_canonical_skill_id_uses_the_package_name():
    source = REPO_ROOT / "orcarouter/agent-harness/cli_anything/orcarouter/skills/SKILL.md"

    assert SYNC._canonical_skill_id(source) == "cli-anything-orcarouter"


def test_canonical_skill_id_falls_back_to_the_software_directory():
    source = REPO_ROOT / "mubu/agent-harness/SKILL.md"

    assert SYNC._canonical_skill_id(source) == "cli-anything-mubu"


def test_frontmatter_name_is_rewritten_and_the_body_is_untouched():
    rewritten = SYNC._rewrite_name_frontmatter(SKILL_SOURCE, "cli-anything-orcarouter")

    assert 'name: "cli-anything-orcarouter"\n' in rewritten
    assert "name: orcarouter\n" not in rewritten
    assert "OAuth 2.0 + PKCE" in rewritten


def test_discovered_sources_include_the_orcarouter_harness():
    discovered = {path.relative_to(REPO_ROOT) for path in VALIDATE._load_sync_helpers()["_discover_sources"]()}

    assert (
        Path("orcarouter/agent-harness/cli_anything/orcarouter/skills/SKILL.md") in discovered
    )


def test_orcarouter_mirror_matches_its_harness_source():
    source = (
        REPO_ROOT / "orcarouter" / "agent-harness" / "cli_anything" / "orcarouter" / "skills" / "SKILL.md"
    )
    mirror = REPO_ROOT / "skills" / "cli-anything-orcarouter" / "SKILL.md"
    assert source.is_file(), "the harness SKILL.md is the source of truth"
    assert mirror.is_file(), "the root mirror must exist for CI to pass"

    expected = SYNC._rewrite_name_frontmatter(
        source.read_text(encoding="utf-8"), "cli-anything-orcarouter"
    )

    assert mirror.read_text(encoding="utf-8") == expected
    assert not VALIDATE._mirror_only_lines(expected, mirror.read_text(encoding="utf-8"))


def test_validation_passes_for_the_current_repository():
    """The CI gate itself, so a drifting mirror fails a local test run too."""
    assert VALIDATE.main() == 0


def test_mirror_only_content_is_detected_as_clobberable():
    expected = SYNC._rewrite_name_frontmatter(SKILL_SOURCE, "cli-anything-orcarouter")
    actual = expected + "\nHand-written line that lives only in the mirror.\n"

    mirror_only = VALIDATE._mirror_only_lines(expected, actual)

    assert mirror_only == ["Hand-written line that lives only in the mirror."]
