"""E2E and subprocess tests for cli-anything-adguardhome.

Subprocess tests work without AdGuardHome (test CLI mechanics).
Docker tests require: docker pull adguard/adguardhome
"""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests


# ---------------------------------------------------------------------------
# CLI resolver
# ---------------------------------------------------------------------------

def _resolve_cli(name: str) -> list[str]:
    """Resolve installed CLI command; falls back to python -m for dev.

    Set env CLI_ANYTHING_FORCE_INSTALLED=1 to require the installed command.
    """
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(
            f"{name} not found in PATH. Install with:\n"
            f"  cd agent-harness && pip install -e ."
        )
    module = "cli_anything.adguardhome.adguardhome_cli"
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m {module}")
    return [sys.executable, "-m", module]


# ---------------------------------------------------------------------------
# Docker fixture
# ---------------------------------------------------------------------------

AGH_TEST_PORT = 3001
AGH_TEST_HOST = "localhost"
AGH_CONTAINER = "agh-cli-test"


def _wait_for_adguardhome(port: int, timeout: int = 30) -> bool:
    """Wait until AdGuardHome API responds."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(f"http://localhost:{port}/control/status", timeout=2)
            if r.status_code in (200, 401, 403):
                return True
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(1)
    return False


def _configure_adguardhome(port: int, username: str, password: str) -> bool:
    """Run the setup wizard via the install API."""
    url = f"http://localhost:{port}/control/install/configure"
    payload = {
        "web": {"ip": "0.0.0.0", "port": 3000, "status": "", "can_autofix": False},
        "dns": {"ip": "0.0.0.0", "port": 53, "status": "", "can_autofix": False},
        "username": username,
        "password": password,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        return False


@pytest.fixture(scope="module")
def agh_docker():
    """Start AdGuardHome in Docker for E2E tests, configure via install API."""
    username = "admin"
    password = "admin123"

    # Stop any existing container
    subprocess.run(["docker", "rm", "-f", AGH_CONTAINER], capture_output=True)

    # Start AdGuardHome container (no config mount - will use install API)
    result = subprocess.run([
        "docker", "run", "-d",
        "--name", AGH_CONTAINER,
        "-p", f"{AGH_TEST_PORT}:3000",
        "--cap-add=NET_ADMIN",
        "adguard/adguardhome",
    ], capture_output=True, text=True)

    if result.returncode != 0:
        pytest.skip(f"Could not start AdGuardHome Docker: {result.stderr}")

    # Wait for setup wizard to be available
    deadline = time.time() + 30
    setup_ready = False
    while time.time() < deadline:
        try:
            r = requests.get(f"http://localhost:{AGH_TEST_PORT}/control/install/get_addresses",
                             timeout=2)
            if r.status_code == 200:
                setup_ready = True
                break
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(1)

    if not setup_ready:
        subprocess.run(["docker", "rm", "-f", AGH_CONTAINER], capture_output=True)
        pytest.skip("AdGuardHome setup wizard not reachable in time")

    # Run setup wizard
    if not _configure_adguardhome(AGH_TEST_PORT, username, password):
        subprocess.run(["docker", "rm", "-f", AGH_CONTAINER], capture_output=True)
        pytest.skip("Could not configure AdGuardHome via install API")

    # Wait for configured instance to be ready
    if not _wait_for_adguardhome(AGH_TEST_PORT, timeout=20):
        subprocess.run(["docker", "rm", "-f", AGH_CONTAINER], capture_output=True)
        pytest.skip("AdGuardHome not ready after configuration")

    print(f"\n  AdGuardHome running at localhost:{AGH_TEST_PORT} (admin/admin123)")

    yield {"host": AGH_TEST_HOST, "port": AGH_TEST_PORT,
           "username": username, "password": password}

    subprocess.run(["docker", "rm", "-f", AGH_CONTAINER], capture_output=True)


# ---------------------------------------------------------------------------
# Subprocess tests (no AdGuardHome needed)
# ---------------------------------------------------------------------------

class TestCLISubprocess:
    CLI_BASE = _resolve_cli("cli-anything-adguardhome")

    def _run(self, args: list[str], check: bool = True, env: dict | None = None) -> subprocess.CompletedProcess:
        run_env = os.environ.copy()
        if env:
            run_env.update(env)
        return subprocess.run(
            self.CLI_BASE + args,
            capture_output=True, text=True,
            check=check,
            env=run_env,
        )

    def test_help(self):
        result = self._run(["--help"])
        assert result.returncode == 0
        assert "adguardhome" in result.stdout.lower() or "Usage" in result.stdout

    def test_config_show_json(self):
        result = self._run(["--json", "config", "show"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "host" in data
        assert "port" in data

    def test_config_show_default_host(self):
        result = self._run(["--json", "config", "show"])
        data = json.loads(result.stdout)
        assert data["host"] == "localhost"
        assert data["port"] == 3000

    def test_help_subcommands_listed(self):
        result = self._run(["--help"])
        assert "filter" in result.stdout
        assert "server" in result.stdout
        assert "stats" in result.stdout

    def test_filter_help(self):
        result = self._run(["filter", "--help"])
        assert result.returncode == 0
        assert "list" in result.stdout

    def test_rewrite_help(self):
        result = self._run(["rewrite", "--help"])
        assert result.returncode == 0

    def test_blocking_help(self):
        result = self._run(["blocking", "--help"])
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# Docker E2E tests
# ---------------------------------------------------------------------------

class TestDockerE2E:
    CLI_BASE = _resolve_cli("cli-anything-adguardhome")

    def _run_agh(self, args: list[str], agh: dict, check: bool = True) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env["AGH_HOST"] = agh["host"]
        env["AGH_PORT"] = str(agh["port"])
        env["AGH_USERNAME"] = agh["username"]
        env["AGH_PASSWORD"] = agh["password"]
        return subprocess.run(
            self.CLI_BASE + args,
            capture_output=True, text=True,
            check=check,
            env=env,
        )

    def test_server_status_json(self, agh_docker):
        result = self._run_agh(["--json", "server", "status"], agh_docker)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        print(f"\n  Server status: {data}")
        assert isinstance(data, dict)

    def test_filter_list_json(self, agh_docker):
        result = self._run_agh(["--json", "filter", "list"], agh_docker)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        print(f"\n  Filters: {data}")
        assert "filters" in data or isinstance(data, dict)

    def test_rewrite_lifecycle(self, agh_docker):
        """Add rewrite, verify in list, remove, verify gone."""
        # Add
        add_result = self._run_agh([
            "--json", "rewrite", "add",
            "--domain", "test-cli.local", "--answer", "10.0.0.99"
        ], agh_docker)
        assert add_result.returncode == 0
        print(f"\n  Rewrite add: {add_result.stdout.strip()}")

        # List and verify
        list_result = self._run_agh(["--json", "rewrite", "list"], agh_docker)
        assert list_result.returncode == 0
        rewrites = json.loads(list_result.stdout)
        print(f"\n  Rewrites: {rewrites}")
        domains = [r.get("domain") for r in (rewrites if isinstance(rewrites, list) else [])]
        assert "test-cli.local" in domains

        # Remove
        rm_result = self._run_agh([
            "--json", "rewrite", "remove",
            "--domain", "test-cli.local", "--answer", "10.0.0.99"
        ], agh_docker)
        assert rm_result.returncode == 0

        # Verify removed
        list_result2 = self._run_agh(["--json", "rewrite", "list"], agh_docker)
        rewrites2 = json.loads(list_result2.stdout)
        domains2 = [r.get("domain") for r in (rewrites2 if isinstance(rewrites2, list) else [])]
        assert "test-cli.local" not in domains2
        print(f"\n  Rewrite lifecycle: PASS")

    def test_stats_show_json(self, agh_docker):
        result = self._run_agh(["--json", "stats", "show"], agh_docker)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        print(f"\n  Stats keys: {list(data.keys()) if isinstance(data, dict) else 'list'}")
        assert isinstance(data, dict)

    def test_config_test(self, agh_docker):
        result = self._run_agh(["--json", "config", "test"], agh_docker)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        print(f"\n  Config test: {data}")
        assert data.get("connected") is True
