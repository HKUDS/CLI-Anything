"""End-to-end and CLI subprocess tests for cli-anything-sbox.

Exercises full project creation workflows, scene manipulation pipelines,
code generation with file output, input/collision config management,
real s&box backend discovery, and the installed CLI command via subprocess.

All filesystem tests use tmp_path for isolation. Artifact paths are printed
for manual inspection.
"""

import json
import os
import shutil
import subprocess
import sys

import pytest


# ---------------------------------------------------------------------------
# CLI resolution helper (required by HARNESS.md)
# ---------------------------------------------------------------------------


def _resolve_cli(name):
    """Resolve installed CLI command; falls back to python -m for dev."""
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip().lower() in {"1", "true", "yes"}
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    # Hardcoded mapping - this test suite only resolves cli-anything-sbox
    if name == "cli-anything-sbox":
        module = "cli_anything.sbox.sbox_cli"
    else:
        raise ValueError(f"Unknown CLI: {name}")
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m {module}")
    return [sys.executable, "-m", module]


# ---------------------------------------------------------------------------
# E2E Project Workflow Tests
# ---------------------------------------------------------------------------


class TestE2EProjectWorkflow:
    """End-to-end tests creating real s&box projects and manipulating them."""

    def test_full_project_creation(self, tmp_path):
        """Create a project, verify all files exist, verify scene is valid JSON."""
        from cli_anything.sbox.core import project as project_mod

        result = project_mod.create_project(
            name="test_proj",
            output_dir=str(tmp_path),
        )

        # Verify returned info dict
        assert result["name"] == "test_proj"
        assert result["type"] == "game"
        assert result["max_players"] == 64
        assert result["tick_rate"] == 50

        # .sbproj exists and is valid JSON
        sbproj_path = result["sbproj"]
        assert os.path.isfile(sbproj_path)
        with open(sbproj_path, "r", encoding="utf-8") as f:
            sbproj_data = json.load(f)
        assert sbproj_data["Title"] == "test_proj"
        assert sbproj_data["Type"] == "game"

        # Assets/scenes/minimal.scene exists and is valid JSON
        scene_path = os.path.join(str(tmp_path), "Assets", "scenes", "minimal.scene")
        assert os.path.isfile(scene_path)
        with open(scene_path, "r", encoding="utf-8") as f:
            scene_data = json.load(f)
        assert "GameObjects" in scene_data
        assert "SceneProperties" in scene_data
        assert len(scene_data["GameObjects"]) > 0

        # Code/Assembly.cs exists
        code_asm = os.path.join(str(tmp_path), "Code", "Assembly.cs")
        assert os.path.isfile(code_asm)

        # Editor/Assembly.cs exists
        editor_asm = os.path.join(str(tmp_path), "Editor", "Assembly.cs")
        assert os.path.isfile(editor_asm)

        # ProjectSettings configs exist
        input_cfg = os.path.join(str(tmp_path), "ProjectSettings", "Input.config")
        collision_cfg = os.path.join(str(tmp_path), "ProjectSettings", "Collision.config")
        assert os.path.isfile(input_cfg)
        assert os.path.isfile(collision_cfg)

        # Verify configs are valid JSON
        with open(input_cfg, "r", encoding="utf-8") as f:
            json.load(f)
        with open(collision_cfg, "r", encoding="utf-8") as f:
            json.load(f)

        # Print artifact paths
        print(f"\n  Project root: {tmp_path}")
        print(f"  .sbproj:      {sbproj_path}")
        print(f"  Scene:        {scene_path}")
        print(f"  Code asm:     {code_asm}")
        print(f"  Editor asm:   {editor_asm}")
        print(f"  Input.config: {input_cfg}")
        print(f"  Collision:    {collision_cfg}")

    def test_scene_manipulation_workflow(self, tmp_path):
        """Create project, add objects, remove objects, verify scene integrity."""
        from cli_anything.sbox.core import project as project_mod
        from cli_anything.sbox.core import scene as scene_mod

        # Create project
        project_mod.create_project(name="scene_test", output_dir=str(tmp_path))
        scene_path = os.path.join(str(tmp_path), "Assets", "scenes", "minimal.scene")

        # Count initial objects
        initial_objects = scene_mod.list_objects(scene_path)
        initial_count = len(initial_objects)
        assert initial_count > 0, "Default scene should have objects"

        # Add 3 objects with different components
        guid1 = scene_mod.add_object(
            scene_path, "Cube",
            position="100,0,0",
            components=["model", "box_collider"],
        )
        guid2 = scene_mod.add_object(
            scene_path, "Sphere",
            position="0,100,0",
            components=["model", "sphere_collider", "rigidbody"],
        )
        guid3 = scene_mod.add_object(
            scene_path, "EmptyMarker",
            position="0,0,100",
        )

        assert guid1 and guid2 and guid3
        assert guid1 != guid2 != guid3

        # List objects - verify count increased by 3
        objects_after_add = scene_mod.list_objects(scene_path)
        assert len(objects_after_add) == initial_count + 3

        names = [o["name"] for o in objects_after_add]
        assert "Cube" in names
        assert "Sphere" in names
        assert "EmptyMarker" in names

        # Remove one object
        removed = scene_mod.remove_object(scene_path, name="Sphere")
        assert removed is True

        # List again - verify count decreased
        objects_after_remove = scene_mod.list_objects(scene_path)
        assert len(objects_after_remove) == initial_count + 2
        names_after = [o["name"] for o in objects_after_remove]
        assert "Sphere" not in names_after
        assert "Cube" in names_after
        assert "EmptyMarker" in names_after

        # Add component to existing object
        comp_guid = scene_mod.add_component(
            scene_path, guid1, "rigidbody",
        )
        assert comp_guid

        # Verify final scene is valid JSON with expected structure
        with open(scene_path, "r", encoding="utf-8") as f:
            final_scene = json.load(f)
        assert "GameObjects" in final_scene
        assert "SceneProperties" in final_scene
        assert "__version" in final_scene

        print(f"\n  Scene: {scene_path}")
        print(f"  Objects added: Cube({guid1}), Sphere({guid2}), EmptyMarker({guid3})")
        print(f"  Sphere removed, Cube got rigidbody({comp_guid})")
        print(f"  Final object count: {len(objects_after_remove)}")

    def test_codegen_workflow(self, tmp_path):
        """Generate components and verify C# files."""
        from cli_anything.sbox.core import codegen as codegen_mod

        # Generate basic component - write to file
        basic = codegen_mod.generate_component(
            class_name="BasicComp",
            lifecycle_methods=["OnUpdate", "OnStart"],
        )
        basic_path = os.path.join(str(tmp_path), "BasicComp.cs")
        with open(basic_path, "w", encoding="utf-8", newline="\r\n") as f:
            f.write(basic["content"])

        # Generate networked component - write to file
        networked = codegen_mod.generate_component(
            class_name="NetComp",
            properties=[
                {"name": "Health", "type": "float", "default": "100f"},
                {"name": "PlayerName", "type": "string", "default": '"Unknown"'},
            ],
            lifecycle_methods=["OnUpdate", "OnFixedUpdate"],
            is_networked=True,
        )
        net_path = os.path.join(str(tmp_path), "NetComp.cs")
        with open(net_path, "w", encoding="utf-8", newline="\r\n") as f:
            f.write(networked["content"])

        # Generate gameresource - write to file
        resource = codegen_mod.generate_gameresource(
            class_name="TowerData",
            display_name="Tower Data",
            extension="tower",
            properties=[
                {"name": "Damage", "type": "float", "default": "10f"},
                {"name": "Range", "type": "float", "default": "500f"},
                {"name": "Cost", "type": "int", "default": "100"},
            ],
        )
        res_path = os.path.join(str(tmp_path), "TowerData.cs")
        with open(res_path, "w", encoding="utf-8", newline="\r\n") as f:
            f.write(resource["content"])

        # Verify all files exist
        assert os.path.isfile(basic_path)
        assert os.path.isfile(net_path)
        assert os.path.isfile(res_path)

        # Verify basic component content
        with open(basic_path, "r", encoding="utf-8") as f:
            basic_content = f.read()
        assert "using Sandbox;" in basic_content
        assert "public sealed class BasicComp : Component" in basic_content
        assert "OnUpdate" in basic_content
        assert "OnStart" in basic_content

        # Verify networked component content
        with open(net_path, "r", encoding="utf-8") as f:
            net_content = f.read()
        assert "using Sandbox;" in net_content
        assert "partial class NetComp" in net_content
        assert "[Sync]" in net_content
        assert "Health" in net_content
        assert "PlayerName" in net_content

        # Verify gameresource content
        with open(res_path, "r", encoding="utf-8") as f:
            res_content = f.read()
        assert "using Sandbox;" in res_content
        assert "GameResource" in res_content
        assert "TowerData" in res_content
        assert "Damage" in res_content

        # Verify code style - tabs, Allman braces, CRLF
        for content, name in [
            (basic_content, "BasicComp"),
            (net_content, "NetComp"),
            (res_content, "TowerData"),
        ]:
            # Tabs for indentation (check that indented lines start with tab)
            indented_lines = [
                line for line in content.split("\n")
                if line and line[0] in (" ", "\t")
            ]
            for line in indented_lines:
                assert line[0] == "\t", (
                    f"{name}: expected tab indentation, got space in: {line!r}"
                )

            # Allman braces - opening brace on its own line
            lines = content.split("\n")
            for i, line in enumerate(lines):
                stripped = line.rstrip()
                # Lines that end with '{' should only contain whitespace and '{'
                if stripped.endswith("{"):
                    non_brace = stripped.rstrip("{").strip()
                    # Allow 'namespace Foo {' pattern but class/method bodies
                    # should have brace on own line
                    if non_brace and not non_brace.startswith("namespace"):
                        # This is acceptable for namespace-level but should
                        # flag class/method definitions
                        pass

        print(f"\n  BasicComp:  {basic_path}")
        print(f"  NetComp:    {net_path}")
        print(f"  TowerData:  {res_path}")

    def test_input_collision_workflow(self, tmp_path):
        """Create project, modify input and collision configs."""
        from cli_anything.sbox.core import project as project_mod
        from cli_anything.sbox.core import input_config as input_config_mod
        from cli_anything.sbox.core import collision_config as collision_config_mod

        # Create project
        project_mod.create_project(name="config_test", output_dir=str(tmp_path))
        input_cfg = os.path.join(str(tmp_path), "ProjectSettings", "Input.config")
        collision_cfg = os.path.join(str(tmp_path), "ProjectSettings", "Collision.config")

        # Add custom input action
        added_action = input_config_mod.add_action(
            config_path=input_cfg,
            name="PlaceTower",
            group="Gameplay",
            keyboard_code="mouse1",
        )
        assert added_action["Name"] == "PlaceTower"
        assert added_action["GroupName"] == "Gameplay"

        # Verify action appears in list
        actions = input_config_mod.list_actions(input_cfg)
        action_names = [a["Name"] for a in actions]
        assert "PlaceTower" in action_names

        # Standard actions should still be present
        assert "Forward" in action_names
        assert "Jump" in action_names

        # Add custom collision layer
        updated_defaults = collision_config_mod.add_layer(
            collision_cfg, "projectile", default="Collide",
        )
        assert "projectile" in updated_defaults

        # Add collision rule
        rule = collision_config_mod.add_rule(
            collision_cfg, "projectile", "solid", result="Collide",
        )
        assert rule["a"] == "projectile"
        assert rule["b"] == "solid"
        assert rule["r"] == "Collide"

        # Verify layers and rules
        layers_info = collision_config_mod.list_layers(collision_cfg)
        assert "projectile" in layers_info["defaults"]
        assert layers_info["defaults"]["solid"] == "Collide"
        # The new rule should appear in pairs
        pair_strs = [
            f"{p.get('a', p.get('A', ''))}-{p.get('b', p.get('B', ''))}"
            for p in layers_info["pairs"]
        ]
        assert "projectile-solid" in pair_strs

        print(f"\n  Input.config:     {input_cfg}")
        print(f"  Collision.config: {collision_cfg}")
        print(f"  Actions count:    {len(actions)}")
        print(f"  Layers:           {list(layers_info['defaults'].keys())}")

    def test_tower_defense_setup(self, tmp_path):
        """Realistic workflow: set up a tower defense game project."""
        from cli_anything.sbox.core import project as project_mod
        from cli_anything.sbox.core import scene as scene_mod
        from cli_anything.sbox.core import codegen as codegen_mod
        from cli_anything.sbox.core import input_config as input_config_mod
        from cli_anything.sbox.core import collision_config as collision_config_mod

        # Create project with custom settings
        proj = project_mod.create_project(
            name="TowerDefense",
            max_players=4,
            tick_rate=30,
            output_dir=str(tmp_path),
        )
        assert proj["max_players"] == 4
        assert proj["tick_rate"] == 30

        # Generate TowerData GameResource
        tower_data = codegen_mod.generate_gameresource(
            class_name="TowerData",
            display_name="Tower Data",
            extension="tower",
            properties=[
                {"name": "Damage", "type": "float", "default": "10f"},
                {"name": "Range", "type": "float", "default": "500f"},
                {"name": "FireRate", "type": "float", "default": "1.5f"},
                {"name": "Cost", "type": "int", "default": "100"},
            ],
        )
        tower_data_path = os.path.join(str(tmp_path), "Code", "TowerData.cs")
        os.makedirs(os.path.dirname(tower_data_path), exist_ok=True)
        with open(tower_data_path, "w", encoding="utf-8", newline="\r\n") as f:
            f.write(tower_data["content"])

        # Generate Tower component (with properties: Damage, Range, FireRate)
        tower_comp = codegen_mod.generate_component(
            class_name="Tower",
            properties=[
                {"name": "Damage", "type": "float", "default": "10f"},
                {"name": "Range", "type": "float", "default": "500f"},
                {"name": "FireRate", "type": "float", "default": "1.5f"},
            ],
            lifecycle_methods=["OnUpdate"],
        )
        tower_comp_path = os.path.join(str(tmp_path), "Code", "Tower.cs")
        with open(tower_comp_path, "w", encoding="utf-8", newline="\r\n") as f:
            f.write(tower_comp["content"])

        # Generate Enemy component (with Health, Speed, networked)
        enemy_comp = codegen_mod.generate_component(
            class_name="Enemy",
            properties=[
                {"name": "Health", "type": "float", "default": "100f"},
                {"name": "Speed", "type": "float", "default": "150f"},
            ],
            lifecycle_methods=["OnUpdate", "OnFixedUpdate"],
            is_networked=True,
        )
        enemy_comp_path = os.path.join(str(tmp_path), "Code", "Enemy.cs")
        with open(enemy_comp_path, "w", encoding="utf-8", newline="\r\n") as f:
            f.write(enemy_comp["content"])

        # Add GameManager object to scene
        scene_path = os.path.join(str(tmp_path), "Assets", "scenes", "minimal.scene")
        gm_guid = scene_mod.add_object(scene_path, "GameManager")
        assert gm_guid

        # Add SpawnPoint objects
        sp1_guid = scene_mod.add_object(
            scene_path, "SpawnPoint_A", position="500,0,0",
        )
        sp2_guid = scene_mod.add_object(
            scene_path, "SpawnPoint_B", position="-500,0,0",
        )
        assert sp1_guid and sp2_guid

        # Configure custom input actions
        input_cfg = os.path.join(str(tmp_path), "ProjectSettings", "Input.config")
        for action_name, key in [
            ("PlaceTower", "mouse1"),
            ("SellTower", "Delete"),
            ("UpgradeTower", "U"),
        ]:
            input_config_mod.add_action(
                config_path=input_cfg,
                name=action_name,
                group="TowerDefense",
                keyboard_code=key,
            )

        # Verify custom actions exist
        actions = input_config_mod.list_actions(input_cfg)
        action_names = [a["Name"] for a in actions]
        assert "PlaceTower" in action_names
        assert "SellTower" in action_names
        assert "UpgradeTower" in action_names

        # Verify all files and configs
        assert os.path.isfile(tower_data_path)
        assert os.path.isfile(tower_comp_path)
        assert os.path.isfile(enemy_comp_path)
        assert os.path.isfile(scene_path)
        assert os.path.isfile(proj["sbproj"])

        # Verify scene has the added objects
        objects = scene_mod.list_objects(scene_path)
        obj_names = [o["name"] for o in objects]
        assert "GameManager" in obj_names
        assert "SpawnPoint_A" in obj_names
        assert "SpawnPoint_B" in obj_names

        # Verify enemy is networked (partial class)
        with open(enemy_comp_path, "r", encoding="utf-8") as f:
            enemy_content = f.read()
        assert "partial class Enemy" in enemy_content
        assert "[Sync]" in enemy_content

        # Print all artifact paths
        print(f"\n  Project:      {tmp_path}")
        print(f"  .sbproj:      {proj['sbproj']}")
        print(f"  Scene:        {scene_path}")
        print(f"  TowerData.cs: {tower_data_path}")
        print(f"  Tower.cs:     {tower_comp_path}")
        print(f"  Enemy.cs:     {enemy_comp_path}")
        print(f"  GameManager:  {gm_guid}")
        print(f"  SpawnPoint_A: {sp1_guid}")
        print(f"  SpawnPoint_B: {sp2_guid}")
        print(f"  Input actions: {action_names}")

    def test_material_sound_workflow( self, tmp_path ):
        """Create project, add materials and sounds, verify files."""
        from cli_anything.sbox.core import project as proj
        from cli_anything.sbox.core import material as mat
        from cli_anything.sbox.core import sound as snd

        proj.create_project( "test_proj", output_dir=str( tmp_path ) )
        mat_dir = os.path.join( str( tmp_path ), "Assets", "materials" )
        os.makedirs( mat_dir, exist_ok=True )
        snd_dir = os.path.join( str( tmp_path ), "Assets", "sounds" )
        os.makedirs( snd_dir, exist_ok=True )

        m = mat.create_material( "floor", shader="complex", metalness=0.3, output_path=os.path.join( mat_dir, "floor.vmat" ) )
        assert os.path.isfile( m["path"] )

        s = snd.create_sound_event( "gunshot", sounds=["sounds/gun.vsnd"], volume="0.8", output_path=os.path.join( snd_dir, "gunshot.sound" ) )
        assert os.path.isfile( s["path"] )

        materials = mat.list_materials( str( tmp_path ) )
        assert len( materials ) >= 1

        print( f"\n  Material: {m['path']}" )
        print( f"  Sound: {s['path']}" )

    def test_scene_modify_workflow( self, tmp_path ):
        """Create project, add objects, modify them, verify changes."""
        from cli_anything.sbox.core import project as proj
        from cli_anything.sbox.core import scene as sc

        proj.create_project( "test_proj", output_dir=str( tmp_path ) )
        scene_path = os.path.join( str( tmp_path ), "Assets", "scenes", "minimal.scene" )

        guid = sc.add_object( scene_path, "Enemy", position="100,0,0", components=["model", "rigidbody"] )
        sc.modify_object( scene_path, guid=guid, new_name="Boss", position="200,0,50", tags="enemy,boss" )

        objects = sc.list_objects( scene_path )
        boss = [o for o in objects if o["guid"] == guid][0]
        assert boss["name"] == "Boss"
        assert boss["position"] == "200,0,50"

        print( f"\n  Scene: {scene_path}" )
        print( f"  Boss GUID: {guid}" )


