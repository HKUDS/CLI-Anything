"""Manages s&box .sbproj project files and project scaffolding."""

import json
import os
import uuid
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Template content
# ---------------------------------------------------------------------------

EDITORCONFIG_CONTENT = """\
root = true

[*]
indent_style = tab
indent_size = 4
end_of_line = crlf
insert_final_newline = true

[*.cs]
csharp_new_line_before_open_brace = all
csharp_space_between_method_declaration_parameter_list_parentheses = true
csharp_space_between_method_call_parameter_list_parentheses = true
csharp_space_after_keywords_in_control_flow_statements = true
csharp_preferred_modifier_order = public, private, protected, internal, static, extern, new, virtual, abstract, sealed, override, readonly, unsafe, volatile, async:suggestion
"""

CODE_ASSEMBLY_CS = """\
global using Sandbox;
global using System.Collections.Generic;
global using System.Linq;
"""

EDITOR_ASSEMBLY_CS = """\
global using Sandbox;
global using Editor;
global using System.Collections.Generic;
global using System.Linq;
"""

DEFAULT_INPUT_CONFIG: Dict[str, Any] = {
    "Actions": [
        {"Name": "Forward", "GroupName": "Movement", "Title": None, "KeyboardCode": "W", "GamepadCode": "None"},
        {"Name": "Backward", "GroupName": "Movement", "Title": None, "KeyboardCode": "S", "GamepadCode": "None"},
        {"Name": "Left", "GroupName": "Movement", "Title": None, "KeyboardCode": "A", "GamepadCode": "None"},
        {"Name": "Right", "GroupName": "Movement", "Title": None, "KeyboardCode": "D", "GamepadCode": "None"},
        {"Name": "Jump", "GroupName": "Movement", "Title": None, "KeyboardCode": "space", "GamepadCode": "A"},
        {"Name": "Run", "GroupName": "Movement", "Title": None, "KeyboardCode": "shift", "GamepadCode": "LeftJoystickButton"},
        {"Name": "Walk", "GroupName": "Movement", "Title": None, "KeyboardCode": "alt", "GamepadCode": "None"},
        {"Name": "Duck", "GroupName": "Movement", "Title": None, "KeyboardCode": "ctrl", "GamepadCode": "B"},
        {"Name": "Attack1", "GroupName": "Actions", "Title": "Primary Attack", "KeyboardCode": "mouse1", "GamepadCode": "RightTrigger"},
        {"Name": "Attack2", "GroupName": "Actions", "Title": "Secondary Attack", "KeyboardCode": "mouse2", "GamepadCode": "LeftTrigger"},
        {"Name": "Reload", "GroupName": "Actions", "Title": None, "KeyboardCode": "r", "GamepadCode": "X"},
        {"Name": "Use", "GroupName": "Actions", "Title": None, "KeyboardCode": "e", "GamepadCode": "Y"},
        {"Name": "Slot1", "GroupName": "Inventory", "Title": "Slot #1", "KeyboardCode": "1", "GamepadCode": "DpadWest"},
        {"Name": "Slot2", "GroupName": "Inventory", "Title": "Slot #2", "KeyboardCode": "2", "GamepadCode": "DpadEast"},
        {"Name": "Slot3", "GroupName": "Inventory", "Title": "Slot #3", "KeyboardCode": "3", "GamepadCode": "DpadSouth"},
        {"Name": "Slot4", "GroupName": "Inventory", "Title": "Slot #4", "KeyboardCode": "4", "GamepadCode": "None"},
        {"Name": "Slot5", "GroupName": "Inventory", "Title": "Slot #5", "KeyboardCode": "5", "GamepadCode": "None"},
        {"Name": "Slot6", "GroupName": "Inventory", "Title": "Slot #6", "KeyboardCode": "6", "GamepadCode": "None"},
        {"Name": "Slot7", "GroupName": "Inventory", "Title": "Slot #7", "KeyboardCode": "7", "GamepadCode": "None"},
        {"Name": "Slot8", "GroupName": "Inventory", "Title": "Slot #8", "KeyboardCode": "8", "GamepadCode": "None"},
        {"Name": "Slot9", "GroupName": "Inventory", "Title": "Slot #9", "KeyboardCode": "9", "GamepadCode": "None"},
        {"Name": "Slot0", "GroupName": "Inventory", "Title": "Slot #0", "KeyboardCode": "0", "GamepadCode": "None"},
        {"Name": "SlotPrev", "GroupName": "Inventory", "Title": "Previous Slot", "KeyboardCode": "mouse4", "GamepadCode": "SwitchLeftBumper"},
        {"Name": "SlotNext", "GroupName": "Inventory", "Title": "Next Slot", "KeyboardCode": "mouse5", "GamepadCode": "SwitchRightBumper"},
        {"Name": "View", "GroupName": "Other", "Title": None, "KeyboardCode": "C", "GamepadCode": "RightJoystickButton"},
        {"Name": "Voice", "GroupName": "Other", "Title": None, "KeyboardCode": "v", "GamepadCode": "None"},
        {"Name": "Drop", "GroupName": "Other", "Title": None, "KeyboardCode": "g", "GamepadCode": "None"},
        {"Name": "Flashlight", "GroupName": "Other", "Title": None, "KeyboardCode": "f", "GamepadCode": "DpadNorth"},
        {"Name": "Score", "GroupName": "Other", "Title": "Scoreboard", "KeyboardCode": "tab", "GamepadCode": "SwitchLeftMenu"},
        {"Name": "Menu", "GroupName": "Other", "Title": None, "KeyboardCode": "Q", "GamepadCode": "SwitchRightMenu"},
        {"Name": "Chat", "GroupName": "Other", "Title": None, "KeyboardCode": "enter", "GamepadCode": "None"},
    ],
    "__guid": str( uuid.uuid4() ),
    "__schema": "configdata",
    "__type": "InputSettings",
    "__version": 1,
}

