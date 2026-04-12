"""Tests for cli-hub — registry, installer, analytics, and CLI."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import click.testing

from cli_hub import __version__
from cli_hub.registry import fetch_registry, get_cli, search_clis, list_categories
from cli_hub.installer import install_cli, uninstall_cli, get_installed, _load_installed, _save_installed
from cli_hub.analytics import _is_enabled, track_event, track_install, track_uninstall as analytics_track_uninstall, track_visit, track_first_run, _detect_is_agent
from cli_hub.cli import main


# ─── Sample registry data ─────────────────────────────────────────────

SAMPLE_REGISTRY = {
    "meta": {"repo": "https://github.com/HKUDS/CLI-Anything", "description": "test"},
    "clis": [
        {
            "name": "gimp",
            "display_name": "GIMP",
            "version": "1.0.0",
            "description": "Image editing via GIMP",
            "requires": "gimp",
            "homepage": "https://gimp.org",
            "install_cmd": "pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=gimp/agent-harness",
            "entry_point": "cli-anything-gimp",
            "skill_md": None,
            "category": "image",
            "contributor": "test-user",
            "contributor_url": "https://github.com/test-user",
        },
        {
            "name": "blender",
            "display_name": "Blender",
            "version": "1.0.0",
            "description": "3D modeling via Blender",
            "requires": "blender",
            "homepage": "https://blender.org",
            "install_cmd": "pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=blender/agent-harness",
            "entry_point": "cli-anything-blender",
            "skill_md": None,
            "category": "3d",
            "contributor": "test-user",
            "contributor_url": "https://github.com/test-user",
        },
        {
            "name": "audacity",
            "display_name": "Audacity",
            "version": "1.0.0",
            "description": "Audio editing and processing via sox",
            "requires": "sox",
            "homepage": "https://audacityteam.org",
            "install_cmd": "pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=audacity/agent-harness",
            "entry_point": "cli-anything-audacity",
            "skill_md": None,
            "category": "audio",
            "contributor": "test-user",
            "contributor_url": "https://github.com/test-user",
        },
    ],
}


# ─── Registry tests ───────────────────────────────────────────────────


class TestRegistry:
    """Tests for registry.py — fetch, cache, search, and lookup."""

    @patch("cli_hub.registry.requests.get")
    @patch("cli_hub.registry.CACHE_FILE", Path(tempfile.mktemp()))
    def test_fetch_registry_from_remote(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = SAMPLE_REGISTRY
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = fetch_registry(force_refresh=True)
        assert result["clis"][0]["name"] == "gimp"
        mock_get.assert_called_once()

    def test_get_cli_found(self):
        cli = get_cli("gimp", SAMPLE_REGISTRY)
        assert cli is not None
        assert cli["display_name"] == "GIMP"

    def test_get_cli_case_insensitive(self):
        cli = get_cli("GIMP", SAMPLE_REGISTRY)
        assert cli is not None
        assert cli["name"] == "gimp"

    def test_get_cli_not_found(self):
        cli = get_cli("nonexistent", SAMPLE_REGISTRY)
        assert cli is None

    def test_search_by_name(self):
        results = search_clis("gimp", SAMPLE_REGISTRY)
        assert len(results) == 1
        assert results[0]["name"] == "gimp"

    def test_search_by_category(self):
        results = search_clis("3d", SAMPLE_REGISTRY)
        assert len(results) == 1
        assert results[0]["name"] == "blender"

    def test_search_by_description(self):
        results = search_clis("audio", SAMPLE_REGISTRY)
        assert len(results) == 1
        assert results[0]["name"] == "audacity"

    def test_search_no_results(self):
        results = search_clis("nonexistent_xyz", SAMPLE_REGISTRY)
        assert len(results) == 0

    def test_list_categories(self):
        cats = list_categories(SAMPLE_REGISTRY)
        assert cats == ["3d", "audio", "image"]


# ─── Installer tests ──────────────────────────────────────────────────


class TestInstaller:
    """Tests for installer.py — install, uninstall, tracking."""

    def test_load_installed_empty(self, tmp_path):
        with patch("cli_hub.installer.INSTALLED_FILE", tmp_path / "installed.json"):
            assert _load_installed() == {}

    def test_save_and_load_installed(self, tmp_path):
        installed_file = tmp_path / "installed.json"
        with patch("cli_hub.installer.INSTALLED_FILE", installed_file):
            _save_installed({"gimp": {"version": "1.0.0"}})
            data = _load_installed()
            assert data["gimp"]["version"] == "1.0.0"

    @patch("cli_hub.installer.subprocess.run")
    @patch("cli_hub.installer.get_cli")
    @patch("cli_hub.installer.INSTALLED_FILE", Path(tempfile.mktemp()))
    def test_install_success(self, mock_get_cli, mock_run):
        mock_get_cli.return_value = SAMPLE_REGISTRY["clis"][0]
        mock_run.return_value = MagicMock(returncode=0)

        success, msg = install_cli("gimp")
        assert success
        assert "GIMP" in msg

    @patch("cli_hub.installer.get_cli")
    def test_install_not_found(self, mock_get_cli):
        mock_get_cli.return_value = None
        success, msg = install_cli("nonexistent")
        assert not success
        assert "not found" in msg

    @patch("cli_hub.installer.subprocess.run")
    @patch("cli_hub.installer.get_cli")
    @patch("cli_hub.installer.INSTALLED_FILE", Path(tempfile.mktemp()))
    def test_install_pip_failure(self, mock_get_cli, mock_run):
        mock_get_cli.return_value = SAMPLE_REGISTRY["clis"][0]
        mock_run.return_value = MagicMock(returncode=1, stderr="some error")

        success, msg = install_cli("gimp")
        assert not success
        assert "failed" in msg

    @patch("cli_hub.installer.subprocess.run")
    @patch("cli_hub.installer.get_cli")
    @patch("cli_hub.installer.INSTALLED_FILE", Path(tempfile.mktemp()))
    def test_uninstall_success(self, mock_get_cli, mock_run):
        mock_get_cli.return_value = SAMPLE_REGISTRY["clis"][0]
        mock_run.return_value = MagicMock(returncode=0)

        success, msg = uninstall_cli("gimp")
        assert success
        assert "GIMP" in msg


# ─── Analytics tests ──────────────────────────────────────────────────


class TestAnalytics:
    """Tests for analytics.py — opt-out, event firing, event names."""

    def test_analytics_enabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            assert _is_enabled()

    def test_analytics_disabled_by_env(self):
        with patch.dict(os.environ, {"CLI_HUB_NO_ANALYTICS": "1"}):
            assert not _is_enabled()

    def test_analytics_disabled_by_true(self):
        with patch.dict(os.environ, {"CLI_HUB_NO_ANALYTICS": "true"}):
            assert not _is_enabled()

    @patch("cli_hub.analytics._send_event")
    def test_track_event_sends_request(self, mock_send):
        with patch.dict(os.environ, {}, clear=True):
            track_event("test-event", data={"key": "value"})
            import time
            time.sleep(0.2)
            mock_send.assert_called_once()
            payload = mock_send.call_args[0][0]
            assert payload["payload"]["name"] == "test-event"
            assert payload["payload"]["hostname"] == "clianything.cc"

    @patch("cli_hub.analytics._send_event")
    def test_track_event_noop_when_disabled(self, mock_send):
        with patch.dict(os.environ, {"CLI_HUB_NO_ANALYTICS": "1"}):
            track_event("test-event")
            import time
            time.sleep(0.2)
            mock_send.assert_not_called()

    @patch("cli_hub.analytics._send_event")
    def test_track_install_event_name_includes_cli(self, mock_send):
        """cli-install event name must include CLI name for dashboard visibility."""
        with patch.dict(os.environ, {}, clear=True):
            track_install("gimp", "1.0.0")
            import time
            time.sleep(0.2)
            mock_send.assert_called_once()
            payload = mock_send.call_args[0][0]
            assert payload["payload"]["name"] == "cli-install:gimp"
            assert payload["payload"]["url"] == "/cli-anything-hub/install/gimp"
            assert payload["payload"]["data"]["cli"] == "gimp"
            assert payload["payload"]["data"]["version"] == "1.0.0"
            assert "platform" in payload["payload"]["data"]

    @patch("cli_hub.analytics._send_event")
    def test_track_uninstall_event_name_includes_cli(self, mock_send):
        """cli-uninstall event name must include CLI name for dashboard visibility."""
        with patch.dict(os.environ, {}, clear=True):
            analytics_track_uninstall("blender")
            import time
            time.sleep(0.2)
            mock_send.assert_called_once()
            payload = mock_send.call_args[0][0]
            assert payload["payload"]["name"] == "cli-uninstall:blender"
            assert payload["payload"]["url"] == "/cli-anything-hub/uninstall/blender"
            assert payload["payload"]["data"]["cli"] == "blender"

    @patch("cli_hub.analytics._send_event")
    def test_track_visit_human(self, mock_send):
        """visit-human event sent when not detected as agent."""
        with patch.dict(os.environ, {}, clear=True):
            track_visit(is_agent=False)
            import time
            time.sleep(0.2)
            mock_send.assert_called_once()
            payload = mock_send.call_args[0][0]
            assert payload["payload"]["name"] == "visit-human"
            assert payload["payload"]["url"] == "/cli-anything-hub"
            assert payload["payload"]["data"]["source"] == "cli-anything-hub"

    @patch("cli_hub.analytics._send_event")
    def test_track_visit_agent(self, mock_send):
        """visit-agent event sent when agent environment detected."""
        with patch.dict(os.environ, {}, clear=True):
            track_visit(is_agent=True)
            import time
            time.sleep(0.2)
            mock_send.assert_called_once()
            payload = mock_send.call_args[0][0]
            assert payload["payload"]["name"] == "visit-agent"

    def test_detect_agent_claude_code(self):
        with patch.dict(os.environ, {"CLAUDE_CODE": "1"}):
            assert _detect_is_agent() is True

    def test_detect_agent_codex(self):
        with patch.dict(os.environ, {"CODEX": "1"}):
            assert _detect_is_agent() is True

    def test_detect_not_agent_clean_env(self):
        """Clean env with a tty should not detect as agent."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("sys.stdin") as mock_stdin:
                mock_stdin.isatty.return_value = True
                assert _detect_is_agent() is False

    @patch("cli_hub.analytics._send_event")
    def test_first_run_sends_event(self, mock_send, tmp_path):
        """First invocation sends cli-hub-installed event."""
        with patch.dict(os.environ, {"HOME": str(tmp_path)}, clear=False):
            track_first_run()
            import time
            time.sleep(0.2)
            mock_send.assert_called_once()
            payload = mock_send.call_args[0][0]
            assert payload["payload"]["name"] == "cli-anything-hub-installed"
            assert payload["payload"]["url"] == "/cli-anything-hub/installed"
            # Marker file should now exist
            assert (tmp_path / ".cli-hub" / ".first_run_sent").exists()

    @patch("cli_hub.analytics._send_event")
    def test_first_run_skips_if_marker_exists(self, mock_send, tmp_path):
        """Second invocation does NOT send cli-hub-installed event."""
        cli_hub_dir = tmp_path / ".cli-hub"
        cli_hub_dir.mkdir()
        (cli_hub_dir / ".first_run_sent").write_text("0.1.0")
        with patch.dict(os.environ, {"HOME": str(tmp_path)}, clear=False):
            track_first_run()
            import time
            time.sleep(0.2)
            mock_send.assert_not_called()


