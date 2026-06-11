"""E2E tests for CC Switch CLI — tests against the real CC Switch database.

These tests require a real CC Switch installation with an active database.
Set env CCSWITCH_HOME to point to a test home directory if needed.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


LIVE_DB_OPT_IN_ENV = "CLI_ANYTHING_CCSWITCH_LIVE_DB"
NO_LIVE_DB_TESTS = {"test_help", "test_providers_help"}


def _live_db_path() -> Path:
    home = Path(os.environ.get("CCSWITCH_HOME", os.path.expanduser("~")))
    return home / ".cc-switch" / "cc-switch.db"


@pytest.fixture(autouse=True)
def _gate_live_db_tests(request):
    if request.node.name in NO_LIVE_DB_TESTS:
        return

    if os.environ.get(LIVE_DB_OPT_IN_ENV) != "1":
        pytest.skip(f"set {LIVE_DB_OPT_IN_ENV}=1 to run live CC Switch DB tests")

    db_path = _live_db_path()
    if not db_path.is_file():
        pytest.skip(f"live CC Switch database not found at {db_path}")


def _resolve_cli(name):
    """Resolve installed CLI command; falls back to python -m for dev."""
    import shutil
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    module = "cli_anything.ccswitch.ccswitch_cli"
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m {module}")
    return [sys.executable, "-m", module]


CLI_BASE = _resolve_cli("cli-anything-ccswitch")


class TestCLISubprocess:
    """Subprocess tests that invoke the real installed CLI command."""

    def _run(self, args, check=True):
        return subprocess.run(
            CLI_BASE + args,
            capture_output=True, text=True,
            check=check,
        )

    # ── help ──

    def test_help(self):
        result = self._run(["--help"])
        assert result.returncode == 0
        assert "CC Switch" in result.stdout

    def test_providers_help(self):
        result = self._run(["providers", "--help"])
        assert result.returncode == 0

    # ── providers ──

    def test_providers_list(self):
        result = self._run(["providers", "list"])
        assert result.returncode == 0
        # Should have table headers
        assert "App" in result.stdout or len(result.stdout) > 0

    def test_providers_list_json(self):
        result = self._run(["--json", "providers", "list"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        if data:
            assert "app_type" in data[0] or "id" in data[0]

    def test_providers_list_filter_claude(self):
        result = self._run(["providers", "list", "--app", "claude"])
        assert result.returncode == 0

    def test_providers_get_nonexistent(self):
        result = self._run(
            ["providers", "get", "__nonexistent__", "--app", "claude"],
            check=False,
        )
        assert result.returncode != 0

    def test_providers_get_no_api_key_leaked(self):
        """Ensure --json output of providers get masks sensitive values."""
        result = self._run(
            ["--json", "providers", "list", "--app", "claude"],
        )
        data = json.loads(result.stdout)
        for prov in data:
            prov_str = json.dumps(prov)
            # No raw API tokens in output
            assert "sk-" not in prov_str.lower() or "sk-" not in prov_str

    # ── skills ──

    def test_skills_list(self):
        result = self._run(["skills", "list"])
        assert result.returncode == 0
        assert "Name" in result.stdout or len(result.stdout) > 0

    def test_skills_list_json(self):
        result = self._run(["--json", "skills", "list"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)

    def test_skills_repos(self):
        result = self._run(["skills", "repos"])
        assert result.returncode == 0

    # ── usage ──

    def test_usage_stats(self):
        result = self._run(["usage", "stats", "--days", "30"])
        assert result.returncode == 0

    def test_usage_stats_json(self):
        result = self._run(["--json", "usage", "stats", "--days", "30"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)

    def test_usage_logs(self):
        result = self._run(["usage", "logs", "--limit", "5"])
        assert result.returncode == 0

    # ── mcp ──

    def test_mcp_list(self):
        result = self._run(["mcp", "list"])
        assert result.returncode == 0

    def test_mcp_list_json(self):
        result = self._run(["--json", "mcp", "list"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)

    # ── settings ──

    def test_settings_list(self):
        result = self._run(["settings", "list"])
        assert result.returncode == 0

    def test_settings_list_json(self):
        result = self._run(["--json", "settings", "list"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, dict)

    # ── proxy ──

    def test_proxy_status(self):
        result = self._run(["proxy", "status", "--app", "claude"])
        assert result.returncode == 0
        assert "127.0.0.1" in result.stdout or "Proxy" in result.stdout

    # ── combined / overview ──

    def test_full_status(self):
        result = self._run([])
        assert result.returncode == 0
        assert "CC Switch" in result.stdout or "Status" in result.stdout

    def test_full_status_json(self):
        result = self._run(["--json"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "providers" in data
        assert isinstance(data["providers"], int)