DEFAULT_COLLISION_CONFIG: Dict[str, Any] = {
    "Version": 2,
    "Defaults": {
        "solid": "Collide",
        "world": "Collide",
        "trigger": "Trigger",
        "ladder": "Ignore",
        "water": "Trigger",
    },
    "Pairs": [
        {"a": "solid", "b": "solid", "r": "Collide"},
        {"a": "trigger", "b": "playerclip", "r": "Ignore"},
        {"a": "trigger", "b": "solid", "r": "Trigger"},
        {"a": "playerclip", "b": "solid", "r": "Collide"},
    ],
    "__guid": str( uuid.uuid4() ),
    "__schema": "configdata",
    "__type": "CollisionRules",
    "__version": 2,
}


def _default_minimal_scene() -> Dict[str, Any]:
    """Return a minimal scene structure with Sun, Skybox, Plane, and Camera."""
    # Import here to avoid circular dependency at module level
    from .scene import _build_default_objects

    scene: Dict[str, Any] = {
        "GameObjects": _build_default_objects(),
        "SceneProperties": {
            "FixedUpdateFrequency": 50,
            "MaxFixedUpdates": 5,
            "NetworkFrequency": 60,
            "NetworkInterpolation": True,
            "PhysicsSubSteps": 1,
            "ThreadedAnimation": True,
            "TimeScale": 1,
            "UseFixedUpdate": True,
        },
        "Title": "minimal",
        "Description": "",
        "ResourceVersion": 1,
        "__references": [],
        "__version": 1,
    }
    return scene


