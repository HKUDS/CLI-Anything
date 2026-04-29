"""Unit tests for cli_anything.sbox.core modules.

Covers: project, scene, prefab, codegen, input_config, collision_config, session, export.
All tests are self-contained and use pytest's tmp_path fixture for file operations.
"""

import copy
import json
import os
import uuid

import pytest

from cli_anything.sbox.core.codegen import (
    generate_class,
    generate_component,
    generate_editor_menu,
    generate_gameresource,
    generate_panel_component,
    generate_razor,
)
from cli_anything.sbox.core.collision_config import (
    add_layer,
    add_rule,
    get_default_collision_config,
    list_layers,
    load_collision_config,
    remove_layer,
    remove_rule,
    save_collision_config,
)
from cli_anything.sbox.core.export import (
    ASSET_EXTENSIONS,
    find_asset_refs,
    find_project_dir,
    find_unused_assets,
    get_asset_info,
    list_assets,
    move_asset,
    rename_asset,
)
from cli_anything.sbox.core.input_config import (
    add_action,
    get_default_input_config,
    list_actions,
    load_input_config,
    remove_action,
    save_input_config,
    set_action,
)
from cli_anything.sbox.core.localization import (
    bulk_set,
    create_translation_file,
    get_key,
    list_keys,
    load_translations,
    remove_key,
    set_key,
)
from cli_anything.sbox.core.material import (
    create_material,
    list_materials,
    parse_material,
    update_material,
)
from cli_anything.sbox.core.prefab import (
    create_prefab,
    diff_prefabs,
    from_scene_object,
    get_prefab_info,
    load_prefab,
    save_prefab,
)
from cli_anything.sbox.core.prefab import (
    extract_asset_refs as prefab_extract_asset_refs,
)
from cli_anything.sbox.core.prefab import (
    modify_component as prefab_modify_component,
)
from cli_anything.sbox.core.project import (
    add_package,
    configure_project,
    create_project,
    find_sbproj,
    get_project_info,
    load_project,
    remove_package,
    save_project,
)
from cli_anything.sbox.core.scene import (
    COMPONENT_PRESETS,
    add_component,
    add_object,
    bulk_modify_objects,
    clone_object,
    create_scene,
    diff_scenes,
    extract_asset_refs,
    find_object,
    get_object,
    get_scene_info,
    instantiate_prefab,
    list_objects,
    load_scene,
    modify_component,
    modify_object,
    query_objects,
    remove_component,
    remove_object,
    save_scene,
    set_navmesh_properties,
    set_scene_properties,
)
from cli_anything.sbox.core.session import Session
from cli_anything.sbox.core.sound import (
    create_sound_event,
    parse_sound_event,
    update_sound_event,
)
from cli_anything.sbox.core.validate import validate_project


# ============================================================================
# TestProject
# ============================================================================


