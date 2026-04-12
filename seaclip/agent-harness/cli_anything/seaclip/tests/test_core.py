"""Unit tests for SeaClip CLI core modules.

All HTTP and SQLite calls are mocked -- no live backend required.
"""

import json
import os
import sys

import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from cli_anything.seaclip.seaclip_cli import cli
from cli_anything.seaclip.utils.seaclip_backend import SeaClipBackend


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def invoke(*args):
    """Invoke the CLI with --json and return the CliRunner result."""
    runner = CliRunner()
    return runner.invoke(cli, list(args), catch_exceptions=False)


def invoke_json(*args):
    """Invoke the CLI with --json flag and parse the output as JSON."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--json"] + list(args), catch_exceptions=False)
    return result, json.loads(result.output) if result.output.strip() else None


# ===========================================================================
# 1. Backend unit tests
# ===========================================================================

class TestBackendURLConstruction:
    """Verify SeaClipBackend builds correct URLs."""

    def test_default_base_url(self):
        b = SeaClipBackend()
        assert b.base_url == "http://127.0.0.1:5200"

    def test_custom_base_url(self):
        b = SeaClipBackend(base_url="http://myhost:9000/")
        assert b.base_url == "http://myhost:9000"  # trailing slash stripped

    def test_url_helper(self):
        b = SeaClipBackend(base_url="http://localhost:5200")
        assert b._url("/health") == "http://localhost:5200/health"

    def test_env_var_url(self, monkeypatch):
        monkeypatch.setenv("SEACLIP_URL", "http://envhost:1234")
        b = SeaClipBackend()
        assert b.base_url == "http://envhost:1234"


# ===========================================================================
# 2. JSON output format tests
# ===========================================================================

class TestJSONOutput:
    """Verify --json flag produces valid JSON for every command group."""

    @patch.object(SeaClipBackend, "health", return_value={"status": "ok", "version": "1.0"})
    def test_server_health_json(self, mock_health):
        result, data = invoke_json("server", "health")
        assert result.exit_code == 0
        assert data["status"] == "ok"

    @patch.object(SeaClipBackend, "list_issues", return_value=[
        {"id": "abc-123", "title": "Bug", "status": "backlog", "priority": "high"}
    ])
    def test_issue_list_json(self, mock_list):
        result, data = invoke_json("issue", "list")
        assert result.exit_code == 0
        assert isinstance(data, list)
        assert data[0]["title"] == "Bug"

    @patch.object(SeaClipBackend, "create_issue", return_value={"id": "new-uuid", "title": "Task"})
    def test_issue_create_json(self, mock_create):
        result, data = invoke_json("issue", "create", "--title", "Task")
        assert result.exit_code == 0
        assert data["id"] == "new-uuid"

    @patch.object(SeaClipBackend, "list_agents", return_value=[
        {"name": "triage", "role": "triage", "status": "idle"}
    ])
    def test_agent_list_json(self, mock_agents):
        result, data = invoke_json("agent", "list")
        assert result.exit_code == 0
        assert isinstance(data, list)
        assert data[0]["name"] == "triage"

    @patch.object(SeaClipBackend, "list_schedules", return_value=[
        {"id": 1, "repo": "org/repo", "enabled": True}
    ])
    def test_scheduler_list_json(self, mock_sched):
        result, data = invoke_json("scheduler", "list")
        assert result.exit_code == 0
        assert isinstance(data, list)

    @patch.object(SeaClipBackend, "list_activity", return_value=[
        {"event_type": "issue_created", "summary": "New issue", "created_at": "2026-03-23T10:00:00"}
    ])
    def test_activity_list_json(self, mock_act):
        result, data = invoke_json("activity", "list", "--limit", "5")
        assert result.exit_code == 0
        assert isinstance(data, list)


# ===========================================================================
# 3. Human-readable output tests
# ===========================================================================

class TestHumanOutput:
    """Verify non-JSON output works without crashing."""

    @patch.object(SeaClipBackend, "list_issues", return_value=[
        {"id": "abc", "title": "Bug", "status": "backlog", "priority": "high"}
    ])
    def test_issue_list_human(self, mock_list):
        result = invoke("issue", "list")
        assert result.exit_code == 0

    @patch.object(SeaClipBackend, "list_issues", return_value=[])
    def test_issue_list_empty_human(self, mock_list):
        result = invoke("issue", "list")
        assert result.exit_code == 0


# ===========================================================================
# 4. CLI argument parsing tests
# ===========================================================================

class TestCLIArgParsing:
    """Verify Click argument/option parsing for each command group."""

    @patch.object(SeaClipBackend, "list_issues", return_value=[])
    def test_issue_list_with_filters(self, mock_list):
        result, _ = invoke_json("issue", "list", "--status", "backlog", "--priority", "high", "--limit", "5")
        assert result.exit_code == 0
        mock_list.assert_called_once_with(status="backlog", priority="high", search=None, limit=5)

    @patch.object(SeaClipBackend, "move_issue", return_value={"ok": True})
    def test_issue_move_requires_column(self, mock_move):
        result, data = invoke_json("issue", "move", "abc-123", "--column", "done")
        assert result.exit_code == 0
        mock_move.assert_called_once_with("abc-123", "done")

    def test_issue_move_missing_column_fails(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "issue", "move", "abc-123"])
        assert result.exit_code != 0

    @patch.object(SeaClipBackend, "start_pipeline", return_value={"started": True})
    def test_pipeline_start_mode(self, mock_start):
        result, data = invoke_json("pipeline", "start", "--issue", "uuid-1", "--mode", "manual")
        assert result.exit_code == 0
        mock_start.assert_called_once_with("uuid-1", mode="manual")

    def test_pipeline_start_invalid_mode(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "pipeline", "start", "--issue", "x", "--mode", "bogus"])
        assert result.exit_code != 0

    @patch.object(SeaClipBackend, "list_activity", return_value=[])
    def test_activity_default_limit(self, mock_act):
        result, _ = invoke_json("activity", "list")
        assert result.exit_code == 0
        mock_act.assert_called_once_with(limit=20)

    @patch.object(SeaClipBackend, "add_schedule", return_value={"id": 1})
    def test_scheduler_add_parsing(self, mock_add):
        result, data = invoke_json("scheduler", "add", "--name", "nightly", "--cron", "0 2 * * *")
        assert result.exit_code == 0
        mock_add.assert_called_once_with({"name": "nightly", "cron": "0 2 * * *"})


# ===========================================================================
# 5. Error handling tests
# ===========================================================================

class TestErrorHandling:
    """Verify error paths produce JSON error objects and non-zero exit."""

    @patch.object(SeaClipBackend, "health", side_effect=ConnectionError("Connection refused"))
    def test_server_health_connection_error(self, mock_health):
        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "server", "health"])
        assert result.exit_code != 0
        data = json.loads(result.output)
        assert "error" in data
        assert "Connection refused" in data["error"]

    @patch.object(SeaClipBackend, "list_issues", side_effect=Exception("timeout"))
    def test_issue_list_error(self, mock_list):
        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "issue", "list"])
        assert result.exit_code != 0
        data = json.loads(result.output)
        assert "error" in data

    @patch.object(SeaClipBackend, "list_agents", side_effect=Exception("DB locked"))
    def test_agent_list_error(self, mock_agents):
        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "agent", "list"])
        assert result.exit_code != 0
        data = json.loads(result.output)
        assert "DB locked" in data["error"]

    def test_unknown_command(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "nonexistent"])
        assert result.exit_code != 0

    def test_version_flag(self):
        result = invoke("--version")
        assert result.exit_code == 0
        assert "1.0.0" in result.output

    def test_help_flag(self):
        result = invoke("--help")
        assert result.exit_code == 0
        assert "SeaClip-Lite CLI" in result.output
