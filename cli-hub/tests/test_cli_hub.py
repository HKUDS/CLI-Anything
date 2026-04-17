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
from cli_hub.matrix import fetch_matrix_registry, fetch_all_matrices, get_matrix, search_matrices
from cli_hub.matrix_skill import resolve_local_skill_path, render_matrix_skill_file, _render_stage_tooling, _render_discovery_section
from cli_hub.installer import (
    install_cli,
    install_matrix,
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
            "skill_md": "gimp/agent-harness/cli_anything/gimp/skills/SKILL.md",
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

SAMPLE_MATRIX_REGISTRY = {
    "meta": {"repo": "https://github.com/HKUDS/CLI-Anything", "description": "test matrices"},
    "matrices": [
        {
            "name": "video-creation",
            "display_name": "Video Creation & Editing",
            "description": "Curated video workflow matrix",
            "category": "video",
            "matrix": "cli-matrix",
            "matrix_id": "V1",
            "skill_md": "cli-hub-matrix/video-creation/SKILL.md",
            "clis": ["gimp", "blender", "audacity"],
            "stages": [
                {
                    "name": "Thumbnail",
                    "clis": ["gimp"],
                    "goal": "Create a thumbnail image",
                    "alternatives": {"python": ["Pillow"], "native": ["ImageMagick convert"]},
                    "skill_search_hints": ["thumbnail", "image editing"],
                },
                {"name": "3D", "clis": ["blender"]},
                {
                    "name": "Audio",
                    "clis": ["audacity"],
                    "goal": "Edit and process audio",
                    "alternatives": {"python": ["pydub"], "native": ["sox"]},
                    "skill_search_hints": ["audio editing"],
                },
            ],
        }
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


class TestMatrixRegistry:
    """Tests for matrix.py — fetch, cache, search, and lookup."""

    @patch("cli_hub.matrix.requests.get")
    @patch("cli_hub.matrix.MATRIX_CACHE_FILE", Path(tempfile.mktemp()))
    def test_fetch_matrix_registry_from_remote(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = SAMPLE_MATRIX_REGISTRY
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = fetch_matrix_registry(force_refresh=True)
        assert result["matrices"][0]["name"] == "video-creation"
        mock_get.assert_called_once()

    @patch("cli_hub.matrix.fetch_all_matrices", return_value=SAMPLE_MATRIX_REGISTRY["matrices"])
    def test_get_matrix_found(self, mock_fetch):
        matrix_item = get_matrix("video-creation")
        assert matrix_item is not None
        assert matrix_item["display_name"] == "Video Creation & Editing"

    @patch("cli_hub.matrix.fetch_all_matrices", return_value=SAMPLE_MATRIX_REGISTRY["matrices"])
    def test_search_matrices_matches_description(self, mock_fetch):
        results = search_matrices("video")
        assert len(results) == 1
        assert results[0]["name"] == "video-creation"


class TestMatrixSkill:
    """Tests for matrix_skill.py — local skill resolution and rendering."""

    @patch("cli_hub.matrix_skill.metadata.distribution")
    def test_resolve_local_skill_path_from_distribution(self, mock_distribution, tmp_path):
        class FakeDist:
            files = [Path("cli_anything/audacity/skills/SKILL.md")]

            def locate_file(self, file):
                return tmp_path / file

        mock_distribution.return_value = FakeDist()
        cli = {"name": "audacity", "_source": "harness"}
        resolved = resolve_local_skill_path(cli)
        assert resolved == str((tmp_path / "cli_anything/audacity/skills/SKILL.md").resolve())

    @patch("cli_hub.matrix_skill.MATRIX_SKILL_DIR", Path(tempfile.mkdtemp()))
    @patch("cli_hub.matrix_skill.resolve_local_skill_path")
    @patch("cli_hub.matrix_skill.get_cli")
    def test_render_matrix_skill_file_injects_paths(self, mock_get_cli, mock_resolve, tmp_dir=None):
        mock_get_cli.side_effect = lambda name: next((c for c in SAMPLE_REGISTRY["clis"] if c["name"] == name), None)
        mock_resolve.side_effect = lambda cli: f"/tmp/{cli['name']}/skills/SKILL.md" if cli["name"] != "blender" else None

        rendered = render_matrix_skill_file(SAMPLE_MATRIX_REGISTRY["matrices"][0], installed={"gimp": {}, "audacity": {}})
        content = Path(rendered).read_text()
        assert "## Installed CLI Skills" in content
        assert "/tmp/gimp/skills/SKILL.md" in content
        assert "gimp/agent-harness/cli_anything/gimp/skills/SKILL.md" in content
        assert "not installed" in content


class TestMultiApproachRendering:
    """Tests for multi-approach stage rendering in matrix_skill.py."""

    def test_render_stage_tooling_includes_goals(self):
        matrix_item = SAMPLE_MATRIX_REGISTRY["matrices"][0]
        result = _render_stage_tooling(matrix_item, installed={"gimp": {}})
        assert "## Stage Tooling Overview" in result
        assert "Create a thumbnail image" in result
        assert "Edit and process audio" in result

    def test_render_stage_tooling_includes_alternatives(self):
        matrix_item = SAMPLE_MATRIX_REGISTRY["matrices"][0]
        result = _render_stage_tooling(matrix_item, installed={})
        assert "Pillow" in result
        assert "pydub" in result
        assert "sox" in result
        assert "ImageMagick convert" in result

    def test_render_stage_tooling_shows_install_status(self):
        matrix_item = SAMPLE_MATRIX_REGISTRY["matrices"][0]
        result = _render_stage_tooling(matrix_item, installed={"gimp": {}})
        assert "`gimp` (installed)" in result
        assert "`audacity` (not installed)" in result

    def test_render_stage_tooling_includes_skill_search_hints(self):
        matrix_item = SAMPLE_MATRIX_REGISTRY["matrices"][0]
        result = _render_stage_tooling(matrix_item, installed={})
        assert 'npx skills search "thumbnail"' in result
        assert 'npx skills search "audio editing"' in result

    def test_render_stage_tooling_backward_compat_no_goal(self):
        """Stages without 'goal' field are skipped gracefully."""
        matrix_no_goals = {
            "name": "test",
            "stages": [
                {"name": "Stage1", "clis": ["foo"]},
            ],
        }
        result = _render_stage_tooling(matrix_no_goals, installed={})
        assert result == ""

    def test_render_discovery_section(self):
        matrix_item = SAMPLE_MATRIX_REGISTRY["matrices"][0]
        result = _render_discovery_section(matrix_item)
        assert "## Skill Discovery Commands" in result
        assert 'npx skills search "thumbnail"' in result
        assert 'npx skills search "audio editing"' in result
        assert "cli-hub search thumbnail" in result
        assert "cli-hub search audio" in result

    def test_render_discovery_section_empty_when_no_hints(self):
        matrix_no_hints = {
            "name": "test",
            "stages": [{"name": "S1", "clis": ["foo"]}],
        }
        result = _render_discovery_section(matrix_no_hints)
        assert result == ""

    @patch("cli_hub.matrix_skill.MATRIX_SKILL_DIR", Path(tempfile.mkdtemp()))
    @patch("cli_hub.matrix_skill.resolve_local_skill_path")
    @patch("cli_hub.matrix_skill.get_cli")
    def test_render_matrix_skill_file_includes_stage_tooling(self, mock_get_cli, mock_resolve):
        mock_get_cli.side_effect = lambda name: next((c for c in SAMPLE_REGISTRY["clis"] if c["name"] == name), None)
        mock_resolve.return_value = None

        rendered = render_matrix_skill_file(SAMPLE_MATRIX_REGISTRY["matrices"][0], installed={"gimp": {}})
        content = Path(rendered).read_text()
        assert "## Stage Tooling Overview" in content
        assert "## Skill Discovery Commands" in content
        assert "Create a thumbnail image" in content


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

    @patch("cli_hub.installer.get_matrix", return_value=SAMPLE_MATRIX_REGISTRY["matrices"][0])
    @patch("cli_hub.installer.get_cli", side_effect=lambda name: next((c for c in SAMPLE_REGISTRY["clis"] if c["name"] == name), None))
    @patch("cli_hub.installer.install_cli", side_effect=[(True, "Installed Blender"), (False, "Install failed")])
    @patch("cli_hub.installer.get_installed", return_value={"gimp": {"version": "1.0.0"}})
    @patch("cli_hub.installer.render_matrix_skill_file", return_value=Path("/tmp/video-creation.SKILL.md"))
    def test_install_matrix_reports_installed_skipped_and_failed(self, mock_render, mock_installed, mock_install_cli, mock_get_cli, mock_get_matrix):
        success, payload = install_matrix("video-creation")
        assert not success
        assert payload["summary"] == {"total": 3, "installed": 1, "skipped": 1, "failed": 1}
        assert payload["results"][0]["status"] == "skipped"
        assert payload["results"][1]["status"] == "installed"
        assert payload["results"][2]["status"] == "failed"
        assert payload["rendered_skill_path"] == "/tmp/video-creation.SKILL.md"

    @patch("cli_hub.installer.get_matrix", return_value=None)
    def test_install_matrix_not_found(self, mock_get_matrix):
        success, payload = install_matrix("missing-matrix")
        assert not success
        assert "not found" in payload["error"]


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
    @patch("cli_hub.cli.fetch_all_matrices", return_value=SAMPLE_MATRIX_REGISTRY["matrices"])
    @patch("cli_hub.cli.get_installed", return_value={"gimp": {"version": "1.0.0"}})
    def test_matrix_list_command(self, mock_installed, mock_fetch_matrices, mock_detect, mock_visit, mock_first_run):
        mock_detect.return_value = self.human_detection
        result = self.runner.invoke(main, ["matrix", "list"])
        assert "video-creation" in result.output
        assert "1/3" in result.output
        assert result.exit_code == 0

    @patch("cli_hub.cli.track_first_run")
    @patch("cli_hub.cli.track_visit")
    @patch("cli_hub.cli.detect_invocation_context")
    @patch("cli_hub.cli.search_matrices", return_value=SAMPLE_MATRIX_REGISTRY["matrices"])
    @patch("cli_hub.cli.get_installed", return_value={"gimp": {"version": "1.0.0"}})
    def test_matrix_search_command(self, mock_installed, mock_search, mock_detect, mock_visit, mock_first_run):
        mock_detect.return_value = self.human_detection
        result = self.runner.invoke(main, ["matrix", "search", "video"])
        assert "video-creation" in result.output
        assert "1/3" in result.output
        assert result.exit_code == 0

    @patch("cli_hub.cli.track_first_run")
    @patch("cli_hub.cli.track_visit")
    @patch("cli_hub.cli.detect_invocation_context")
    @patch("cli_hub.cli.search_matrices", return_value=[])
    def test_matrix_search_no_results(self, mock_search, mock_detect, mock_visit, mock_first_run):
        mock_detect.return_value = self.human_detection
        result = self.runner.invoke(main, ["matrix", "search", "nonexistent"])
        assert "No matrices matching" in result.output
        assert result.exit_code == 0

    @patch("cli_hub.cli.track_first_run")
    @patch("cli_hub.cli.track_visit")
    @patch("cli_hub.cli.detect_invocation_context")
    @patch("cli_hub.cli.get_matrix", return_value=SAMPLE_MATRIX_REGISTRY["matrices"][0])
    @patch("cli_hub.cli.get_installed", return_value={"gimp": {"version": "1.0.0"}})
    @patch("cli_hub.cli.get_rendered_matrix_skill_path", return_value=Path("/tmp/video-creation.SKILL.md"))
    @patch("pathlib.Path.exists", return_value=True)
    def test_matrix_info_command(self, mock_exists, mock_rendered, mock_installed, mock_get_matrix, mock_detect, mock_visit, mock_first_run):
        mock_detect.return_value = self.human_detection
        result = self.runner.invoke(main, ["matrix", "info", "video-creation"])
        assert "Video Creation & Editing" in result.output
        assert "cli-hub matrix install video-creation" in result.output
        assert "cli-hub-matrix/video-creation/SKILL.md" in result.output
        assert "Local skill: /tmp/video-creation.SKILL.md" in result.output
        assert result.exit_code == 0

    @patch("cli_hub.cli.track_first_run")
    @patch("cli_hub.cli.track_visit")
    @patch("cli_hub.cli.detect_invocation_context")
    @patch("cli_hub.cli.install_matrix", return_value=(False, {
        "matrix": SAMPLE_MATRIX_REGISTRY["matrices"][0],
        "results": [
            {"name": "gimp", "status": "skipped", "message": "Already installed"},
            {"name": "blender", "status": "installed", "message": "Installed Blender"},
            {"name": "audacity", "status": "failed", "message": "Install failed"},
        ],
        "summary": {"installed": 1, "skipped": 1, "failed": 1},
        "rendered_skill_path": "/tmp/video-creation.SKILL.md",
    }))
    def test_matrix_install_command_partial_failure(self, mock_install_matrix, mock_detect, mock_visit, mock_first_run):
        mock_detect.return_value = self.human_detection
        result = self.runner.invoke(main, ["matrix", "install", "video-creation"])
        assert result.exit_code == 1
        assert "Summary: 1 installed, 1 skipped, 1 failed" in result.output
        assert "Matrix skill: cli-hub-matrix/video-creation/SKILL.md" in result.output
        assert "Local matrix skill: /tmp/video-creation.SKILL.md" in result.output

    @patch("cli_hub.cli.track_first_run")
    @patch("cli_hub.cli.track_visit")
    @patch("cli_hub.cli.detect_invocation_context")
    @patch("cli_hub.cli.install_matrix", return_value=(False, {"error": "Matrix 'missing' not found."}))
    def test_matrix_install_command_not_found(self, mock_install_matrix, mock_detect, mock_visit, mock_first_run):
        mock_detect.return_value = self.human_detection
        result = self.runner.invoke(main, ["matrix", "install", "missing"])
        assert result.exit_code == 1
        assert "not found" in result.output

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
        assert "Skill:" in result.output
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
