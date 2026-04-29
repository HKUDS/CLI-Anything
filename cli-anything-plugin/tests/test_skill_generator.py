"""
Tests for skill_generator.py — SKILL.md generation for CLI-Anything harnesses.

Verifies metadata extraction, SKILL.md generation, and edge cases.

Run with: pytest tests/test_skill_generator.py -v
"""

import os
import sys
import textwrap
import tempfile
from pathlib import Path

import pytest

# Resolve skill_generator.py location:
# - In the repo: cli-anything-plugin/skill_generator.py (parent dir)
# - After install.sh: scripts/skill_generator.py (sibling dir)
_PLUGIN_DIR = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _PLUGIN_DIR / "scripts"
if (_SCRIPTS_DIR / "skill_generator.py").exists():
    sys.path.insert(0, str(_SCRIPTS_DIR))
else:
    sys.path.insert(0, str(_PLUGIN_DIR))

from skill_generator import (
    extract_cli_metadata,
    generate_skill_md,
    generate_skill_md_simple,
    generate_skill_file,
    extract_intro_from_readme,
    extract_system_package,
    extract_version_from_setup,
    SkillMetadata,
    CommandInfo,
    CommandGroup,
    Example,
)


# ─── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def harness_dir(tmp_path):
    """Create a minimal harness directory structure."""
    software = "testapp"
    cli_pkg = tmp_path / "cli_anything" / software
    cli_pkg.mkdir(parents=True)

    # __init__.py
    (cli_pkg / "__init__.py").write_text('"""Test application CLI."""\n')

    # README.md
    (cli_pkg / "README.md").write_text(
        textwrap.dedent(f"""\
        # {software}

        A powerful test application for demonstrating CLI harness generation.
        This application supports batch processing and interactive use.
        """)
    )

    # setup.py
    (tmp_path / "setup.py").write_text(
        textwrap.dedent("""\
        from setuptools import setup, find_packages
        setup(
            name="cli-anything-testapp",
            version="2.1.0",
            packages=find_packages(),
        )
        """)
    )

    # CLI file with Click commands
    (cli_pkg / f"{software}_cli.py").write_text(
        textwrap.dedent("""\
        import click

        @click.group()
        def cli():
            \"\"\"Main CLI group.\"\"\"
            pass

        @cli.command()
        def export():
            \"\"\"Export data to file.\"\"\"
            pass

        @cli.command()
        def import_data():
            \"\"\"Import data from file.\"\"\"
            pass
        """)
    )

    return tmp_path


@pytest.fixture
def minimal_harness(tmp_path):
    """Create the absolute minimal harness (just __init__.py)."""
    software = "minimal"
    cli_pkg = tmp_path / "cli_anything" / software
    cli_pkg.mkdir(parents=True)
    (cli_pkg / "__init__.py").write_text("")
    return tmp_path


# ─── extract_cli_metadata Tests ────────────────────────────────────────


class TestExtractCliMetadata:
    def test_extracts_software_name(self, harness_dir):
        metadata = extract_cli_metadata(str(harness_dir))
        assert metadata.software_name == "testapp"

    def test_extracts_skill_name(self, harness_dir):
        metadata = extract_cli_metadata(str(harness_dir))
        assert metadata.skill_name == "cli-anything-testapp"

    def test_extracts_version_from_setup_py(self, harness_dir):
        metadata = extract_cli_metadata(str(harness_dir))
        assert metadata.version == "2.1.0"

    def test_extracts_intro_from_readme(self, harness_dir):
        metadata = extract_cli_metadata(str(harness_dir))
        assert "powerful test application" in metadata.skill_intro

    def test_extracts_command_groups(self, harness_dir):
        metadata = extract_cli_metadata(str(harness_dir))
        assert len(metadata.command_groups) > 0

    def test_extracts_commands_from_cli_file(self, harness_dir):
        metadata = extract_cli_metadata(str(harness_dir))
        all_commands = []
        for group in metadata.command_groups:
            all_commands.extend(group.commands)
        # Should find at least 'export' and 'import-data'
        cmd_names = [c.name for c in all_commands]
        assert "export" in cmd_names
        assert "import-data" in cmd_names

    def test_generates_examples(self, harness_dir):
        metadata = extract_cli_metadata(str(harness_dir))
        assert len(metadata.examples) > 0

    def test_minimal_harness(self, minimal_harness):
        metadata = extract_cli_metadata(str(minimal_harness))
        assert metadata.software_name == "minimal"
        assert metadata.version == "1.0.0"  # Default when no setup.py

    def test_raises_on_missing_cli_anything_dir(self, tmp_path):
        with pytest.raises(ValueError, match="cli_anything directory not found"):
            extract_cli_metadata(str(tmp_path))

    def test_raises_on_empty_cli_anything_dir(self, tmp_path):
        (tmp_path / "cli_anything").mkdir()
        with pytest.raises(ValueError, match="No CLI package found"):
            extract_cli_metadata(str(tmp_path))

    def test_description_contains_software_name(self, harness_dir):
        metadata = extract_cli_metadata(str(harness_dir))
        assert "testapp" in metadata.skill_description.lower() or "Testapp" in metadata.skill_description


