"""End-to-end tests for SeaClip CLI.

These tests call the REAL SeaClip-Lite API at localhost:5200.
They require the backend to be running. Skip gracefully if it is not.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import requests

SEACLIP_URL = os.environ.get("SEACLIP_URL", "http://127.0.0.1:5200")


def _backend_available():
    """Check whether the SeaClip-Lite backend is reachable."""
    try:
        r = requests.get(f"{SEACLIP_URL}/health", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


skip_no_backend = pytest.mark.skipif(
    not _backend_available(),
    reason=f"SeaClip-Lite backend not reachable at {SEACLIP_URL}",
)


# ---------------------------------------------------------------------------
# Resolve the CLI binary
# ---------------------------------------------------------------------------

def _resolve_cli(name):
    """Resolve installed CLI command; fall back to python -m for local dev."""
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        return [path], None
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")

    module = "cli_anything.seaclip.seaclip_cli"
    package_root = Path(__file__).resolve().parents[3]
    env = os.environ.copy()
    current = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"{package_root}{os.pathsep}{current}" if current else str(package_root)
    )
    return [sys.executable, "-m", module], env


# ---------------------------------------------------------------------------
# Subprocess helpers
# ---------------------------------------------------------------------------

class TestCLISubprocess:
    """E2E tests that shell out to the real CLI binary."""

    CLI_CMD, CLI_ENV = _resolve_cli("cli-anything-seaclip")

    def _run(self, *args, expect_ok=True):
        """Run the CLI and return (returncode, parsed_json_or_None, raw_stdout)."""
        cmd = self.CLI_CMD + ["--json"] + list(args)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            env=self.CLI_ENV,
        )
        stdout = result.stdout.strip()
        data = None
        if stdout:
            try:
                data = json.loads(stdout)
            except json.JSONDecodeError:
                pass
        if expect_ok:
            assert result.returncode == 0, (
                f"CLI exited {result.returncode}\nstdout: {stdout}\nstderr: {result.stderr}"
            )
        return result.returncode, data, stdout

    # ---- Health ----

    @skip_no_backend
    def test_server_health(self):
        rc, data, _ = self._run("server", "health")
        assert rc == 0
        assert isinstance(data, dict)
        assert "status" in data or "version" in data or data  # any valid response

    # ---- Issues ----

    @skip_no_backend
    def test_issue_list(self):
        rc, data, _ = self._run("issue", "list")
        assert rc == 0
        assert isinstance(data, list)

    @skip_no_backend
    def test_issue_list_with_limit(self):
        rc, data, _ = self._run("issue", "list", "--limit", "3")
        assert rc == 0
        assert isinstance(data, list)
        # Note: the API may not enforce the limit server-side;
        # we only verify the CLI passes the param without error.

    @skip_no_backend
    def test_issue_list_with_status_filter(self):
        rc, data, _ = self._run("issue", "list", "--status", "backlog")
        assert rc == 0
        assert isinstance(data, list)

    # ---- Agents ----

    @skip_no_backend
    def test_agent_list(self):
        rc, data, _ = self._run("agent", "list")
        assert rc == 0
        assert isinstance(data, list)

    # ---- Scheduler ----

    @skip_no_backend
    def test_scheduler_list(self):
        rc, data, _ = self._run("scheduler", "list")
        assert rc == 0
        assert isinstance(data, list)

    # ---- Activity ----

    @skip_no_backend
    def test_activity_list(self):
        rc, data, _ = self._run("activity", "list", "--limit", "5")
        assert rc == 0
        assert isinstance(data, list)
        assert len(data) <= 5

    # ---- Version / Help ----

    def test_version_subprocess(self):
        cmd = self.CLI_CMD + ["--version"]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10, env=self.CLI_ENV,
        )
        assert result.returncode == 0
        assert "1.0.0" in result.stdout

    def test_help_subprocess(self):
        cmd = self.CLI_CMD + ["--help"]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10, env=self.CLI_ENV,
        )
        assert result.returncode == 0
        assert "SeaClip-Lite CLI" in result.stdout

    # ---- Error path (no backend needed) ----

    def test_invalid_subcommand(self):
        cmd = self.CLI_CMD + ["--json", "nonexistent"]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10, env=self.CLI_ENV,
        )
        assert result.returncode != 0
