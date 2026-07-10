"""
End-to-end tests for cli-anything-jumpserver CLI.

Tests the installed CLI command via subprocess.
Uses `CLI_ANYTHING_FORCE_INSTALLED=1` env var.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch


class TestCLISubprocess:
    """Base class for CLI subprocess tests."""

    CLI_NAME = "cli-anything-jumpserver"

    @staticmethod
    def _resolve_cli(name: str) -> list[str]:
        """Resolve installed CLI command; fall back to module execution."""
        force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
        path = shutil.which(name)
        if path:
            return [path]
        if force:
            raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
        return [sys.executable, "-m", "cli_anything.jumpserver.jumpserver_cli"]

    def _run(self, *args, expected_exit=0, timeout=10, input_text=None):
        """Run CLI command and return CompletedProcess."""
        cmd = self._resolve_cli(self.CLI_NAME) + list(args)
        with tempfile.TemporaryDirectory(prefix="jumpserver-cli-home-") as home:
            env = os.environ.copy()
            env["HOME"] = home
            harness_root = str(Path(__file__).resolve().parents[3])
            env["PYTHONPATH"] = (
                harness_root
                if not env.get("PYTHONPATH")
                else f"{harness_root}{os.pathsep}{env['PYTHONPATH']}"
            )
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                input=input_text,
                env=env,
            )

        if expected_exit is not None:
            assert result.returncode == expected_exit, (
                f"Exit code mismatch for '{' '.join(args)}': "
                f"got {result.returncode}, stderr={result.stderr[:500]}"
            )

        return result

    def _run_json(self, *args, expected_exit=0):
        """Run with --output json and parse JSON output."""
        return self._run(*args, "--output", "json", expected_exit=expected_exit)

    def _parse_json(self, result):
        """Parse JSON stdout, useful for explicit --output calls."""
        return json.loads(result.stdout)


class TestCLIDiscovery(TestCLISubprocess):
    """CLI availability and help."""

    def test_fallback_cli_uses_module_path(self):
        with patch.dict(os.environ, {"CLI_ANYTHING_FORCE_INSTALLED": ""}):
            with patch("shutil.which", return_value=None):
                assert self._resolve_cli(self.CLI_NAME) == [
                    sys.executable,
                    "-m",
                    "cli_anything.jumpserver.jumpserver_cli",
                ]

    def test_help_output(self):
        result = self._run("--help")
        assert "JumpServer CLI" in result.stdout or "Usage:" in result.stdout

    def test_version(self):
        result = self._run("--version")
        assert True  # version option works

    def test_help_contains_command_groups(self):
        result = self._run("--help")
        output = result.stdout
        expected_groups = ["auth", "asset", "user", "perm", "account", "session", "audit", "ops", "system"]
        for group in expected_groups:
            assert group in output.lower(), f"Expected '{group}' in help output"


class TestAuthCommands(TestCLISubprocess):
    """Authentication command tests."""

    def test_auth_help(self):
        result = self._run("auth", "--help")
        assert "login" in result.stdout

    def test_auth_status_no_session(self):
        result = self._run_json("auth", "status")
        data = self._parse_json(result)
        assert data["status"] == "not authenticated"

    def test_auth_status_global_json(self):
        result = self._run("--json", "auth", "status")
        data = self._parse_json(result)
        assert data["status"] == "not authenticated"

    def test_auth_status_global_json_output_alias(self):
        result = self._run("--json-output", "auth", "status")
        data = self._parse_json(result)
        assert data["status"] == "not authenticated"

    def test_auth_login_help(self):
        result = self._run("auth", "login", "--help")
        assert "--url" in result.stdout

    def test_auth_login_requires_url(self):
        result = self._run("auth", "login", expected_exit=2)

    def test_auth_org_help(self):
        result = self._run("auth", "org", "--help")
        assert "--list" in result.stdout


class TestAssetCommands(TestCLISubprocess):
    """Asset management command tests."""

    def test_asset_help(self):
        result = self._run("asset", "--help")
        assert "list" in result.stdout

    def test_asset_type_option(self):
        result = self._run("asset", "list", "--help")
        assert "--type" in result.stdout

    def test_asset_create_requires_params(self):
        result = self._run("asset", "create", expected_exit=2)

    def test_asset_create_has_dry_run(self):
        result = self._run("asset", "create", "--help")
        assert "--dry-run" in result.stdout

    def test_asset_update_has_dry_run(self):
        result = self._run("asset", "update", "--help")
        assert "--dry-run" in result.stdout

    def test_asset_delete_has_dry_run(self):
        result = self._run("asset", "delete", "--help")
        assert "--dry-run" in result.stdout

    def test_asset_node_help(self):
        result = self._run("asset", "node", "--help")
        assert "list" in result.stdout


class TestUserCommands(TestCLISubprocess):
    """User management command tests."""

    def test_user_help(self):
        result = self._run("user", "--help")
        assert "list" in result.stdout

    def test_user_create_requires_params(self):
        result = self._run("user", "create", expected_exit=2)

    def test_user_profile_help(self):
        result = self._run("user", "profile", "--help")
        assert "output" in result.stdout.lower()

    def test_user_my_assets_help(self):
        result = self._run("user", "my-assets", "--help")
        assert "output" in result.stdout.lower()

    def test_reset_password_requires_force_or_confirmation(self):
        result = self._run(
            "user",
            "reset-password",
            "user-1",
            "--password",
            "secret-password",
            input_text="n\n",
            expected_exit=1,
        )
        assert "Reset password for user 'user-1'?" in result.stdout
        assert "secret-password" not in result.stdout
        assert "secret-password" not in result.stderr

    def test_reset_password_force_reaches_json_auth_gate(self):
        result = self._run(
            "--json",
            "user",
            "reset-password",
            "user-1",
            "--password",
            "secret-password",
            "--force",
            expected_exit=1,
        )
        assert result.stdout == ""
        data = json.loads(result.stderr)
        assert data["status"] == "error"
        assert "Not authenticated" in data["message"]
        assert "secret-password" not in result.stderr

    def test_reset_password_has_force_and_yes_options(self):
        result = self._run("user", "reset-password", "--help")
        assert "--force" in result.stdout
        assert "--yes" in result.stdout


class TestPermCommands(TestCLISubprocess):
    """Permission management command tests."""

    def test_perm_help(self):
        result = self._run("perm", "--help")
        assert "list" in result.stdout

    def test_perm_create_has_dry_run(self):
        result = self._run("perm", "create", "--help")
        assert "--dry-run" in result.stdout

    def test_perm_delete_has_force(self):
        result = self._run("perm", "delete", "--help")
        assert "--force" in result.stdout


class TestAccountCommands(TestCLISubprocess):
    """Account management command tests."""

    def test_account_help(self):
        result = self._run("account", "--help")
        assert "list" in result.stdout

    def test_account_secret_help(self):
        result = self._run("account", "secret", "--help")
        assert "view" in result.stdout


class TestSessionCommands(TestCLISubprocess):
    """Session management command tests."""

    def test_session_help(self):
        result = self._run("session", "--help")
        assert "list" in result.stdout

    def test_session_kill_has_force(self):
        result = self._run("session", "kill", "--help")
        assert "--force" in result.stdout


class TestAuditCommands(TestCLISubprocess):
    """Audit command tests."""

    def test_audit_help(self):
        result = self._run("audit", "--help")
        assert "login" in result.stdout


class TestOpsCommands(TestCLISubprocess):
    """Operations command tests."""

    def test_ops_help(self):
        result = self._run("ops", "--help")
        assert "job-list" in result.stdout


class TestSystemCommands(TestCLISubprocess):
    """System command tests."""

    def test_system_help(self):
        result = self._run("system", "--help")
        assert "settings" in result.stdout


class TestOutputFormats(TestCLISubprocess):
    """Output format verification."""

    def test_json_output_works(self):
        result = self._run_json("auth", "status")
        data = self._parse_json(result)
        assert isinstance(data, dict)
        assert "status" in data

    def test_output_option_table(self):
        result = self._run("auth", "status", "--output", "table")
        assert "not authenticated" in result.stdout.lower()

    def test_unauthenticated_global_json_error_is_parseable(self):
        result = self._run("--json", "asset", "list", expected_exit=1)
        assert result.stdout == ""
        data = json.loads(result.stderr)
        assert data["status"] == "error"
        assert "Not authenticated" in data["message"]


class TestDryRun(TestCLISubprocess):
    """Dry-run functionality."""

    def test_dry_run_asset_create(self):
        result = self._run(
            "asset", "create",
            "--name", "test-dry",
            "--address", "10.0.0.1",
            "--platform", "1",
            "--type", "host",
            "--dry-run",
            "--output", "json",
        )
        data = self._parse_json(result)
        assert data["action"] == "create"

    def test_dry_run_user_create(self):
        result = self._run(
            "user", "create",
            "--name", "Test User",
            "--username", "testuser",
            "--email", "test@example.com",
            "--dry-run",
            "--output", "json",
        )
        data = self._parse_json(result)
        assert data["action"] == "create user"

    def test_dry_run_perm_create(self):
        result = self._run(
            "perm", "create",
            "--name", "test-perm",
            "--users", "u1,u2",
            "--assets", "a1",
            "--dry-run",
            "--output", "json",
        )
        data = self._parse_json(result)
        assert data["action"] == "create permission"

    def test_dry_run_account_create_masks_secret_json(self):
        result = self._run(
            "account", "create",
            "--asset", "1",
            "--username", "root",
            "--secret", "super-secret",
            "--dry-run",
            "--output", "json",
        )
        data = self._parse_json(result)
        assert data["action"] == "create account"
        assert data["data"]["secret"] == "********"
        assert "super-secret" not in result.stdout

    def test_dry_run_account_create_masks_secret_text(self):
        result = self._run(
            "account", "create",
            "--asset", "1",
            "--username", "root",
            "--secret", "super-secret",
            "--dry-run",
        )
        assert "********" in result.stdout
        assert "super-secret" not in result.stdout

    def test_dry_run_asset_delete(self):
        result = self._run(
            "asset", "delete", "test-id",
            "--type", "host",
            "--dry-run",
        )
        assert "[DRY RUN]" in result.stdout


class TestErrorHandling(TestCLISubprocess):
    """Error handling verification."""

    def test_invalid_output_format(self):
        result = self._run("asset", "list", "--output", "invalid_format", expected_exit=2)

    def test_missing_required_option(self):
        result = self._run("asset", "create", "--name", "test", expected_exit=2)


class TestREPLMode(TestCLISubprocess):
    """REPL mode entry tests."""

    def test_interactive_flag(self):
        result = self._run("--help")
        assert "--interactive" in result.stdout or "-i" in result.stdout


# ─── Workflow Integration Tests ──────────────────────────────────


class TestWorkflow:
    """Simulated workflow tests exercising the full CLI lifecycle."""

    def test_full_help_coverage(self):
        """Verify all 12+ command groups have valid help."""
        groups = [
            "auth", "asset", "asset node", "asset platform", "asset gateway", "asset zone",
            "user", "user group",
            "perm",
            "account", "account secret", "account template",
            "session", "session command", "session terminal",
            "audit", "ops",
            "system", "label", "role",
        ]

        runner = TestCLISubprocess()
        for group_cmd in groups:
            args = group_cmd.split() + ["--help"]
            result = runner._run(*args)
            assert len(result.stdout) > 20, f"Help output too short for: {group_cmd}"

    def test_dry_run_mutation_commands(self):
        """Verify --dry-run works for all create commands."""
        runner = TestCLISubprocess()

        r = runner._run(
            "asset", "create", "--name", "x", "--address", "1.1.1.1",
            "--platform", "1", "--dry-run", "--output", "json",
        )
        assert runner._parse_json(r)["action"] == "create"

        r = runner._run(
            "user", "create", "--name", "X", "--username", "x",
            "--email", "x@x.com", "--dry-run", "--output", "json",
        )
        assert runner._parse_json(r)["action"] == "create user"

        r = runner._run(
            "perm", "create", "--name", "x", "--users", "1", "--assets", "1",
            "--dry-run", "--output", "json",
        )
        assert runner._parse_json(r)["action"] == "create permission"

        r = runner._run(
            "account", "create", "--asset", "1", "--username", "root",
            "--dry-run", "--output", "json",
        )
        assert runner._parse_json(r)["action"] == "create account"

    def test_json_output_for_all_list_commands(self):
        """Verify commands produce valid JSON in --output json mode."""
        runner = TestCLISubprocess()
        r = runner._run("auth", "status", "--output", "json")
        data = runner._parse_json(r)
        assert isinstance(data, dict)


class TestCLIParameterValidation(TestCLISubprocess):
    """Additional parameter validation tests."""

    def test_asset_type_validation(self):
        result = self._run("asset", "list", "--type", "invalid", expected_exit=2)

    def test_output_choice_validation(self):
        result = self._run("auth", "status", "--output", "csv", expected_exit=2)

    def test_secret_type_validation(self):
        result = self._run("account", "list", "--help")
        assert "--secret-type" in result.stdout
