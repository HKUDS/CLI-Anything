"""End-to-end tests for cli-anything-godot.

These tests require Godot 4.x to be installed and on PATH.
They are automatically skipped when the binary is not available.
Run explicitly with: pytest -m e2e
"""

import json
import textwrap

import pytest
from click.testing import CliRunner

from cli_anything.godot.godot_cli import cli
from cli_anything.godot.utils.godot_backend import is_available


_godot_missing = not is_available()
skip_no_godot = pytest.mark.skipif(
    _godot_missing, reason="Godot binary not found on PATH"
)


# ── helpers ───────────────────────────────────────────────────────────

def _invoke_json(runner, args):
    """Invoke CLI with --json flag and return parsed dict."""
    result = runner.invoke(cli, ["--json"] + args)
    assert result.exit_code == 0, f"CLI exited {result.exit_code}: {result.output}"
    return json.loads(result.output)


def _invoke_project_json(runner, project_path, args):
    """Invoke CLI with --json and -p flags and return parsed dict."""
    return _invoke_json(runner, ["-p", str(project_path)] + args)


# ── fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def e2e_project(tmp_path, runner):
    """Create a real Godot project for E2E tests."""
    project_dir = tmp_path / "e2e_game"
    data = _invoke_json(runner, ["project", "create", str(project_dir), "--name", "E2E Game"])
    assert data["status"] == "ok"
    return project_dir


# ── Engine ────────────────────────────────────────────────────────────

@skip_no_godot
class TestE2EEngineVersion:
    def test_version(self, runner):
        data = _invoke_json(runner, ["engine", "version"])
        assert "version" in data

    def test_status(self, runner):
        data = _invoke_json(runner, ["engine", "status"])
        assert data["available"] is True
        assert data["binary"] != "not found"


# ── Project basics ────────────────────────────────────────────────────

@skip_no_godot
class TestE2EProject:
    def test_create_and_info(self, runner, tmp_path):
        project_dir = tmp_path / "test_game"
        data = _invoke_json(runner, ["project", "create", str(project_dir), "--name", "Test Game"])
        assert data["status"] == "ok"

        data = _invoke_project_json(runner, project_dir, ["project", "info"])
        assert data["name"] == "Test Game"

    def test_reimport(self, runner, e2e_project):
        data = _invoke_project_json(runner, e2e_project, ["project", "reimport"])
        assert "status" in data


# ── Scene ─────────────────────────────────────────────────────────────

@skip_no_godot
class TestE2EScene:
    def test_create_and_read(self, runner, e2e_project):
        data = _invoke_project_json(
            runner, e2e_project,
            ["scene", "create", "scenes/TestScene.tscn", "--root-type", "Node2D"],
        )
        assert data["status"] == "ok"

        data = _invoke_project_json(
            runner, e2e_project,
            ["scene", "read", "scenes/TestScene.tscn"],
        )
        assert data["status"] == "ok"
        assert len(data["nodes"]) >= 1

    def test_add_node_and_verify(self, runner, e2e_project):
        _invoke_project_json(
            runner, e2e_project,
            ["scene", "create", "scenes/NodeTest.tscn"],
        )
        data = _invoke_project_json(
            runner, e2e_project,
            ["scene", "add-node", "scenes/NodeTest.tscn",
             "--name", "Sprite", "--type", "Sprite2D"],
        )
        assert data["status"] == "ok"

        data = _invoke_project_json(
            runner, e2e_project,
            ["scene", "read", "scenes/NodeTest.tscn"],
        )
        node_names = [n.get("name") for n in data["nodes"]]
        assert "Sprite" in node_names


# ── Script ────────────────────────────────────────────────────────────

@skip_no_godot
class TestE2EScript:
    def test_run_script(self, runner, e2e_project):
        script_path = e2e_project / "tool_test.gd"
        script_path.write_text(
            "extends SceneTree\n\n"
            "func _init():\n"
            '\tprint("Hello from E2E!")\n'
            "\tquit()\n",
            encoding="utf-8",
        )
        data = _invoke_project_json(
            runner, e2e_project, ["script", "run", "tool_test.gd"],
        )
        assert "status" in data
        if data["status"] == "ok":
            assert "Hello from E2E!" in data.get("stdout", "")

    def test_inline_script(self, runner, e2e_project):
        data = _invoke_project_json(
            runner, e2e_project,
            ["script", "inline", 'print("inline test")'],
        )
        assert "status" in data