# ─── extract_version_from_setup Tests ──────────────────────────────────


class TestExtractVersionFromSetup:
    def test_extracts_version(self, tmp_path):
        setup_py = tmp_path / "setup.py"
        setup_py.write_text('version="3.2.1"')
        assert extract_version_from_setup(setup_py) == "3.2.1"

    def test_extracts_version_single_quotes(self, tmp_path):
        setup_py = tmp_path / "setup.py"
        setup_py.write_text("version='1.0.0'")
        assert extract_version_from_setup(setup_py) == "1.0.0"

    def test_returns_default_when_no_version(self, tmp_path):
        setup_py = tmp_path / "setup.py"
        setup_py.write_text("# no version here")
        assert extract_version_from_setup(setup_py) == "1.0.0"


# ─── extract_intro_from_readme Tests ───────────────────────────────────


class TestExtractIntroFromReadme:
    def test_extracts_first_paragraph(self):
        content = "# My App\n\nThis is the intro paragraph.\n\n## Section\nMore text"
        intro = extract_intro_from_readme(content)
        assert "This is the intro paragraph" in intro

    def test_returns_default_for_empty(self):
        content = "# Title\n## Section\n"
        intro = extract_intro_from_readme(content)
        assert "CLI interface" in intro

    def test_handles_multiline_intro(self):
        content = "# App\nLine one.\nLine two.\n\n## Details"
        intro = extract_intro_from_readme(content)
        assert "Line one" in intro
        assert "Line two" in intro



# ─── extract_system_package Tests ─────────────────────


class TestExtractSystemPackage:
    def test_apt_install(self):
        content = "Install with `apt install mytool`."
        result = extract_system_package(content)
        assert result == "apt install mytool"

    def test_brew_install(self):
        content = "Install with `brew install mytool`."
        result = extract_system_package(content)
        assert result == "brew install mytool"

    def test_apt_get_install_returns_apt_get_command(self):
        # Regression: apt-get pattern contains "apt" as a substring, so the
        # condition must check "apt-get" before "apt" to avoid returning the
        # wrong command ("apt install" instead of "apt-get install").
        content = "Install with `apt-get install mytool`."
        result = extract_system_package(content)
        assert result == "apt-get install mytool", (
            f"Expected 'apt-get install mytool', got {result!r}"
        )

    def test_returns_none_when_no_match(self):
        content = "No installation instructions here."
        assert extract_system_package(content) is None

# ─── generate_skill_md Tests ───────────────────────────────────────────


class TestGenerateSkillMd:
    def _make_metadata(self, **overrides):
        defaults = dict(
            skill_name="cli-anything-testapp",
            skill_description="CLI for TestApp",
            software_name="testapp",
            skill_intro="A test application.",
            version="1.0.0",
            system_package=None,
            command_groups=[],
            examples=[],
        )
        defaults.update(overrides)
        return SkillMetadata(**defaults)

    def test_simple_output_has_yaml_frontmatter(self):
        metadata = self._make_metadata()
        content = generate_skill_md_simple(metadata)
        assert content.startswith("---")
        assert 'name: "cli-anything-testapp"' in content
        assert 'description: "CLI for TestApp"' in content

    def test_simple_output_has_installation_section(self):
        metadata = self._make_metadata()
        content = generate_skill_md_simple(metadata)
        assert "## Installation" in content
        assert "pip install cli-anything-testapp" in content

    def test_simple_output_includes_version(self):
        metadata = self._make_metadata(version="2.5.0")
        content = generate_skill_md_simple(metadata)
        assert "2.5.0" in content

    def test_simple_output_has_command_groups(self):
        groups = [
            CommandGroup(
                name="Export",
                description="Export commands",
                commands=[
                    CommandInfo(name="pdf", description="Export as PDF"),
                    CommandInfo(name="svg", description="Export as SVG"),
                ],
            )
        ]
        metadata = self._make_metadata(command_groups=groups)
        content = generate_skill_md_simple(metadata)
        assert "### Export" in content
        assert "`pdf`" in content
        assert "`svg`" in content

    def test_simple_output_has_examples(self):
        examples = [
            Example(
                title="Quick Start",
                description="Get started quickly",
                code="cli-anything-testapp --help",
            )
        ]
        metadata = self._make_metadata(examples=examples)
        content = generate_skill_md_simple(metadata)
        assert "### Quick Start" in content
        assert "cli-anything-testapp --help" in content

    def test_generate_skill_md_falls_back_to_simple(self):
        metadata = self._make_metadata()
        # Without a template file, should fall back to simple generation
        content = generate_skill_md(metadata, template_path="/nonexistent/template")
        assert "cli-anything-testapp" in content

    def test_generate_skill_md_with_no_template_arg(self):
        metadata = self._make_metadata()
        # Should work without template_path argument (uses default or falls back)
        content = generate_skill_md(metadata)
        assert isinstance(content, str)
        assert len(content) > 0


