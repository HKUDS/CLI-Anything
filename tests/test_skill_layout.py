"""
Test suite for CLI-Anything repo structure validation.

This test ensures the dual-entrypoint design (plugin + repo-local skill)
is properly documented and aligned with README claims.
"""

import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


def test_readme_mentions_plugin_and_skill():
    """README should mention both plugin and repo-local skill paths."""
    readme = REPO_ROOT / "README.md"
    content = readme.read_text()
    
    # Check plugin path is documented
    assert "cli-anything-plugin" in content, "README should mention cli-anything-plugin"
    
    # Check skill path is documented (dual-entrypoint)
    assert ".agents/skills" in content or "repo-local" in content.lower(), \
        "README should mention repo-local skill path"


def test_skill_directory_exists():
    """Repo-local skill directory should exist."""
    skill_dir = REPO_ROOT / ".agents" / "skills" / "cli-anything"
    assert skill_dir.exists(), f"Skill directory should exist at {skill_dir}"
    assert (skill_dir / "SKILL.md").exists(), "Skill should have SKILL.md"


def test_skill_reuses_harness():
    """Skill should reference the existing HARNESS.md."""
    skill_md = REPO_ROOT / ".agents" / "skills" / "cli-anything" / "SKILL.md"
    content = skill_md.read_text()
    
    assert "HARNESS.md" in content, "Skill should reference HARNESS.md"
    assert "cli-anything-plugin" in content, "Skill should mention plugin for shared specs"


def test_plugin_directory_exists():
    """Plugin directory should exist for dual-entrypoint design."""
    plugin_dir = REPO_ROOT / "cli-anything-plugin"
    assert plugin_dir.exists(), "cli-anything-plugin directory should exist"
    assert (plugin_dir / "HARNESS.md").exists(), "Plugin should have HARNESS.md"
    assert (plugin_dir / "commands").exists(), "Plugin should have commands directory"


def test_example_appsocumented():
    """README should list example applications."""
    readme = REPO_ROOT / "README.md"
    content = readme.read_text()
    
    examples = ["GIMP", "Blender", "Inkscape", "Audacity"]
    for example in examples:
        assert example in content, f"README should mention {example} as example"


if __name__ == "__main__":
    import sys
    
    tests = [
        test_readme_mentions_plugin_and_skill,
        test_skill_directory_exists,
        test_skill_reuses_harness,
        test_plugin_directory_exists,
        test_example_appsocumented,
    ]
    
    failed = []
    for test in tests:
        try:
            test()
            print(f"✓ {test.__name__}")
        except AssertionError as e:
            print(f"✗ {test.__name__}: {e}")
            failed.append(test.__name__)
    
    if failed:
        print(f"\n{len(failed)} test(s) failed")
        sys.exit(1)
    else:
        print(f"\nAll {len(tests)} tests passed!")
        sys.exit(0)
