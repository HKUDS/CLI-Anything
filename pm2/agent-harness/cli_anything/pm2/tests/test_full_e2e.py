"""End-to-end tests for the PM2 CLI-Anything harness.

These tests call the REAL pm2 binary and the installed cli-anything-pm2
CLI. They require:
  - pm2 installed globally (npm install -g pm2)
  - cli-anything-pm2 installed (pip install -e .)
  - PM2 daemon running with at least one process

Skip gracefully if pm2 is not available.
"""

import json
import os
import shutil
import subprocess
import sys

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_cli() -> str:
    """Resolve the cli-anything-pm2 binary path.

    Checks: shutil.which, then common venv/bin locations.
    """
    binary = shutil.which("cli-anything-pm2")
    if binary:
        return binary

    # Try the venv bin dir that matches the running Python
    venv_bin = os.path.join(os.path.dirname(sys.executable), "cli-anything-pm2")
    if os.path.isfile(venv_bin):
        return venv_bin

    pytest.skip("cli-anything-pm2 binary not found on PATH")


def _has_pm2() -> bool:
    """Check whether pm2 is installed."""
    return shutil.which("pm2") is not None


def _run_cli(*args: str, timeout: int = 30) -> subprocess.CompletedProcess:
    """Run cli-anything-pm2 with the given arguments."""
    cli = _resolve_cli()
    cmd = [cli, *args]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


# Skip entire module if pm2 is not installed
pytestmark = pytest.mark.skipif(
    not _has_pm2(),
    reason="pm2 is not installed -- skipping E2E tests",
)


# ===========================================================================
# E2E Tests
# ===========================================================================

class TestProcessListE2E:
    """E2E tests for the process list command."""

    def test_process_list_json_returns_valid_json(self):
        """cli-anything-pm2 --json process list outputs parseable JSON."""
        result = _run_cli("--json", "process", "list")
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        assert isinstance(data, list)

    def test_process_list_human_returns_zero(self):
        """cli-anything-pm2 process list exits 0."""
        result = _run_cli("process", "list")
        assert result.returncode == 0


class TestProcessDescribeE2E:
    """E2E tests for process describe."""

    def test_describe_existing_process_json(self):
        """Describe a known process and get valid JSON."""
        # First get list to find an actual process name
        list_result = _run_cli("--json", "process", "list")
        if list_result.returncode != 0:
            pytest.skip("Could not list processes")
        processes = json.loads(list_result.stdout)
        if not processes:
            pytest.skip("No PM2 processes running")

        # Pick first process
        name = processes[0].get("name") or str(processes[0].get("pm_id", 0))
        result = _run_cli("--json", "process", "describe", name)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, dict)

    def test_describe_nonexistent_process(self):
        """Describe a process that does not exist exits with code 1."""
        result = _run_cli("--json", "process", "describe", "__nonexistent_process_xyz__")
        assert result.returncode != 0


class TestSystemE2E:
    """E2E tests for system commands."""

    def test_system_version_json(self):
        """cli-anything-pm2 --json system version returns valid JSON with version key."""
        result = _run_cli("--json", "system", "version")
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        assert "version" in data
        # PM2 version is a semver string like "5.3.0"
        assert len(data["version"]) > 0

    def test_system_version_human(self):
        """cli-anything-pm2 system version returns a version string."""
        result = _run_cli("system", "version")
        assert result.returncode == 0
        # Should contain at least a digit (version number)
        assert any(c.isdigit() for c in result.stdout)


class TestHelpE2E:
    """E2E tests for help output."""

    def test_help_flag_exits_zero(self):
        """cli-anything-pm2 --help exits with code 0."""
        result = _run_cli("--help")
        assert result.returncode == 0
        assert "CLI-Anything PM2" in result.stdout or "Usage" in result.stdout

    def test_process_help(self):
        """cli-anything-pm2 process --help shows subcommands."""
        result = _run_cli("process", "--help")
        assert result.returncode == 0
        assert "list" in result.stdout
        assert "describe" in result.stdout


class TestProcessMetricsE2E:
    """E2E test for process metrics."""

    def test_metrics_json_returns_list(self):
        """cli-anything-pm2 --json process metrics returns a JSON list."""
        result = _run_cli("--json", "process", "metrics")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
