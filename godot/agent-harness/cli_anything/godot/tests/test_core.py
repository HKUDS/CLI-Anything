"""Unit tests for cli-anything-godot — no Godot binary required.

Tests project management, scene I/O, and export preset parsing
using temporary directories and mock files.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner

from cli_anything.godot.godot_cli import cli


# ── Fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def tmp_project(tmp_path):
    """Create a minimal Godot project in a temp directory."""
    project_file = tmp_path / "project.godot"
    project_file.write_text(
        '; Engine configuration file.\n\n'
        '[application]\n\n'
        'config/name="TestGame"\n'
        'config/features=PackedStringArray("4.4", "GL Compatibility")\n'
        'run/main_scene="res://scenes/Main.tscn"\n\n'
        '[rendering]\n\n'
        'renderer/rendering_method="gl_compatibility"\n',
        encoding="utf-8",
    )

    # Create some scene files
    scenes_dir = tmp_path / "scenes"
    scenes_dir.mkdir()
    (scenes_dir / "Main.tscn").write_text(
        '[gd_scene format=3 uid="uid://abc123"]\n\n'
        '[node name="Main" type="Node2D"]\n',
        encoding="utf-8",
    )
    (scenes_dir / "Level1.tscn").write_text(
        '[gd_scene format=3 uid="uid://def456"]\n\n'
        '[node name="Level1" type="Node3D"]\n\n'
        '[node name="Player" type="CharacterBody3D" parent="."]\n',
        encoding="utf-8",
    )

    # Create script files
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "player.gd").write_text(
        'extends CharacterBody3D\n\nfunc _ready():\n\tpass\n',
        encoding="utf-8",
    )

    # Create resource files
    (tmp_path / "icon.tres").write_text("", encoding="utf-8")

    return tmp_path


@pytest.fixture
def runner():
    return CliRunner()


# ── Project tests ──────────────────────────────────────────────────────

class TestProjectCreate:
    def test_create_new_project(self, runner, tmp_path):
        project_dir = tmp_path / "new_game"
        result = runner.invoke(cli, ["--json", "project", "create", str(project_dir)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "ok"
        assert data["project_name"] == "new_game"
        assert (project_dir / "project.godot").exists()

    def test_create_with_custom_name(self, runner, tmp_path):
        project_dir = tmp_path / "my_dir"
        result = runner.invoke(cli, [
            "--json", "project", "create", str(project_dir), "--name", "Cool Game"
        ])
        data = json.loads(result.output)
        assert data["status"] == "ok"
        assert data["project_name"] == "Cool Game"

    def test_create_duplicate_fails(self, runner, tmp_project):
        result = runner.invoke(cli, ["--json", "project", "create", str(tmp_project)])
        data = json.loads(result.output)
        assert data["status"] == "error"


class TestProjectInfo:
    def test_info_valid_project(self, runner, tmp_project):
        result = runner.invoke(cli, ["--json", "-p", str(tmp_project), "project", "info"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "ok"
        assert data["name"] == "TestGame"
        assert "4.4" in data["features"]

    def test_info_invalid_project(self, runner, tmp_path):
        result = runner.invoke(cli, ["--json", "-p", str(tmp_path), "project", "info"])
        data = json.loads(result.output)
        assert data["status"] == "error"


class TestProjectList:
    def test_list_scenes(self, runner, tmp_project):
        result = runner.invoke(cli, ["--json", "-p", str(tmp_project), "project", "scenes"])
        data = json.loads(result.output)
        assert data["status"] == "ok"
        assert data["count"] == 2
        assert "scenes/Main.tscn" in data["scenes"]
        assert "scenes/Level1.tscn" in data["scenes"]

    def test_list_scripts(self, runner, tmp_project):
        result = runner.invoke(cli, ["--json", "-p", str(tmp_project), "project", "scripts"])
        data = json.loads(result.output)
        assert data["status"] == "ok"
        assert data["count"] == 1
        assert "scripts/player.gd" in data["scripts"]

    def test_list_resources(self, runner, tmp_project):
        result = runner.invoke(cli, ["--json", "-p", str(tmp_project), "project", "resources"])
        data = json.loads(result.output)
        assert data["status"] == "ok"
        assert data["count"] == 1


# ── Scene tests ────────────────────────────────────────────────────────

class TestSceneCreate:
    def test_create_scene(self, runner, tmp_project):
        result = runner.invoke(cli, [
            "--json", "-p", str(tmp_project),
            "scene", "create", "scenes/NewScene.tscn",
            "--root-type", "Node3D",
        ])
        data = json.loads(result.output)
        assert data["status"] == "ok"
        assert data["root_type"] == "Node3D"
        assert (tmp_project / "scenes" / "NewScene.tscn").exists()

    def test_create_duplicate_scene_fails(self, runner, tmp_project):
        result = runner.invoke(cli, [
            "--json", "-p", str(tmp_project),
            "scene", "create", "scenes/Main.tscn",
        ])
        data = json.loads(result.output)
        assert data["status"] == "error"


class TestSceneRead:
    def test_read_scene(self, runner, tmp_project):
        result = runner.invoke(cli, [
            "--json", "-p", str(tmp_project),
            "scene", "read", "scenes/Level1.tscn",
        ])
        data = json.loads(result.output)
        assert data["status"] == "ok"
        assert len(data["nodes"]) == 2
        assert data["nodes"][0]["name"] == "Level1"
        assert data["nodes"][1]["name"] == "Player"

    def test_read_nonexistent_scene(self, runner, tmp_project):
        result = runner.invoke(cli, [
            "--json", "-p", str(tmp_project),
            "scene", "read", "scenes/Nope.tscn",
        ])
        data = json.loads(result.output)
        assert data["status"] == "error"


class TestSceneAddNode:
    def test_add_node(self, runner, tmp_project):
        result = runner.invoke(cli, [
            "--json", "-p", str(tmp_project),
            "scene", "add-node", "scenes/Main.tscn",
            "--name", "Camera",
            "--type", "Camera2D",
        ])
        data = json.loads(result.output)
        assert data["status"] == "ok"
        assert data["node_name"] == "Camera"

        # Verify the node was added to the file
        content = (tmp_project / "scenes" / "Main.tscn").read_text()
        assert 'name="Camera"' in content
        assert 'type="Camera2D"' in content


# ── Export tests ───────────────────────────────────────────────────────

class TestExportPresets:
    def test_no_presets_file(self, runner, tmp_project):
        result = runner.invoke(cli, [
            "--json", "-p", str(tmp_project), "export", "presets"
        ])
        data = json.loads(result.output)
        assert data["status"] == "ok"
        assert data["count"] == 0

    def test_parse_presets(self, runner, tmp_project):
        presets_file = tmp_project / "export_presets.cfg"
        presets_file.write_text(
            '[preset.0]\n\n'
            'name="Windows Desktop"\n'
            'platform="Windows Desktop"\n'
            'export_path="build/game.exe"\n\n'
            '[preset.1]\n\n'
            'name="Linux"\n'
            'platform="Linux/X11"\n'
            'export_path="build/game.x86_64"\n',
            encoding="utf-8",
        )
        result = runner.invoke(cli, [
            "--json", "-p", str(tmp_project), "export", "presets"
        ])
        data = json.loads(result.output)
        assert data["count"] == 2
        assert data["presets"][0]["name"] == "Windows Desktop"
        assert data["presets"][1]["platform"] == "Linux/X11"


# ── Engine tests ───────────────────────────────────────────────────────

class TestEngineStatus:
    def test_engine_status_no_godot(self, runner):
        with mock.patch(
            "cli_anything.godot.utils.godot_backend.find_godot_binary",
            return_value=None,
        ):
            result = runner.invoke(cli, ["--json", "engine", "status"])
            data = json.loads(result.output)
            assert data["available"] is False

    def test_engine_status_found(self, runner):
        with mock.patch(
            "cli_anything.godot.godot_cli.find_godot_binary",
            return_value="/usr/bin/godot",
        ):
            with mock.patch(
                "cli_anything.godot.godot_cli.is_available",
                return_value=True,
            ):
                result = runner.invoke(cli, ["--json", "engine", "status"])
                data = json.loads(result.output)
                assert data["available"] is True
                assert data["binary"] == "/usr/bin/godot"


# ── Backend tests ──────────────────────────────────────────────────────

class TestBackend:
    def test_validate_project(self, tmp_project):
        from cli_anything.godot.utils.godot_backend import validate_project
        assert validate_project(str(tmp_project)) is True

    def test_validate_non_project(self, tmp_path):
        from cli_anything.godot.utils.godot_backend import validate_project
        assert validate_project(str(tmp_path)) is False

    def test_find_godot_binary_env(self):
        from cli_anything.godot.utils.godot_backend import find_godot_binary
        with mock.patch.dict(os.environ, {"GODOT_BIN": "python"}):
            # python is guaranteed to be on PATH
            result = find_godot_binary()
            assert result is not None


# ── CLI root tests ─────────────────────────────────────────────────────

class TestCLIRoot:
    def test_help(self, runner):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "cli-anything-godot" in result.output

    def test_no_args_shows_help(self, runner):
        result = runner.invoke(cli, [])
        assert "cli-anything-godot" in result.output

    def test_json_flag(self, runner, tmp_project):
        result = runner.invoke(cli, ["--json", "-p", str(tmp_project), "project", "info"])
        data = json.loads(result.output)
        assert isinstance(data, dict)

    def test_human_output(self, runner, tmp_project):
        result = runner.invoke(cli, ["-p", str(tmp_project), "project", "info"])
        assert "TestGame" in result.output
