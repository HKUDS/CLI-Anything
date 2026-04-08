import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from cli_anything.dify_workflow.dify_workflow_cli import cli
from cli_anything.dify_workflow.utils.dify_workflow_backend import (
    build_command,
    has_upstream_cli,
    require_dify_workflow_command,
)


class TestBackendDiscovery:
    def test_require_command_returns_binary_path(self):
        with patch("cli_anything.dify_workflow.utils.dify_workflow_backend.shutil.which", return_value="/usr/bin/dify-workflow"):
            assert require_dify_workflow_command() == ["/usr/bin/dify-workflow"]

    def test_require_command_falls_back_to_python_module(self):
        with patch("cli_anything.dify_workflow.utils.dify_workflow_backend.shutil.which", return_value=None), patch(
            "cli_anything.dify_workflow.utils.dify_workflow_backend.importlib.util.find_spec",
            return_value=object(),
        ), patch("cli_anything.dify_workflow.utils.dify_workflow_backend.sys.executable", "python"):
            assert require_dify_workflow_command() == ["python", "-m", "dify_workflow.cli"]

    def test_require_command_raises_install_guidance(self):
        with patch("cli_anything.dify_workflow.utils.dify_workflow_backend.shutil.which", return_value=None), patch(
            "cli_anything.dify_workflow.utils.dify_workflow_backend.importlib.util.find_spec",
            return_value=None,
        ):
            with pytest.raises(RuntimeError, match="dify-workflow command not found"):
                require_dify_workflow_command()

    def test_build_command_appends_args(self):
        with patch("cli_anything.dify_workflow.utils.dify_workflow_backend.require_dify_workflow_command", return_value=["dify-workflow"]):
            assert build_command(["guide", "-j"]) == ["dify-workflow", "guide", "-j"]

    def test_has_upstream_cli_false_when_resolution_fails(self):
        with patch("cli_anything.dify_workflow.utils.dify_workflow_backend.require_dify_workflow_command", side_effect=RuntimeError("missing")):
            assert has_upstream_cli() is False


class TestWrapperCLI:
    def test_help_renders(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "CLI-Anything wrapper for the Dify workflow DSL editor" in result.output
        assert "edit" in result.output
        assert "config" in result.output


class TestPackagingFixtures:
    def test_readme_documents_two_step_install(self):
        package_root = Path(__file__).resolve().parents[1]
        readme = (package_root / "README.md").read_text(encoding="utf-8")
        assert "Install the upstream Dify workflow CLI first" in readme
        assert "git+https://github.com/Akabane71/dify-workflow-cli.git@main" in readme

    def test_skill_file_documents_wrapper_behavior(self):
        package_root = Path(__file__).resolve().parents[1]
        skill = (package_root / "skills" / "SKILL.md").read_text(encoding="utf-8")
        assert "wrapper" in skill.lower()
        assert "cli-anything-dify-workflow" in skill
        assert "dify-workflow" in skill
