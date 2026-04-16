"""Tests that SKILL.md is discoverable after pip install.

Simulates the installed package layout and verifies:
1. ReplSkin auto-detects the skill file from its __file__ location
2. The banner output includes the absolute skill path
3. Missing skill file results in skill_path=None
"""

import os
import sys
import shutil
import tempfile
import textwrap
from pathlib import Path
from io import StringIO

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_package_tree(root: Path, software: str = "demo") -> Path:
    """Create a minimal cli_anything/<software>/ layout with repl_skin + SKILL.md.

    Returns the path to the utils/ directory (where repl_skin.py lives).
    """
    pkg = root / "cli_anything" / software
    utils = pkg / "utils"
    skills = pkg / "skills"
    utils.mkdir(parents=True)
    skills.mkdir(parents=True)

    # Copy the canonical repl_skin.py from the plugin
    src = Path(__file__).resolve().parent.parent.parent / "cli-anything-plugin" / "repl_skin.py"
    shutil.copy(src, utils / "repl_skin.py")

    # Write a minimal SKILL.md
    (skills / "SKILL.md").write_text(textwrap.dedent("""\
        ---
        name: "cli-anything-demo"
        description: "Demo skill"
        ---
        # cli-anything-demo
    """))

    return utils


def _load_repl_skin(utils_dir: Path):
    """Import ReplSkin from the given utils directory (simulating installed path)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "repl_skin", utils_dir / "repl_skin.py"
    )
    mod = importlib.util.module_from_spec(spec)
    # Set __file__ so auto-detection resolves relative to this location
    mod.__file__ = str(utils_dir / "repl_skin.py")
    spec.loader.exec_module(mod)
    return mod.ReplSkin


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSkillPathAutoDetect:
    """ReplSkin should auto-detect skills/SKILL.md relative to its own location."""

    def test_auto_detects_skill_path(self, tmp_path):
        utils = _build_package_tree(tmp_path)
        ReplSkin = _load_repl_skin(utils)

        skin = ReplSkin("demo", version="1.0.0")

        expected = str(tmp_path / "cli_anything" / "demo" / "skills" / "SKILL.md")
        assert skin.skill_path == expected

    def test_skill_path_is_absolute(self, tmp_path):
        utils = _build_package_tree(tmp_path)
        ReplSkin = _load_repl_skin(utils)

        skin = ReplSkin("demo", version="1.0.0")

        assert os.path.isabs(skin.skill_path)

    def test_skill_file_exists_at_detected_path(self, tmp_path):
        utils = _build_package_tree(tmp_path)
        ReplSkin = _load_repl_skin(utils)

        skin = ReplSkin("demo", version="1.0.0")

        assert Path(skin.skill_path).is_file()

    def test_none_when_skill_missing(self, tmp_path):
        utils = _build_package_tree(tmp_path)
        # Remove the SKILL.md
        (tmp_path / "cli_anything" / "demo" / "skills" / "SKILL.md").unlink()

        ReplSkin = _load_repl_skin(utils)
        skin = ReplSkin("demo", version="1.0.0")

        assert skin.skill_path is None

    def test_explicit_skill_path_overrides_auto(self, tmp_path):
        utils = _build_package_tree(tmp_path)
        ReplSkin = _load_repl_skin(utils)

        skin = ReplSkin("demo", version="1.0.0", skill_path="/custom/SKILL.md")

        assert skin.skill_path == "/custom/SKILL.md"


class TestSkillPathInBanner:
    """The REPL banner should display the skill path when present."""

    def test_banner_shows_skill_path(self, tmp_path, capsys):
        utils = _build_package_tree(tmp_path)
        ReplSkin = _load_repl_skin(utils)

        skin = ReplSkin("demo", version="1.0.0")
        skin.print_banner()

        output = capsys.readouterr().out
        assert "Skill:" in output
        assert "SKILL.md" in output

    def test_banner_omits_skill_when_missing(self, tmp_path, capsys):
        utils = _build_package_tree(tmp_path)
        (tmp_path / "cli_anything" / "demo" / "skills" / "SKILL.md").unlink()

        ReplSkin = _load_repl_skin(utils)
        skin = ReplSkin("demo", version="1.0.0")
        skin.print_banner()

        output = capsys.readouterr().out
        assert "Skill:" not in output


class TestInstalledHarnesses:
    """Verify each real harness has SKILL.md in the correct package location."""

    HARNESSES = [
        ("adguardhome", "adguardhome"),
        ("anygen", "anygen"),
        ("audacity", "audacity"),
        ("blender", "blender"),
        ("comfyui", "comfyui"),
        ("drawio", "drawio"),
        ("gimp", "gimp"),
        ("inkscape", "inkscape"),
        ("kdenlive", "kdenlive"),
        ("libreoffice", "libreoffice"),
        ("mermaid", "mermaid"),
        ("mubu", "mubu"),
        ("notebooklm", "notebooklm"),
        ("novita", "novita"),
        ("obs-studio", "obs_studio"),
        ("ollama", "ollama"),
        ("shotcut", "shotcut"),
        ("zoom", "zoom"),
    ]

    @pytest.mark.parametrize("dir_name,pkg_name", HARNESSES)
    def test_skill_md_exists_in_package(self, dir_name, pkg_name):
        repo_root = Path(__file__).resolve().parent.parent.parent
        skill_path = repo_root / dir_name / "agent-harness" / "cli_anything" / pkg_name / "skills" / "SKILL.md"
        assert skill_path.is_file(), f"Missing: {skill_path}"

    @pytest.mark.parametrize("dir_name,pkg_name", HARNESSES)
    def test_skill_md_has_yaml_frontmatter(self, dir_name, pkg_name):
        repo_root = Path(__file__).resolve().parent.parent.parent
        skill_path = repo_root / dir_name / "agent-harness" / "cli_anything" / pkg_name / "skills" / "SKILL.md"
        content = skill_path.read_text()
        assert content.startswith("---"), f"Missing YAML frontmatter in {skill_path}"
        # Must have closing ---
        assert content.count("---") >= 2

    @pytest.mark.parametrize("dir_name,pkg_name", HARNESSES)
    def test_skill_md_has_command_groups(self, dir_name, pkg_name):
        repo_root = Path(__file__).resolve().parent.parent.parent
        skill_path = repo_root / dir_name / "agent-harness" / "cli_anything" / pkg_name / "skills" / "SKILL.md"
        content = skill_path.read_text()
        assert "## Command Groups" in content
        # Must have at least one filled command row
        assert "| `" in content, f"Empty command tables in {skill_path}"

    @pytest.mark.parametrize("dir_name,pkg_name", HARNESSES)
    def test_setup_py_includes_package_data(self, dir_name, pkg_name):
        repo_root = Path(__file__).resolve().parent.parent.parent
        setup_path = repo_root / dir_name / "agent-harness" / "setup.py"
        content = setup_path.read_text()
        assert "package_data" in content, f"Missing package_data in {setup_path}"
        # Accept both glob style ("skills/*.md") and explicit style ("SKILL.md" in a .skills key)
        has_skill_ref = "skills/*.md" in content or ("skills" in content and "SKILL.md" in content)
        assert has_skill_ref, f"Missing skills/*.md or SKILL.md in package_data: {setup_path}"
