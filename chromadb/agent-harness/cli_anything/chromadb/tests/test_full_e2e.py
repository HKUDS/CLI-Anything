#!/usr/bin/env python3
"""End-to-end tests for the ChromaDB CLI-Anything harness.

These tests call the REAL ChromaDB server at localhost:8000 via subprocess,
exercising the installed CLI binary. They validate exit codes, JSON output
parsing, and actual server responses.

Requirements:
- ChromaDB running at localhost:8000
- cli-anything-chromadb installed (pip install -e .)
"""

import json
import os
import shutil
import subprocess
import sys

import pytest


# ============================================================================
# Helper: resolve the CLI binary
# ============================================================================

def _resolve_cli():
    """Find the cli-anything-chromadb binary.

    Checks in order:
    1. Installed console_script on PATH
    2. python -m cli_anything.chromadb fallback
    """
    # Check if the console script is on PATH
    cli_path = shutil.which("cli-anything-chromadb")
    if cli_path:
        return [cli_path]
    # Fallback: run as module
    return [sys.executable, "-m", "cli_anything.chromadb"]


CLI = _resolve_cli()


def _run(args, timeout=15):
    """Run the CLI with the given args and return CompletedProcess."""
    cmd = CLI + args
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _chromadb_available():
    """Check if ChromaDB is reachable at localhost:8000."""
    try:
        import requests
        r = requests.get("http://localhost:8000/api/v2/heartbeat", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


# Skip all E2E tests if ChromaDB is not running
pytestmark = pytest.mark.skipif(
    not _chromadb_available(),
    reason="ChromaDB server not available at localhost:8000"
)


# ============================================================================
# 1. CLI basic invocation
# ============================================================================

class TestCLIBasic:
    """Test basic CLI invocation and help."""

    def test_help_returns_zero(self):
        """cli-anything-chromadb --help should exit 0."""
        result = _run(["--help"])
        assert result.returncode == 0
        assert "chromadb" in result.stdout.lower() or "ChromaDB" in result.stdout

    def test_server_help(self):
        """server --help should list subcommands."""
        result = _run(["server", "--help"])
        assert result.returncode == 0
        assert "heartbeat" in result.stdout
        assert "version" in result.stdout

    def test_unknown_command(self):
        """An unknown subcommand should return non-zero."""
        result = _run(["nonexistent-command"])
        assert result.returncode != 0


# ============================================================================
# 2. Server commands (real ChromaDB)
# ============================================================================

class TestServerE2E:
    """Test server heartbeat and version against real ChromaDB."""

    def test_heartbeat_json(self):
        """server heartbeat --json should return valid JSON with heartbeat data."""
        result = _run(["--json", "server", "heartbeat"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, dict)
        # ChromaDB heartbeat returns nanosecond_heartbeat
        assert "nanosecond_heartbeat" in data or len(data) > 0

    def test_version_json(self):
        """server version --json should return valid JSON with version string."""
        result = _run(["--json", "server", "version"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "version" in data
        assert isinstance(data["version"], str)
        assert len(data["version"]) > 0

    def test_heartbeat_human(self):
        """server heartbeat (human mode) should exit 0."""
        result = _run(["server", "heartbeat"])
        assert result.returncode == 0


# ============================================================================
# 3. Collection commands (real ChromaDB)
# ============================================================================

class TestCollectionE2E:
    """Test collection operations against real ChromaDB."""

    def test_collection_list_json(self):
        """collection list --json should return a valid JSON array."""
        result = _run(["--json", "collection", "list"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)

    def test_collection_list_has_names(self):
        """Each collection in the list should have a name field."""
        result = _run(["--json", "collection", "list"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        for col in data:
            assert "name" in col

    def test_collection_info_hub_knowledge(self):
        """collection info hub_knowledge should return info if collection exists."""
        # First check if hub_knowledge exists
        list_result = _run(["--json", "collection", "list"])
        collections = json.loads(list_result.stdout)
        names = [c["name"] for c in collections]

        if "hub_knowledge" not in names:
            pytest.skip("hub_knowledge collection does not exist on this server")

        result = _run(["--json", "collection", "info", "hub_knowledge"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["name"] == "hub_knowledge"
        assert "id" in data

    def test_collection_info_nonexistent(self):
        """collection info for a nonexistent collection should return error."""
        result = _run(["--json", "collection", "info", "nonexistent_collection_xyz_999"])
        assert result.returncode != 0


# ============================================================================
# 4. JSON output validity
# ============================================================================

class TestJSONOutputValidity:
    """Verify that --json flag always produces parseable JSON."""

    def test_heartbeat_json_parseable(self):
        result = _run(["--json", "server", "heartbeat"])
        assert result.returncode == 0
        # Must not raise
        data = json.loads(result.stdout)
        assert data is not None

    def test_version_json_parseable(self):
        result = _run(["--json", "server", "version"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data is not None

    def test_collection_list_json_parseable(self):
        result = _run(["--json", "collection", "list"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data is not None

    def test_error_json_parseable(self):
        """Even errors in --json mode should produce parseable JSON."""
        result = _run(["--json", "collection", "info", "nonexistent_collection_xyz_999"])
        # Should fail but output should still be JSON
        if result.stdout.strip():
            data = json.loads(result.stdout)
            assert "error" in data
