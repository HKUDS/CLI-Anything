"""E2E tests for cli-anything-siyuan.

Requires a running SiYuan instance at http://127.0.0.1:6806.
Set SIYUAN_TOKEN env var if authentication is enabled.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from cli_anything.siyuan.core.client import SiYuanClient, SiYuanClientError, load_config


def _resolve_cli(name: str) -> list[str]:
    """Resolve installed CLI command; falls back to python -m for dev."""
    import shutil
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    module = name.replace("cli-anything-", "cli_anything.")  # e.g. cli_anything.siyuan (has __main__.py)
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m {module}")
    return [sys.executable, "-m", module]


CLI_BASE = _resolve_cli("cli-anything-siyuan")


# ── Fixtures ───────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def client() -> SiYuanClient:
    """Create a client connected to the real SiYuan instance."""
    config = load_config()
    c = SiYuanClient(config)
    if not c.ping():
        pytest.skip("SiYuan is not running — E2E tests require a running instance")
    return c


@pytest.fixture
def tmp_dir() -> Path:
    """Create a temporary directory for test artifacts."""
    import tempfile
    path = Path(tempfile.mkdtemp(prefix="siyuan_e2e_"))
    yield path
    import shutil
    shutil.rmtree(path, ignore_errors=True)


class TestCLISubprocess:
    CLI_BASE = CLI_BASE

    def _run(self, args: list[str], check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(
            self.CLI_BASE + args,
            capture_output=True, text=True, check=check,
        )

    def test_help(self):
        """--help returns 0 and shows usage."""
        result = self._run(["--help"])
        assert result.returncode == 0
        assert "Usage:" in result.stdout
        print(f"\n  --help: OK ({len(result.stdout)} chars)")

    def test_version_json(self, client: SiYuanClient):
        """--json version returns valid JSON with version string."""
        result = self._run(["--json", "version"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "version" in data
        assert data["version"]
        print(f"\n  SiYuan version: {data['version']}")

    def test_status_json(self, client: SiYuanClient):
        """--json status returns valid JSON with connection info."""
        result = self._run(["--json", "status"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "siyuan_version" in data
        assert data["siyuan_version"]
        print(f"\n  Status: connected to SiYuan v{data['siyuan_version']}")


class TestBackendE2E:
    """Tests that hit the real SiYuan API via Python client."""

    def test_get_version(self, client: SiYuanClient):
        """Get the SiYuan kernel version from a running instance."""
        ver = client.get_version()
        assert ver
        assert isinstance(ver, str)
        assert len(ver) > 0
        print(f"\n  SiYuan kernel version: {ver}")

    def test_list_notebooks(self, client: SiYuanClient):
        """List all notebooks from the running instance."""
        notebooks = client.list_notebooks()
        assert isinstance(notebooks, list)
        if notebooks:
            nb = notebooks[0]
            assert "id" in nb
            assert "name" in nb
            print(f"\n  Notebooks found: {len(notebooks)}")
            print(f"  First: {nb['name']} ({nb['id']})")
        else:
            print("\n  No notebooks found (empty instance)")

    def test_get_current_time(self, client: SiYuanClient):
        """Get current time from server."""
        t = client.get_current_time()
        assert t > 0
        assert isinstance(t, int)
        print(f"\n  Server time (ts): {t}")
