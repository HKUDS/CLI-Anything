"""OBS Studio CLI - Scene management."""

import copy
from typing import Dict, Any, List, Optional
from cli_anything.obs_studio.utils.obs_utils import generate_id, unique_name, get_item


def _get_scenes(project: Dict[str, Any]) -> List[Dict[str, Any]]:
    return project.setdefault("scenes", [])


def add_scene(project: Dict[str, Any], name: str = "Scene") -> Dict[str, Any]:
    """Add a new scene to the project."""
    scenes = _get_scenes(project)
    name = unique_name(name, scenes)
    scene = {
        "id": generate_id(scenes),
        "name": name,
        "sources": [],
    }
    scenes.append(scene)
    return scene


def remove_scene(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Remove a scene by index."""
    scenes = _get_scenes(project)
    scene = get_item(scenes, index, "scene")
    if len(scenes) <= 1:
        raise ValueError("Cannot remove the last scene. At least one scene must exist.")
    removed = scenes.pop(index)
    # Fix active_scene reference
    active = project.get("active_scene", 0)
    if active >= len(scenes):
        project["active_scene"] = len(scenes) - 1
    elif active > index:
        project["active_scene"] = active - 1
    return removed


def duplicate_scene(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Duplicate a scene."""
    scenes = _get_scenes(project)
    original = get_item(scenes, index, "scene")
    dup = copy.deepcopy(original)
    dup["id"] = generate_id(scenes)
    dup["name"] = unique_name(original["name"] + " (Copy)", scenes)
    # Give duplicated sources new IDs
    for i, src in enumerate(dup.get("sources", [])):
        src["id"] = i
    scenes.append(dup)
    return dup


def set_active_scene(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Set the active scene by index."""
    scenes = _get_scenes(project)
    scene = get_item(scenes, index, "scene")
    project["active_scene"] = index
    return {"active_scene": scene["name"], "index": index}


def list_scenes(project: Dict[str, Any]) -> List[Dict[str, Any]]:
    """List all scenes."""
    scenes = _get_scenes(project)
    active = project.get("active_scene", 0)
    return [
        {
            "index": i,
            "id": s.get("id", i),
            "name": s.get("name", f"Scene {i}"),
            "source_count": len(s.get("sources", [])),
            "active": i == active,
        }
        for i, s in enumerate(scenes)
    ]


def get_active_scene(project: Dict[str, Any]) -> Dict[str, Any]:
    """Get the currently active scene."""
    scenes = _get_scenes(project)
    active = project.get("active_scene", 0)
    if active >= len(scenes):
        active = 0
        project["active_scene"] = 0
    return scenes[active]