class TestProject:
    """Tests for cli_anything.sbox.core.project."""

    def test_create_project(self, tmp_path):
        """Create a project and verify .sbproj, scene, configs are created."""
        info = create_project("MyGame", output_dir=str(tmp_path / "MyGame"))
        root = tmp_path / "MyGame"

        # Check returned info
        assert info["name"] == "MyGame"
        assert info["type"] == "game"
        assert info["max_players"] == 64
        assert info["tick_rate"] == 50

        # Check directory structure
        assert (root / "MyGame.sbproj").is_file()
        assert (root / ".editorconfig").is_file()
        assert (root / "Code" / "Assembly.cs").is_file()
        assert (root / "Editor" / "Assembly.cs").is_file()
        assert (root / "Assets" / "scenes" / "minimal.scene").is_file()
        assert (root / "ProjectSettings" / "Input.config").is_file()
        assert (root / "ProjectSettings" / "Collision.config").is_file()
        assert (root / "Libraries").is_dir()
        assert (root / "Localization").is_dir()

        # Verify .sbproj is valid JSON with StartupScene in Metadata
        with open(root / "MyGame.sbproj", "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["Title"] == "MyGame"
        assert data["Type"] == "game"
        assert "StartupScene" not in data, "StartupScene should be in Metadata, not root"
        assert data["Metadata"]["StartupScene"] == "scenes/minimal.scene"

        # Verify Input.config has all 31 actions including Slot0-Slot9
        with open(root / "ProjectSettings" / "Input.config", "r", encoding="utf-8") as f:
            input_data = json.load(f)
        action_names = [a["Name"] for a in input_data["Actions"]]
        assert len( action_names ) == 31
        for slot in ["Slot0", "Slot1", "Slot2", "Slot3", "Slot4", "Slot5",
                      "Slot6", "Slot7", "Slot8", "Slot9"]:
            assert slot in action_names, f"Missing {slot} in Input.config"

    def test_create_project_custom_settings(self, tmp_path):
        """Create project with custom max_players, tick_rate, etc."""
        info = create_project(
            "CustomGame",
            output_dir=str(tmp_path / "CustomGame"),
            max_players=8,
            tick_rate=128,
            network_type="ServerOnly",
            org="myorg",
        )

        assert info["max_players"] == 8
        assert info["tick_rate"] == 128
        assert info["network_type"] == "ServerOnly"
        assert info["org"] == "myorg"

        # Verify persisted in JSON
        data = load_project(info["sbproj"])
        assert data["Metadata"]["MaxPlayers"] == 8
        assert data["Metadata"]["TickRate"] == 128
        assert data["Metadata"]["GameNetworkType"] == "ServerOnly"
        assert data["Org"] == "myorg"

    def test_load_save_project(self, tmp_path):
        """Load and re-save a project, verify round-trip."""
        info = create_project("RoundTrip", output_dir=str(tmp_path / "RoundTrip"))
        sbproj = info["sbproj"]

        data = load_project(sbproj)
        data["Title"] = "Modified"
        data["Metadata"]["MaxPlayers"] = 32
        save_project(sbproj, data)

        reloaded = load_project(sbproj)
        assert reloaded["Title"] == "Modified"
        assert reloaded["Metadata"]["MaxPlayers"] == 32

    def test_get_project_info(self, tmp_path):
        """Verify project info dict has all expected fields."""
        info = create_project("InfoTest", output_dir=str(tmp_path / "InfoTest"))
        proj_info = get_project_info(info["sbproj"])

        expected_keys = {
            "title", "type", "org", "ident", "startup_scene",
            "max_players", "min_players", "tick_rate", "network_type",
            "map_select", "map_list", "package_references", "path",
        }
        assert expected_keys.issubset(set(proj_info.keys()))
        assert proj_info["title"] == "InfoTest"
        assert proj_info["ident"] == "infotest"
        assert proj_info["max_players"] == 64
        assert proj_info["tick_rate"] == 50

    def test_configure_project(self, tmp_path):
        """Modify project settings and verify they persist."""
        info = create_project("ConfigTest", output_dir=str(tmp_path / "ConfigTest"))
        sbproj = info["sbproj"]

        updated = configure_project(
            sbproj,
            title="Renamed",
            max_players=16,
            tick_rate=30,
            org="neworg",
        )

        assert updated["title"] == "Renamed"
        assert updated["max_players"] == 16
        assert updated["tick_rate"] == 30
        assert updated["org"] == "neworg"

        # Confirm persistence by reloading raw JSON
        raw = load_project(sbproj)
        assert raw["Title"] == "Renamed"
        assert raw["Org"] == "neworg"
        assert raw["Metadata"]["MaxPlayers"] == 16
        assert raw["Metadata"]["TickRate"] == 30

    def test_find_sbproj(self, tmp_path):
        """Test finding .sbproj file in a directory."""
        info = create_project("FindMe", output_dir=str(tmp_path / "FindMe"))
        found = find_sbproj(str(tmp_path / "FindMe"))
        assert found is not None
        assert found.endswith("FindMe.sbproj")

    def test_find_sbproj_not_found(self, tmp_path):
        """Test when no .sbproj exists."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        result = find_sbproj(str(empty_dir))
        assert result is None


# ============================================================================
# TestScene
# ============================================================================


class TestScene:
    """Tests for cli_anything.sbox.core.scene."""

    def test_create_scene_with_defaults(self, tmp_path):
        """Create scene with default objects (Sun, Skybox, Plane, Camera)."""
        scene_path = str(tmp_path / "test.scene")
        data = create_scene("test", output_path=scene_path)

        objects = data["GameObjects"]
        names = [obj["Name"] for obj in objects]
        assert "Sun" in names
        assert "2D Skybox" in names
        assert "Plane" in names
        assert "Camera" in names

        props = data["SceneProperties"]
        assert props["FixedUpdateFrequency"] == 50
        assert props["NetworkFrequency"] == 60

    def test_create_scene_empty(self, tmp_path):
        """Create scene without defaults."""
        data = create_scene("empty", include_defaults=False)
        assert data["GameObjects"] == []
        assert data["Title"] == "empty"

    def test_list_objects(self, tmp_path):
        """List objects in a scene."""
        scene_path = str(tmp_path / "list.scene")
        create_scene("list", output_path=scene_path)

        objects = list_objects(scene_path)
        assert len(objects) >= 4  # Sun, Skybox, Plane, Camera
        for obj in objects:
            assert "guid" in obj
            assert "name" in obj
            assert "position" in obj
            assert "component_types" in obj

    def test_add_object(self, tmp_path):
        """Add a named object and verify it appears in list."""
        scene_path = str(tmp_path / "add.scene")
        create_scene("add", output_path=scene_path)

        guid = add_object(scene_path, "Turret", position="100,0,50")
        assert guid is not None

        objects = list_objects(scene_path)
        turret = [o for o in objects if o["name"] == "Turret"]
        assert len(turret) == 1
        assert turret[0]["guid"] == guid
        assert turret[0]["position"] == "100,0,50"

    def test_add_object_with_components(self, tmp_path):
        """Add object with component presets."""
        scene_path = str(tmp_path / "comps.scene")
        create_scene("comps", output_path=scene_path)

        guid = add_object(
            scene_path,
            "PhysicsBox",
            components=["model", "box_collider", "rigidbody"],
        )

        objects = list_objects(scene_path)
        box = [o for o in objects if o["name"] == "PhysicsBox"][0]
        types = box["component_types"]
        assert "Sandbox.ModelRenderer" in types
        assert "Sandbox.BoxCollider" in types
        assert "Sandbox.Rigidbody" in types

    def test_remove_object_by_name(self, tmp_path):
        """Remove an object and verify it's gone."""
        scene_path = str(tmp_path / "rem_name.scene")
        create_scene("rem_name", output_path=scene_path)
        add_object(scene_path, "Removable")

        removed = remove_object(scene_path, name="Removable")
        assert removed is True

        objects = list_objects(scene_path)
        names = [o["name"] for o in objects]
        assert "Removable" not in names

    def test_remove_object_by_guid(self, tmp_path):
        """Remove by GUID."""
        scene_path = str(tmp_path / "rem_guid.scene")
        create_scene("rem_guid", output_path=scene_path)
        guid = add_object(scene_path, "ByGuid")

        removed = remove_object(scene_path, guid=guid)
        assert removed is True

        objects = list_objects(scene_path)
        guids = [o["guid"] for o in objects]
        assert guid not in guids

    def test_find_object(self, tmp_path):
        """Find object by name and by GUID."""
        scene_path = str(tmp_path / "find.scene")
        create_scene("find", output_path=scene_path)
        guid = add_object(scene_path, "Findable")

        data = load_scene(scene_path)

        # Find by name
        obj_by_name = find_object(data, name="Findable")
        assert obj_by_name is not None
        assert obj_by_name["Name"] == "Findable"

        # Find by guid
        obj_by_guid = find_object(data, guid=guid)
        assert obj_by_guid is not None
        assert obj_by_guid["__guid"] == guid

        # Not found
        assert find_object(data, name="NonExistent") is None

    def test_add_component(self, tmp_path):
        """Add a component to an existing object."""
        scene_path = str(tmp_path / "add_comp.scene")
        create_scene("add_comp", output_path=scene_path)
        obj_guid = add_object(scene_path, "Target")

        comp_guid = add_component(scene_path, obj_guid, "rigidbody")
        assert comp_guid is not None

        data = load_scene(scene_path)
        obj = find_object(data, guid=obj_guid)
        comp_types = [c["__type"] for c in obj["Components"]]
        assert "Sandbox.Rigidbody" in comp_types

    def test_remove_component(self, tmp_path):
        """Remove a component from an object."""
        scene_path = str(tmp_path / "rem_comp.scene")
        create_scene("rem_comp", output_path=scene_path)
        obj_guid = add_object(
            scene_path, "WithRB", components=["rigidbody", "model"]
        )

        removed = remove_component(
            scene_path, obj_guid, component_type="Sandbox.Rigidbody"
        )
        assert removed is True

        data = load_scene(scene_path)
        obj = find_object(data, guid=obj_guid)
        comp_types = [c["__type"] for c in obj["Components"]]
        assert "Sandbox.Rigidbody" not in comp_types
        # model should still be there
        assert "Sandbox.ModelRenderer" in comp_types

    def test_scene_guid_uniqueness(self, tmp_path):
        """All GUIDs in a scene should be unique."""
        scene_path = str(tmp_path / "guids.scene")
        create_scene("guids", output_path=scene_path)
        add_object(scene_path, "Extra1", components=["model", "rigidbody"])
        add_object(scene_path, "Extra2", components=["camera"])

        data = load_scene(scene_path)
        guids = []

        def collect_guids(objects):
            for obj in objects:
                if "__guid" in obj:
                    guids.append(obj["__guid"])
                for comp in obj.get("Components", []):
                    if "__guid" in comp:
                        guids.append(comp["__guid"])
                collect_guids(obj.get("Children", []))

        collect_guids(data.get("GameObjects", []))

        assert len(guids) == len(set(guids)), (
            f"Duplicate GUIDs found: {len(guids)} total, {len(set(guids))} unique"
        )

    def test_scene_json_valid(self, tmp_path):
        """Generated scene is valid JSON with expected structure."""
        scene_path = str(tmp_path / "valid.scene")
        create_scene("valid", output_path=scene_path)

        with open(scene_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "GameObjects" in data
        assert "SceneProperties" in data
        assert "Title" in data
        assert "__version" in data
        assert isinstance(data["GameObjects"], list)
        assert isinstance(data["SceneProperties"], dict)


# ============================================================================
# TestPrefab
# ============================================================================


class TestPrefab:
    """Tests for cli_anything.sbox.core.prefab."""

    def test_create_prefab(self, tmp_path):
        """Create a prefab and verify structure."""
        prefab_path = str(tmp_path / "test.prefab")
        data = create_prefab("TestPrefab", output_path=prefab_path)

        assert "RootObject" in data
        root = data["RootObject"]
        assert root["Name"] == "TestPrefab"
        assert "__guid" in root
        assert root["Enabled"] is True
        assert "Components" in root
        assert "Children" in root
        assert data["ResourceVersion"] == 1
        assert data["__version"] == 1

        # Verify file was written
        with open(prefab_path, "r", encoding="utf-8") as f:
            on_disk = json.load(f)
        assert on_disk["RootObject"]["Name"] == "TestPrefab"

    def test_create_prefab_with_components(self, tmp_path):
        """Create prefab with component presets."""
        prefab_path = str(tmp_path / "comps.prefab")
        data = create_prefab(
            "PhysicsPrefab",
            output_path=prefab_path,
            components=["model", "box_collider", "rigidbody"],
        )

        root = data["RootObject"]
        comp_types = [c["__type"] for c in root["Components"]]
        assert "Sandbox.ModelRenderer" in comp_types
        assert "Sandbox.BoxCollider" in comp_types
        assert "Sandbox.Rigidbody" in comp_types

        # Each component should have a unique __guid
        comp_guids = [c["__guid"] for c in root["Components"]]
        assert len(comp_guids) == len(set(comp_guids))

    def test_get_prefab_info(self, tmp_path):
        """Verify prefab info."""
        prefab_path = str(tmp_path / "info.prefab")
        create_prefab(
            "InfoPrefab",
            output_path=prefab_path,
            components=["model", "rigidbody"],
        )

        info = get_prefab_info(prefab_path)
        assert info["name"] == "InfoPrefab"
        assert "guid" in info
        assert info["path"] == prefab_path
        assert info["component_count"] == 2
        assert "Sandbox.ModelRenderer" in info["component_types"]
        assert "Sandbox.Rigidbody" in info["component_types"]
        assert info["children_count"] == 0
        assert info["network_mode"] == 0

    def test_from_scene_object(self, tmp_path):
        """Extract a scene object into a prefab."""
        scene_path = str(tmp_path / "source.scene")
        create_scene("source", output_path=scene_path)
        obj_guid = add_object(
            scene_path,
            "ExtractMe",
            position="10,20,30",
            components=["model", "rigidbody"],
        )

        prefab_path = str(tmp_path / "extracted.prefab")
        data = from_scene_object(scene_path, obj_guid, prefab_path)

        assert "RootObject" in data
        root = data["RootObject"]
        assert root["Name"] == "ExtractMe"
        assert root["Position"] == "10,20,30"

        comp_types = [c["__type"] for c in root.get("Components", [])]
        assert "Sandbox.ModelRenderer" in comp_types
        assert "Sandbox.Rigidbody" in comp_types

        # Verify the prefab file exists on disk
        assert os.path.isfile(prefab_path)


# ============================================================================
# TestCodegen
# ============================================================================


class TestCodegen:
    """Tests for cli_anything.sbox.core.codegen."""

    def test_generate_component_basic(self):
        """Generate a basic sealed component."""
        result = generate_component("PlayerHealth")

        assert result["filename"] == "PlayerHealth.cs"
        assert result["class_name"] == "PlayerHealth"
        content = result["content"]
        assert "using Sandbox;" in content
        assert "public sealed class PlayerHealth : Component" in content

    def test_generate_component_with_properties(self):
        """Generate component with typed properties."""
        props = [
            {"name": "Health", "type": "float", "default": "100f"},
            {"name": "MaxHealth", "type": "float", "default": "100f"},
            {"name": "DisplayName", "type": "string"},
        ]
        result = generate_component("PlayerStats", properties=props)
        content = result["content"]

        assert "[Property]" in content
        assert "public float Health { get; set; } = 100f;" in content
        assert "public float MaxHealth { get; set; } = 100f;" in content
        assert "public string DisplayName { get; set; }" in content

    def test_generate_component_networked(self):
        """Generate partial class with [Sync] and IsProxy guard."""
        result = generate_component(
            "NetPlayer",
            is_networked=True,
            properties=[{"name": "Health", "type": "float", "default": "100f"}],
            lifecycle_methods=["OnFixedUpdate"],
        )
        content = result["content"]

        assert "public partial class NetPlayer : Component" in content
        assert "sealed" not in content
        assert "[Sync]" in content
        assert "if ( IsProxy ) return;" in content

    def test_generate_component_with_interfaces(self):
        """Generate component implementing interfaces."""
        result = generate_component(
            "DamageReceiver",
            interfaces=["Component.ITriggerListener", "Component.IDamageable"],
        )
        content = result["content"]

        assert (
            "public sealed class DamageReceiver : Component, "
            "Component.ITriggerListener, Component.IDamageable"
        ) in content

    def test_generate_component_lifecycle_methods(self):
        """Generate with OnUpdate, OnFixedUpdate, OnStart."""
        result = generate_component(
            "LifecycleTest",
            lifecycle_methods=["OnStart", "OnUpdate", "OnFixedUpdate"],
        )
        content = result["content"]

        assert "protected override void OnStart()" in content
        assert "protected override void OnUpdate()" in content
        assert "protected override void OnFixedUpdate()" in content

    def test_generate_gameresource(self):
        """Generate a GameResource class."""
        result = generate_gameresource(
            "TowerData",
            display_name="Tower Data",
            extension="tower",
            description="Data for a tower defense tower",
            properties=[
                {"name": "Cost", "type": "int", "default": "100"},
                {"name": "Range", "type": "float", "default": "500f"},
            ],
        )

        assert result["filename"] == "TowerData.cs"
        assert result["class_name"] == "TowerData"
        content = result["content"]

        assert "using Sandbox;" in content
        assert '[GameResource( "Tower Data", "tower", "Data for a tower defense tower" )]' in content
        assert "public class TowerData : GameResource" in content
        assert "public int Cost { get; set; } = 100;" in content
        assert "public float Range { get; set; } = 500f;" in content

    def test_generate_editor_menu(self):
        """Generate an editor menu class."""
        result = generate_editor_menu(
            "MyTool",
            menu_path="Tools/My Tool",
            method_name="Open",
            dialog_title="My Tool",
            dialog_message="Hello from My Tool",
        )

        assert result["filename"] == "MyTool.cs"
        assert result["class_name"] == "MyTool"
        content = result["content"]

        assert "using Editor;" in content
        assert "using Sandbox;" in content
        assert "public static class MyTool" in content
        assert '[Menu( "Editor", "Tools/My Tool" )]' in content
        assert "public static void Open()" in content
        assert 'EditorUtility.DisplayDialog( "My Tool", "Hello from My Tool" );' in content

    def test_code_style_tabs(self):
        """Verify generated code uses tabs, not spaces."""
        result = generate_component(
            "TabTest",
            properties=[{"name": "Value", "type": "int"}],
            lifecycle_methods=["OnUpdate"],
        )
        content = result["content"]

        # Split into lines, check that indented lines use tabs
        for line in content.split("\r\n"):
            stripped = line.lstrip("\t")
            if len(stripped) < len(line):
                # This line was indented - verify it used tabs not spaces
                indent = line[: len(line) - len(stripped)]
                assert "\t" in indent, f"Line uses spaces instead of tabs: {repr(line)}"
                # Indentation part should be only tabs
                assert indent == indent.replace(" ", ""), (
                    f"Mixed tabs/spaces in indent: {repr(line)}"
                )

    def test_code_style_allman_braces(self):
        """Verify Allman-style braces."""
        result = generate_component(
            "BraceTest",
            lifecycle_methods=["OnUpdate"],
        )
        content = result["content"]
        lines = content.split("\r\n")

        # Find lines with opening braces - they should be on their own line
        # (possibly with leading whitespace only)
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped == "{":
                # This is correct Allman style - brace on its own line
                continue
            if stripped.endswith("{") and stripped != "{":
                # Brace at end of a non-empty line would be K&R style
                # But we need to allow attribute lines like [Menu( "Editor", "..." )]
                # that aren't brace-bearing. The check is: if the line has a brace
                # AND is not just the brace, that would violate Allman style.
                # However, there is no K&R brace in our generated code.
                pytest.fail(
                    f"K&R-style brace found on line {i + 1}: {repr(line)}"
                )

    def test_code_style_crlf(self):
        """Verify CRLF line endings."""
        result = generate_component("CrlfTest")
        content = result["content"]

        # Content should have \r\n
        assert "\r\n" in content, "Expected CRLF line endings"

        # Should not have bare \n (without preceding \r)
        # Replace all \r\n first, then check for remaining \n
        remaining = content.replace("\r\n", "")
        assert "\n" not in remaining, "Found bare LF without CR"


# ============================================================================
# TestInputConfig
# ============================================================================


class TestInputConfig:
    """Tests for cli_anything.sbox.core.input_config."""

    def _write_default_config(self, tmp_path):
        """Helper: write default input config to a temp file and return path."""
        config_path = str(tmp_path / "Input.config")
        data = get_default_input_config()
        save_input_config(config_path, data)
        return config_path

    def test_get_default_config(self):
        """Default config has all standard actions."""
        config = get_default_input_config()
        actions = config["Actions"]
        names = [a["Name"] for a in actions]

        assert "Forward" in names
        assert "Backward" in names
        assert "Jump" in names
        assert "Attack1" in names
        assert "Reload" in names
        assert "Use" in names

        # Should have __guid and __type metadata
        assert "__guid" in config
        assert config["__type"] == "InputSettings"

    def test_add_action(self, tmp_path):
        """Add a new action and verify it appears."""
        config_path = self._write_default_config(tmp_path)

        new_action = add_action(
            config_path,
            name="Sprint",
            group="Movement",
            keyboard_code="shift",
        )
        assert new_action["Name"] == "Sprint"
        assert new_action["GroupName"] == "Movement"
        assert new_action["KeyboardCode"] == "shift"

        # Verify persistence
        actions = list_actions(config_path)
        names = [a["Name"] for a in actions]
        assert "Sprint" in names

    def test_add_duplicate_action(self, tmp_path):
        """Adding duplicate action should raise ValueError."""
        config_path = self._write_default_config(tmp_path)

        with pytest.raises(ValueError, match="already exists"):
            add_action(config_path, name="Forward", group="Movement")

    def test_remove_action(self, tmp_path):
        """Remove an action and verify it's gone."""
        config_path = self._write_default_config(tmp_path)

        removed = remove_action(config_path, "Voice")
        assert removed is True

        actions = list_actions(config_path)
        names = [a["Name"] for a in actions]
        assert "Voice" not in names

    def test_set_action(self, tmp_path):
        """Modify action bindings."""
        config_path = self._write_default_config(tmp_path)

        updated = set_action(
            config_path,
            name="Jump",
            keyboard_code="F",
            group="Custom",
        )
        assert updated["KeyboardCode"] == "F"
        assert updated["GroupName"] == "Custom"

        # Verify persistence
        actions = list_actions(config_path)
        jump = [a for a in actions if a["Name"] == "Jump"][0]
        assert jump["KeyboardCode"] == "F"
        assert jump["GroupName"] == "Custom"

    def test_list_actions(self, tmp_path):
        """List all actions returns proper format."""
        config_path = self._write_default_config(tmp_path)

        actions = list_actions(config_path)
        assert isinstance(actions, list)
        assert len(actions) > 0

        for action in actions:
            assert "Name" in action
            assert isinstance(action["Name"], str)


# ============================================================================
# TestCollisionConfig
# ============================================================================


class TestCollisionConfig:
    """Tests for cli_anything.sbox.core.collision_config."""

    def _write_default_config(self, tmp_path):
        """Helper: write default collision config to a temp file and return path."""
        config_path = str(tmp_path / "Collision.config")
        data = get_default_collision_config()
        save_collision_config(config_path, data)
        return config_path

    def test_get_default_config(self):
        """Default config has standard layers."""
        config = get_default_collision_config()
        defaults = config["Defaults"]

        assert "solid" in defaults
        assert "world" in defaults
        assert "trigger" in defaults
        assert "ladder" in defaults
        assert "water" in defaults

        # Should have pairs
        pairs = config["Pairs"]
        assert isinstance(pairs, list)
        assert len(pairs) > 0

    def test_add_layer(self, tmp_path):
        """Add a custom collision layer."""
        config_path = self._write_default_config(tmp_path)

        updated_defaults = add_layer(config_path, "projectile", default="Collide")
        assert "projectile" in updated_defaults
        assert updated_defaults["projectile"] == "Collide"

        # Verify persistence
        data = load_collision_config(config_path)
        assert "projectile" in data["Defaults"]

    def test_remove_builtin_layer(self, tmp_path):
        """Removing built-in layer should raise ValueError."""
        config_path = self._write_default_config(tmp_path)

        with pytest.raises(ValueError, match="Cannot remove built-in layer"):
            remove_layer(config_path, "solid")

        with pytest.raises(ValueError, match="Cannot remove built-in layer"):
            remove_layer(config_path, "trigger")

    def test_add_rule(self, tmp_path):
        """Add a collision pair rule."""
        config_path = self._write_default_config(tmp_path)

        # First add custom layers so the rule makes sense
        add_layer(config_path, "projectile", default="Collide")
        add_layer(config_path, "enemy", default="Collide")

        rule = add_rule(config_path, "projectile", "enemy", result="Collide")
        assert rule["a"] == "projectile"
        assert rule["b"] == "enemy"
        assert rule["r"] == "Collide"

        # Verify persistence
        data = load_collision_config(config_path)
        pairs = data["Pairs"]
        matching = [
            p for p in pairs
            if (p["a"] == "projectile" and p["b"] == "enemy")
            or (p["a"] == "enemy" and p["b"] == "projectile")
        ]
        assert len(matching) == 1

    def test_remove_rule(self, tmp_path):
        """Remove a pair rule."""
        config_path = self._write_default_config(tmp_path)

        # Add a custom rule then remove it
        add_layer(config_path, "projectile", default="Collide")
        add_rule(config_path, "projectile", "solid", result="Collide")

        removed = remove_rule(config_path, "projectile", "solid")
        assert removed is True

        # Verify it's gone
        data = load_collision_config(config_path)
        pairs = data["Pairs"]
        matching = [
            p for p in pairs
            if (p["a"] == "projectile" and p["b"] == "solid")
            or (p["a"] == "solid" and p["b"] == "projectile")
        ]
        assert len(matching) == 0


# ============================================================================
# TestSession
# ============================================================================


class TestSession:
    """Tests for cli_anything.sbox.core.session."""

    def test_session_create(self, tmp_path):
        """Create a new session."""
        session_path = str(tmp_path / "session.json")
        session = Session(session_path=session_path)

        status = session.get_status()
        assert status["project_path"] is None
        assert status["scene_path"] is None
        assert status["undo_count"] == 0
        assert status["redo_count"] == 0

    def test_session_set_project(self, tmp_path):
        """Set project path."""
        session_path = str(tmp_path / "session.json")
        session = Session(session_path=session_path)

        # Create a dummy sbproj to reference
        dummy_proj = tmp_path / "test.sbproj"
        dummy_proj.write_text("{}", encoding="utf-8")

        session.set_project(str(dummy_proj))
        assert session.project_path == str(dummy_proj.resolve())

        # Verify persistence by creating a new Session from the same file
        session2 = Session(session_path=session_path)
        assert session2.project_path == str(dummy_proj.resolve())

    def test_session_undo_redo(self, tmp_path):
        """Record ops, undo, redo."""
        session_path = str(tmp_path / "session.json")
        session = Session(session_path=session_path)

        # Record two operations
        session.record_operation(
            op_type="scene_modify",
            description="Added turret",
            before_state={"count": 0},
            after_state={"count": 1},
        )
        session.record_operation(
            op_type="scene_modify",
            description="Added wall",
            before_state={"count": 1},
            after_state={"count": 2},
        )

        status = session.get_status()
        assert status["undo_count"] == 2
        assert status["redo_count"] == 0

        # Undo last operation
        undone = session.undo()
        assert undone is not None
        assert undone["undone"] is True
        assert undone["description"] == "Added wall"
        assert undone["before_state"] == {"count": 1}

        status = session.get_status()
        assert status["undo_count"] == 1
        assert status["redo_count"] == 1

        # Redo it
        redone = session.redo()
        assert redone is not None
        assert redone["redone"] is True
        assert redone["description"] == "Added wall"

        status = session.get_status()
        assert status["undo_count"] == 2
        assert status["redo_count"] == 0

        # Undo when stack is empty after undoing everything
        session.undo()
        session.undo()
        result = session.undo()
        assert result is None

    def test_session_save_load(self, tmp_path):
        """Save and reload session."""
        session_path = str(tmp_path / "session.json")
        session = Session(session_path=session_path)

        dummy_proj = tmp_path / "test.sbproj"
        dummy_proj.write_text("{}", encoding="utf-8")
        dummy_scene = tmp_path / "test.scene"
        dummy_scene.write_text("{}", encoding="utf-8")

        session.set_project(str(dummy_proj))
        session.set_scene(str(dummy_scene))
        session.record_operation(
            op_type="codegen",
            description="Generated component",
        )

        # Create a fresh Session from the same path
        session2 = Session(session_path=session_path)
        status = session2.get_status()
        assert status["project_path"] == str(dummy_proj.resolve())
        assert status["scene_path"] == str(dummy_scene.resolve())
        assert status["undo_count"] == 1

    def test_session_clear(self, tmp_path):
        """Clear session state."""
        session_path = str(tmp_path / "session.json")
        session = Session(session_path=session_path)

        dummy_proj = tmp_path / "test.sbproj"
        dummy_proj.write_text("{}", encoding="utf-8")
        session.set_project(str(dummy_proj))
        session.record_operation(
            op_type="scene_modify",
            description="Test op",
        )

        session.clear()

        status = session.get_status()
        assert status["project_path"] is None
        assert status["scene_path"] is None
        assert status["undo_count"] == 0
        assert status["redo_count"] == 0

    def test_session_load_corrupt_file_warns_and_preserves_backup(self, tmp_path, capsys):
        """A malformed session file is preserved as .corrupt.<ts> and warned about.

        Reset must not be silent: the user's undo history could otherwise be
        destroyed without any signal. The backup uses a timestamp suffix so a
        second corruption does not silently overwrite the first.
        """
        session_path = tmp_path / "session.json"
        session_path.write_text("not valid json{{{", encoding="utf-8")

        session = Session(session_path=str(session_path))

        captured = capsys.readouterr()
        assert "could not be read" in captured.err
        assert "preserved as" in captured.err

        # Original file moved aside
        assert not session_path.exists()

        # Backup exists with timestamp suffix and contains the original bytes
        backups = list(tmp_path.glob("session.json.corrupt.*"))
        assert len(backups) == 1
        assert backups[0].read_text(encoding="utf-8") == "not valid json{{{"

        # Session is reset to empty state
        assert session.get_status()["project_path"] is None


# ============================================================================
# TestExport
# ============================================================================


class TestExport:
    """Tests for cli_anything.sbox.core.export."""

    def _create_project_with_assets(self, tmp_path):
        """Helper: create a project with known asset files and return root path."""
        info = create_project("AssetTest", output_dir=str(tmp_path / "AssetTest"))
        root = tmp_path / "AssetTest"

        # Add additional asset files
        # A prefab
        prefab_dir = root / "Assets" / "prefabs"
        prefab_dir.mkdir(parents=True, exist_ok=True)
        create_prefab("Turret", output_path=str(prefab_dir / "turret.prefab"))

        # A C# file
        code_dir = root / "Assets" / "code"
        code_dir.mkdir(parents=True, exist_ok=True)
        (code_dir / "PlayerHealth.cs").write_text(
            "public class PlayerHealth {}", encoding="utf-8"
        )

        return str(root)

    def test_list_assets(self, tmp_path):
        """List assets in a project directory."""
        project_dir = self._create_project_with_assets(tmp_path)

        assets = list_assets(project_dir)
        assert len(assets) >= 3  # minimal.scene + turret.prefab + PlayerHealth.cs

        types = {a["type"] for a in assets}
        assert "scene" in types
        assert "prefab" in types
        assert "code" in types

        # Each asset should have required keys
        for asset in assets:
            assert "path" in asset
            assert "type" in asset
            assert "name" in asset
            assert "size_bytes" in asset

    def test_list_assets_filtered(self, tmp_path):
        """Filter assets by type."""
        project_dir = self._create_project_with_assets(tmp_path)

        # Filter to scenes only
        scenes = list_assets(project_dir, asset_type="scene")
        for asset in scenes:
            assert asset["type"] == "scene"
            assert asset["name"].endswith(".scene")

        # Filter to prefabs only
        prefabs = list_assets(project_dir, asset_type="prefab")
        for asset in prefabs:
            assert asset["type"] == "prefab"
            assert asset["name"].endswith(".prefab")

        # Scenes and prefabs should not overlap
        scene_names = {a["name"] for a in scenes}
        prefab_names = {a["name"] for a in prefabs}
        assert scene_names.isdisjoint(prefab_names)

    def test_find_project_dir(self, tmp_path):
        """Find project dir from a subdirectory."""
        info = create_project("FindDir", output_dir=str(tmp_path / "FindDir"))
        root = tmp_path / "FindDir"

        # Create a nested directory
        nested = root / "Assets" / "scenes" / "subdir"
        nested.mkdir(parents=True, exist_ok=True)

        # find_project_dir should walk up and find the root
        found = find_project_dir(str(nested))
        assert found is not None
        # Normalize paths for comparison
        assert os.path.normcase(os.path.normpath(found)) == os.path.normcase(
            os.path.normpath(str(root))
        )

        # Should also work from a file inside the project
        scene_file = root / "Assets" / "scenes" / "minimal.scene"
        found_from_file = find_project_dir(str(scene_file))
        assert found_from_file is not None
        assert os.path.normcase(os.path.normpath(found_from_file)) == os.path.normcase(
            os.path.normpath(str(root))
        )


# ---------------------------------------------------------------------------
# New tests for refinement pass
# ---------------------------------------------------------------------------


class TestComponentPresets:
    """Tests for expanded COMPONENT_PRESETS."""

    def test_preset_count(self):
        """Verify we have 29 component presets."""
        assert len( COMPONENT_PRESETS ) == 29

    def test_all_presets_have_type(self):
        """Every preset must have a __type key."""
        for name, preset in COMPONENT_PRESETS.items():
            assert "__type" in preset, f"Preset '{name}' missing __type"
            assert preset["__type"].startswith( "Sandbox." ), f"Preset '{name}' __type should start with Sandbox."


class TestSceneModify:
    """Tests for modify_object and set_scene_properties."""

    def test_modify_object_name_and_position(self, tmp_path):
        scene_path = str( tmp_path / "test.scene" )
        create_scene( "test", output_path=scene_path, include_defaults=False )
        guid = add_object( scene_path, "OldName", position="0,0,0" )

        result = modify_object( scene_path, guid=guid, new_name="NewName", position="100,200,300" )
        assert result["name"] == "NewName"
        assert "Name" in result["modified_fields"]
        assert "Position" in result["modified_fields"]

        objects = list_objects( scene_path )
        obj = [o for o in objects if o["guid"] == guid][0]
        assert obj["name"] == "NewName"
        assert obj["position"] == "100,200,300"

    def test_modify_object_selective(self, tmp_path):
        scene_path = str( tmp_path / "test.scene" )
        create_scene( "test", output_path=scene_path, include_defaults=False )
        guid = add_object( scene_path, "MyObj", position="10,20,30", scale="2,2,2" )

        # Only modify position, scale should stay unchanged
        modify_object( scene_path, guid=guid, position="99,99,99" )

        data = load_scene( scene_path )
        obj = find_object( data, guid=guid )
        assert obj["Position"] == "99,99,99"
        assert obj["Scale"] == "2,2,2"
        assert obj["Name"] == "MyObj"

    def test_modify_object_not_found(self, tmp_path):
        scene_path = str( tmp_path / "test.scene" )
        create_scene( "test", output_path=scene_path, include_defaults=False )

        with pytest.raises( ValueError, match="not found" ):
            modify_object( scene_path, guid="nonexistent-guid", new_name="X" )

    def test_set_scene_properties(self, tmp_path):
        scene_path = str( tmp_path / "test.scene" )
        create_scene( "test", output_path=scene_path, fixed_update_freq=50 )

        props = set_scene_properties( scene_path, fixed_update_freq=64, timescale=0.5 )
        assert props["FixedUpdateFrequency"] == 64
        assert props["TimeScale"] == 0.5

        # Verify persistence
        data = load_scene( scene_path )
        assert data["SceneProperties"]["FixedUpdateFrequency"] == 64
        assert data["SceneProperties"]["TimeScale"] == 0.5


class TestCodegenRazor:
    """Tests for Razor UI generation and RPC support."""

    def test_generate_razor_basic(self):
        result = generate_razor( "HudPanel" )
        assert result["filename"] == "HudPanel.razor"
        assert result["scss_filename"] == "HudPanel.razor.scss"
        assert "@using Sandbox;" in result["content"]
        assert "@using Sandbox.UI;" in result["content"]
        assert "@inherits PanelComponent" in result["content"]
        assert 'class="hud-panel"' in result["content"]

    def test_generate_razor_with_properties(self):
        result = generate_razor( "ScoreBoard", properties=[
            {"name": "Score", "type": "int", "default": "0"},
            {"name": "PlayerName", "type": "string"},
        ])
        assert "[Property] public int Score" in result["content"]
        assert "[Property] public string PlayerName" in result["content"]
        assert "BuildHash" in result["content"]
        assert "System.HashCode.Combine" in result["content"]

    def test_generate_razor_scss(self):
        result = generate_razor( "MyWidget", root_class="custom-widget" )
        assert ".custom-widget" in result["scss_content"]
        assert "flex-direction: column;" in result["scss_content"]

    def test_generate_component_with_rpc(self):
        result = generate_component(
            "NetPlayer",
            rpc_methods=[
                {"name": "FireBullet", "type": "Broadcast"},
                {"name": "TakeDamage", "type": "Host"},
            ],
        )
        content = result["content"]
        assert "public partial class NetPlayer" in content
        assert "[Rpc.Broadcast]" in content
        assert "[Rpc.Host]" in content
        assert "public void FireBullet()" in content
        assert "public void TakeDamage()" in content

    def test_generate_component_net_collections(self):
        result = generate_component(
            "Inventory",
            is_networked=True,
            properties=[
                {"name": "Items", "type": "NetList<string>"},
                {"name": "Score", "type": "int", "default": "0"},
            ],
        )
        content = result["content"]
        # NetList should NOT have [Sync]
        # Score should have [Sync]
        lines = content.split( "\r\n" )
        for i, line in enumerate( lines ):
            if "NetList<string>" in line:
                # Check previous lines don't have [Sync]
                prev = lines[max(0, i-1)].strip() if i > 0 else ""
                prev2 = lines[max(0, i-2)].strip() if i > 1 else ""
                assert "[Sync]" not in prev, "NetList should not have [Sync]"
                assert "[Sync]" not in prev2, "NetList should not have [Sync]"


class TestMaterial:
    """Tests for material creation and parsing."""

    def test_create_material_default(self, tmp_path):
        path = str( tmp_path / "test.vmat" )
        result = create_material( "test", output_path=path )
        assert result["name"] == "test"
        assert result["shader"] == "shaders/complex.vfx"
        assert os.path.isfile( path )
        with open( path, "r", encoding="utf-8" ) as f:
            content = f.read()
        assert 'shader "shaders/complex.vfx"' in content
        assert "Layer0" in content

    def test_create_material_with_textures(self, tmp_path):
        path = str( tmp_path / "brick.vmat" )
        result = create_material(
            "brick",
            color_texture="textures/brick_color.tga",
            normal_texture="textures/brick_normal.tga",
            metalness=0.2,
            output_path=path,
        )
        with open( path, "r", encoding="utf-8" ) as f:
            content = f.read()
        assert 'TextureColor "textures/brick_color.tga"' in content
        assert 'TextureNormal "textures/brick_normal.tga"' in content
        assert 'g_flMetalness "0.2"' in content

    def test_parse_material(self, tmp_path):
        path = str( tmp_path / "mat.vmat" )
        create_material( "mat", color_texture="tex/color.tga", metalness=0.8, output_path=path )
        parsed = parse_material( path )
        assert parsed["name"] == "mat"
        assert parsed["shader"] == "shaders/complex.vfx"
        assert "TextureColor" in parsed["properties"]
        assert parsed["properties"]["g_flMetalness"] == "0.8"

    def test_list_materials(self, tmp_path):
        create_project( "test", output_dir=str( tmp_path ) )
        mat_dir = tmp_path / "Assets" / "materials"
        mat_dir.mkdir( parents=True, exist_ok=True )
        create_material( "floor", output_path=str( mat_dir / "floor.vmat" ) )
        create_material( "wall", output_path=str( mat_dir / "wall.vmat" ) )
        materials = list_materials( str( tmp_path ) )
        names = [m["name"] for m in materials]
        assert "floor" in names
        assert "wall" in names

    def test_vmat_format(self, tmp_path):
        """Verify .vmat is text format, not JSON."""
        path = str( tmp_path / "test.vmat" )
        create_material( "test", output_path=path )
        with open( path, "r", encoding="utf-8" ) as f:
            content = f.read()
        # Should NOT be valid JSON
        try:
            json.loads( content )
            assert False, "vmat should not be JSON"
        except json.JSONDecodeError:
            pass  # Expected


class TestSound:
    """Tests for sound event creation and parsing."""

    def test_create_sound_event(self, tmp_path):
        path = str( tmp_path / "bang.sound" )
        result = create_sound_event( "bang", sounds=["sounds/bang.vsnd"], output_path=path )
        assert result["name"] == "bang"
        assert os.path.isfile( path )
        with open( path, "r", encoding="utf-8" ) as f:
            data = json.load( f )
        assert data["Sounds"] == ["sounds/bang.vsnd"]
        assert data["__version"] == 1

    def test_create_sound_multiple(self, tmp_path):
        result = create_sound_event(
            "footstep",
            sounds=["sounds/step1.vsnd", "sounds/step2.vsnd", "sounds/step3.vsnd"],
            volume="0.5",
        )
        assert len( result["data"]["Sounds"] ) == 3
        assert result["data"]["Volume"] == "0.5"

    def test_parse_sound_event(self, tmp_path):
        path = str( tmp_path / "test.sound" )
        create_sound_event( "test", sounds=["sounds/a.vsnd"], volume="0.7", output_path=path )
        parsed = parse_sound_event( path )
        assert parsed["name"] == "test"
        assert parsed["volume"] == "0.7"
        assert "sounds/a.vsnd" in parsed["sounds"]

    def test_sound_defaults(self):
        result = create_sound_event( "default" )
        data = result["data"]
        assert data["Volume"] == "1"
        assert data["Pitch"] == "1"
        assert data["Decibels"] == 70
        assert data["Occlusion"] is True
        assert data["UI"] is False


class TestLocalization:
    """Tests for translation file management."""

    def test_create_translation_file(self, tmp_path):
        path = str( tmp_path / "en.json" )
        result = create_translation_file(
            lang="en",
            initial_keys={"game.title": "My Game"},
            output_path=path,
        )
        assert result["lang"] == "en"
        assert result["key_count"] == 1
        assert os.path.isfile( path )

    def test_set_and_get_key(self, tmp_path):
        path = str( tmp_path / "en.json" )
        create_translation_file( lang="en", output_path=path )
        set_key( path, "ui.button.start", "Start Game" )
        value = get_key( path, "ui.button.start" )
        assert value == "Start Game"

    def test_list_keys(self, tmp_path):
        path = str( tmp_path / "en.json" )
        create_translation_file(
            lang="en",
            initial_keys={"b.key": "B", "a.key": "A", "c.key": "C"},
            output_path=path,
        )
        keys = list_keys( path )
        assert keys == ["a.key", "b.key", "c.key"]  # sorted

    def test_remove_key(self, tmp_path):
        path = str( tmp_path / "en.json" )
        create_translation_file(
            lang="en",
            initial_keys={"game.title": "Title", "game.desc": "Desc"},
            output_path=path,
        )
        removed = remove_key( path, "game.title" )
        assert removed is True
        assert get_key( path, "game.title" ) is None
        assert get_key( path, "game.desc" ) == "Desc"

    def test_remove_key_not_found(self, tmp_path):
        path = str( tmp_path / "en.json" )
        create_translation_file( lang="en", output_path=path )
        removed = remove_key( path, "nonexistent" )
        assert removed is False


class TestSceneCloneAndGet:
    """Tests for clone_object, get_object, and set_navmesh_properties."""

    def test_clone_object(self, tmp_path):
        scene_path = str( tmp_path / "test.scene" )
        create_scene( "test", output_path=scene_path, include_defaults=False )
        guid = add_object( scene_path, "Original", position="10,20,30", components=["model", "rigidbody"] )

        result = clone_object( scene_path, guid=guid, new_name="Copy", position="100,0,0" )
        assert result["name"] == "Copy"
        assert result["original_name"] == "Original"
        assert result["guid"] != result["original_guid"]

        objects = list_objects( scene_path )
        names = [o["name"] for o in objects]
        assert "Original" in names
        assert "Copy" in names
        assert len( objects ) == 2

    def test_clone_object_default_name(self, tmp_path):
        scene_path = str( tmp_path / "test.scene" )
        create_scene( "test", output_path=scene_path, include_defaults=False )
        add_object( scene_path, "Box", position="0,0,0" )

        result = clone_object( scene_path, name="Box" )
        assert result["name"] == "Box (Clone)"

    def test_clone_object_new_guids(self, tmp_path):
        scene_path = str( tmp_path / "test.scene" )
        create_scene( "test", output_path=scene_path, include_defaults=False )
        guid = add_object( scene_path, "Obj", components=["model", "box_collider"] )

        clone_result = clone_object( scene_path, guid=guid )
        data = load_scene( scene_path )

        # Collect all GUIDs - none should be duplicated
        all_guids = set()
        for obj in data["GameObjects"]:
            all_guids.add( obj["__guid"] )
            for comp in obj.get( "Components", [] ):
                guid_val = comp.get( "__guid", "" )
                assert guid_val not in all_guids or guid_val == "", f"Duplicate GUID: {guid_val}"
                all_guids.add( guid_val )

    def test_get_object(self, tmp_path):
        scene_path = str( tmp_path / "test.scene" )
        create_scene( "test", output_path=scene_path, include_defaults=False )
        guid = add_object( scene_path, "TestObj", position="1,2,3", components=["model", "rigidbody"] )

        result = get_object( scene_path, guid=guid )
        assert result["name"] == "TestObj"
        assert result["guid"] == guid
        assert result["position"] == "1,2,3"
        assert len( result["components"] ) == 2
        types = [c["type"] for c in result["components"]]
        assert "Sandbox.ModelRenderer" in types
        assert "Sandbox.Rigidbody" in types

    def test_get_object_not_found(self, tmp_path):
        scene_path = str( tmp_path / "test.scene" )
        create_scene( "test", output_path=scene_path, include_defaults=False )

        with pytest.raises( ValueError, match="not found" ):
            get_object( scene_path, guid="nonexistent" )

    def test_set_navmesh_properties(self, tmp_path):
        scene_path = str( tmp_path / "test.scene" )
        create_scene( "test", output_path=scene_path )

        result = set_navmesh_properties(
            scene_path,
            navmesh_enabled=True,
            navmesh_agent_height=72,
            navmesh_agent_radius=16,
        )
        assert result["Enabled"] is True
        assert result["AgentHeight"] == 72
        assert result["AgentRadius"] == 16

        data = load_scene( scene_path )
        assert data["SceneProperties"]["NavMesh"]["Enabled"] is True


class TestProjectPackages:
    """Tests for add_package and remove_package."""

    def test_add_package(self, tmp_path):
        info = create_project( "test", output_dir=str( tmp_path ) )
        sbproj = info["sbproj"]
        result = add_package( sbproj, "facepunch.libsdf" )
        assert "facepunch.libsdf" in result["package_references"]

    def test_add_duplicate_package(self, tmp_path):
        info = create_project( "test", output_dir=str( tmp_path ) )
        sbproj = info["sbproj"]
        add_package( sbproj, "facepunch.libsdf" )
        with pytest.raises( ValueError, match="already referenced" ):
            add_package( sbproj, "facepunch.libsdf" )

    def test_remove_package(self, tmp_path):
        info = create_project( "test", output_dir=str( tmp_path ) )
        sbproj = info["sbproj"]
        add_package( sbproj, "facepunch.libsdf" )
        add_package( sbproj, "local.mylib" )
        result = remove_package( sbproj, "facepunch.libsdf" )
        assert "facepunch.libsdf" not in result["package_references"]
        assert "local.mylib" in result["package_references"]

    def test_remove_missing_package(self, tmp_path):
        info = create_project( "test", output_dir=str( tmp_path ) )
        sbproj = info["sbproj"]
        with pytest.raises( ValueError, match="not found" ):
            remove_package( sbproj, "nonexistent.pkg" )


class TestPrefabComponents:
    """Tests for prefab add-component and remove-component."""

    def test_prefab_add_component(self, tmp_path):
        path = str( tmp_path / "test.prefab" )
        create_prefab( "TestPrefab", output_path=path, components=["model"] )
        data = load_prefab( path )
        assert len( data["RootObject"]["Components"] ) == 1
        root = data["RootObject"]
        comp = copy.deepcopy( COMPONENT_PRESETS["rigidbody"] )
        comp["__guid"] = str( uuid.uuid4() )
        root["Components"].append( comp )
        save_prefab( path, data )
        data2 = load_prefab( path )
        assert len( data2["RootObject"]["Components"] ) == 2
        types = [c["__type"] for c in data2["RootObject"]["Components"]]
        assert "Sandbox.Rigidbody" in types

    def test_prefab_remove_component(self, tmp_path):
        path = str( tmp_path / "test.prefab" )
        create_prefab( "TestPrefab", output_path=path, components=["model", "rigidbody"] )
        data = load_prefab( path )
        assert len( data["RootObject"]["Components"] ) == 2
        root = data["RootObject"]
        root["Components"] = [c for c in root["Components"] if c["__type"] != "Sandbox.Rigidbody"]
        save_prefab( path, data )
        data2 = load_prefab( path )
        assert len( data2["RootObject"]["Components"] ) == 1
        assert data2["RootObject"]["Components"][0]["__type"] == "Sandbox.ModelRenderer"


class TestCollisionRemoveLayer:
    """Test collision remove-layer success path."""

    def test_remove_custom_layer(self, tmp_path):
        path = str( tmp_path / "Collision.config" )
        save_collision_config( path, get_default_collision_config() )
        add_layer( path, "projectile", default="Collide" )
        add_rule( path, "projectile", "solid", result="Collide" )
        data = load_collision_config( path )
        assert "projectile" in data["Defaults"]
        removed = remove_layer( path, "projectile" )
        assert removed is True
        data2 = load_collision_config( path )
        assert "projectile" not in data2["Defaults"]
        for pair in data2["Pairs"]:
            assert pair["a"] != "projectile" and pair["b"] != "projectile"


class TestJointPresets:
    """Test joint component presets in scenes."""

    def test_add_object_with_joints(self, tmp_path):
        scene_path = str( tmp_path / "test.scene" )
        create_scene( "test", output_path=scene_path, include_defaults=False )
        add_object( scene_path, "Door", components=["model", "hinge_joint"] )
        objects = list_objects( scene_path )
        assert len( objects ) == 1
        types = objects[0]["component_types"]
        assert "Sandbox.ModelRenderer" in types
        assert "Sandbox.HingeJoint" in types


class TestMaterialUpdate:
    """Test material update functionality."""

    def test_update_metalness(self, tmp_path):
        path = str( tmp_path / "test.vmat" )
        create_material( "test", metalness=0.0, output_path=path )
        result = update_material( path, metalness=0.8 )
        assert result["properties"]["g_flMetalness"] == "0.8"

    def test_update_texture(self, tmp_path):
        path = str( tmp_path / "test.vmat" )
        create_material( "test", output_path=path )
        result = update_material( path, color_texture="textures/new_color.tga" )
        assert result["properties"]["TextureColor"] == "textures/new_color.tga"


class TestSoundUpdate:
    """Test sound event update functionality."""

    def test_update_volume(self, tmp_path):
        path = str( tmp_path / "test.sound" )
        create_sound_event( "test", volume="1", output_path=path )
        result = update_sound_event( path, volume="0.5" )
        assert result["volume"] == "0.5"

    def test_update_sounds_list(self, tmp_path):
        path = str( tmp_path / "test.sound" )
        create_sound_event( "test", sounds=["a.vsnd"], output_path=path )
        result = update_sound_event( path, sounds=["b.vsnd", "c.vsnd"] )
        assert result["sounds"] == ["b.vsnd", "c.vsnd"]


class TestSceneModifyComponent:
    """Tests for modify_component."""

    def test_modify_component_by_type(self, tmp_path):
        scene_path = str( tmp_path / "test.scene" )
        create_scene( "test", output_path=scene_path, include_defaults=False )
        guid = add_object( scene_path, "Obj", components=["rigidbody"] )

        result = modify_component(
            scene_path, guid,
            component_type="Sandbox.Rigidbody",
            properties={"Gravity": False, "LinearDamping": 5},
        )
        assert "Gravity" in result["updated_keys"]
        assert "LinearDamping" in result["updated_keys"]

        data = load_scene( scene_path )
        obj = find_object( data, guid=guid )
        rb = [c for c in obj["Components"] if c["__type"] == "Sandbox.Rigidbody"][0]
        assert rb["Gravity"] is False
        assert rb["LinearDamping"] == 5

    def test_modify_component_not_found(self, tmp_path):
        scene_path = str( tmp_path / "test.scene" )
        create_scene( "test", output_path=scene_path, include_defaults=False )
        guid = add_object( scene_path, "Obj" )

        with pytest.raises( ValueError, match="not found" ):
            modify_component( scene_path, guid, component_type="Sandbox.Rigidbody", properties={"Gravity": False} )


class TestCodegenClass:
    """Tests for generate_class."""

    def test_generate_static_class(self):
        result = generate_class( "GameUtils", is_static=True, properties=[
            {"name": "Version", "type": "string", "default": '"1.0"'},
        ])
        assert result["filename"] == "GameUtils.cs"
        assert "public static class GameUtils" in result["content"]
        assert "public static string Version" in result["content"]
        assert "\r\n" in result["content"]

    def test_generate_class_with_base(self):
        result = generate_class( "EnemyManager", base_class="BaseManager" )
        assert "public class EnemyManager : BaseManager" in result["content"]
        assert "using Sandbox;" in result["content"]

    def test_generate_class_method_with_multiline_body(self):
        """Method body containing newlines must be split into separate output lines.

        Regression test for a bug where the body was split on the literal
        two-character string ``\\n`` instead of an actual newline, collapsing
        every multi-line method body into a single line of malformed C#.
        """
        result = generate_class( "Counter", methods=[
            {
                "name": "Tick",
                "return_type": "void",
                "body": "var x = 1;\nvar y = 2;\nreturn;",
            }
        ])
        content = result["content"]
        assert "\t\tvar x = 1;" in content
        assert "\t\tvar y = 2;" in content
        assert "\t\treturn;" in content
        # The literal two-character sequence \n must NOT appear as a body
        # line - that would mean the buggy split was still in effect.
        assert "\t\tvar x = 1;\\nvar y = 2;" not in content


class TestLocalizationBulkSet:
    """Test bulk_set for localization."""

    def test_bulk_set(self, tmp_path):
        path = str( tmp_path / "en.json" )
        create_translation_file( lang="en", initial_keys={"existing": "value"}, output_path=path )
        result = bulk_set( path, {"game.title": "My Game", "game.desc": "A game", "ui.start": "Start"} )
        assert len( result ) == 4
        assert result["game.title"] == "My Game"
        assert result["existing"] == "value"
        keys = list_keys( path )
        assert "game.title" in keys
        assert "ui.start" in keys


# ============================================================================
# Refine batch: query, refs, bulk-modify, validate, panel-component
# ============================================================================


class TestSceneQuery:
    """Tests for scene.query_objects."""

    def _make_test_scene(self, tmp_path):
        scene_path = str( tmp_path / "q.scene" )
        create_scene( "q", output_path=scene_path, include_defaults=False )
        add_object( scene_path, "Tower1", position="100,0,0", tags="tower,placed", components=["model", "rigidbody"] )
        add_object( scene_path, "Tower2", position="200,0,0", tags="tower", components=["model"] )
        add_object( scene_path, "Enemy1", position="0,500,0", tags="enemy", components=["skinned_model_renderer", "rigidbody"] )
        add_object( scene_path, "Disabled", position="0,0,0", tags="" )
        # Disable the last one
        modify_object( scene_path, name_match="Disabled", enabled=False )
        return scene_path

    def test_query_by_component_preset(self, tmp_path):
        path = self._make_test_scene( tmp_path )
        result = query_objects( path, has_component="rigidbody" )
        names = sorted( r["name"] for r in result )
        assert names == ["Enemy1", "Tower1"]

    def test_query_by_component_full_type(self, tmp_path):
        path = self._make_test_scene( tmp_path )
        result = query_objects( path, has_component="Sandbox.SkinnedModelRenderer" )
        assert len( result ) == 1
        assert result[0]["name"] == "Enemy1"

    def test_query_by_tag(self, tmp_path):
        path = self._make_test_scene( tmp_path )
        result = query_objects( path, has_tag="tower" )
        names = sorted( r["name"] for r in result )
        assert names == ["Tower1", "Tower2"]

    def test_query_by_name_substring(self, tmp_path):
        path = self._make_test_scene( tmp_path )
        result = query_objects( path, name_match="Tower" )
        assert len( result ) == 2

    def test_query_by_name_regex(self, tmp_path):
        path = self._make_test_scene( tmp_path )
        result = query_objects( path, name_regex=r"^Tower\d$" )
        assert len( result ) == 2

    def test_query_by_bounds(self, tmp_path):
        path = self._make_test_scene( tmp_path )
        # Bounds that capture only the Towers (x in [50, 250])
        result = query_objects( path, in_bounds="50,-1,-1,250,1,1" )
        names = sorted( r["name"] for r in result )
        assert names == ["Tower1", "Tower2"]

    def test_query_by_enabled(self, tmp_path):
        path = self._make_test_scene( tmp_path )
        result = query_objects( path, enabled=False )
        assert len( result ) == 1
        assert result[0]["name"] == "Disabled"

    def test_query_combined_filters_and(self, tmp_path):
        path = self._make_test_scene( tmp_path )
        # tower tag AND has rigidbody = only Tower1
        result = query_objects( path, has_tag="tower", has_component="rigidbody" )
        assert len( result ) == 1
        assert result[0]["name"] == "Tower1"

    def test_query_no_matches(self, tmp_path):
        path = self._make_test_scene( tmp_path )
        result = query_objects( path, has_tag="nonexistent" )
        assert result == []


class TestSceneRefs:
    """Tests for scene.extract_asset_refs."""

    def test_refs_from_default_scene(self, tmp_path):
        scene_path = str( tmp_path / "default.scene" )
        create_scene( "default", output_path=scene_path, include_defaults=True )
        refs = extract_asset_refs( scene_path )

        # The default scene has a model, materials, a sky material, and a cubemap
        assert "models" in refs
        assert "materials" in refs
        assert "textures" in refs
        # Check specific known refs from the default scene
        assert any( "models/dev/plane.vmdl" in r for r in refs["models"] )
        assert any( "materials/skybox" in r for r in refs["materials"] )

    def test_refs_dedup_and_sort(self, tmp_path):
        scene_path = str( tmp_path / "dup.scene" )
        create_scene( "dup", output_path=scene_path, include_defaults=False )
        # Add two objects that share the same model
        add_object( scene_path, "A", components=["model"] )
        add_object( scene_path, "B", components=["model"] )
        refs = extract_asset_refs( scene_path )
        # The model "models/dev/box.vmdl" appears in both objects but should be deduped
        assert refs["models"].count( "models/dev/box.vmdl" ) == 1

    def test_refs_empty_scene(self, tmp_path):
        scene_path = str( tmp_path / "empty.scene" )
        create_scene( "empty", output_path=scene_path, include_defaults=False )
        refs = extract_asset_refs( scene_path )
        assert refs == {}


class TestSceneBulkModify:
    """Tests for scene.bulk_modify_objects."""

    def test_bulk_modify_position(self, tmp_path):
        scene_path = str( tmp_path / "bulk.scene" )
        create_scene( "bulk", output_path=scene_path, include_defaults=False )
        add_object( scene_path, "T1", position="0,0,0", tags="tower" )
        add_object( scene_path, "T2", position="0,0,0", tags="tower" )
        add_object( scene_path, "E1", position="0,0,0", tags="enemy" )

        result = bulk_modify_objects( scene_path, has_tag="tower", new_position="100,200,300" )
        assert result["modified_count"] == 2
        assert result["modified_fields"] == ["Position"]

        towers = query_objects( scene_path, has_tag="tower" )
        for t in towers:
            assert t["position"] == "100,200,300"
        # Enemy untouched
        enemies = query_objects( scene_path, has_tag="enemy" )
        assert enemies[0]["position"] == "0,0,0"

    def test_bulk_modify_multiple_fields(self, tmp_path):
        scene_path = str( tmp_path / "bulk2.scene" )
        create_scene( "bulk2", output_path=scene_path, include_defaults=False )
        guid = add_object( scene_path, "X", position="0,0,0", tags="a" )

        result = bulk_modify_objects(
            scene_path,
            has_tag="a",
            new_scale="2,2,2",
            new_tags="modified",
            new_enabled=False,
        )
        assert result["modified_count"] == 1
        assert set( result["modified_fields"] ) == {"Scale", "Tags", "Enabled"}

        obj = get_object( scene_path, guid=guid )
        assert obj["scale"] == "2,2,2"
        assert obj["tags"] == "modified"
        assert obj["enabled"] is False

    def test_bulk_modify_no_matches(self, tmp_path):
        scene_path = str( tmp_path / "none.scene" )
        create_scene( "none", output_path=scene_path, include_defaults=False )
        result = bulk_modify_objects( scene_path, has_tag="nope", new_position="0,0,0" )
        assert result["modified_count"] == 0
        assert result["modified_guids"] == []

    def test_bulk_modify_requires_update(self, tmp_path):
        scene_path = str( tmp_path / "req.scene" )
        create_scene( "req", output_path=scene_path, include_defaults=False )
        with pytest.raises( ValueError, match="at least one modification" ):
            bulk_modify_objects( scene_path, has_tag="x" )


class TestPrefabRefs:
    """Tests for prefab.extract_asset_refs."""

    def test_refs_from_prefab(self, tmp_path):
        prefab_path = str( tmp_path / "p.prefab" )
        create_prefab( "p", output_path=prefab_path, components=["model", "rigidbody", "model_collider"] )
        refs = prefab_extract_asset_refs( prefab_path )
        assert "models" in refs
        assert "models/dev/box.vmdl" in refs["models"]


class TestPrefabModifyComponent:
    """Tests for prefab.modify_component."""

    def test_modify_by_type(self, tmp_path):
        prefab_path = str( tmp_path / "rb.prefab" )
        create_prefab( "rb", output_path=prefab_path, components=["model", "rigidbody"] )
        result = prefab_modify_component(
            prefab_path,
            component_type="Sandbox.Rigidbody",
            properties={"Gravity": False, "MassOverride": 100},
        )
        assert result["component_type"] == "Sandbox.Rigidbody"
        assert "Gravity" in result["updated_keys"]
        assert "MassOverride" in result["updated_keys"]

        data = load_prefab( prefab_path )
        rb = next( c for c in data["RootObject"]["Components"] if c["__type"] == "Sandbox.Rigidbody" )
        assert rb["Gravity"] is False
        assert rb["MassOverride"] == 100

    def test_modify_by_guid(self, tmp_path):
        prefab_path = str( tmp_path / "guid.prefab" )
        create_prefab( "guid", output_path=prefab_path, components=["model"] )
        data = load_prefab( prefab_path )
        comp_guid = data["RootObject"]["Components"][0]["__guid"]

        result = prefab_modify_component(
            prefab_path,
            component_guid=comp_guid,
            properties={"Tint": "1,0,0,1"},
        )
        assert result["component_guid"] == comp_guid

        data2 = load_prefab( prefab_path )
        assert data2["RootObject"]["Components"][0]["Tint"] == "1,0,0,1"

    def test_modify_not_found(self, tmp_path):
        prefab_path = str( tmp_path / "nf.prefab" )
        create_prefab( "nf", output_path=prefab_path, components=["model"] )
        with pytest.raises( ValueError, match="not found" ):
            prefab_modify_component( prefab_path, component_type="Sandbox.Missing", properties={"x": 1} )

    def test_modify_requires_identifier(self, tmp_path):
        prefab_path = str( tmp_path / "id.prefab" )
        create_prefab( "id", output_path=prefab_path, components=["model"] )
        with pytest.raises( ValueError, match="component_guid or component_type" ):
            prefab_modify_component( prefab_path, properties={"x": 1} )

    def test_modify_requires_properties(self, tmp_path):
        prefab_path = str( tmp_path / "noprops.prefab" )
        create_prefab( "noprops", output_path=prefab_path, components=["model"] )
        with pytest.raises( ValueError, match="No properties" ):
            prefab_modify_component( prefab_path, component_type="Sandbox.ModelRenderer" )


class TestAssetRefGraph:
    """Tests for export.find_asset_refs and find_unused_assets."""

    def _make_project(self, tmp_path):
        """Build a minimal project with a scene + prefab + a stray unused model."""
        info = create_project( "RefTest", output_dir=str( tmp_path / "RefTest" ) )
        proj_dir = os.path.dirname( info["sbproj"] )

        # Custom scene with a known asset reference
        scene_path = os.path.join( proj_dir, "Assets", "scenes", "level.scene" )
        os.makedirs( os.path.dirname( scene_path ), exist_ok=True )
        create_scene( "level", output_path=scene_path, include_defaults=False )
        add_object( scene_path, "Box", components=[
            {"__type": "Sandbox.ModelRenderer", "Model": "models/myteam/widget.vmdl"},
        ] )

        # Prefab that references the same model
        prefab_path = os.path.join( proj_dir, "Assets", "prefabs", "widget.prefab" )
        os.makedirs( os.path.dirname( prefab_path ), exist_ok=True )
        create_prefab( "widget", output_path=prefab_path, components=[
            {"__type": "Sandbox.ModelRenderer", "Model": "models/myteam/widget.vmdl"},
        ] )

        # Create the actual asset files (so list_assets sees them)
        widget_vmdl = os.path.join( proj_dir, "Assets", "models", "myteam", "widget.vmdl" )
        os.makedirs( os.path.dirname( widget_vmdl ), exist_ok=True )
        with open( widget_vmdl, "w", encoding="utf-8" ) as f:
            f.write( "<MODEL_PLACEHOLDER>" )

        # Unused asset
        unused_vmdl = os.path.join( proj_dir, "Assets", "models", "myteam", "unused.vmdl" )
        with open( unused_vmdl, "w", encoding="utf-8" ) as f:
            f.write( "<UNUSED_MODEL>" )

        # Unused material
        unused_mat = os.path.join( proj_dir, "Assets", "materials", "unused.vmat" )
        os.makedirs( os.path.dirname( unused_mat ), exist_ok=True )
        with open( unused_mat, "w", encoding="utf-8" ) as f:
            f.write( "Layer0 { shader \"complex.shader\" }" )

        return proj_dir

    def test_find_asset_refs_finds_both(self, tmp_path):
        proj_dir = self._make_project( tmp_path )
        refs = find_asset_refs( proj_dir, "models/myteam/widget.vmdl" )
        assert len( refs ) == 2
        files = sorted( r["file"] for r in refs )
        assert any( "level.scene" in f for f in files )
        assert any( "widget.prefab" in f for f in files )
        for r in refs:
            assert r["category"] == "models"

    def test_find_asset_refs_case_insensitive(self, tmp_path):
        proj_dir = self._make_project( tmp_path )
        refs = find_asset_refs( proj_dir, "MODELS/MyTeam/Widget.VMDL" )
        assert len( refs ) == 2

    def test_find_asset_refs_none(self, tmp_path):
        proj_dir = self._make_project( tmp_path )
        refs = find_asset_refs( proj_dir, "models/nonexistent/foo.vmdl" )
        assert refs == []

    def test_find_unused_assets(self, tmp_path):
        proj_dir = self._make_project( tmp_path )
        unused = find_unused_assets( proj_dir )
        unused_paths = sorted( u["path"].replace( "\\", "/" ) for u in unused )
        # Both unused.vmdl and unused.vmat should be flagged
        assert any( "unused.vmdl" in p for p in unused_paths )
        assert any( "unused.vmat" in p for p in unused_paths )
        # widget.vmdl is referenced -> should NOT be flagged
        assert not any( "widget.vmdl" in p for p in unused_paths )

    def test_find_unused_assets_filtered_by_type(self, tmp_path):
        proj_dir = self._make_project( tmp_path )
        unused = find_unused_assets( proj_dir, asset_types=["material"] )
        types = {u["type"] for u in unused}
        # Only materials should appear
        assert types <= {"material"}
        assert any( "unused.vmat" in u["path"].replace( "\\", "/" ) for u in unused )


class TestProjectValidate:
    """Tests for validate.validate_project."""

    def test_validate_clean_project(self, tmp_path):
        info = create_project( "Clean", output_dir=str( tmp_path / "Clean" ) )
        proj_dir = os.path.dirname( info["sbproj"] )
        # The default scene only references engine built-ins - should be clean
        result = validate_project( proj_dir )
        assert result["broken_refs"] == []
        assert result["duplicate_guids"] == []

    def test_validate_detects_broken_refs(self, tmp_path):
        info = create_project( "Broken", output_dir=str( tmp_path / "Broken" ) )
        proj_dir = os.path.dirname( info["sbproj"] )

        scene_path = os.path.join( proj_dir, "Assets", "scenes", "broken.scene" )
        create_scene( "broken", output_path=scene_path, include_defaults=False )
        add_object( scene_path, "Bad", components=[
            {"__type": "Sandbox.ModelRenderer", "Model": "models/missing/whoops.vmdl"},
        ] )

        result = validate_project( proj_dir, check_inputs=False )
        broken_refs = [b["ref"] for b in result["broken_refs"]]
        assert any( "missing/whoops" in r for r in broken_refs )
        assert result["ok"] is False
        assert result["issue_count"] >= 1

    def test_validate_detects_duplicate_guids(self, tmp_path):
        info = create_project( "Dups", output_dir=str( tmp_path / "Dups" ) )
        proj_dir = os.path.dirname( info["sbproj"] )

        scene_path = os.path.join( proj_dir, "Assets", "scenes", "dup.scene" )
        create_scene( "dup", output_path=scene_path, include_defaults=False )
        # Forcefully inject a duplicate GUID
        data = load_scene( scene_path )
        same_guid = "11111111-1111-1111-1111-111111111111"
        data["GameObjects"] = [
            {"__guid": same_guid, "Name": "A", "Components": [], "Children": []},
            {"__guid": same_guid, "Name": "B", "Components": [], "Children": []},
        ]
        save_scene( scene_path, data )

        result = validate_project( proj_dir, check_refs=False, check_inputs=False )
        assert any( g["guid"] == same_guid for g in result["duplicate_guids"] )

    def test_validate_can_disable_checks(self, tmp_path):
        info = create_project( "Disabled", output_dir=str( tmp_path / "Disabled" ) )
        proj_dir = os.path.dirname( info["sbproj"] )
        result = validate_project( proj_dir, check_refs=False, check_guids=False, check_inputs=False )
        assert result["broken_refs"] == []
        assert result["duplicate_guids"] == []
        assert result["invalid_inputs"] == []


class TestCodegenPanelComponent:
    """Tests for codegen.generate_panel_component."""

    def test_panel_component_basic(self):
        result = generate_panel_component( "HudPanel" )
        assert result["filename"] == "HudPanel.razor"
        assert result["scss_filename"] == "HudPanel.razor.scss"
        assert "@inherits PanelComponent" in result["content"]
        assert "scene_snippet" in result
        # The snippet must be valid JSON describing one GameObject
        snippet = json.loads( result["scene_snippet"] )
        assert snippet["Name"] == "HudPanel"

    def test_panel_component_includes_screen_panel(self):
        result = generate_panel_component( "Crosshair" )
        snippet = json.loads( result["scene_snippet"] )
        types = [c["__type"] for c in snippet["Components"]]
        assert "Sandbox.ScreenPanel" in types
        assert "Crosshair" in types  # The PanelComponent type
        assert len( snippet["Components"] ) == 2

    def test_panel_component_with_namespace(self):
        result = generate_panel_component( "Bar", namespace="MyGame.UI" )
        snippet = json.loads( result["scene_snippet"] )
        types = [c["__type"] for c in snippet["Components"]]
        assert "MyGame.UI.Bar" in types

    def test_panel_component_with_properties(self):
        result = generate_panel_component(
            "Score",
            properties=[{"name": "Points", "type": "int", "default": "0"}],
        )
        assert "[Property] public int Points" in result["content"]
        assert "BuildHash()" in result["content"]

    def test_panel_component_unique_guids(self):
        result = generate_panel_component( "Foo" )
        guids = {result["screen_panel_guid"], result["panel_component_guid"], result["object_guid"]}
        assert len( guids ) == 3


# ============================================================================
# Refine batch 2: diff, rename/move, instantiate-prefab
# ============================================================================


class TestSceneDiff:
    """Tests for scene.diff_scenes."""

    def test_identical_scenes(self, tmp_path):
        a = str( tmp_path / "a.scene" )
        b = str( tmp_path / "b.scene" )
        create_scene( "x", output_path=a, include_defaults=False )
        # Same scene contents -> identical (GUIDs differ but we compare by Name)
        create_scene( "x", output_path=b, include_defaults=False )
        result = diff_scenes( a, b )
        assert result["identical"] is True
        assert result["added"] == []
        assert result["removed"] == []
        assert result["modified"] == []

    def test_added_and_removed(self, tmp_path):
        a = str( tmp_path / "a.scene" )
        b = str( tmp_path / "b.scene" )
        create_scene( "x", output_path=a, include_defaults=False )
        create_scene( "x", output_path=b, include_defaults=False )
        add_object( a, "OnlyInA" )
        add_object( a, "Shared" )
        add_object( b, "Shared" )
        add_object( b, "OnlyInB" )

        result = diff_scenes( a, b )
        assert result["added"] == ["OnlyInB"]
        assert result["removed"] == ["OnlyInA"]
        assert result["modified"] == []
        assert result["identical"] is False

    def test_modified_position(self, tmp_path):
        a = str( tmp_path / "a.scene" )
        b = str( tmp_path / "b.scene" )
        create_scene( "x", output_path=a, include_defaults=False )
        create_scene( "x", output_path=b, include_defaults=False )
        add_object( a, "Box", position="0,0,0" )
        add_object( b, "Box", position="100,200,300" )

        result = diff_scenes( a, b )
        assert len( result["modified"] ) == 1
        m = result["modified"][0]
        assert m["name"] == "Box"
        assert "position" in m["changes"]
        assert m["changes"]["position"]["from"] == "0,0,0"
        assert m["changes"]["position"]["to"] == "100,200,300"

    def test_modified_components(self, tmp_path):
        a = str( tmp_path / "a.scene" )
        b = str( tmp_path / "b.scene" )
        create_scene( "x", output_path=a, include_defaults=False )
        create_scene( "x", output_path=b, include_defaults=False )
        add_object( a, "X", components=["model"] )
        add_object( b, "X", components=["model", "rigidbody"] )

        result = diff_scenes( a, b )
        assert len( result["modified"] ) == 1
        m = result["modified"][0]
        assert "components_added" in m["changes"]
        assert "Sandbox.Rigidbody" in m["changes"]["components_added"]

    def test_scene_property_changes(self, tmp_path):
        a = str( tmp_path / "a.scene" )
        b = str( tmp_path / "b.scene" )
        create_scene( "x", output_path=a, include_defaults=False )
        create_scene( "x", output_path=b, include_defaults=False )
        set_scene_properties( b, fixed_update_freq=120 )

        result = diff_scenes( a, b )
        assert "FixedUpdateFrequency" in result["scene_property_changes"]


class TestPrefabDiff:
    """Tests for prefab.diff_prefabs."""

    def test_identical_prefabs(self, tmp_path):
        a = str( tmp_path / "a.prefab" )
        b = str( tmp_path / "b.prefab" )
        create_prefab( "P", output_path=a, components=["model", "rigidbody"] )
        create_prefab( "P", output_path=b, components=["model", "rigidbody"] )
        result = diff_prefabs( a, b )
        assert result["identical"] is True

    def test_root_changes(self, tmp_path):
        a = str( tmp_path / "a.prefab" )
        b = str( tmp_path / "b.prefab" )
        create_prefab( "P", output_path=a, components=["model"] )
        create_prefab( "P", output_path=b, components=["model", "rigidbody"] )
        result = diff_prefabs( a, b )
        assert result["identical"] is False
        assert result["root_changes"] is not None
        assert "components_added" in result["root_changes"]["changes"]


class TestSceneInstantiatePrefab:
    """Tests for scene.instantiate_prefab."""

    def test_instantiate_default_name(self, tmp_path):
        scene_path = str( tmp_path / "level.scene" )
        prefab_path = str( tmp_path / "Bullet.prefab" )
        create_scene( "level", output_path=scene_path, include_defaults=False )
        create_prefab( "Bullet", output_path=prefab_path, components=["model"] )

        guid = instantiate_prefab( scene_path, prefab_path, position="50,0,0" )
        obj = get_object( scene_path, guid=guid )
        assert obj["name"] == "Bullet"
        assert obj["position"] == "50,0,0"

    def test_instantiate_with_override_name(self, tmp_path):
        scene_path = str( tmp_path / "level.scene" )
        prefab_path = str( tmp_path / "Tower.prefab" )
        create_scene( "level", output_path=scene_path, include_defaults=False )
        create_prefab( "Tower", output_path=prefab_path, components=["model"] )

        guid = instantiate_prefab( scene_path, prefab_path, name="Tower_Spawn1" )
        obj = get_object( scene_path, guid=guid )
        assert obj["name"] == "Tower_Spawn1"

    def test_instantiate_writes_prefab_source(self, tmp_path):
        scene_path = str( tmp_path / "level.scene" )
        prefab_path = str( tmp_path / "P.prefab" )
        create_scene( "level", output_path=scene_path, include_defaults=False )
        create_prefab( "P", output_path=prefab_path, components=["model"] )

        instantiate_prefab( scene_path, prefab_path )
        data = load_scene( scene_path )
        # PrefabSource should be present on the new GameObject
        new_obj = data["GameObjects"][0]
        assert "PrefabSource" in new_obj
        assert "P.prefab" in new_obj["PrefabSource"]

    def test_instantiate_into_parent(self, tmp_path):
        scene_path = str( tmp_path / "level.scene" )
        prefab_path = str( tmp_path / "Child.prefab" )
        create_scene( "level", output_path=scene_path, include_defaults=False )
        create_prefab( "Child", output_path=prefab_path, components=["model"] )

        parent_guid = add_object( scene_path, "Parent" )
        child_guid = instantiate_prefab( scene_path, prefab_path, parent_guid=parent_guid )

        data = load_scene( scene_path )
        parent_obj = next( o for o in data["GameObjects"] if o["__guid"] == parent_guid )
        assert any( c["__guid"] == child_guid for c in parent_obj.get( "Children", [] ) )

    def test_instantiate_invalid_parent(self, tmp_path):
        scene_path = str( tmp_path / "level.scene" )
        prefab_path = str( tmp_path / "P.prefab" )
        create_scene( "level", output_path=scene_path, include_defaults=False )
        create_prefab( "P", output_path=prefab_path, components=["model"] )

        with pytest.raises( ValueError, match="Parent" ):
            instantiate_prefab( scene_path, prefab_path, parent_guid="bogus-guid" )


class TestAssetRenameMove:
    """Tests for export.rename_asset and export.move_asset."""

    def _make_project_with_widget(self, tmp_path):
        """Build a project with a widget.vmdl + a scene + a prefab that reference it."""
        info = create_project( "Refactor", output_dir=str( tmp_path / "Refactor" ) )
        proj_dir = os.path.dirname( info["sbproj"] )

        # Asset on disk
        widget = os.path.join( proj_dir, "Assets", "models", "team", "widget.vmdl" )
        os.makedirs( os.path.dirname( widget ), exist_ok=True )
        with open( widget, "w", encoding="utf-8" ) as f:
            f.write( "<MODEL>" )

        # Scene referencing it
        scene_path = os.path.join( proj_dir, "Assets", "scenes", "level.scene" )
        create_scene( "level", output_path=scene_path, include_defaults=False )
        add_object( scene_path, "Box", components=[
            {"__type": "Sandbox.ModelRenderer", "Model": "models/team/widget.vmdl"},
        ] )

        # Prefab referencing the same model
        prefab_path = os.path.join( proj_dir, "Assets", "prefabs", "boxer.prefab" )
        create_prefab( "boxer", output_path=prefab_path, components=[
            {"__type": "Sandbox.ModelRenderer", "Model": "models/team/widget.vmdl"},
        ] )

        return proj_dir, scene_path, prefab_path

    def test_rename_updates_scene_and_prefab(self, tmp_path):
        proj_dir, scene_path, prefab_path = self._make_project_with_widget( tmp_path )

        result = rename_asset( proj_dir, "models/team/widget.vmdl", "gizmo.vmdl" )

        assert result["new_path"] == "models/team/gizmo.vmdl"
        assert result["file_renamed"] is True
        # Both the scene and prefab should appear in references_updated
        files = sorted( r["file"] for r in result["references_updated"] )
        assert any( "level.scene" in f for f in files )
        assert any( "boxer.prefab" in f for f in files )

        # The new file exists, the old one doesn't
        assert os.path.isfile( os.path.join( proj_dir, "Assets", "models", "team", "gizmo.vmdl" ) )
        assert not os.path.isfile( os.path.join( proj_dir, "Assets", "models", "team", "widget.vmdl" ) )

        # Refs in the scene/prefab are rewritten
        s_refs = extract_asset_refs( scene_path )
        assert "models/team/gizmo.vmdl" in s_refs.get( "models", [] )
        p_refs = prefab_extract_asset_refs( prefab_path )
        assert "models/team/gizmo.vmdl" in p_refs.get( "models", [] )

    def test_rename_preserves_extension(self, tmp_path):
        proj_dir, _, _ = self._make_project_with_widget( tmp_path )
        # Pass new name without extension; existing .vmdl should be preserved
        result = rename_asset( proj_dir, "models/team/widget.vmdl", "gizmo" )
        assert result["new_path"] == "models/team/gizmo.vmdl"

    def test_rename_dry_run(self, tmp_path):
        proj_dir, _, _ = self._make_project_with_widget( tmp_path )
        result = rename_asset( proj_dir, "models/team/widget.vmdl", "gizmo.vmdl", dry_run=True )
        assert result["dry_run"] is True
        assert result["file_renamed"] is False
        assert result["references_would_update"] == 2
        # File should still exist at original path
        assert os.path.isfile( os.path.join( proj_dir, "Assets", "models", "team", "widget.vmdl" ) )

    def test_rename_target_exists(self, tmp_path):
        proj_dir, _, _ = self._make_project_with_widget( tmp_path )
        # Pre-create the target
        existing = os.path.join( proj_dir, "Assets", "models", "team", "gizmo.vmdl" )
        with open( existing, "w", encoding="utf-8" ) as f:
            f.write( "<other>" )

        with pytest.raises( FileExistsError ):
            rename_asset( proj_dir, "models/team/widget.vmdl", "gizmo.vmdl" )

    def test_rename_source_missing(self, tmp_path):
        proj_dir, _, _ = self._make_project_with_widget( tmp_path )
        with pytest.raises( FileNotFoundError ):
            rename_asset( proj_dir, "models/nope/missing.vmdl", "x.vmdl" )

    def test_move_to_new_directory(self, tmp_path):
        proj_dir, scene_path, _ = self._make_project_with_widget( tmp_path )

        result = move_asset( proj_dir, "models/team/widget.vmdl", "models/shared/widget.vmdl" )
        assert result["file_moved"] is True
        assert result["new_path"] == "models/shared/widget.vmdl"

        # File moved
        assert os.path.isfile( os.path.join( proj_dir, "Assets", "models", "shared", "widget.vmdl" ) )
        assert not os.path.isfile( os.path.join( proj_dir, "Assets", "models", "team", "widget.vmdl" ) )

        # Refs updated
        s_refs = extract_asset_refs( scene_path )
        assert "models/shared/widget.vmdl" in s_refs.get( "models", [] )

    def test_move_dry_run(self, tmp_path):
        proj_dir, _, _ = self._make_project_with_widget( tmp_path )
        result = move_asset( proj_dir, "models/team/widget.vmdl", "models/shared/widget.vmdl", dry_run=True )
        assert result["dry_run"] is True
        assert result["file_moved"] is False
        assert result["references_would_update"] == 2
        assert os.path.isfile( os.path.join( proj_dir, "Assets", "models", "team", "widget.vmdl" ) )