def _default_sbproj(
    name: str,
    project_type: str = "game",
    org: str = "local",
    max_players: int = 64,
    tick_rate: int = 50,
    network_type: str = "Multiplayer",
    startup_scene: str = "scenes/minimal.scene",
) -> Dict[str, Any]:
    """Build a default .sbproj dict."""
    return {
        "Title": name,
        "Type": project_type,
        "Org": org,
        "Ident": name.lower().replace(" ", "_"),
        "Schema": 1,
        "HasAssets": True,
        "AssetsPath": "",
        "HasCode": True,
        "CodePath": "/code/",
        "Metadata": {
            "MaxPlayers": max_players,
            "MinPlayers": 1,
            "TickRate": tick_rate,
            "GameNetworkType": network_type,
            "MapSelect": "Tagged",
            "MapList": [],
            "RankType": "None",
            "PerMapRanking": False,
            "LeaderboardType": "None",
            "CsProjName": "",
            "StartupScene": startup_scene,
        },
        "PackageReferences": [],
        "EditorReferences": [],
        "IsWhitelistDisabled": False,
        "Physics": {
            "SubSteps": 1,
            "TimeScale": 1,
            "Gravity": "0,0,-800",
            "AirDensity": 1.2,
            "SleepingEnabled": True,
            "SimulationMode": "Continuous",
            "PositionIterations": 2,
            "VelocityIterations": 8,
        },
        "__references": [],
        "__version": 1,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_project(
    name: str,
    project_type: str = "game",
    org: str = "local",
    max_players: int = 64,
    tick_rate: int = 50,
    network_type: str = "Multiplayer",
    startup_scene: str = "scenes/minimal.scene",
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new s&box project directory with .sbproj and standard structure.

    Creates:
    - <name>.sbproj
    - .editorconfig
    - Code/Assembly.cs
    - Editor/Assembly.cs
    - Assets/scenes/minimal.scene (basic scene)
    - ProjectSettings/Input.config (default bindings)
    - ProjectSettings/Collision.config (default layers)
    - Libraries/ (empty)
    - Localization/ (empty)

    Returns dict with project info.
    """
    root = output_dir if output_dir else os.path.join(os.getcwd(), name)
    os.makedirs(root, exist_ok=True)

    # .sbproj
    sbproj_data = _default_sbproj(
        name,
        project_type=project_type,
        org=org,
        max_players=max_players,
        tick_rate=tick_rate,
        network_type=network_type,
        startup_scene=startup_scene,
    )
    sbproj_path = os.path.join(root, f"{name}.sbproj")
    _write_json(sbproj_path, sbproj_data)

    # .editorconfig
    _write_text(os.path.join(root, ".editorconfig"), EDITORCONFIG_CONTENT)

    # Code/Assembly.cs
    code_dir = os.path.join(root, "Code")
    os.makedirs(code_dir, exist_ok=True)
    _write_text(os.path.join(code_dir, "Assembly.cs"), CODE_ASSEMBLY_CS)

    # Editor/Assembly.cs
    editor_dir = os.path.join(root, "Editor")
    os.makedirs(editor_dir, exist_ok=True)
    _write_text(os.path.join(editor_dir, "Assembly.cs"), EDITOR_ASSEMBLY_CS)

    # Assets/scenes/minimal.scene
    scenes_dir = os.path.join(root, "Assets", "scenes")
    os.makedirs(scenes_dir, exist_ok=True)
    scene_data = _default_minimal_scene()
    _write_json(os.path.join(scenes_dir, "minimal.scene"), scene_data)

    # ProjectSettings
    settings_dir = os.path.join(root, "ProjectSettings")
    os.makedirs(settings_dir, exist_ok=True)
    _write_json(os.path.join(settings_dir, "Input.config"), DEFAULT_INPUT_CONFIG)
    _write_json(os.path.join(settings_dir, "Collision.config"), DEFAULT_COLLISION_CONFIG)

    # Empty directories
    os.makedirs(os.path.join(root, "Libraries"), exist_ok=True)
    os.makedirs(os.path.join(root, "Localization"), exist_ok=True)

    return {
        "name": name,
        "path": root,
        "sbproj": sbproj_path,
        "type": project_type,
        "org": org,
        "max_players": max_players,
        "tick_rate": tick_rate,
        "network_type": network_type,
        "startup_scene": startup_scene,
    }


def load_project(sbproj_path: str) -> Dict[str, Any]:
    """Load and return parsed .sbproj JSON."""
    with open(sbproj_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_project(sbproj_path: str, data: Dict[str, Any]) -> None:
    """Save .sbproj JSON."""
    _write_json(sbproj_path, data)


def get_project_info(sbproj_path: str) -> Dict[str, Any]:
    """Return dict with project metadata suitable for display/JSON output."""
    data = load_project(sbproj_path)
    meta = data.get("Metadata", {})
    return {
        "title": data.get("Title", ""),
        "type": data.get("Type", ""),
        "org": data.get("Org", ""),
        "ident": data.get("Ident", ""),
        "startup_scene": meta.get("StartupScene", ""),
        "max_players": meta.get("MaxPlayers"),
        "min_players": meta.get("MinPlayers"),
        "tick_rate": meta.get("TickRate"),
        "network_type": meta.get("GameNetworkType", ""),
        "map_select": meta.get("MapSelect", ""),
        "map_list": meta.get("MapList", []),
        "package_references": data.get("PackageReferences", []),
        "path": sbproj_path,
    }


def configure_project(sbproj_path: str, **kwargs: Any) -> Dict[str, Any]:
    """Update project metadata fields.

    Accepts: title, max_players, min_players, tick_rate, network_type,
    startup_scene, map_list, map_select, org, ident, etc.

    Returns updated project info dict.
    """
    data = load_project(sbproj_path)
    meta = data.setdefault("Metadata", {})

    # Top-level fields
    top_level_map = {
        "title": "Title",
        "org": "Org",
        "ident": "Ident",
        "type": "Type",
    }
    for kwarg_key, json_key in top_level_map.items():
        if kwarg_key in kwargs:
            data[json_key] = kwargs[kwarg_key]

    # Metadata fields
    meta_map = {
        "max_players": "MaxPlayers",
        "min_players": "MinPlayers",
        "tick_rate": "TickRate",
        "network_type": "GameNetworkType",
        "map_select": "MapSelect",
        "map_list": "MapList",
        "startup_scene": "StartupScene",
    }
    for kwarg_key, json_key in meta_map.items():
        if kwarg_key in kwargs:
            meta[json_key] = kwargs[kwarg_key]

    save_project(sbproj_path, data)
    return get_project_info(sbproj_path)


def add_package( sbproj_path: str, package_ref: str ) -> Dict[str, Any]:
    """Add a package reference to the project.

    Args:
        sbproj_path: Path to the .sbproj file.
        package_ref: Package identifier (e.g. "facepunch.libsdf", "org.package").

    Returns:
        Updated project info dict.

    Raises:
        ValueError: If the package is already referenced.
    """
    data = load_project( sbproj_path )
    refs = data.get( "PackageReferences", [] ) or []

    if package_ref in refs:
        raise ValueError( f"Package '{package_ref}' is already referenced" )

    refs.append( package_ref )
    data["PackageReferences"] = refs
    save_project( sbproj_path, data )

    return get_project_info( sbproj_path )


def remove_package( sbproj_path: str, package_ref: str ) -> Dict[str, Any]:
    """Remove a package reference from the project.

    Returns:
        Updated project info dict.

    Raises:
        ValueError: If the package is not found.
    """
    data = load_project( sbproj_path )
    refs = data.get( "PackageReferences", [] ) or []

    if package_ref not in refs:
        raise ValueError( f"Package '{package_ref}' not found in references" )

    refs.remove( package_ref )
    data["PackageReferences"] = refs
    save_project( sbproj_path, data )

    return get_project_info( sbproj_path )


def find_sbproj(directory: str) -> Optional[str]:
    """Find .sbproj file in a directory. Returns path or None."""
    if not os.path.isdir(directory):
        return None
    for entry in os.listdir(directory):
        if entry.endswith(".sbproj"):
            return os.path.join(directory, entry)
    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_json(path: str, data: Dict[str, Any]) -> None:
    """Write data as formatted JSON to path."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\r\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _write_text(path: str, content: str) -> None:
    """Write text content to path, ensuring parent dirs exist."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(content)
