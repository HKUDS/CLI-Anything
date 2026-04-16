"""CLI smoke tests for the NotebookLM harness scaffold."""

import os
from pathlib import Path
import shutil
import subprocess
import sys

from click.testing import CliRunner

from cli_anything.notebooklm.notebooklm_cli import cli


def _resolve_cli(name):
    """Resolve installed CLI command; fall back to python -m for local dev."""
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        return [path], None
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")

    module = "cli_anything.notebooklm.notebooklm_cli"
    package_root = Path(__file__).resolve().parents[3]
    env = os.environ.copy()
    current = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"{package_root}{os.pathsep}{current}" if current else str(package_root)
    )
    return [sys.executable, "-m", module], env


class TestRootHelp:
    def test_root_help_shows_experimental_notebooklm(self):
        result = CliRunner().invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "NotebookLM CLI" in result.output
        assert "Experimental" in result.output

    def test_root_help_lists_command_groups(self):
        result = CliRunner().invoke(cli, ["--help"])
        assert result.exit_code == 0
        for group in ["auth", "notebook", "source", "chat", "artifact", "download", "share"]:
            assert group in result.output


class TestSubcommandHelp:
    def test_auth_status_help(self):
        result = CliRunner().invoke(cli, ["auth", "status", "--help"])
        assert result.exit_code == 0
        assert "Check authentication status" in result.output

    def test_notebook_list_help(self):
        result = CliRunner().invoke(cli, ["notebook", "list", "--help"])
        assert result.exit_code == 0
        assert "List notebooks" in result.output


class TestCommandRouting:
    def test_auth_status_routes_to_auth_check(self, monkeypatch):
        calls = []

        def fake_run(args, **kwargs):
            calls.append((args, kwargs))
            return {"ok": True}

        monkeypatch.setattr(
            "cli_anything.notebooklm.notebooklm_cli.run_notebooklm",
            fake_run,
        )

        result = CliRunner().invoke(cli, ["auth", "status"])

        assert result.exit_code == 0
        assert calls == [(["auth", "check"], {"json_output": False})]


class TestModuleExecution:
    def test_python_m_module_help_emits_output(self):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "cli_anything.notebooklm.notebooklm_cli",
                "--help",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        assert "NotebookLM CLI" in result.stdout

    def test_resolved_cli_help_emits_output(self):
        command, env = _resolve_cli("cli-anything-notebooklm")
        result = subprocess.run(
            command + ["--help"],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        assert result.returncode == 0
        assert "NotebookLM CLI" in result.stdout
        assert "auth" in result.stdout
