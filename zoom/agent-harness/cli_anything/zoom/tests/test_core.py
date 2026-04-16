"""Unit tests for Zoom CLI — no network calls, no Zoom account required.

Tests cover:
- Auth config save/load
- Meeting data formatting
- Participant data formatting
- Recording data formatting
- Report data formatting
- CLI command parsing
"""

import json
import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from cli_anything.zoom.zoom_cli import cli


# ── Fixtures ────────────────────────────────────────────────────

@pytest.fixture
def runner():
    """Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def tmp_config_dir(tmp_path):
    """Temporary config directory for token/config storage."""
    config_dir = tmp_path / ".cli-anything-zoom"
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def mock_config(tmp_config_dir):
    """Patch config directory to use temp dir."""
    with patch("cli_anything.zoom.utils.zoom_backend.CONFIG_DIR", tmp_config_dir), \
         patch("cli_anything.zoom.utils.zoom_backend.TOKEN_FILE", tmp_config_dir / "tokens.json"), \
         patch("cli_anything.zoom.utils.zoom_backend.CONFIG_FILE", tmp_config_dir / "config.json"):
        yield tmp_config_dir


# ── Auth Tests ──────────────────────────────────────────────────

class TestAuthSetup:
    """Test OAuth configuration."""

    def test_setup_saves_config(self, runner, mock_config):
        """auth setup should save client_id and client_secret."""
        result = runner.invoke(cli, [
            "auth", "setup",
            "--client-id", "test_id_123",
            "--client-secret", "test_secret_456",
        ])
        assert result.exit_code == 0
        assert "configured" in result.output.lower() or "OAuth" in result.output

        config_file = mock_config / "config.json"
        assert config_file.exists()
        config = json.loads(config_file.read_text())
        assert config["client_id"] == "test_id_123"
        assert config["client_secret"] == "test_secret_456"

    def test_setup_with_custom_redirect(self, runner, mock_config):
        """auth setup should accept custom redirect URI."""
        result = runner.invoke(cli, [
            "auth", "setup",
            "--client-id", "id",
            "--client-secret", "secret",
            "--redirect-uri", "http://localhost:9999/cb",
        ])
        assert result.exit_code == 0

        config = json.loads((mock_config / "config.json").read_text())
        assert config["redirect_uri"] == "http://localhost:9999/cb"

    def test_status_not_configured(self, runner, mock_config):
        """auth status should report not configured when no config exists."""
        result = runner.invoke(cli, ["auth", "status"])
        assert result.exit_code == 0
        assert "False" in result.output or "false" in result.output.lower()

    def test_logout_no_tokens(self, runner, mock_config):
        """auth logout should succeed even when no tokens exist."""
        result = runner.invoke(cli, ["auth", "logout"])
        assert result.exit_code == 0
        assert "logged_out" in result.output.lower() or "Logged out" in result.output


class TestAuthLogin:
    """Test login flow (mocked)."""

    def test_login_without_config_fails(self, runner, mock_config):
        """Login should fail without OAuth config."""
        result = runner.invoke(cli, ["auth", "login", "--code", "dummy"])
        assert result.exit_code == 1
        assert "not configured" in result.output.lower() or "Error" in result.output

    def test_login_with_code(self, runner, mock_config):
        """Login with manual code should exchange it for tokens."""
        # Setup config first
        (mock_config / "config.json").write_text(json.dumps({
            "client_id": "id", "client_secret": "secret",
            "redirect_uri": "http://localhost:4199/callback",
        }))

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "at_123",
            "refresh_token": "rt_456",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()

        with patch("cli_anything.zoom.utils.zoom_backend.requests.post",
                    return_value=mock_response), \
             patch("cli_anything.zoom.utils.zoom_backend.api_get",
                    return_value={"email": "test@example.com",
                                  "first_name": "Test", "last_name": "User",
                                  "account_id": "acc123"}):
            result = runner.invoke(cli, ["auth", "login", "--code", "auth_code_xyz"])

        assert result.exit_code == 0
        token_file = mock_config / "tokens.json"
        assert token_file.exists()
        tokens = json.loads(token_file.read_text())
        assert tokens["access_token"] == "at_123"


# ── Meeting Tests ───────────────────────────────────────────────

class TestMeetingCommands:
    """Test meeting CLI commands with mocked API."""

    def test_create_meeting(self, runner, mock_config):
        """meeting create should call API and show result."""
        mock_meeting = {
            "id": 12345,
            "uuid": "uuid-abc",
            "topic": "Test Standup",
            "type": 2,
            "status": "waiting",
            "start_time": "2025-06-01T10:00:00Z",
            "duration": 30,
            "timezone": "UTC",
            "agenda": "",
            "join_url": "https://zoom.us/j/12345",
            "start_url": "https://zoom.us/s/12345",
            "password": "abc123",
            "settings": {
                "auto_recording": "none",
                "waiting_room": False,
                "join_before_host": False,
                "mute_upon_entry": True,
            },
            "created_at": "2025-05-30T09:00:00Z",
        }

        with patch("cli_anything.zoom.core.meetings.api_post",
                    return_value=mock_meeting):
            result = runner.invoke(cli, [
                "meeting", "create",
                "--topic", "Test Standup",
                "--duration", "30",
            ])

        assert result.exit_code == 0
        assert "Test Standup" in result.output
        assert "12345" in result.output

    def test_list_meetings(self, runner, mock_config):
        """meeting list should show meetings."""
        mock_list = {
            "total_records": 1,
            "page_count": 1,
            "page_number": 1,
            "page_size": 30,
            "meetings": [{
                "id": 12345,
                "topic": "Weekly Sync",
                "type": 2,
                "start_time": "2025-06-01T10:00:00Z",
                "duration": 60,
                "timezone": "UTC",
                "join_url": "https://zoom.us/j/12345",
                "created_at": "2025-05-30T09:00:00Z",
            }],
        }

        with patch("cli_anything.zoom.core.meetings.api_get",
                    return_value=mock_list):
            result = runner.invoke(cli, ["meeting", "list"])

        assert result.exit_code == 0
        assert "Weekly Sync" in result.output

    def test_get_meeting_info(self, runner, mock_config):
        """meeting info should show meeting details."""
        mock_meeting = {
            "id": 12345,
            "uuid": "uuid-abc",
            "topic": "Standup",
            "type": 2,
            "status": "waiting",
            "start_time": "2025-06-01T10:00:00Z",
            "duration": 30,
            "timezone": "UTC",
            "agenda": "Daily standup",
            "join_url": "https://zoom.us/j/12345",
            "start_url": "https://zoom.us/s/12345",
            "password": "pass",
            "settings": {
                "auto_recording": "cloud",
                "waiting_room": True,
                "join_before_host": False,
                "mute_upon_entry": True,
            },
            "created_at": "2025-05-30T09:00:00Z",
        }

        with patch("cli_anything.zoom.core.meetings.api_get",
                    return_value=mock_meeting):
            result = runner.invoke(cli, ["meeting", "info", "12345"])

        assert result.exit_code == 0
        assert "Standup" in result.output

    def test_delete_meeting(self, runner, mock_config):
        """meeting delete should confirm and delete."""
        with patch("cli_anything.zoom.core.meetings.api_delete",
                    return_value={"status": "success"}):
            result = runner.invoke(cli, [
                "meeting", "delete", "12345", "--confirm",
            ])

        assert result.exit_code == 0
        assert "deleted" in result.output.lower()

    def test_update_meeting(self, runner, mock_config):
        """meeting update should patch meeting fields."""
        with patch("cli_anything.zoom.core.meetings.api_patch"):
            result = runner.invoke(cli, [
                "meeting", "update", "12345",
                "--topic", "Updated Topic",
                "--duration", "45",
            ])

        assert result.exit_code == 0
        assert "updated" in result.output.lower()


# ── Participant Tests ───────────────────────────────────────────

class TestParticipantCommands:
    """Test participant CLI commands."""

    def test_add_participant(self, runner, mock_config):
        """participant add should register a user."""
        mock_result = {
            "registrant_id": "reg_123",
            "id": 12345,
            "topic": "Meeting",
            "email": "user@example.com",
            "join_url": "https://zoom.us/j/12345?tk=reg_123",
            "start_time": "",
        }

        with patch("cli_anything.zoom.core.participants.api_post",
                    return_value=mock_result):
            result = runner.invoke(cli, [
                "participant", "add", "12345",
                "--email", "user@example.com",
                "--first-name", "John",
            ])

        assert result.exit_code == 0
        assert "user@example.com" in result.output

    def test_list_registrants(self, runner, mock_config):
        """participant list should show registrants."""
        mock_result = {
            "total_records": 1,
            "registrants": [{
                "id": "reg_123",
                "email": "user@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "status": "approved",
                "create_time": "2025-05-30T09:00:00Z",
            }],
        }

        with patch("cli_anything.zoom.core.participants.api_get",
                    return_value=mock_result):
            result = runner.invoke(cli, [
                "participant", "list", "12345",
            ])

        assert result.exit_code == 0
        assert "user@example.com" in result.output


# ── Recording Tests ─────────────────────────────────────────────

class TestRecordingCommands:
    """Test recording CLI commands."""

    def test_list_recordings(self, runner, mock_config):
        """recording list should show cloud recordings."""
        mock_result = {
            "total_records": 1,
            "meetings": [{
                "id": 12345,
                "uuid": "uuid-abc",
                "topic": "Recorded Meeting",
                "start_time": "2025-06-01T10:00:00Z",
                "duration": 60,
                "total_size": 104857600,
                "recording_count": 2,
                "recording_files": [
                    {
                        "id": "file_1",
                        "file_type": "MP4",
                        "file_extension": "MP4",
                        "file_size": 83886080,
                        "status": "completed",
                        "recording_start": "2025-06-01T10:00:00Z",
                        "recording_end": "2025-06-01T11:00:00Z",
                        "download_url": "https://zoom.us/rec/download/abc",
                    },
                ],
            }],
        }

        with patch("cli_anything.zoom.core.recordings.api_get",
                    return_value=mock_result):
            result = runner.invoke(cli, ["recording", "list"])

        assert result.exit_code == 0
        assert "Recorded Meeting" in result.output

    def test_get_recording_files(self, runner, mock_config):
        """recording files should show recording details."""
        mock_result = {
            "id": 12345,
            "uuid": "uuid-abc",
            "topic": "My Meeting",
            "start_time": "2025-06-01T10:00:00Z",
            "duration": 60,
            "total_size": 104857600,
            "recording_files": [
                {
                    "id": "file_1",
                    "file_type": "MP4",
                    "file_extension": "MP4",
                    "file_size": 83886080,
                    "status": "completed",
                    "download_url": "https://zoom.us/rec/download/abc",
                    "play_url": "https://zoom.us/rec/play/abc",
                    "recording_start": "2025-06-01T10:00:00Z",
                    "recording_end": "2025-06-01T11:00:00Z",
                },
            ],
        }

        with patch("cli_anything.zoom.core.recordings.api_get",
                    return_value=mock_result):
            result = runner.invoke(cli, ["recording", "files", "12345"])

        assert result.exit_code == 0
        assert "MP4" in result.output


# ── JSON Output Tests ───────────────────────────────────────────

class TestJsonOutput:
    """Test --json flag produces valid JSON."""

    def test_meeting_list_json(self, runner, mock_config):
        """--json flag should produce valid JSON output."""
        mock_list = {
            "total_records": 1,
            "page_count": 1,
            "page_number": 1,
            "page_size": 30,
            "meetings": [{
                "id": 99999,
                "topic": "JSON Test",
                "type": 2,
                "start_time": "",
                "duration": 30,
                "timezone": "UTC",
                "join_url": "",
                "created_at": "",
            }],
        }

        with patch("cli_anything.zoom.core.meetings.api_get",
                    return_value=mock_list):
            result = runner.invoke(cli, ["--json", "meeting", "list"])

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["total_records"] == 1
        assert parsed["meetings"][0]["topic"] == "JSON Test"

    def test_auth_status_json(self, runner, mock_config):
        """auth status with --json should return valid JSON."""
        result = runner.invoke(cli, ["--json", "auth", "status"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "configured" in parsed
        assert "authenticated" in parsed


# ── Backend Unit Tests ──────────────────────────────────────────

class TestBackend:
    """Test zoom_backend utilities."""

    def test_config_save_load(self, mock_config):
        """Config should round-trip through save/load."""
        from cli_anything.zoom.utils.zoom_backend import save_config, load_config

        save_config({"client_id": "abc", "client_secret": "xyz"})
        loaded = load_config()
        assert loaded["client_id"] == "abc"
        assert loaded["client_secret"] == "xyz"

    def test_token_save_load(self, mock_config):
        """Tokens should round-trip with saved_at timestamp."""
        from cli_anything.zoom.utils.zoom_backend import save_tokens, load_tokens

        save_tokens({"access_token": "at_test", "refresh_token": "rt_test"})
        loaded = load_tokens()
        assert loaded["access_token"] == "at_test"
        assert "saved_at" in loaded

    def test_authorize_url(self):
        """get_authorize_url should build valid URL."""
        from cli_anything.zoom.utils.zoom_backend import get_authorize_url

        url = get_authorize_url("my_client_id", "http://localhost:4199/callback")
        assert "zoom.us/oauth/authorize" in url
        assert "my_client_id" in url
        assert "response_type=code" in url

    def test_load_empty_config(self, mock_config):
        """load_config should return empty dict when no config file."""
        from cli_anything.zoom.utils.zoom_backend import load_config
        result = load_config()
        assert result == {}

    def test_load_empty_tokens(self, mock_config):
        """load_tokens should return empty dict when no token file."""
        from cli_anything.zoom.utils.zoom_backend import load_tokens
        result = load_tokens()
        assert result == {}