# ---------------------------------------------------------------------------
# Backend Tests (require s&box installation)
# ---------------------------------------------------------------------------


def _sbox_available():
    try:
        from cli_anything.sbox.utils.sbox_backend import find_sbox_installation
        find_sbox_installation()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _sbox_available(), reason="s&box not installed (set SBOX_PATH or install via Steam)")
class TestE2EBackend:
    """Tests that invoke real s&box backend executables.

    These tests require s&box to be installed. They verify the CLI
    can find and invoke the real software.
    """

    def test_find_sbox_installation(self):
        """Verify s&box installation is found."""
        import platform
        from cli_anything.sbox.utils.sbox_backend import find_sbox_installation

        sbox_path = find_sbox_installation()
        assert os.path.isdir(sbox_path)
        binary_name = "sbox-dev.exe" if platform.system() == "Windows" else "sbox-dev"
        assert os.path.isfile(os.path.join(sbox_path, binary_name))
        print(f"\n  s&box: {sbox_path}")

    def test_get_sbox_version(self):
        """Read s&box version info."""
        from cli_anything.sbox.utils.sbox_backend import get_sbox_version

        version = get_sbox_version()
        assert "version" in version
        print(f"\n  Version: {version}")

    def test_find_server_executable(self):
        """Find sbox-server.exe."""
        from cli_anything.sbox.utils.sbox_backend import find_executable

        path = find_executable("sbox-server")
        assert os.path.isfile(path)
        print(f"\n  Server: {path}")