# ─── CLI tests ─────────────────────────────────────────────────────────


class TestCLI:
    """Tests for the Click CLI interface."""

    def setup_method(self):
        self.runner = click.testing.CliRunner()

    @patch("cli_hub.cli.track_first_run")
    @patch("cli_hub.cli.track_visit")
    @patch("cli_hub.cli._detect_is_agent", return_value=False)
    def test_version(self, mock_detect, mock_visit, mock_first_run):
        result = self.runner.invoke(main, ["--version"])
        assert __version__ in result.output
        assert result.exit_code == 0
        mock_visit.assert_called_once_with(is_agent=False)
        mock_first_run.assert_called_once()

    @patch("cli_hub.cli.track_first_run")
    @patch("cli_hub.cli.track_visit")
    @patch("cli_hub.cli._detect_is_agent", return_value=False)
    def test_help(self, mock_detect, mock_visit, mock_first_run):
        result = self.runner.invoke(main, ["--help"])
        assert "cli-hub" in result.output
        assert result.exit_code == 0

    @patch("cli_hub.cli.track_first_run")
    @patch("cli_hub.cli.track_visit")
    @patch("cli_hub.cli._detect_is_agent", return_value=False)
    @patch("cli_hub.cli.fetch_registry", return_value=SAMPLE_REGISTRY)
    @patch("cli_hub.cli.get_installed", return_value={})
    def test_list_command(self, mock_installed, mock_fetch, mock_detect, mock_visit, mock_first_run):
        result = self.runner.invoke(main, ["list"])
        assert "gimp" in result.output
        assert "blender" in result.output
        assert result.exit_code == 0

    @patch("cli_hub.cli.track_first_run")
    @patch("cli_hub.cli.track_visit")
    @patch("cli_hub.cli._detect_is_agent", return_value=False)
    @patch("cli_hub.cli.fetch_registry", return_value=SAMPLE_REGISTRY)
    @patch("cli_hub.cli.get_installed", return_value={})
    def test_list_with_category(self, mock_installed, mock_fetch, mock_detect, mock_visit, mock_first_run):
        result = self.runner.invoke(main, ["list", "-c", "image"])
        assert "gimp" in result.output
        assert "blender" not in result.output

    @patch("cli_hub.cli.track_first_run")
    @patch("cli_hub.cli.track_visit")
    @patch("cli_hub.cli._detect_is_agent", return_value=False)
    @patch("cli_hub.cli.search_clis", return_value=[SAMPLE_REGISTRY["clis"][0]])
    @patch("cli_hub.cli.get_installed", return_value={})
    def test_search_command(self, mock_installed, mock_search, mock_detect, mock_visit, mock_first_run):
        result = self.runner.invoke(main, ["search", "gimp"])
        assert "gimp" in result.output
        assert result.exit_code == 0

    @patch("cli_hub.cli.track_first_run")
    @patch("cli_hub.cli.track_visit")
    @patch("cli_hub.cli._detect_is_agent", return_value=False)
    @patch("cli_hub.cli.get_cli", return_value=SAMPLE_REGISTRY["clis"][0])
    @patch("cli_hub.cli.get_installed", return_value={})
    def test_info_command(self, mock_installed, mock_get, mock_detect, mock_visit, mock_first_run):
        result = self.runner.invoke(main, ["info", "gimp"])
        assert "GIMP" in result.output
        assert "image" in result.output
        assert result.exit_code == 0

    @patch("cli_hub.cli.track_first_run")
    @patch("cli_hub.cli.track_visit")
    @patch("cli_hub.cli._detect_is_agent", return_value=False)
    @patch("cli_hub.cli.get_cli", return_value=None)
    def test_info_not_found(self, mock_get, mock_detect, mock_visit, mock_first_run):
        result = self.runner.invoke(main, ["info", "nonexistent"])
        assert result.exit_code == 1

    @patch("cli_hub.cli.track_first_run")
    @patch("cli_hub.cli.track_visit")
    @patch("cli_hub.cli._detect_is_agent", return_value=False)
    @patch("cli_hub.cli.track_install")
    @patch("cli_hub.cli.install_cli", return_value=(True, "Installed GIMP (cli-anything-gimp)"))
    @patch("cli_hub.cli.get_cli", return_value=SAMPLE_REGISTRY["clis"][0])
    def test_install_command(self, mock_get, mock_install, mock_track, mock_detect, mock_visit, mock_first_run):
        result = self.runner.invoke(main, ["install", "gimp"])
        assert result.exit_code == 0
        assert "Installed" in result.output
        mock_track.assert_called_once()

    @patch("cli_hub.cli.track_first_run")
    @patch("cli_hub.cli.track_visit")
    @patch("cli_hub.cli._detect_is_agent", return_value=False)
    @patch("cli_hub.cli.track_uninstall")
    @patch("cli_hub.cli.uninstall_cli", return_value=(True, "Uninstalled GIMP"))
    def test_uninstall_command(self, mock_uninstall, mock_track, mock_detect, mock_visit, mock_first_run):
        result = self.runner.invoke(main, ["uninstall", "gimp"])
        assert result.exit_code == 0
        mock_track.assert_called_once()

    @patch("cli_hub.cli.track_first_run")
    @patch("cli_hub.cli.track_visit")
    @patch("cli_hub.cli._detect_is_agent", return_value=True)
    def test_visit_agent_on_invocation(self, mock_detect, mock_visit, mock_first_run):
        """When agent env detected, track_visit is called with is_agent=True."""
        result = self.runner.invoke(main, ["--version"])
        mock_visit.assert_called_once_with(is_agent=True)
