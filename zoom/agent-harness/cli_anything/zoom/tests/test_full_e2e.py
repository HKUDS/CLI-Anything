"""End-to-end tests for Zoom CLI — requires actual Zoom OAuth credentials.

These tests make real API calls to the Zoom API. They require:
1. A Zoom account with OAuth app configured
2. Valid tokens saved via 'cli-anything-zoom auth login'

To run: python3 -m pytest cli_anything/zoom/tests/test_full_e2e.py -v

Set CLI_ANYTHING_ZOOM_E2E=1 to enable these tests.
"""

import json
import os
import time
import pytest
from click.testing import CliRunner

from cli_anything.zoom.zoom_cli import cli


# Skip all E2E tests unless explicitly enabled
pytestmark = pytest.mark.skipif(
    not os.environ.get("CLI_ANYTHING_ZOOM_E2E"),
    reason="Set CLI_ANYTHING_ZOOM_E2E=1 to run E2E tests (requires Zoom credentials)",
)


@pytest.fixture
def runner():
    return CliRunner()


class TestAuthE2E:
    """Test authentication against real Zoom API."""

    def test_auth_status(self, runner):
        """Should show authenticated status."""
        result = runner.invoke(cli, ["--json", "auth", "status"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["configured"] is True
        assert data["authenticated"] is True
        assert data["token_valid"] is True
        assert "@" in data.get("user", "")


class TestMeetingLifecycleE2E:
    """Test full meeting lifecycle: create -> info -> update -> delete."""

    def test_meeting_crud(self, runner):
        """Create, read, update, and delete a test meeting."""
        # Create
        result = runner.invoke(cli, [
            "--json", "meeting", "create",
            "--topic", "CLI-Anything E2E Test Meeting",
            "--duration", "15",
            "--timezone", "UTC",
        ])
        assert result.exit_code == 0
        meeting = json.loads(result.output)
        meeting_id = meeting["id"]
        assert meeting["topic"] == "CLI-Anything E2E Test Meeting"
        assert meeting["duration"] == 15
        assert meeting["join_url"]

        try:
            # Read
            result = runner.invoke(cli, [
                "--json", "meeting", "info", str(meeting_id),
            ])
            assert result.exit_code == 0
            info = json.loads(result.output)
            assert info["id"] == meeting_id
            assert info["topic"] == "CLI-Anything E2E Test Meeting"

            # Update
            result = runner.invoke(cli, [
                "--json", "meeting", "update", str(meeting_id),
                "--topic", "CLI-Anything Updated Meeting",
                "--duration", "30",
            ])
            assert result.exit_code == 0
            assert "updated" in json.loads(result.output).get("status", "")

            # Verify update
            result = runner.invoke(cli, [
                "--json", "meeting", "info", str(meeting_id),
            ])
            updated = json.loads(result.output)
            assert updated["topic"] == "CLI-Anything Updated Meeting"
            assert updated["duration"] == 30

        finally:
            # Delete (cleanup)
            result = runner.invoke(cli, [
                "--json", "meeting", "delete", str(meeting_id), "--confirm",
            ])
            assert result.exit_code == 0


class TestMeetingListE2E:
    """Test meeting listing."""

    def test_list_meetings(self, runner):
        """Should list upcoming meetings."""
        result = runner.invoke(cli, ["--json", "meeting", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "meetings" in data
        assert isinstance(data["meetings"], list)
        assert "total_records" in data


class TestRecordingE2E:
    """Test recording listing (read-only)."""

    def test_list_recordings(self, runner):
        """Should list cloud recordings."""
        result = runner.invoke(cli, ["--json", "recording", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "meetings" in data