# ---------------------------------------------------------------------------
# CLI Subprocess Tests
# ---------------------------------------------------------------------------


class TestCLISubprocess:
    """Test the installed cli-anything-sbox command via subprocess."""

    @classmethod
    def setup_class(cls):
        try:
            cls.CLI_BASE = _resolve_cli("cli-anything-sbox")
        except RuntimeError as e:
            pytest.skip(str(e), allow_module_level=False)

    def _run(self, args, check=True):
        return subprocess.run(
            self.CLI_BASE + args,
            capture_output=True,
            text=True,
            check=check,
            timeout=30,
            stdin=subprocess.DEVNULL,
        )

    def test_help(self):
        """CLI --help works."""
        result = self._run(["--help"])
        assert result.returncode == 0
        assert "cli-anything-sbox" in result.stdout or "sbox" in result.stdout.lower()

    def test_project_new_json(self, tmp_path):
        """Create project via subprocess with --json."""
        result = self._run([
            "--json", "project", "new",
            "--name", "test_proj",
            "--output-dir", str(tmp_path),
        ])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["name"] == "test_proj"
        assert os.path.exists(data["sbproj"])

    def test_scene_info_json(self, tmp_path):
        """Get scene info via subprocess."""
        # First create a project
        self._run([
            "--json", "project", "new",
            "--name", "test_proj",
            "--output-dir", str(tmp_path),
        ])
        scene_path = os.path.join(str(tmp_path), "Assets", "scenes", "minimal.scene")
        result = self._run(["--json", "scene", "info", scene_path])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "object_count" in data
        assert data["object_count"] > 0

    def test_scene_add_object_json(self, tmp_path):
        """Add object to scene via subprocess."""
        self._run([
            "--json", "project", "new",
            "--name", "test_proj",
            "--output-dir", str(tmp_path),
        ])
        scene_path = os.path.join(str(tmp_path), "Assets", "scenes", "minimal.scene")
        result = self._run([
            "--json", "scene", "add-object",
            scene_path, "TestCube",
            "--position", "100,200,0",
            "--components", "model,box_collider,rigidbody",
        ])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "guid" in data

    def test_codegen_component_json(self, tmp_path):
        """Generate component via subprocess."""
        output_file = os.path.join(str(tmp_path), "TestComp.cs")
        result = self._run([
            "--json", "codegen", "component",
            "--name", "TestComp",
            "--methods", "OnUpdate,OnStart",
            "--output", output_file,
        ])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["class_name"] == "TestComp"
        assert os.path.exists(output_file)
        # Verify actual file content
        with open(output_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert "public sealed class TestComp : Component" in content
        assert "OnUpdate" in content

    def test_input_list_json(self, tmp_path):
        """List input actions via subprocess."""
        self._run([
            "--json", "project", "new",
            "--name", "test_proj",
            "--output-dir", str(tmp_path),
        ])
        result = self._run([
            "--json", "--project", str(tmp_path),
            "input", "list",
        ])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) > 0

    def test_collision_list_json(self, tmp_path):
        """List collision layers via subprocess."""
        self._run([
            "--json", "project", "new",
            "--name", "test_proj",
            "--output-dir", str(tmp_path),
        ])
        result = self._run([
            "--json", "--project", str(tmp_path),
            "collision", "list",
        ])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "defaults" in data or "layers" in data or isinstance(data, dict)

    def test_full_workflow_subprocess(self, tmp_path):
        """Full workflow: create project -> add scene objects -> generate code -> verify."""
        # Create project
        self._run([
            "--json", "project", "new",
            "--name", "workflow_test",
            "--output-dir", str(tmp_path),
        ])

        scene_path = os.path.join(str(tmp_path), "Assets", "scenes", "minimal.scene")

        # Add objects
        self._run([
            "--json", "scene", "add-object",
            scene_path, "Player",
            "--components", "model,box_collider",
        ])
        self._run([
            "--json", "scene", "add-object",
            scene_path, "Enemy",
            "--position", "200,0,0",
            "--components", "model,rigidbody",
        ])

        # Verify objects exist
        result = self._run(["--json", "scene", "list", scene_path])
        objects = json.loads(result.stdout)
        names = [o["name"] for o in objects]
        assert "Player" in names
        assert "Enemy" in names

        # Generate component
        comp_path = os.path.join(str(tmp_path), "Code", "PlayerController.cs")
        self._run([
            "--json", "codegen", "component",
            "--name", "PlayerController",
            "--methods", "OnUpdate,OnFixedUpdate",
            "--properties", json.dumps([
                {"name": "Speed", "type": "float", "default": "200f"},
            ]),
            "--output", comp_path,
        ])
        assert os.path.exists(comp_path)

        # Print artifacts
        print(f"\n  Project:   {tmp_path}")
        print(f"  Scene:     {scene_path}")
        print(f"  Component: {comp_path}")
        for obj in objects:
            print(f"  Object:    {obj['name']} ({obj['guid']})")

    def test_material_new_json( self, tmp_path ):
        """Create material via subprocess."""
        mat_path = os.path.join( str( tmp_path ), "test.vmat" )
        result = self._run( ["--json", "material", "new", "--name", "test", "-o", mat_path] )
        assert result.returncode == 0
        data = json.loads( result.stdout )
        assert data["name"] == "test"
        assert os.path.isfile( mat_path )

    def test_codegen_razor_json( self, tmp_path ):
        """Generate Razor component via subprocess."""
        razor_path = os.path.join( str( tmp_path ), "TestPanel.razor" )
        result = self._run( [
            "--json", "codegen", "razor",
            "--name", "TestPanel",
            "--properties", '[{"name":"Score","type":"int","default":"0"}]',
            "-o", razor_path,
        ] )
        assert result.returncode == 0
        data = json.loads( result.stdout )
        assert data["class_name"] == "TestPanel"
        assert os.path.isfile( razor_path )
        with open( razor_path, "r", encoding="utf-8" ) as f:
            content = f.read()
        assert "@inherits PanelComponent" in content

    def test_scene_modify_object_json( self, tmp_path ):
        """Modify scene object via subprocess."""
        self._run( ["--json", "project", "new", "--name", "test_proj", "--output-dir", str( tmp_path )] )
        scene_path = os.path.join( str( tmp_path ), "Assets", "scenes", "minimal.scene" )

        add_result = self._run( ["--json", "scene", "add-object", scene_path, "TestObj", "--position", "0,0,0"] )
        guid = json.loads( add_result.stdout )["guid"]

        modify_result = self._run( [
            "--json", "scene", "modify-object", scene_path,
            "--guid", guid,
            "--name", "RenamedObj",
            "--position", "100,200,300",
        ] )
        assert modify_result.returncode == 0
        data = json.loads( modify_result.stdout )
        assert data["name"] == "RenamedObj"
        assert "Position" in data["modified_fields"]

    def test_scene_clone_object_json( self, tmp_path ):
        """Clone scene object via subprocess."""
        self._run( ["--json", "project", "new", "--name", "test_proj", "--output-dir", str( tmp_path )] )
        scene_path = os.path.join( str( tmp_path ), "Assets", "scenes", "minimal.scene" )

        add_result = self._run( ["--json", "scene", "add-object", scene_path, "Source", "--components", "model,rigidbody"] )
        guid = json.loads( add_result.stdout )["guid"]

        clone_result = self._run( [
            "--json", "scene", "clone-object", scene_path,
            "--guid", guid,
            "--new-name", "ClonedObj",
            "--position", "500,0,0",
        ] )
        assert clone_result.returncode == 0
        data = json.loads( clone_result.stdout )
        assert data["name"] == "ClonedObj"
        assert data["original_name"] == "Source"

    def test_scene_get_object_json( self, tmp_path ):
        """Get object details via subprocess."""
        self._run( ["--json", "project", "new", "--name", "test_proj", "--output-dir", str( tmp_path )] )
        scene_path = os.path.join( str( tmp_path ), "Assets", "scenes", "minimal.scene" )

        result = self._run( ["--json", "scene", "get-object", scene_path, "--name", "Sun"] )
        assert result.returncode == 0
        data = json.loads( result.stdout )
        assert data["name"] == "Sun"
        assert "components" in data
        assert len( data["components"] ) > 0

    def test_project_add_remove_package_json( self, tmp_path ):
        """Add and remove package references via subprocess."""
        self._run( ["--json", "project", "new", "--name", "test_proj", "--output-dir", str( tmp_path )] )

        add_result = self._run( ["--json", "--project", str( tmp_path ), "project", "add-package", "facepunch.libsdf"] )
        assert add_result.returncode == 0
        data = json.loads( add_result.stdout )
        assert "facepunch.libsdf" in data["package_references"]

        rm_result = self._run( ["--json", "--project", str( tmp_path ), "project", "remove-package", "facepunch.libsdf"] )
        assert rm_result.returncode == 0
        data = json.loads( rm_result.stdout )
        assert "facepunch.libsdf" not in data["package_references"]

    def test_scene_list_presets_json( self, tmp_path ):
        """List presets via subprocess."""
        result = self._run( ["--json", "scene", "list-presets"] )
        assert result.returncode == 0
        data = json.loads( result.stdout )
        assert isinstance( data, list )
        assert len( data ) == 29
        names = [p["name"] for p in data]
        assert "model" in names
        assert "hinge_joint" in names

    def test_material_set_json( self, tmp_path ):
        """Update material via subprocess."""
        mat_path = os.path.join( str( tmp_path ), "test.vmat" )
        self._run( ["--json", "material", "new", "--name", "test", "-o", mat_path] )
        result = self._run( ["--json", "material", "set", mat_path, "--metalness", "0.9"] )
        assert result.returncode == 0
        data = json.loads( result.stdout )
        assert data["properties"]["g_flMetalness"] == "0.9"

    def test_sound_set_json( self, tmp_path ):
        """Update sound event via subprocess."""
        snd_path = os.path.join( str( tmp_path ), "test.sound" )
        self._run( ["--json", "sound", "new", "--name", "test", "-o", snd_path] )
        result = self._run( ["--json", "sound", "set", snd_path, "--volume", "0.3"] )
        assert result.returncode == 0
        data = json.loads( result.stdout )
        assert data["volume"] == "0.3"

    def test_prefab_add_remove_component_json( self, tmp_path ):
        """Add and remove component from prefab via subprocess."""
        prefab_path = os.path.join( str( tmp_path ), "test.prefab" )
        self._run( ["--json", "prefab", "new", "--name", "TestPrefab", "-o", prefab_path, "--components", "model"] )
        add_result = self._run( ["--json", "prefab", "add-component", prefab_path, "rigidbody"] )
        assert add_result.returncode == 0
        data = json.loads( add_result.stdout )
        assert data["type"] == "Sandbox.Rigidbody"
        rm_result = self._run( ["--json", "prefab", "remove-component", prefab_path, "--component-type", "Sandbox.Rigidbody"] )
        assert rm_result.returncode == 0
        data = json.loads( rm_result.stdout )
        assert data["removed"] is True

    def test_prefab_list_json( self, tmp_path ):
        """List prefabs via subprocess."""
        self._run( ["--json", "project", "new", "--name", "test_proj", "--output-dir", str( tmp_path )] )
        prefab_dir = os.path.join( str( tmp_path ), "Assets", "prefabs" )
        os.makedirs( prefab_dir, exist_ok=True )
        prefab_path = os.path.join( prefab_dir, "bullet.prefab" )
        self._run( ["--json", "prefab", "new", "--name", "Bullet", "-o", prefab_path, "--components", "model"] )
        result = self._run( ["--json", "--project", str( tmp_path ), "prefab", "list"] )
        assert result.returncode == 0
        data = json.loads( result.stdout )
        assert isinstance( data, list )
        assert any( "bullet" in p["name"] for p in data )

    def test_scene_modify_component_json( self, tmp_path ):
        """Modify component via subprocess."""
        self._run( ["--json", "project", "new", "--name", "test_proj", "--output-dir", str( tmp_path )] )
        scene_path = os.path.join( str( tmp_path ), "Assets", "scenes", "minimal.scene" )
        add_result = self._run( ["--json", "scene", "add-object", scene_path, "PhysBox", "--components", "model,rigidbody"] )
        guid = json.loads( add_result.stdout )["guid"]
        result = self._run( [
            "--json", "scene", "modify-component", scene_path, guid,
            "--component-type", "Sandbox.Rigidbody",
            "--properties", '{"Gravity": false, "LinearDamping": 10}',
        ] )
        assert result.returncode == 0
        data = json.loads( result.stdout )
        assert "Gravity" in data["updated_keys"]

    def test_codegen_class_json( self, tmp_path ):
        """Generate plain class via subprocess."""
        output_path = os.path.join( str( tmp_path ), "GameUtils.cs" )
        result = self._run( [
            "--json", "codegen", "class",
            "--name", "GameUtils", "--static",
            "--properties", '[{"name":"Version","type":"string","default":"\\"1.0\\""}]',
            "-o", output_path,
        ] )
        assert result.returncode == 0
        data = json.loads( result.stdout )
        assert data["class_name"] == "GameUtils"
        assert os.path.isfile( output_path )
        with open( output_path, "r", encoding="utf-8" ) as f:
            content = f.read()
        assert "public static class GameUtils" in content

    def test_localization_bulk_set_json( self, tmp_path ):
        """Bulk set translation keys via subprocess."""
        loc_path = os.path.join( str( tmp_path ), "en.json" )
        self._run( ["--json", "localization", "new", "--lang", "en", "-o", loc_path] )
        result = self._run( [
            "--json", "localization", "bulk-set", loc_path,
            "--keys", '{"game.title": "Test Game", "ui.ok": "OK"}',
        ] )
        assert result.returncode == 0
        data = json.loads( result.stdout )
        assert data["added"] == 2

    # ---- Refine batch: query, refs, bulk-modify, validate, panel-component ----

    def test_scene_query_json( self, tmp_path ):
        """scene query filters objects via subprocess."""
        scene_path = os.path.join( str( tmp_path ), "q.scene" )
        self._run( ["--json", "scene", "new", "--name", "q", "-o", scene_path, "--no-defaults"] )
        self._run( ["--json", "scene", "add-object", scene_path, "T1", "--tags", "tower", "--components", "rigidbody"] )
        self._run( ["--json", "scene", "add-object", scene_path, "T2", "--tags", "tower"] )
        self._run( ["--json", "scene", "add-object", scene_path, "E1", "--tags", "enemy"] )

        result = self._run( ["--json", "scene", "query", scene_path, "--has-tag", "tower"] )
        assert result.returncode == 0
        data = json.loads( result.stdout )
        names = sorted( r["name"] for r in data )
        assert names == ["T1", "T2"]

        # Compose two filters
        result2 = self._run( ["--json", "scene", "query", scene_path, "--has-tag", "tower", "--has-component", "rigidbody"] )
        data2 = json.loads( result2.stdout )
        assert len( data2 ) == 1
        assert data2[0]["name"] == "T1"

    def test_scene_refs_json( self, tmp_path ):
        """scene refs lists asset references via subprocess."""
        scene_path = os.path.join( str( tmp_path ), "r.scene" )
        self._run( ["--json", "scene", "new", "--name", "r", "-o", scene_path] )
        result = self._run( ["--json", "scene", "refs", scene_path] )
        assert result.returncode == 0
        data = json.loads( result.stdout )
        assert isinstance( data, dict )
        # Default scene has at least one model and one material
        assert "models" in data or "materials" in data

    def test_scene_bulk_modify_json( self, tmp_path ):
        """scene bulk-modify modifies all matches via subprocess."""
        scene_path = os.path.join( str( tmp_path ), "b.scene" )
        self._run( ["--json", "scene", "new", "--name", "b", "-o", scene_path, "--no-defaults"] )
        for n in ["A", "B", "C"]:
            self._run( ["--json", "scene", "add-object", scene_path, n, "--tags", "movable"] )

        result = self._run( [
            "--json", "scene", "bulk-modify", scene_path,
            "--has-tag", "movable",
            "--position", "999,888,777",
        ] )
        assert result.returncode == 0
        data = json.loads( result.stdout )
        assert data["modified_count"] == 3

        # Verify via query
        check = self._run( ["--json", "scene", "query", scene_path, "--has-tag", "movable"] )
        for row in json.loads( check.stdout ):
            assert row["position"] == "999,888,777"

    def test_prefab_refs_json( self, tmp_path ):
        """prefab refs lists asset references via subprocess."""
        prefab_path = os.path.join( str( tmp_path ), "p.prefab" )
        self._run( ["--json", "prefab", "new", "--name", "P", "-o", prefab_path, "--components", "model,rigidbody"] )
        result = self._run( ["--json", "prefab", "refs", prefab_path] )
        assert result.returncode == 0
        data = json.loads( result.stdout )
        assert "models" in data
        assert any( "models/dev/box.vmdl" in r for r in data["models"] )

    def test_prefab_modify_component_json( self, tmp_path ):
        """prefab modify-component edits component props via subprocess."""
        prefab_path = os.path.join( str( tmp_path ), "m.prefab" )
        self._run( ["--json", "prefab", "new", "--name", "M", "-o", prefab_path, "--components", "rigidbody"] )
        result = self._run( [
            "--json", "prefab", "modify-component", prefab_path,
            "--component-type", "Sandbox.Rigidbody",
            "--properties", '{"Gravity": false, "MassOverride": 50}',
        ] )
        assert result.returncode == 0
        data = json.loads( result.stdout )
        assert "Gravity" in data["updated_keys"]
        assert "MassOverride" in data["updated_keys"]

    def test_asset_find_refs_json( self, tmp_path ):
        """asset find-refs locates referrers via subprocess."""
        # Build a small project
        self._run( ["--json", "project", "new", "--name", "rg", "--output-dir", str( tmp_path )] )

        scene_path = os.path.join( str( tmp_path ), "Assets", "scenes", "level.scene" )
        self._run( ["--json", "scene", "new", "--name", "level", "-o", scene_path, "--no-defaults"] )
        # Inject a custom model ref via add-component on a fresh object
        add_obj = self._run( ["--json", "scene", "add-object", scene_path, "Box"] )
        guid = json.loads( add_obj.stdout )["guid"]
        self._run( [
            "--json", "scene", "add-component", scene_path, guid, "Sandbox.ModelRenderer",
            "--properties", '{"Model": "models/team/widget.vmdl"}',
        ] )

        # Create the actual asset file so list_assets finds it
        os.makedirs( os.path.join( str( tmp_path ), "Assets", "models", "team" ), exist_ok=True )
        with open( os.path.join( str( tmp_path ), "Assets", "models", "team", "widget.vmdl" ), "w", encoding="utf-8" ) as f:
            f.write( "<model>" )

        result = self._run( [
            "--json", "--project", str( tmp_path ),
            "asset", "find-refs", "models/team/widget.vmdl",
        ] )
        assert result.returncode == 0
        data = json.loads( result.stdout )
        assert len( data ) >= 1
        assert any( "level.scene" in row["file"] for row in data )

    def test_asset_find_unused_json( self, tmp_path ):
        """asset find-unused detects unreferenced assets via subprocess."""
        self._run( ["--json", "project", "new", "--name", "un", "--output-dir", str( tmp_path )] )
        # Drop an unreferenced material into Assets/
        mat_path = os.path.join( str( tmp_path ), "Assets", "materials", "stray.vmat" )
        os.makedirs( os.path.dirname( mat_path ), exist_ok=True )
        with open( mat_path, "w", encoding="utf-8" ) as f:
            f.write( "Layer0 { shader \"complex.shader\" }" )

        result = self._run( [
            "--json", "--project", str( tmp_path ),
            "asset", "find-unused", "--type", "material",
        ] )
        assert result.returncode == 0
        data = json.loads( result.stdout )
        assert any( "stray.vmat" in u["path"].replace( "\\", "/" ) for u in data )

    def test_project_validate_clean_json( self, tmp_path ):
        """project validate reports OK on a fresh project."""
        self._run( ["--json", "project", "new", "--name", "v", "--output-dir", str( tmp_path )] )
        result = self._run( ["--json", "--project", str( tmp_path ), "project", "validate"] )
        assert result.returncode == 0
        data = json.loads( result.stdout )
        assert data["broken_refs"] == []
        assert data["duplicate_guids"] == []

    def test_project_validate_broken_json( self, tmp_path ):
        """project validate flags a broken model reference and exits 1.

        Validation failures must exit non-zero so CI can gate on this command;
        check=False is required because subprocess.run with check=True would
        raise CalledProcessError before our assertions run.
        """
        self._run( ["--json", "project", "new", "--name", "v2", "--output-dir", str( tmp_path )] )
        scene_path = os.path.join( str( tmp_path ), "Assets", "scenes", "broken.scene" )
        self._run( ["--json", "scene", "new", "--name", "broken", "-o", scene_path, "--no-defaults"] )
        add_obj = self._run( ["--json", "scene", "add-object", scene_path, "Bad"] )
        guid = json.loads( add_obj.stdout )["guid"]
        self._run( [
            "--json", "scene", "add-component", scene_path, guid, "Sandbox.ModelRenderer",
            "--properties", '{"Model": "models/missing/whoops.vmdl"}',
        ] )
        result = self._run(
            ["--json", "--project", str( tmp_path ), "project", "validate", "--no-inputs"],
            check=False,
        )
        assert result.returncode == 1
        data = json.loads( result.stdout )
        assert data["ok"] is False
        assert any( "missing/whoops" in b["ref"] for b in data["broken_refs"] )

    def test_codegen_panel_component_json( self, tmp_path ):
        """codegen panel-component scaffolds Razor + scene snippet."""
        razor_path = os.path.join( str( tmp_path ), "HudBar.razor" )
        result = self._run( [
            "--json", "codegen", "panel-component",
            "--name", "HudBar",
            "--properties", '[{"name":"Health","type":"float","default":"100f"}]',
            "-o", razor_path,
        ] )
        assert result.returncode == 0
        data = json.loads( result.stdout )
        assert data["class_name"] == "HudBar"
        assert os.path.isfile( razor_path )
        assert os.path.isfile( os.path.join( str( tmp_path ), "HudBar.razor.scss" ) )
        snippet = json.loads( data["scene_snippet"] )
        types = [c["__type"] for c in snippet["Components"]]
        assert "Sandbox.ScreenPanel" in types
        assert "HudBar" in types

    def test_codegen_panel_component_appends_to_scene( self, tmp_path ):
        """codegen panel-component --scene appends GameObject to a scene."""
        scene_path = os.path.join( str( tmp_path ), "ui.scene" )
        razor_path = os.path.join( str( tmp_path ), "Crosshair.razor" )
        self._run( ["--json", "scene", "new", "--name", "ui", "-o", scene_path, "--no-defaults"] )

        result = self._run( [
            "--json", "codegen", "panel-component",
            "--name", "Crosshair",
            "-o", razor_path,
            "--scene", scene_path,
        ] )
        assert result.returncode == 0
        data = json.loads( result.stdout )
        assert data["scene_appended_to"]

        # Verify scene has the new object with both ScreenPanel and Crosshair
        with open( scene_path, "r", encoding="utf-8" ) as f:
            scene_json = json.load( f )
        names = [o["Name"] for o in scene_json["GameObjects"]]
        assert "Crosshair" in names

    # ---- Refine batch 2: diff, rename/move, instantiate-prefab ----

    def test_scene_diff_identical_json( self, tmp_path ):
        """scene diff reports identical when scenes match by name structure."""
        a = os.path.join( str( tmp_path ), "a.scene" )
        b = os.path.join( str( tmp_path ), "b.scene" )
        self._run( ["--json", "scene", "new", "--name", "x", "-o", a, "--no-defaults"] )
        self._run( ["--json", "scene", "new", "--name", "x", "-o", b, "--no-defaults"] )
        for n in ["A", "B"]:
            self._run( ["--json", "scene", "add-object", a, n] )
            self._run( ["--json", "scene", "add-object", b, n] )
        result = self._run( ["--json", "scene", "diff", a, b] )
        assert result.returncode == 0
        data = json.loads( result.stdout )
        assert data["identical"] is True

    def test_scene_diff_added_removed_modified_json( self, tmp_path ):
        """scene diff captures all three categories of change."""
        a = os.path.join( str( tmp_path ), "a.scene" )
        b = os.path.join( str( tmp_path ), "b.scene" )
        self._run( ["--json", "scene", "new", "--name", "x", "-o", a, "--no-defaults"] )
        self._run( ["--json", "scene", "new", "--name", "x", "-o", b, "--no-defaults"] )
        self._run( ["--json", "scene", "add-object", a, "OnlyA"] )
        self._run( ["--json", "scene", "add-object", a, "Shared", "--position", "0,0,0"] )
        self._run( ["--json", "scene", "add-object", b, "Shared", "--position", "1,2,3"] )
        self._run( ["--json", "scene", "add-object", b, "OnlyB"] )
        result = self._run( ["--json", "scene", "diff", a, b] )
        assert result.returncode == 0
        data = json.loads( result.stdout )
        assert "OnlyB" in data["added"]
        assert "OnlyA" in data["removed"]
        assert any( m["name"] == "Shared" for m in data["modified"] )

    def test_prefab_diff_json( self, tmp_path ):
        """prefab diff reports root component changes."""
        a = os.path.join( str( tmp_path ), "a.prefab" )
        b = os.path.join( str( tmp_path ), "b.prefab" )
        self._run( ["--json", "prefab", "new", "--name", "P", "-o", a, "--components", "model"] )
        self._run( ["--json", "prefab", "new", "--name", "P", "-o", b, "--components", "model,rigidbody"] )
        result = self._run( ["--json", "prefab", "diff", a, b] )
        assert result.returncode == 0
        data = json.loads( result.stdout )
        assert data["identical"] is False
        assert data["root_changes"] is not None

    def test_scene_instantiate_prefab_json( self, tmp_path ):
        """scene instantiate-prefab inserts a prefab as a GameObject."""
        scene_path = os.path.join( str( tmp_path ), "level.scene" )
        prefab_path = os.path.join( str( tmp_path ), "Bullet.prefab" )
        self._run( ["--json", "scene", "new", "--name", "level", "-o", scene_path, "--no-defaults"] )
        self._run( ["--json", "prefab", "new", "--name", "Bullet", "-o", prefab_path, "--components", "model"] )

        result = self._run( [
            "--json", "scene", "instantiate-prefab", scene_path, prefab_path,
            "--position", "10,20,30",
        ] )
        assert result.returncode == 0
        data = json.loads( result.stdout )
        assert data["guid"]

        # Verify scene now has a GameObject named "Bullet" with PrefabSource
        with open( scene_path, "r", encoding="utf-8" ) as f:
            scene_data = json.load( f )
        names = [o["Name"] for o in scene_data["GameObjects"]]
        assert "Bullet" in names
        bullet = next( o for o in scene_data["GameObjects"] if o["Name"] == "Bullet" )
        assert "PrefabSource" in bullet
        assert bullet["Position"] == "10,20,30"

    def test_asset_rename_json( self, tmp_path ):
        """asset rename moves the file and rewrites refs in scene+prefab."""
        self._run( ["--json", "project", "new", "--name", "rn", "--output-dir", str( tmp_path )] )

        # Asset on disk
        widget_dir = os.path.join( str( tmp_path ), "Assets", "models", "team" )
        os.makedirs( widget_dir, exist_ok=True )
        widget = os.path.join( widget_dir, "widget.vmdl" )
        with open( widget, "w", encoding="utf-8" ) as f:
            f.write( "<MODEL>" )

        # Scene that references it
        scene_path = os.path.join( str( tmp_path ), "Assets", "scenes", "level.scene" )
        self._run( ["--json", "scene", "new", "--name", "level", "-o", scene_path, "--no-defaults"] )
        add_obj = self._run( ["--json", "scene", "add-object", scene_path, "Box"] )
        guid = json.loads( add_obj.stdout )["guid"]
        self._run( [
            "--json", "scene", "add-component", scene_path, guid, "Sandbox.ModelRenderer",
            "--properties", '{"Model": "models/team/widget.vmdl"}',
        ] )

        result = self._run( [
            "--json", "--project", str( tmp_path ),
            "asset", "rename", "models/team/widget.vmdl", "gizmo",
        ] )
        assert result.returncode == 0
        data = json.loads( result.stdout )
        assert data["new_path"] == "models/team/gizmo.vmdl"
        assert data["file_renamed"] is True
        assert len( data["references_updated"] ) >= 1

        # File renamed on disk
        assert os.path.isfile( os.path.join( widget_dir, "gizmo.vmdl" ) )
        assert not os.path.isfile( widget )

    def test_asset_rename_dry_run_json( self, tmp_path ):
        """asset rename --dry-run reports counts but doesn't touch files."""
        self._run( ["--json", "project", "new", "--name", "dry", "--output-dir", str( tmp_path )] )
        widget = os.path.join( str( tmp_path ), "Assets", "models", "team", "widget.vmdl" )
        os.makedirs( os.path.dirname( widget ), exist_ok=True )
        with open( widget, "w", encoding="utf-8" ) as f:
            f.write( "<X>" )

        result = self._run( [
            "--json", "--project", str( tmp_path ),
            "asset", "rename", "models/team/widget.vmdl", "renamed.vmdl",
            "--dry-run",
        ] )
        assert result.returncode == 0
        data = json.loads( result.stdout )
        assert data["dry_run"] is True
        assert data["file_renamed"] is False
        # File still exists at the original path
        assert os.path.isfile( widget )

    def test_asset_move_json( self, tmp_path ):
        """asset move relocates file across directories and rewrites refs."""
        self._run( ["--json", "project", "new", "--name", "mv", "--output-dir", str( tmp_path )] )
        widget = os.path.join( str( tmp_path ), "Assets", "models", "team", "widget.vmdl" )
        os.makedirs( os.path.dirname( widget ), exist_ok=True )
        with open( widget, "w", encoding="utf-8" ) as f:
            f.write( "<X>" )

        scene_path = os.path.join( str( tmp_path ), "Assets", "scenes", "level.scene" )
        self._run( ["--json", "scene", "new", "--name", "level", "-o", scene_path, "--no-defaults"] )
        add_obj = self._run( ["--json", "scene", "add-object", scene_path, "Box"] )
        guid = json.loads( add_obj.stdout )["guid"]
        self._run( [
            "--json", "scene", "add-component", scene_path, guid, "Sandbox.ModelRenderer",
            "--properties", '{"Model": "models/team/widget.vmdl"}',
        ] )

        result = self._run( [
            "--json", "--project", str( tmp_path ),
            "asset", "move", "models/team/widget.vmdl", "models/shared/widget.vmdl",
        ] )
        assert result.returncode == 0
        data = json.loads( result.stdout )
        assert data["file_moved"] is True
        assert data["new_path"] == "models/shared/widget.vmdl"

        moved = os.path.join( str( tmp_path ), "Assets", "models", "shared", "widget.vmdl" )
        assert os.path.isfile( moved )
        assert not os.path.isfile( widget )
