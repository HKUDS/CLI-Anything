"""E2E tests for cli-anything-obsidian — requires Obsidian running with Local REST API plugin.

These tests interact with a real Obsidian instance. Skip if not available.

Usage:
    OBSIDIAN_API_KEY=your-key python -m pytest cli_anything/obsidian/tests/test_full_e2e.py -v
"""

import os
import pytest
from click.testing import CliRunner

from cli_anything.obsidian.utils.obsidian_backend import is_available, DEFAULT_BASE_URL
from cli_anything.obsidian.obsidian_cli import cli

API_KEY = os.environ.get("OBSIDIAN_API_KEY", "")

# Skip all tests if Obsidian REST API is not running
pytestmark = pytest.mark.skipif(
    not API_KEY or not is_available(API_KEY, DEFAULT_BASE_URL),
    reason="Obsidian REST API not available (set OBSIDIAN_API_KEY and ensure Obsidian is running)"
)

TEST_NOTE = "_cli_anything_test_note.md"
TEST_CONTENT = "# Test Note\n\nCreated by cli-anything-obsidian E2E tests."


@pytest.fixture
def runner():
    return CliRunner()


class TestServerE2E:
    def test_server_status(self, runner):
        result = runner.invoke(cli, ["--api-key", API_KEY, "server", "status"])
        assert result.exit_code == 0

    def test_server_status_json(self, runner):
        result = runner.invoke(cli, ["--json", "--api-key", API_KEY, "server", "status"])
        assert result.exit_code == 0
        import json
        data = json.loads(result.output)
        assert "status" in data or "authenticated" in data


class TestVaultE2E:
    def test_vault_list(self, runner):
        result = runner.invoke(cli, ["--json", "--api-key", API_KEY, "vault", "list"])
        assert result.exit_code == 0
        import json
        data = json.loads(result.output)
        assert "files" in data

    def test_vault_create_read_delete(self, runner):
        import json
        # Create
        result = runner.invoke(cli, ["--json", "--api-key", API_KEY, "vault", "create",
                                     TEST_NOTE, "--content", TEST_CONTENT])
        assert result.exit_code == 0

        # Read
        result = runner.invoke(cli, ["--json", "--api-key", API_KEY, "vault", "read", TEST_NOTE])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "Test Note" in data.get("content", "")

        # Delete
        result = runner.invoke(cli, ["--json", "--api-key", API_KEY, "vault", "delete", TEST_NOTE])
        assert result.exit_code == 0

    def test_vault_append(self, runner):
        import json
        # Create note first
        runner.invoke(cli, ["--api-key", API_KEY, "vault", "create",
                           TEST_NOTE, "--content", TEST_CONTENT])
        # Append
        result = runner.invoke(cli, ["--json", "--api-key", API_KEY, "vault", "append",
                                     TEST_NOTE, "--content", "\n\nAppended line."])
        assert result.exit_code == 0
        # Cleanup
        runner.invoke(cli, ["--api-key", API_KEY, "vault", "delete", TEST_NOTE])


class TestSearchE2E:
    def test_search_simple(self, runner):
        result = runner.invoke(cli, ["--json", "--api-key", API_KEY, "search", "simple", "the"])
        assert result.exit_code == 0


class TestNoteTagsDailyE2E:
    def _j(self, runner, *args):
        import json
        r = runner.invoke(cli, ["--json", "--api-key", API_KEY, *args])
        assert r.exit_code == 0, r.output
        return json.loads(r.output)

    def test_note_open_then_active(self, runner):
        self._j(runner, "vault", "create", TEST_NOTE, "--content", TEST_CONTENT)
        self._j(runner, "note", "open", TEST_NOTE)
        import time; time.sleep(0.5)
        assert "Test Note" in self._j(runner, "note", "active")["content"]

    def test_tags_list(self, runner):
        self._j(runner, "vault", "create", TEST_NOTE, "--content", "#clianythingtag")
        import time; time.sleep(1)  # metadata cache indexes asynchronously
        names = [t["name"] for t in self._j(runner, "tags", "list")["tags"]]
        assert "clianythingtag" in names

    def test_daily_cycle(self, runner):
        args = ["--date", "1999-01-02", "--folder", "_cli_daily"]
        assert self._j(runner, "daily", "create", *args)["created"] is True
        assert self._j(runner, "daily", "create", *args)["created"] is False
        self._j(runner, "daily", "append", *args, "--content", "- item")
        assert self._j(runner, "daily", "read", *args)["content"].endswith("\n- item")
        assert "_cli_daily/1999-01-02.md" in self._j(runner, "daily", "list", "--folder", "_cli_daily")["files"]
        self._j(runner, "vault", "delete", "_cli_daily/1999-01-02.md")

    def test_vaults_list(self, runner):
        assert "vaults" in self._j(runner, "vaults", "list")


class TestCleanup:
    def test_cleanup_test_note(self, runner):
        """Clean up test note if it still exists."""
        runner.invoke(cli, ["--api-key", API_KEY, "vault", "delete", TEST_NOTE])