# ── Full demo-game pipeline ──────────────────────────────────────────
#
# This is the key test the maintainer asked for: walk through every step
# of building a small game project — from ``project create`` to export
# config — and verify intermediate state at each stage.

@skip_no_godot
class TestE2EDemoGamePipeline:
    """Build a mini platformer project from scratch and verify each stage."""

    @pytest.fixture(autouse=True)
    def _setup(self, runner, tmp_path):
        self.runner = runner
        self.project_dir = tmp_path / "demo_platformer"

    # -- helpers local to the pipeline ------------------------------------

    def _pj(self, args):
        return _invoke_project_json(self.runner, self.project_dir, args)

    # -- phase 1: project creation ----------------------------------------

    def test_01_create_project(self):
        data = _invoke_json(
            self.runner,
            ["project", "create", str(self.project_dir), "--name", "Demo Platformer"],
        )
        assert data["status"] == "ok"
        assert (self.project_dir / "project.godot").exists()

    def test_02_project_info(self):
        _invoke_json(
            self.runner,
            ["project", "create", str(self.project_dir), "--name", "Demo Platformer"],
        )
        data = self._pj(["project", "info"])
        assert data["name"] == "Demo Platformer"

    # -- phase 2: build scene hierarchy -----------------------------------

    def test_03_create_multiple_scenes(self):
        _invoke_json(
            self.runner,
            ["project", "create", str(self.project_dir), "--name", "Demo Platformer"],
        )

        scenes = [
            ("scenes/Main.tscn", "Node2D", "Main"),
            ("scenes/Player.tscn", "CharacterBody2D", "Player"),
            ("scenes/Level1.tscn", "Node2D", "Level1"),
            ("scenes/UI.tscn", "Control", "UI"),
        ]
        for path, root_type, root_name in scenes:
            data = self._pj([
                "scene", "create", path,
                "--root-type", root_type,
                "--root-name", root_name,
            ])
            assert data["status"] == "ok", f"Failed to create {path}"
            assert data["root_type"] == root_type

    def test_04_build_node_hierarchy(self):
        """Assemble a player scene with multiple child nodes."""
        _invoke_json(
            self.runner,
            ["project", "create", str(self.project_dir), "--name", "Demo Platformer"],
        )
        self._pj([
            "scene", "create", "scenes/Player.tscn",
            "--root-type", "CharacterBody2D",
            "--root-name", "Player",
        ])

        children = [
            ("Sprite", "Sprite2D"),
            ("CollisionShape", "CollisionShape2D"),
            ("AnimPlayer", "AnimationPlayer"),
            ("Camera", "Camera2D"),
        ]
        for name, node_type in children:
            data = self._pj([
                "scene", "add-node", "scenes/Player.tscn",
                "--name", name, "--type", node_type,
            ])
            assert data["status"] == "ok"

        data = self._pj(["scene", "read", "scenes/Player.tscn"])
        node_names = {n.get("name") for n in data["nodes"]}
        assert {"Player", "Sprite", "CollisionShape", "AnimPlayer", "Camera"} <= node_names

    def test_05_nested_node_hierarchy(self):
        """Add nodes under non-root parents to verify parent path handling."""
        _invoke_json(
            self.runner,
            ["project", "create", str(self.project_dir), "--name", "Demo Platformer"],
        )
        self._pj([
            "scene", "create", "scenes/Level1.tscn",
            "--root-type", "Node2D",
            "--root-name", "Level1",
        ])
        self._pj([
            "scene", "add-node", "scenes/Level1.tscn",
            "--name", "Platforms", "--type", "Node2D",
        ])
        self._pj([
            "scene", "add-node", "scenes/Level1.tscn",
            "--name", "Platform1", "--type", "StaticBody2D",
            "--parent", "Platforms",
        ])
        self._pj([
            "scene", "add-node", "scenes/Level1.tscn",
            "--name", "CollisionShape", "--type", "CollisionShape2D",
            "--parent", "Platforms/Platform1",
        ])

        data = self._pj(["scene", "read", "scenes/Level1.tscn"])
        nodes_by_name = {n["name"]: n for n in data["nodes"] if "name" in n}
        assert "Platform1" in nodes_by_name
        assert nodes_by_name["Platform1"].get("parent") == "Platforms"
        assert nodes_by_name["CollisionShape"].get("parent") == "Platforms/Platform1"

    # -- phase 3: scripting & validation ----------------------------------

    def test_06_write_and_validate_script(self):
        """Write a player movement script and validate its syntax."""
        _invoke_json(
            self.runner,
            ["project", "create", str(self.project_dir), "--name", "Demo Platformer"],
        )

        scripts_dir = self.project_dir / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        (scripts_dir / "player_movement.gd").write_text(textwrap.dedent("""\
            extends CharacterBody2D

            const SPEED = 300.0
            const JUMP_VELOCITY = -400.0

            func _physics_process(delta: float) -> void:
                if not is_on_floor():
                    velocity += get_gravity() * delta

                if Input.is_action_just_pressed("ui_accept") and is_on_floor():
                    velocity.y = JUMP_VELOCITY

                var direction := Input.get_axis("ui_left", "ui_right")
                if direction:
                    velocity.x = direction * SPEED
                else:
                    velocity.x = move_toward(velocity.x, 0, SPEED)

                move_and_slide()
        """), encoding="utf-8")

        data = self._pj(["script", "validate", "scripts/player_movement.gd"])
        assert data["status"] == "ok"
        # Godot's check-only should find no errors in valid GDScript
        assert data["valid"] is True, f"Validation errors: {data.get('errors')}"

    def test_07_validate_invalid_script(self):
        """Ensure the validator catches syntax errors."""
        _invoke_json(
            self.runner,
            ["project", "create", str(self.project_dir), "--name", "Demo Platformer"],
        )

        bad_script = self.project_dir / "bad.gd"
        bad_script.write_text(
            "extends Node2D\n\nfunc broken(\n  # missing closing paren and body\n",
            encoding="utf-8",
        )

        data = self._pj(["script", "validate", "bad.gd"])
        assert data["status"] == "ok"  # command itself succeeds
        assert data["valid"] is False

    def test_08_run_procedural_generation_script(self):
        """Run a script that programmatically generates data, simulating
        procedural level generation — the kind of thing an agent would do."""
        _invoke_json(
            self.runner,
            ["project", "create", str(self.project_dir), "--name", "Demo Platformer"],
        )

        gen_script = self.project_dir / "gen_level.gd"
        gen_script.write_text(textwrap.dedent("""\
            extends SceneTree

            func _init():
                var platforms := []
                for i in range(5):
                    platforms.append({
                        "x": i * 200,
                        "y": 500 - (i * 30),
                        "width": 150,
                    })
                print(JSON.stringify(platforms))
                quit()
        """), encoding="utf-8")

        data = self._pj(["script", "run", "gen_level.gd"])
        assert data["status"] == "ok"
        # The script should emit valid JSON describing platform positions
        stdout = data.get("stdout", "")
        platforms = json.loads(stdout.strip().splitlines()[-1])
        assert len(platforms) == 5
        assert platforms[0]["x"] == 0
        assert platforms[4]["x"] == 800

    def test_09_inline_script_computes_result(self):
        """Run inline code that performs a computation and verify output."""
        _invoke_json(
            self.runner,
            ["project", "create", str(self.project_dir), "--name", "Demo Platformer"],
        )

        data = self._pj([
            "script", "inline",
            'var total := 0\nfor i in range(1, 11):\n\ttotal += i\nprint(total)',
        ])
        assert data["status"] == "ok"
        assert "55" in data.get("stdout", "")

    # -- phase 4: asset inventory -----------------------------------------

    def test_10_list_project_assets(self):
        """After creating scenes and scripts, verify asset listing commands."""
        _invoke_json(
            self.runner,
            ["project", "create", str(self.project_dir), "--name", "Demo Platformer"],
        )

        # Create two scenes
        self._pj(["scene", "create", "scenes/Main.tscn", "--root-type", "Node2D"])
        self._pj(["scene", "create", "scenes/Player.tscn", "--root-type", "CharacterBody2D"])

        # Write a script
        scripts_dir = self.project_dir / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        (scripts_dir / "player.gd").write_text(
            "extends CharacterBody2D\n", encoding="utf-8",
        )

        # Write a resource file
        (self.project_dir / "icon.tres").write_text(
            '[gd_resource type="CompressedTexture2D"]\n', encoding="utf-8",
        )

        # Verify scene listing
        data = self._pj(["project", "scenes"])
        scene_paths = [s if isinstance(s, str) else s.get("path", "") for s in data["scenes"]]
        assert len(scene_paths) >= 2

        # Verify script listing
        data = self._pj(["project", "scripts"])
        assert data["count"] >= 1

        # Verify resource listing
        data = self._pj(["project", "resources"])
        assert data["count"] >= 1

    # -- phase 5: export configuration ------------------------------------

    def test_11_export_presets_empty(self):
        """A fresh project has no export presets."""
        _invoke_json(
            self.runner,
            ["project", "create", str(self.project_dir), "--name", "Demo Platformer"],
        )
        data = self._pj(["export", "presets"])
        assert data["status"] == "ok"
        assert data["count"] == 0

    def test_12_export_presets_parsed(self):
        """Write an export_presets.cfg and verify it gets parsed correctly."""
        _invoke_json(
            self.runner,
            ["project", "create", str(self.project_dir), "--name", "Demo Platformer"],
        )
        (self.project_dir / "export_presets.cfg").write_text(textwrap.dedent("""\
            [preset.0]
            name="Windows Desktop"
            platform="Windows Desktop"
            export_path="build/game.exe"

            [preset.0.options]

            [preset.1]
            name="Linux/X11"
            platform="Linux/X11"
            export_path="build/game.x86_64"

            [preset.1.options]
        """), encoding="utf-8")

        data = self._pj(["export", "presets"])
        assert data["status"] == "ok"
        assert data["count"] == 2
        preset_names = {p["name"] for p in data["presets"]}
        assert preset_names == {"Windows Desktop", "Linux/X11"}
        preset_platforms = {p["platform"] for p in data["presets"]}
        assert preset_platforms == {"Windows Desktop", "Linux/X11"}

    def test_13_export_build_without_presets_fails(self):
        """Export build on a project without presets should return an error."""
        _invoke_json(
            self.runner,
            ["project", "create", str(self.project_dir), "--name", "Demo Platformer"],
        )
        result = self.runner.invoke(cli, [
            "--json", "-p", str(self.project_dir), "export", "build",
        ])
        data = json.loads(result.output)
        assert data["status"] == "error"
        assert "export_presets.cfg" in data["message"]

    # -- phase 6: full pipeline in a single test --------------------------

    def test_14_complete_game_assembly(self):
        """Walk through the entire game-creation pipeline in one test:
        create project → build scenes → add nodes → write scripts →
        validate → list assets → configure export → verify presets.

        This is the true end-to-end rendering-pipeline test: every CLI
        command that an agent would invoke to assemble a playable demo.
        """
        proj = self.project_dir

        # 1. Create project
        data = _invoke_json(
            self.runner,
            ["project", "create", str(proj), "--name", "Full Pipeline Game"],
        )
        assert data["status"] == "ok"

        # 2. Create main scene
        data = self._pj([
            "scene", "create", "scenes/Main.tscn",
            "--root-type", "Node2D", "--root-name", "Main",
        ])
        assert data["status"] == "ok"

        # 3. Create player scene with full hierarchy
        self._pj([
            "scene", "create", "scenes/Player.tscn",
            "--root-type", "CharacterBody2D", "--root-name", "Player",
        ])
        for name, ntype in [
            ("Sprite", "Sprite2D"),
            ("Collision", "CollisionShape2D"),
            ("Anim", "AnimationPlayer"),
        ]:
            data = self._pj([
                "scene", "add-node", "scenes/Player.tscn",
                "--name", name, "--type", ntype,
            ])
            assert data["status"] == "ok"

        # 4. Create level scene with nested hierarchy
        self._pj([
            "scene", "create", "scenes/Level1.tscn",
            "--root-type", "Node2D", "--root-name", "Level1",
        ])
        self._pj([
            "scene", "add-node", "scenes/Level1.tscn",
            "--name", "Platforms", "--type", "Node2D",
        ])
        self._pj([
            "scene", "add-node", "scenes/Level1.tscn",
            "--name", "Ground", "--type", "StaticBody2D",
            "--parent", "Platforms",
        ])

        # 5. Verify player scene structure
        data = self._pj(["scene", "read", "scenes/Player.tscn"])
        node_names = {n["name"] for n in data["nodes"] if "name" in n}
        assert {"Player", "Sprite", "Collision", "Anim"} <= node_names

        # 6. Write and validate game scripts
        scripts_dir = proj / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)

        (scripts_dir / "player.gd").write_text(textwrap.dedent("""\
            extends CharacterBody2D

            const SPEED = 300.0
            const JUMP_VELOCITY = -400.0

            func _physics_process(delta: float) -> void:
                if not is_on_floor():
                    velocity += get_gravity() * delta
                if Input.is_action_just_pressed("ui_accept") and is_on_floor():
                    velocity.y = JUMP_VELOCITY
                var direction := Input.get_axis("ui_left", "ui_right")
                velocity.x = direction * SPEED if direction else move_toward(velocity.x, 0, SPEED)
                move_and_slide()
        """), encoding="utf-8")

        (scripts_dir / "main.gd").write_text(textwrap.dedent("""\
            extends Node2D

            func _ready() -> void:
                print("Game started")
        """), encoding="utf-8")

        for script_name in ["scripts/player.gd", "scripts/main.gd"]:
            data = self._pj(["script", "validate", script_name])
            assert data["status"] == "ok"
            assert data["valid"] is True, (
                f"{script_name} failed validation: {data.get('errors')}"
            )

        # 7. Run a tool-script that verifies the project is well-formed
        checker = proj / "check_project.gd"
        checker.write_text(textwrap.dedent("""\
            extends SceneTree

            func _init():
                var dir := DirAccess.open("res://scenes")
                var scenes := []
                if dir:
                    dir.list_dir_begin()
                    var file_name := dir.get_next()
                    while file_name != "":
                        if file_name.ends_with(".tscn"):
                            scenes.append(file_name)
                        file_name = dir.get_next()
                print(JSON.stringify({"scene_count": scenes.size(), "scenes": scenes}))
                quit()
        """), encoding="utf-8")

        data = self._pj(["script", "run", "check_project.gd"])
        assert data["status"] == "ok"
        stdout = data.get("stdout", "")
        report = json.loads(stdout.strip().splitlines()[-1])
        assert report["scene_count"] == 3  # Main, Player, Level1

        # 8. Verify asset inventory
        data = self._pj(["project", "scenes"])
        assert len(data["scenes"]) >= 3

        data = self._pj(["project", "scripts"])
        assert data["count"] >= 2

        # 9. Configure export and verify presets
        (proj / "export_presets.cfg").write_text(textwrap.dedent("""\
            [preset.0]
            name="Windows Desktop"
            platform="Windows Desktop"
            export_path="build/game.exe"

            [preset.0.options]

            [preset.1]
            name="Linux/X11"
            platform="Linux/X11"
            export_path="build/game.x86_64"

            [preset.1.options]
        """), encoding="utf-8")

        data = self._pj(["export", "presets"])
        assert data["count"] == 2

        # 10. Attempt export build (will fail without export templates,
        #     but we verify the CLI invokes Godot correctly)
        result = self.runner.invoke(cli, [
            "--json", "-p", str(proj), "export", "build",
        ])
        data = json.loads(result.output)
        assert data["preset"] == "all"
        assert "returncode" in data
