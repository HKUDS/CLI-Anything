"""Tests for cli-hub — registry, installer, analytics, and CLI."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import click.testing
import requests

from cli_hub import __version__
from cli_hub.registry import fetch_registry, fetch_all_clis, get_cli, search_clis, list_categories
from cli_hub.preview import (
    inspect_bundle,
    inspect_session,
    open_in_browser,
    render_html,
    render_inspect_text,
    render_live_html,
    render_session_text,
)
from cli_hub.installer import (
    install_cli,
    uninstall_cli,
    get_installed,
    _load_installed,
    _save_installed,
    _run_command,
    _install_strategy,
    _UV_INSTALL_HINT,
)
from cli_hub.analytics import _is_enabled, track_event, track_install, track_uninstall as analytics_track_uninstall, track_visit, track_first_run, _detect_is_agent, detect_invocation_context
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
            "skill_md": "skills/cli-anything-gimp/SKILL.md",
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


def _make_preview_bundle(tmp_path: Path, *, with_trajectory: bool = False) -> Path:
    bundle_dir = tmp_path / "preview-bundle"
    artifacts_dir = bundle_dir / "artifacts"
    artifacts_dir.mkdir(parents=True)
    (artifacts_dir / "hero.png").write_bytes(b"\x89PNG\r\n\x1a\npreview")
    (artifacts_dir / "preview.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42")
    summary = {
        "headline": "Quick preview rendered",
        "facts": {
            "duration_s": 6.0,
            "resolution": "640x360",
        },
        "warnings": [],
    }
    manifest = {
        "protocol_version": "preview-bundle/v1",
        "bundle_id": "20260419T104530Z_deadbeef_quick",
        "bundle_kind": "capture",
        "software": "shotcut",
        "recipe": "quick",
        "status": "ok",
        "created_at": "2026-04-19T10:45:30Z",
        "generator": {"entry_point": "cli-anything-shotcut", "command": "cli-anything-shotcut preview capture --recipe quick"},
        "source": {"project_path": "/tmp/demo.mlt", "project_fingerprint": "sha256:test"},
        "summary_path": "summary.json",
        "artifacts": [
            {
                "artifact_id": "hero",
                "role": "hero",
                "kind": "image",
                "label": "Midpoint frame",
                "media_type": "image/png",
                "path": "artifacts/hero.png",
                "width": 960,
                "height": 540,
                "bytes": (artifacts_dir / "hero.png").stat().st_size,
            },
            {
                "artifact_id": "clip",
                "role": "preview-clip",
                "kind": "clip",
                "label": "Preview clip",
                "media_type": "video/mp4",
                "path": "artifacts/preview.mp4",
                "width": 640,
                "height": 360,
                "duration_s": 6.0,
                "bytes": (artifacts_dir / "preview.mp4").stat().st_size,
            },
        ],
    }
    if with_trajectory:
        trajectory = {
            "protocol_version": "preview-trajectory/v1",
            "step_count": 1,
            "current_step_id": "step-001",
            "steps": [
                {
                    "step_id": "step-001",
                    "step_index": 1,
                    "bundle_id": "20260419T104530Z_deadbeef_quick",
                    "bundle_dir": str(bundle_dir),
                    "manifest_path": str(bundle_dir / "manifest.json"),
                    "summary_path": str(bundle_dir / "summary.json"),
                    "created_at": "2026-04-19T10:45:30Z",
                    "status": "ok",
                    "cached": False,
                    "publish_reason": "capture",
                    "command": "cli-anything-shotcut preview capture --recipe quick",
                }
            ],
        }
        (tmp_path / "trajectory.json").write_text(json.dumps(trajectory, indent=2))
        manifest["context"] = {"trajectory_path": "../trajectory.json"}
    (bundle_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    (bundle_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return bundle_dir


def _make_preview_session(tmp_path: Path, *, with_trajectory: bool = False) -> Path:
    bundle_dir = _make_preview_bundle(tmp_path)
    session_dir = tmp_path / "live-session"
    session_dir.mkdir()
    (session_dir / "current").symlink_to(bundle_dir, target_is_directory=True)
    session = {
        "protocol_version": "preview-live/v1",
        "software": "shotcut",
        "recipe": "quick",
        "status": "active",
        "session_name": "demo-live",
        "project_path": "/tmp/demo.mlt",
        "project_name": "demo.mlt",
        "updated_at": "2026-04-20T09:00:00Z",
        "current_link": "current",
        "current_bundle_id": "20260419T104530Z_deadbeef_quick",
        "watch_command": "cli-hub previews watch /tmp/live-session --open",
        "publish_command": "cli-anything-shotcut preview live push --recipe quick",
        "inspect_command": "cli-hub previews inspect /tmp/live-session",
        "history": [
            {
                "bundle_id": "20260419T104530Z_deadbeef_quick",
                "bundle_dir": str(bundle_dir),
                "created_at": "2026-04-19T10:45:30Z",
                "status": "ok",
            }
        ],
    }
    if with_trajectory:
        trajectory = {
            "protocol_version": "preview-trajectory/v1",
            "step_count": 2,
            "current_step_id": "step-002",
            "steps": [
                {
                    "step_id": "step-001",
                    "step_index": 0,
                    "bundle_id": "20260419T104530Z_deadbeef_quick",
                    "bundle_dir": str(bundle_dir),
                    "manifest_path": str(bundle_dir / "manifest.json"),
                    "summary_path": str(bundle_dir / "summary.json"),
                    "created_at": "2026-04-19T10:45:30Z",
                    "status": "ok",
                    "cached": False,
                    "publish_reason": "live-start",
                    "command": "cli-anything-shotcut preview live start --recipe quick",
                    "command_started_at": "2026-04-19T10:45:28Z",
                    "command_finished_at": "2026-04-19T10:45:30Z",
                    "source_fingerprint": "sha256:test-a",
                },
                {
                    "step_id": "step-002",
                    "step_index": 1,
                    "bundle_id": "20260419T104530Z_deadbeef_quick",
                    "bundle_dir": str(bundle_dir),
                    "manifest_path": str(bundle_dir / "manifest.json"),
                    "summary_path": str(bundle_dir / "summary.json"),
                    "created_at": "2026-04-19T10:47:10Z",
                    "status": "ok",
                    "cached": True,
                    "publish_reason": "manual-push",
                    "command": "cli-anything-shotcut preview live push --recipe quick",
                    "command_started_at": "2026-04-19T10:47:07Z",
                    "command_finished_at": "2026-04-19T10:47:10Z",
                    "source_fingerprint": "sha256:test-b",
                },
            ],
        }
        (session_dir / "trajectory.json").write_text(json.dumps(trajectory, indent=2))
        session.update(
            {
                "trajectory_path": "trajectory.json",
                "trajectory_protocol_version": "preview-trajectory/v1",
                "trajectory_step_count": 2,
                "current_step_id": "step-002",
                "latest_command": "cli-anything-shotcut preview live push --recipe quick",
                "latest_publish_reason": "manual-push",
            }
        )
    (session_dir / "session.json").write_text(json.dumps(session, indent=2))
    return session_dir


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

    @patch("cli_hub.registry.requests.get", side_effect=requests.ConnectionError("network down"))
    def test_fetch_registry_uses_cache_on_refresh_failure(self, mock_get, tmp_path):
        cache_file = tmp_path / "registry_cache.json"
        cache_payload = {"_cached_at": 0, "data": SAMPLE_REGISTRY}
        cache_file.write_text(json.dumps(cache_payload, indent=2))

        with patch("cli_hub.registry.CACHE_FILE", cache_file):
            result = fetch_registry(force_refresh=True)

        assert result["clis"][0]["name"] == "gimp"
        mock_get.assert_called_once()

    @patch("cli_hub.registry.fetch_all_clis", return_value=SAMPLE_REGISTRY["clis"])
    def test_get_cli_found(self, mock_fetch):
        cli = get_cli("gimp")
        assert cli is not None
        assert cli["display_name"] == "GIMP"

    @patch("cli_hub.registry.fetch_all_clis", return_value=SAMPLE_REGISTRY["clis"])
    def test_get_cli_case_insensitive(self, mock_fetch):
        cli = get_cli("GIMP")
        assert cli is not None
        assert cli["name"] == "gimp"

    @patch("cli_hub.registry.fetch_all_clis", return_value=SAMPLE_REGISTRY["clis"])
    def test_get_cli_not_found(self, mock_fetch):
        cli = get_cli("nonexistent")
        assert cli is None

    @patch("cli_hub.registry.fetch_all_clis", return_value=SAMPLE_REGISTRY["clis"])
    def test_search_by_name(self, mock_fetch):
        results = search_clis("gimp")
        assert len(results) == 1
        assert results[0]["name"] == "gimp"

    @patch("cli_hub.registry.fetch_all_clis", return_value=SAMPLE_REGISTRY["clis"])
    def test_search_by_category(self, mock_fetch):
        results = search_clis("3d")
        assert len(results) == 1
        assert results[0]["name"] == "blender"

    @patch("cli_hub.registry.fetch_all_clis", return_value=SAMPLE_REGISTRY["clis"])
    def test_search_by_description(self, mock_fetch):
        results = search_clis("audio")
        assert len(results) == 1
        assert results[0]["name"] == "audacity"

    @patch("cli_hub.registry.fetch_all_clis", return_value=SAMPLE_REGISTRY["clis"])
    def test_search_no_results(self, mock_fetch):
        results = search_clis("nonexistent_xyz")
        assert len(results) == 0

    @patch("cli_hub.registry.fetch_all_clis", return_value=SAMPLE_REGISTRY["clis"])
    def test_list_categories(self, mock_fetch):
        cats = list_categories()
        assert cats == ["3d", "audio", "image"]


class TestPreviewBundle:
    """Tests for preview bundle inspection and HTML rendering."""

    def test_inspect_bundle(self, tmp_path):
        bundle_dir = _make_preview_bundle(tmp_path)
        payload = inspect_bundle(str(bundle_dir))
        assert payload["artifact_count"] == 2
        assert payload["manifest"]["software"] == "shotcut"
        assert payload["summary"]["headline"] == "Quick preview rendered"

    def test_inspect_bundle_loads_trajectory_from_context_path(self, tmp_path):
        bundle_dir = _make_preview_bundle(tmp_path, with_trajectory=True)
        payload = inspect_bundle(str(bundle_dir))
        assert payload["trajectory"]["protocol"] == "preview-trajectory/v1"
        assert payload["trajectory"]["step_count"] == 1
        assert payload["trajectory"]["recent_publish_reason"] == "capture"

    def test_render_inspect_text(self, tmp_path):
        bundle_dir = _make_preview_bundle(tmp_path)
        text = render_inspect_text(str(bundle_dir))
        assert "Bundle:" in text
        assert "Artifacts" in text
        assert "Midpoint frame" in text

    def test_render_html(self, tmp_path):
        bundle_dir = _make_preview_bundle(tmp_path)
        output_path = tmp_path / "preview.html"
        rendered = render_html(str(bundle_dir), str(output_path))
        assert rendered == str(output_path.resolve())
        content = output_path.read_text()
        assert "CLI-Anything Preview Bundle" in content
        assert "Quick preview rendered" in content
        assert "artifacts/hero.png" in content
        assert "artifacts/preview.mp4" in content

    def test_previews_inspect_cli_command(self, tmp_path):
        bundle_dir = _make_preview_bundle(tmp_path)
        runner = click.testing.CliRunner()
        result = runner.invoke(main, ["previews", "inspect", str(bundle_dir)])
        assert result.exit_code == 0
        assert "Quick preview rendered" in result.output

    def test_previews_html_cli_command(self, tmp_path):
        bundle_dir = _make_preview_bundle(tmp_path)
        output_path = tmp_path / "bundle-preview.html"
        runner = click.testing.CliRunner()
        result = runner.invoke(main, ["previews", "html", str(bundle_dir), "-o", str(output_path)])
        assert result.exit_code == 0
        assert str(output_path) in result.output
        assert output_path.is_file()

    def test_inspect_session(self, tmp_path):
        session_dir = _make_preview_session(tmp_path)
        payload = inspect_session(str(session_dir))
        assert payload["session"]["software"] == "shotcut"
        assert payload["current_bundle"]["manifest"]["bundle_id"] == "20260419T104530Z_deadbeef_quick"

    def test_inspect_session_loads_trajectory(self, tmp_path):
        session_dir = _make_preview_session(tmp_path, with_trajectory=True)
        payload = inspect_session(str(session_dir))
        assert payload["trajectory"]["protocol"] == "preview-trajectory/v1"
        assert payload["trajectory"]["step_count"] == 2
        assert payload["trajectory"]["current_step_id"] == "step-002"
        assert payload["trajectory"]["recent_publish_reason"] == "manual-push"

    def test_render_session_text(self, tmp_path):
        session_dir = _make_preview_session(tmp_path)
        text = render_session_text(str(session_dir))
        assert "Live Session:" in text
        assert "Watch:" in text
        assert "History" in text

    def test_render_session_text_with_trajectory(self, tmp_path):
        session_dir = _make_preview_session(tmp_path, with_trajectory=True)
        text = render_session_text(str(session_dir))
        assert "Trajectory" in text
        assert "Current step: step-002" in text
        assert "Recent publish: manual-push" in text
        assert "cli-anything-shotcut preview live push --recipe quick" in text

    def test_render_live_html(self, tmp_path):
        session_dir = _make_preview_session(tmp_path)
        output_path = tmp_path / "live.html"
        rendered = render_live_html(str(session_dir), str(output_path), poll_ms=800)
        assert rendered == str(output_path.resolve())
        content = output_path.read_text()
        assert "CLI-Anything Live Preview Session" in content
        assert 'const CURRENT_LINK = "current";' in content
        assert "manifest = await fetchJson(`${CURRENT_LINK}/manifest.json`);" in content
        assert "const POLL_MS = 800;" in content

    def test_render_live_html_with_trajectory(self, tmp_path):
        session_dir = _make_preview_session(tmp_path, with_trajectory=True)
        output_path = tmp_path / "live-trajectory.html"
        render_live_html(str(session_dir), str(output_path), poll_ms=600)
        content = output_path.read_text()
        assert 'const TRAJECTORY_CANDIDATES = ["trajectory.json", "timeline.json"];' in content
        assert "function normalizeTrajectory(session, payload)" in content
        assert "Trajectory Timeline" in content
        assert "trajectory_step_count" in content
        assert "latest_publish_reason" in content

    @patch("cli_hub.preview.subprocess.Popen")
    @patch("cli_hub.preview.shutil.which")
    def test_open_in_browser_prefers_app_mode(self, mock_which, mock_popen):
        mock_which.side_effect = lambda binary: f"/usr/bin/{binary}" if binary == "chromium" else None
        mock_popen.return_value = MagicMock(pid=4321)
        result = open_in_browser("http://127.0.0.1:9933/live.html")
        assert result["launched"] is True
        assert result["browser"] == "chromium"
        assert "--app=http://127.0.0.1:9933/live.html" in result["command"]

    def test_previews_inspect_cli_handles_session(self, tmp_path):
        session_dir = _make_preview_session(tmp_path)
        runner = click.testing.CliRunner()
        result = runner.invoke(main, ["previews", "inspect", str(session_dir)])
        assert result.exit_code == 0
        assert "Live Session:" in result.output

    def test_previews_html_cli_renders_session(self, tmp_path):
        session_dir = _make_preview_session(tmp_path)
        output_path = tmp_path / "session-live.html"
        runner = click.testing.CliRunner()
        result = runner.invoke(main, ["previews", "html", str(session_dir), "-o", str(output_path), "--poll-ms", "700"])
        assert result.exit_code == 0
        assert output_path.is_file()
        assert "const POLL_MS = 700;" in output_path.read_text()

    def test_previews_help_and_cli(self, tmp_path):
        session_dir = _make_preview_session(tmp_path, with_trajectory=True)
        runner = click.testing.CliRunner()
        help_result = runner.invoke(main, ["--help"])
        assert help_result.exit_code == 0
        assert "previews" in help_result.output
        assert "\n  review" not in help_result.output
        assert "\n  open-preview" not in help_result.output

        inspect_result = runner.invoke(main, ["previews", "inspect", str(session_dir)])
        assert inspect_result.exit_code == 0
        assert "Trajectory" in inspect_result.output
        assert "Current step: step-002" in inspect_result.output


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

    @patch("cli_hub.installer.subprocess.run")
    @patch("cli_hub.installer.get_cli")
    @patch("cli_hub.installer.INSTALLED_FILE", Path(tempfile.mktemp()))
    def test_install_command_strategy_success(self, mock_get_cli, mock_run):
        mock_get_cli.return_value = {
            "name": "onepassword-cli",
            "display_name": "1Password CLI",
            "version": "latest",
            "description": "Secrets automation",
            "entry_point": "op",
            "_source": "public",
            "install_strategy": "command",
            "package_manager": "brew",
            "install_cmd": "brew install --cask 1password-cli",
        }
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        success, msg = install_cli("onepassword-cli")
        assert success
        assert "1Password CLI" in msg

    @patch("cli_hub.installer.subprocess.run", side_effect=FileNotFoundError(2, "No such file or directory", "brew"))
    @patch("cli_hub.installer.get_cli")
    @patch("cli_hub.installer.INSTALLED_FILE", Path(tempfile.mktemp()))
    def test_install_command_strategy_missing_executable(self, mock_get_cli, mock_run):
        mock_get_cli.return_value = {
            "name": "onepassword-cli",
            "display_name": "1Password CLI",
            "version": "latest",
            "description": "Secrets automation",
            "entry_point": "op",
            "_source": "public",
            "install_strategy": "command",
            "package_manager": "brew",
            "install_cmd": "brew install --cask 1password-cli",
        }

        success, msg = install_cli("onepassword-cli")
        assert not success
        assert "Command not found: brew" in msg

    @patch("cli_hub.installer.shutil.which", return_value="/usr/local/bin/obsidian")
    @patch("cli_hub.installer.get_cli")
    @patch("cli_hub.installer.INSTALLED_FILE", Path(tempfile.mktemp()))
    def test_install_bundled_strategy_success_when_detected(self, mock_get_cli, mock_which):
        mock_get_cli.return_value = {
            "name": "obsidian-cli",
            "display_name": "Obsidian CLI",
            "version": "bundled",
            "description": "Bundled inside Obsidian",
            "entry_point": "obsidian",
            "_source": "public",
            "install_strategy": "bundled",
            "package_manager": "bundled",
        }

        success, msg = install_cli("obsidian-cli")
        assert success
        assert "already available" in msg


GENERATE_VEO_CLI = {
    "name": "generate-veo-video",
    "display_name": "Generate Veo Video",
    "version": "0.2.5",
    "description": "CLI for generating videos with Google Veo 3.1",
    "category": "ai",
    "entry_point": "generate-veo",
    "_source": "public",
    "package_manager": "uv",
    "install_cmd": "uv tool install git+https://github.com/charles-forsyth/generate-veo-video.git",
    "uninstall_cmd": "uv tool uninstall generate-veo-video",
    "update_cmd": "uv tool upgrade generate-veo-video",
}


class TestUvStrategy:
    """Tests for uv-managed public CLI installs (e.g. generate-veo-video)."""

    def test_strategy_detected_as_uv(self):
        assert _install_strategy(GENERATE_VEO_CLI) == "uv"

    def test_strategy_uv_not_overridden_by_install_strategy_field(self):
        """If install_strategy is explicitly set it takes priority over package_manager."""
        cli = {**GENERATE_VEO_CLI, "install_strategy": "command"}
        assert _install_strategy(cli) == "command"

    @patch("cli_hub.installer.subprocess.run")
    @patch("cli_hub.installer.get_cli")
    @patch("cli_hub.installer.INSTALLED_FILE", Path(tempfile.mktemp()))
    @patch("cli_hub.installer._find_uv", return_value="/usr/bin/uv")
    def test_install_uv_success(self, mock_find_uv, mock_get_cli, mock_run):
        mock_get_cli.return_value = GENERATE_VEO_CLI
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        success, msg = install_cli("generate-veo-video")
        assert success
        assert "Generate Veo Video" in msg

    @patch("cli_hub.installer.get_cli")
    @patch("cli_hub.installer._find_uv", return_value=None)
    def test_install_uv_missing_shows_hint(self, mock_find_uv, mock_get_cli):
        mock_get_cli.return_value = GENERATE_VEO_CLI
        success, msg = install_cli("generate-veo-video")
        assert not success
        assert "uv is not installed" in msg
        assert "astral.sh/uv" in msg
        assert "brew install uv" in msg

    @patch("cli_hub.installer.subprocess.run")
    @patch("cli_hub.installer.get_cli")
    @patch("cli_hub.installer.INSTALLED_FILE", Path(tempfile.mktemp()))
    @patch("cli_hub.installer._find_uv", return_value="/usr/bin/uv")
    def test_uninstall_uv_success(self, mock_find_uv, mock_get_cli, mock_run):
        mock_get_cli.return_value = GENERATE_VEO_CLI
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        success, msg = uninstall_cli("generate-veo-video")
        assert success
        assert "Generate Veo Video" in msg

    @patch("cli_hub.installer.get_cli")
    @patch("cli_hub.installer._find_uv", return_value=None)
    def test_uninstall_uv_missing_shows_hint(self, mock_find_uv, mock_get_cli):
        mock_get_cli.return_value = GENERATE_VEO_CLI
        success, msg = uninstall_cli("generate-veo-video")
        assert not success
        assert "uv is not installed" in msg

    @patch("cli_hub.installer.subprocess.run")
    @patch("cli_hub.installer.get_cli")
    @patch("cli_hub.installer.INSTALLED_FILE", Path(tempfile.mktemp()))
    @patch("cli_hub.installer._find_uv", return_value="/usr/bin/uv")
    def test_update_uv_success(self, mock_find_uv, mock_get_cli, mock_run):
        mock_get_cli.return_value = GENERATE_VEO_CLI
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        from cli_hub.installer import update_cli
        success, msg = update_cli("generate-veo-video")
        assert success
        assert "Generate Veo Video" in msg

    @patch("cli_hub.installer.subprocess.run")
    @patch("cli_hub.installer.get_cli")
    @patch("cli_hub.installer._find_uv", return_value="/usr/bin/uv")
    def test_install_uv_failure_propagated(self, mock_find_uv, mock_get_cli, mock_run):
        mock_get_cli.return_value = GENERATE_VEO_CLI
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error: package not found")
        success, msg = install_cli("generate-veo-video")
        assert not success
        assert "failed" in msg.lower()


# ─── Script / pipe-command strategy tests (jimeng / Dreamina) ─────────

JIMENG_CLI = {
    "name": "jimeng",
    "display_name": "Jimeng / Dreamina CLI",
    "version": "latest",
    "description": "ByteDance AI image and video generation CLI",
    "category": "ai",
    "entry_point": "dreamina",
    "_source": "public",
    "install_strategy": "command",
    "package_manager": "script",
    "install_cmd": "curl -s https://jimeng.jianying.com/cli | bash",
}


class TestScriptStrategy:
    """Tests for script/pipe-command installs (e.g. jimeng curl | bash)."""

    # ── _install_strategy routing ──────────────────────────────────────

    def test_strategy_detected_as_command(self):
        """install_strategy field takes priority — jimeng routes to 'command'."""
        assert _install_strategy(JIMENG_CLI) == "command"

    def test_strategy_script_package_manager_without_field_falls_back_to_command(self):
        """Without install_strategy field, script package_manager still routes to 'command'."""
        cli = {**JIMENG_CLI}
        del cli["install_strategy"]
        assert _install_strategy(cli) == "command"

    # ── _run_command shell detection ───────────────────────────────────

    @patch("cli_hub.installer.subprocess.run")
    def test_run_command_uses_shell_true_for_pipe(self, mock_run):
        """Pipe character triggers shell=True so bash can interpret it."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        _run_command("curl -s https://jimeng.jianying.com/cli | bash")
        mock_run.assert_called_once()
        _, kwargs = mock_run.call_args
        assert kwargs.get("shell") is True
        # cmd passed as a single string, not a list
        args = mock_run.call_args[0][0]
        assert isinstance(args, str)
        assert "| bash" in args

    @patch("cli_hub.installer.subprocess.run")
    def test_run_command_uses_shell_false_for_simple_command(self, mock_run):
        """Simple commands (no shell operators) must NOT use shell=True."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        _run_command("brew install --cask 1password-cli")
        _, kwargs = mock_run.call_args
        assert kwargs.get("shell") is False or kwargs.get("shell") is None

    @patch("cli_hub.installer.subprocess.run")
    def test_run_command_uses_shell_true_for_and_operator(self, mock_run):
        """&& operator also triggers shell=True."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        _run_command("curl -O https://example.com/install.sh && bash install.sh")
        _, kwargs = mock_run.call_args
        assert kwargs.get("shell") is True

    # ── Full install flow ──────────────────────────────────────────────

    @patch("cli_hub.installer.subprocess.run")
    @patch("cli_hub.installer.get_cli")
    @patch("cli_hub.installer.INSTALLED_FILE", Path(tempfile.mktemp()))
    def test_install_jimeng_success(self, mock_get_cli, mock_run):
        """install_cli('jimeng') succeeds and invokes the pipe command via shell."""
        mock_get_cli.return_value = JIMENG_CLI
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        success, msg = install_cli("jimeng")

        assert success, f"Expected success but got: {msg}"
        assert "Jimeng" in msg

        mock_run.assert_called_once()
        _, kwargs = mock_run.call_args
        assert kwargs.get("shell") is True
        assert "| bash" in mock_run.call_args[0][0]

    @patch("cli_hub.installer.subprocess.run")
    @patch("cli_hub.installer.get_cli")
    @patch("cli_hub.installer.INSTALLED_FILE", Path(tempfile.mktemp()))
    def test_install_jimeng_failure_propagated(self, mock_get_cli, mock_run):
        """A non-zero exit from the curl|bash script surfaces as failure."""
        mock_get_cli.return_value = JIMENG_CLI
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="curl: (6) Could not resolve host"
        )

        success, msg = install_cli("jimeng")

        assert not success
        assert "failed" in msg.lower()

    @patch("cli_hub.installer.get_cli")
    def test_uninstall_jimeng_no_cmd_returns_graceful_message(self, mock_get_cli):
        """Uninstalling jimeng (no uninstall_cmd defined) returns a non-crash message."""
        mock_get_cli.return_value = JIMENG_CLI  # no uninstall_cmd key

        success, msg = uninstall_cli("jimeng")

        assert not success
        # Should mention the CLI name or explain no command available — never crash
        assert msg

    @patch("cli_hub.installer.subprocess.run")
    @patch("cli_hub.installer.get_cli")
    @patch("cli_hub.installer.INSTALLED_FILE", Path(tempfile.mktemp()))
    def test_install_jimeng_recorded_in_installed_json(self, mock_get_cli, mock_run):
        """After a successful install, jimeng appears in installed.json."""
        installed_file = Path(tempfile.mktemp())
        mock_get_cli.return_value = JIMENG_CLI
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        with patch("cli_hub.installer.INSTALLED_FILE", installed_file):
            success, _ = install_cli("jimeng")
            assert success
            data = json.loads(installed_file.read_text())
            assert "jimeng" in data
            assert data["jimeng"]["strategy"] == "command"
            assert data["jimeng"]["package_manager"] == "script"

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
            assert payload["event"] == "test-event"
            assert payload["properties"]["hostname"] == "clianything.cc"
            assert payload["properties"]["source"] == "cli"

    @patch("cli_hub.analytics._send_event")
    def test_track_event_noop_when_disabled(self, mock_send):
        with patch.dict(os.environ, {"CLI_HUB_NO_ANALYTICS": "1"}):
            track_event("test-event")
            import time
            time.sleep(0.2)
            mock_send.assert_not_called()

    @patch("cli_hub.analytics._send_event")
    def test_track_event_supports_umami_provider(self, mock_send):
        with patch.dict(os.environ, {"CLI_HUB_ANALYTICS_PROVIDER": "umami"}, clear=False):
            track_event("test-event")
            import time
            time.sleep(0.2)
            mock_send.assert_called_once()
            payload = mock_send.call_args[0][0]
            assert payload["payload"]["name"] == "test-event"
            assert payload["payload"]["hostname"] == "clianything.cc"

    @patch("cli_hub.analytics._send_event")
    def test_track_install_event_name_is_flat(self, mock_send):
        """cli-install event name is static; CLI name lives in properties.cli."""
        with patch.dict(os.environ, {}, clear=True):
            track_install("gimp", "1.0.0")
            import time
            time.sleep(0.2)
            mock_send.assert_called_once()
            payload = mock_send.call_args[0][0]
            assert payload["event"] == "cli-install"
            assert payload["properties"]["$current_url"] == "https://clianything.cc/cli-anything-hub/install/gimp"
            assert payload["properties"]["cli"] == "gimp"
            assert payload["properties"]["version"] == "1.0.0"
            assert "platform" in payload["properties"]

    @patch("cli_hub.analytics._send_event")
    def test_track_uninstall_event_name_is_flat(self, mock_send):
        """cli-uninstall event name is static; CLI name lives in properties.cli."""
        with patch.dict(os.environ, {}, clear=True):
            analytics_track_uninstall("blender")
            import time
            time.sleep(0.2)
            mock_send.assert_called_once()
            payload = mock_send.call_args[0][0]
            assert payload["event"] == "cli-uninstall"
            assert payload["properties"]["$current_url"] == "https://clianything.cc/cli-anything-hub/uninstall/blender"
            assert payload["properties"]["cli"] == "blender"
            assert "platform" in payload["properties"]

    @patch("cli_hub.analytics._send_event")
    def test_track_launch_fires(self, mock_send):
        """cli-launch event fires with the CLI name in properties."""
        from cli_hub.analytics import track_launch
        with patch.dict(os.environ, {}, clear=True):
            track_launch("gimp")
            import time
            time.sleep(0.2)
            mock_send.assert_called_once()
            payload = mock_send.call_args[0][0]
            assert payload["event"] == "cli-launch"
            assert payload["properties"]["cli"] == "gimp"
            assert payload["properties"]["$current_url"] == "https://clianything.cc/cli-anything-hub/launch/gimp"

    @patch("cli_hub.analytics._send_event")
    def test_track_visit_human(self, mock_send):
        """cli-hub call event sent when not detected as agent."""
        with patch.dict(os.environ, {}, clear=True):
            track_visit(is_agent=False)
            import time
            time.sleep(0.2)
            mock_send.assert_called_once()
            payload = mock_send.call_args[0][0]
            assert payload["event"] == "cli-hub call"
            assert payload["properties"]["$current_url"] == "https://clianything.cc/cli-anything-hub/call"
            assert payload["properties"]["command"] == "root"
            assert payload["properties"]["is_agent"] is False
            assert payload["properties"]["traffic_type"] == "human"

    @patch("cli_hub.analytics._send_event")
    def test_track_visit_agent(self, mock_send):
        """cli-hub call event captures the agent flag."""
        with patch.dict(os.environ, {}, clear=True):
            track_visit(is_agent=True, command="--version")
            import time
            time.sleep(0.2)
            mock_send.assert_called_once()
            payload = mock_send.call_args[0][0]
            assert payload["event"] == "cli-hub call"
            assert payload["properties"]["command"] == "--version"
            assert payload["properties"]["is_agent"] is True
            assert payload["properties"]["traffic_type"] == "agent"

    def test_detect_agent_claude_code(self):
        with patch.dict(os.environ, {"CLAUDE_CODE": "1"}):
            assert _detect_is_agent() is True

    def test_detect_agent_codex(self):
        with patch.dict(os.environ, {"CODEX": "1"}):
            assert _detect_is_agent() is True

    @patch("cli_hub.analytics._parent_process_commands", return_value=["/usr/local/bin/codex --run"])
    def test_detect_agent_from_parent_process(self, mock_cmds):
        with patch.dict(os.environ, {}, clear=True):
            context = detect_invocation_context()
            assert context["is_agent"] is True
            assert context["reason"] == "codex-process"
            assert "codex-process" in context["signals"]

    @pytest.mark.parametrize(
        ("command", "expected_reason"),
        [
            ("/usr/local/bin/gemini --prompt fix tests", "gemini-process"),
            ("/usr/local/bin/copilot agent", "copilot-process"),
            ("/usr/local/bin/auggie --print review", "auggie-process"),
            ("/opt/augment/bin/augment", "augment-process"),
            ("/usr/local/bin/ampcode fix build", "amp-process"),
            ("/usr/local/bin/opencode agent create", "opencode-process"),
            ("/usr/local/bin/kilo auth", "kilo-process"),
            ("/usr/local/bin/qodo chat", "qodo-process"),
            ("/usr/local/bin/kiro /agent create", "kiro-process"),
        ],
    )
    @patch("cli_hub.analytics._parent_process_commands")
    def test_detect_agent_from_expanded_parent_process_names(self, mock_cmds, command, expected_reason):
        mock_cmds.return_value = [command]
        with patch.dict(os.environ, {}, clear=True):
            context = detect_invocation_context()
            assert context["is_agent"] is True
            assert context["reason"] == expected_reason
            assert expected_reason in context["signals"]

    @patch("cli_hub.analytics._parent_process_commands", return_value=[])
    def test_detect_not_agent_clean_env(self, mock_cmds):
        """Clean env with a tty should not detect as agent."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("sys.stdin") as mock_stdin:
                mock_stdin.isatty.return_value = True
                assert _detect_is_agent() is False

    @patch("cli_hub.analytics._parent_process_commands", return_value=[])
    def test_detect_non_tty_is_agent(self, mock_cmds):
        with patch.dict(os.environ, {}, clear=True):
            with patch("sys.stdin") as mock_stdin:
                mock_stdin.isatty.return_value = False
                context = detect_invocation_context()
                assert context["is_agent"] is True
                assert context["traffic_type"] == "agent"
                assert context["category"] == "scripted_client"
                assert context["reason"] == "stdin-not-tty"

    @patch("cli_hub.analytics._send_event")
    def test_track_visit_uses_detection_context(self, mock_send):
        detection = {
            "is_agent": True,
            "traffic_type": "agent",
            "category": "agent_tool",
            "reason": "codex-process",
            "signals": ["codex-process", "stdin-not-tty"],
            "stdin_tty": False,
            "is_interactive": False,
        }
        with patch.dict(os.environ, {}, clear=True):
            track_visit(command="search", detection=detection)
            import time
            time.sleep(0.2)
            payload = mock_send.call_args[0][0]
            assert payload["properties"]["command"] == "search"
            assert payload["properties"]["agent_reason"] == "codex-process"
            assert payload["properties"]["agent_category"] == "agent_tool"
            assert payload["properties"]["agent_signals"] == ["codex-process", "stdin-not-tty"]
            assert payload["properties"]["stdin_tty"] is False
            assert payload["properties"]["is_interactive"] is False

    @patch("cli_hub.analytics._send_event")
    def test_first_run_sends_event(self, mock_send, tmp_path):
        """First invocation sends cli-hub-installed event."""
        with patch.dict(os.environ, {"HOME": str(tmp_path)}, clear=False):
            track_first_run()
            import time
            time.sleep(0.2)
            mock_send.assert_called_once()
            payload = mock_send.call_args[0][0]
            assert payload["event"] == "cli-anything-hub-installed"
            assert payload["properties"]["$current_url"] == "https://clianything.cc/cli-anything-hub/installed"
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
        self.human_detection = {
            "is_agent": False,
            "traffic_type": "human",
            "category": "human",
            "reason": "human",
            "signals": [],
            "stdin_tty": True,
            "is_interactive": True,
        }
        self.agent_detection = {
            "is_agent": True,
            "traffic_type": "agent",
            "category": "agent_tool",
            "reason": "codex-env",
            "signals": ["codex-env"],
            "stdin_tty": False,
            "is_interactive": False,
        }

    @patch("cli_hub.cli.track_first_run")
    @patch("cli_hub.cli.track_visit")
    @patch("cli_hub.cli.detect_invocation_context")
    def test_version(self, mock_detect, mock_visit, mock_first_run):
        mock_detect.return_value = self.human_detection
        result = self.runner.invoke(main, ["--version"])
        assert __version__ in result.output
        assert result.exit_code == 0
        mock_visit.assert_called_once_with(command="--version", detection=self.human_detection)
        mock_first_run.assert_called_once()

    @patch("cli_hub.cli.track_first_run")
    @patch("cli_hub.cli.track_visit")
    @patch("cli_hub.cli.detect_invocation_context")
    def test_help(self, mock_detect, mock_visit, mock_first_run):
        mock_detect.return_value = self.human_detection
        result = self.runner.invoke(main, ["--help"])
        assert "cli-hub" in result.output
        assert result.exit_code == 0

    @patch("cli_hub.cli.track_first_run")
    @patch("cli_hub.cli.track_visit")
    @patch("cli_hub.cli.detect_invocation_context")
    @patch("cli_hub.cli.fetch_all_clis", return_value=SAMPLE_REGISTRY["clis"])
    @patch("cli_hub.cli.list_categories", return_value=["3d", "audio", "image"])
    @patch("cli_hub.cli.get_installed", return_value={})
    def test_list_command(self, mock_installed, mock_categories, mock_fetch, mock_detect, mock_visit, mock_first_run):
        mock_detect.return_value = self.human_detection
        result = self.runner.invoke(main, ["list"])
        assert "gimp" in result.output
        assert "blender" in result.output
        assert result.exit_code == 0

    @patch("cli_hub.cli.track_first_run")
    @patch("cli_hub.cli.track_visit")
    @patch("cli_hub.cli.detect_invocation_context")
    @patch("cli_hub.cli.fetch_all_clis", return_value=SAMPLE_REGISTRY["clis"])
    @patch("cli_hub.cli.list_categories", return_value=["3d", "audio", "image"])
    @patch("cli_hub.cli.get_installed", return_value={})
    def test_list_with_category(self, mock_installed, mock_categories, mock_fetch, mock_detect, mock_visit, mock_first_run):
        mock_detect.return_value = self.human_detection
        result = self.runner.invoke(main, ["list", "-c", "image"])
        assert "gimp" in result.output
        assert "blender" not in result.output

    @patch("cli_hub.cli.track_first_run")
    @patch("cli_hub.cli.track_visit")
    @patch("cli_hub.cli.detect_invocation_context")
    @patch("cli_hub.cli.search_clis", return_value=[SAMPLE_REGISTRY["clis"][0]])
    @patch("cli_hub.cli.get_installed", return_value={})
    def test_search_command(self, mock_installed, mock_search, mock_detect, mock_visit, mock_first_run):
        mock_detect.return_value = self.human_detection
        result = self.runner.invoke(main, ["search", "gimp"])
        assert "gimp" in result.output
        assert result.exit_code == 0

    @patch("cli_hub.cli.track_first_run")
    @patch("cli_hub.cli.track_visit")
    @patch("cli_hub.cli.detect_invocation_context")
    @patch("cli_hub.cli.get_cli", return_value=SAMPLE_REGISTRY["clis"][0])
    @patch("cli_hub.cli.get_installed", return_value={})
    def test_info_command(self, mock_installed, mock_get, mock_detect, mock_visit, mock_first_run):
        mock_detect.return_value = self.human_detection
        result = self.runner.invoke(main, ["info", "gimp"])
        assert "GIMP" in result.output
        assert "image" in result.output
        assert "Install: cli-hub install gimp" in result.output
        assert result.exit_code == 0

    @patch("cli_hub.cli.track_first_run")
    @patch("cli_hub.cli.track_visit")
    @patch("cli_hub.cli.detect_invocation_context")
    @patch("cli_hub.cli.get_cli", return_value=None)
    def test_info_not_found(self, mock_get, mock_detect, mock_visit, mock_first_run):
        mock_detect.return_value = self.human_detection
        result = self.runner.invoke(main, ["info", "nonexistent"])
        assert result.exit_code == 1

    @patch("cli_hub.cli.track_first_run")
    @patch("cli_hub.cli.track_visit")
    @patch("cli_hub.cli.detect_invocation_context")
    @patch("cli_hub.cli.track_install")
    @patch("cli_hub.cli.install_cli", return_value=(True, "Installed GIMP (cli-anything-gimp)"))
    @patch("cli_hub.cli.get_cli", return_value=SAMPLE_REGISTRY["clis"][0])
    def test_install_command(self, mock_get, mock_install, mock_track, mock_detect, mock_visit, mock_first_run):
        mock_detect.return_value = self.human_detection
        result = self.runner.invoke(main, ["install", "gimp"])
        assert result.exit_code == 0
        assert "Installed" in result.output
        mock_track.assert_called_once()

    @patch("cli_hub.cli.track_first_run")
    @patch("cli_hub.cli.track_visit")
    @patch("cli_hub.cli.detect_invocation_context")
    @patch("cli_hub.cli.track_uninstall")
    @patch("cli_hub.cli.uninstall_cli", return_value=(True, "Uninstalled GIMP"))
    def test_uninstall_command(self, mock_uninstall, mock_track, mock_detect, mock_visit, mock_first_run):
        mock_detect.return_value = self.human_detection
        result = self.runner.invoke(main, ["uninstall", "gimp"])
        assert result.exit_code == 0
        mock_track.assert_called_once()

    @patch("cli_hub.cli.track_first_run")
    @patch("cli_hub.cli.track_visit")
    @patch("cli_hub.cli.detect_invocation_context")
    def test_visit_agent_on_invocation(self, mock_detect, mock_visit, mock_first_run):
        """When agent env detected, track_visit is called with the new cli-hub call metadata."""
        mock_detect.return_value = self.agent_detection
        result = self.runner.invoke(main, ["--version"])
        mock_visit.assert_called_once_with(command="--version", detection=self.agent_detection)

    @patch("cli_hub.cli.track_first_run")
    @patch("cli_hub.cli.track_visit")
    @patch("cli_hub.cli.detect_invocation_context")
    @patch("cli_hub.cli.install_cli", return_value=(True, "Installed Jimeng / Dreamina CLI (dreamina)"))
    @patch("cli_hub.cli.get_cli", return_value={**SAMPLE_REGISTRY["clis"][0], "entry_point": "dreamina", "name": "jimeng", "display_name": "Jimeng / Dreamina CLI", "version": "latest", "_source": "public"})
    @patch("cli_hub.cli.track_install")
    def test_install_shows_launch_hint(self, mock_track, mock_get, mock_install, mock_detect, mock_visit, mock_first_run):
        """Post-install output includes both entry point and cli-hub launch hint."""
        mock_detect.return_value = self.human_detection
        result = self.runner.invoke(main, ["install", "jimeng"])
        assert result.exit_code == 0
        assert "dreamina" in result.output
        assert "cli-hub launch jimeng" in result.output

    @patch("cli_hub.cli.track_first_run")
    @patch("cli_hub.cli.track_visit")
    @patch("cli_hub.cli.detect_invocation_context")
    @patch("cli_hub.cli.shutil.which", return_value="/usr/bin/dreamina")
    @patch("cli_hub.cli.os.execvp")
    @patch("cli_hub.cli.get_cli", return_value=JIMENG_CLI)
    def test_launch_execs_entry_point(self, mock_get, mock_execvp, mock_which, mock_detect, mock_visit, mock_first_run):
        """launch execs the CLI entry point, passing through extra args."""
        mock_detect.return_value = self.human_detection
        result = self.runner.invoke(main, ["launch", "jimeng", "login"])
        mock_execvp.assert_called_once_with("dreamina", ["dreamina", "login"])

    @patch("cli_hub.cli.track_first_run")
    @patch("cli_hub.cli.track_visit")
    @patch("cli_hub.cli.detect_invocation_context")
    @patch("cli_hub.cli.shutil.which", return_value=None)
    @patch("cli_hub.cli.get_cli", return_value=JIMENG_CLI)
    def test_launch_not_on_path_shows_install_hint(self, mock_get, mock_which, mock_detect, mock_visit, mock_first_run):
        """launch fails gracefully when entry point not on PATH."""
        mock_detect.return_value = self.human_detection
        result = self.runner.invoke(main, ["launch", "jimeng"])
        assert result.exit_code == 1
        assert "cli-hub install jimeng" in result.output

    @patch("cli_hub.cli.track_first_run")
    @patch("cli_hub.cli.track_visit")
    @patch("cli_hub.cli.detect_invocation_context")
    @patch("cli_hub.cli.get_cli", return_value=None)
    def test_launch_unknown_cli(self, mock_get, mock_detect, mock_visit, mock_first_run):
        """launch with an unknown CLI name exits with error."""
        mock_detect.return_value = self.human_detection
        result = self.runner.invoke(main, ["launch", "nonexistent"])
        assert result.exit_code == 1
        assert "not found" in result.output