# ─── generate_skill_file Tests ─────────────────────────────────────────


class TestGenerateSkillFile:
    def test_generates_file_at_default_path(self, harness_dir):
        output = generate_skill_file(str(harness_dir))
        assert Path(output).exists()
        content = Path(output).read_text()
        assert "cli-anything-testapp" in content

    def test_generates_file_at_custom_path(self, harness_dir, tmp_path):
        output_file = tmp_path / "custom" / "SKILL.md"
        output = generate_skill_file(str(harness_dir), str(output_file))
        assert Path(output).exists()
        content = Path(output).read_text()
        assert "testapp" in content.lower()

    def test_creates_parent_directories(self, harness_dir, tmp_path):
        output_file = tmp_path / "deep" / "nested" / "dir" / "SKILL.md"
        output = generate_skill_file(str(harness_dir), str(output_file))
        assert Path(output).exists()


# ─── Edge Case Tests ──────────────────────────────────────────────────


class TestEdgeCases:
    def test_harness_without_readme(self, tmp_path):
        """Harness with no README.md should have empty intro."""
        software = "noreadme"
        cli_pkg = tmp_path / "cli_anything" / software
        cli_pkg.mkdir(parents=True)
        (cli_pkg / "__init__.py").write_text("")
        # No README.md, no setup.py, no CLI file

        metadata = extract_cli_metadata(str(tmp_path))
        assert metadata.software_name == "noreadme"
        assert metadata.skill_intro == ""  # No README → empty intro
        assert metadata.version == "1.0.0"
        assert metadata.command_groups == []
        # skill_description must not contain trailing " - ..." when intro is empty
        assert " - " not in metadata.skill_description
        assert not metadata.skill_description.endswith("...")

    def test_harness_with_system_package(self, tmp_path):
        """README with apt install instructions should extract system_package."""
        software = "syspkg"
        cli_pkg = tmp_path / "cli_anything" / software
        cli_pkg.mkdir(parents=True)
        (cli_pkg / "__init__.py").write_text("")
        (cli_pkg / "README.md").write_text(
            "# Syspkg\n\nInstall via `apt install syspkg-tool`.\n"
        )

        metadata = extract_cli_metadata(str(tmp_path))
        assert metadata.system_package is not None
        assert "syspkg-tool" in metadata.system_package

    def test_malformed_setup_py(self, tmp_path):
        """Malformed setup.py should default to version 1.0.0."""
        software = "badsetup"
        cli_pkg = tmp_path / "cli_anything" / software
        cli_pkg.mkdir(parents=True)
        (cli_pkg / "__init__.py").write_text("")
        (tmp_path / "setup.py").write_text("THIS IS NOT VALID PYTHON { } }")

        metadata = extract_cli_metadata(str(tmp_path))
        assert metadata.version == "1.0.0"

    def test_empty_setup_py(self, tmp_path):
        """Empty setup.py should default to 1.0.0."""
        software = "emptysetup"
        cli_pkg = tmp_path / "cli_anything" / software
        cli_pkg.mkdir(parents=True)
        (cli_pkg / "__init__.py").write_text("")
        (tmp_path / "setup.py").write_text("")

        metadata = extract_cli_metadata(str(tmp_path))
        assert metadata.version == "1.0.0"
