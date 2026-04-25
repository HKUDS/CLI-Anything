"""Source operations."""

from __future__ import annotations

import copy

from .session import Session
from .scenes import _find_scene

SOURCE_TYPES = [
    "video_capture", "display_capture", "window_capture", "image",
    "media", "browser", "text", "color", "audio_input", "audio_output",
    "group", "scene",
]


def _get_state(session: Session) -> dict:
    if not session.is_open or session.state is None:
        raise RuntimeError("No project is open")
    return session.state


def _parse_setting_pairs(setting_pairs: tuple[str, ...]) -> dict:
    settings: dict[str, object] = {}
    for item in setting_pairs:
        if "=" not in item:
            raise ValueError(f"Invalid setting {item!r}; expected key=value")
        key, value = item.split("=", 1)
        settings[key] = value
    return settings


def _get_scene(proj: dict, scene_index: int | None = None) -> dict:
    idx = scene_index if scene_index is not None else proj.get("active_scene", 0)
    if idx < 0 or idx >= len(proj["scenes"]):
        raise IndexError(f"Scene index {idx} out of range (0-{len(proj['scenes']) - 1})")
    return proj["scenes"][idx]


def _get_source(proj: dict, source_index: int, scene_index: int | None = None) -> dict:
    scene = _get_scene(proj, scene_index)
    sources = scene.get("sources", [])
    if not sources:
        raise ValueError("No sources exist in this scene.")
    if source_index < 0 or source_index >= len(sources):
        raise ValueError(f"Source index {source_index} out of range (0-{len(sources) - 1})")
    return sources[source_index]


def add_source(
    session_or_proj,
    source_type: str | None = None,
    *,
    name: str | None = None,
    scene_name: str | None = None,
    scene_index: int | None = None,
    visible: bool = True,
    settings=None,
    position: dict | None = None,
    size: dict | None = None,
    hidden: bool = False,
) -> dict:
    if isinstance(session_or_proj, Session):
        state = _get_state(session_or_proj)
        target_scene_name = scene_name or state["scenes"][state["active_scene"]]["name"]
        scene = _find_scene(state, target_scene_name)
        if name and any(source["name"] == name for source in scene["sources"]):
            raise ValueError(f"Source already exists in scene {target_scene_name}: {name}")
        session_or_proj.checkpoint()
        parsed_settings = _parse_setting_pairs(settings) if isinstance(settings, tuple) else (settings or {})
        source = {
            "id": len(scene["sources"]),
            "name": name or source_type,
            "type": source_type,
            "visible": visible and not hidden,
            "locked": False,
            "position": position or {"x": 0, "y": 0},
            "size": size or {"width": 1920, "height": 1080},
            "crop": {"top": 0, "bottom": 0, "left": 0, "right": 0},
            "rotation": 0,
            "opacity": 1.0,
            "filters": [],
            "settings": parsed_settings,
        }
        scene["sources"].append(source)
        if source_type in {"audio_input", "audio_output"}:
            state["audio_sources"].append(
                {"name": name, "type": source_type, "volume_db": 0.0, "monitoring": "off"}
            )
        return {"action": "add_source", "scene": target_scene_name, "source": source}

    proj = session_or_proj
    scene = _get_scene(proj, scene_index)
    parsed_settings = settings if isinstance(settings, dict) else {}
    source = {
        "id": len(scene.get("sources", [])),
        "name": name or source_type,
        "type": source_type,
        "visible": visible and not hidden,
        "locked": False,
        "position": position or {"x": 0, "y": 0},
        "size": size or {"width": 1920, "height": 1080},
        "crop": {"top": 0, "bottom": 0, "left": 0, "right": 0},
        "rotation": 0,
        "opacity": 1.0,
        "filters": [],
        "settings": parsed_settings,
    }
    scene.setdefault("sources", []).append(source)
    return source


def remove_source(proj: dict, source_index: int, scene_index: int | None = None) -> dict:
    scene = _get_scene(proj, scene_index)
    sources = scene.get("sources", [])
    if not sources:
        raise ValueError("No sources exist in this scene.")
    if source_index < 0 or source_index >= len(sources):
        raise ValueError(f"Source index {source_index} out of range")
    return sources.pop(source_index)


def duplicate_source(proj: dict, source_index: int, scene_index: int | None = None) -> dict:
    scene = _get_scene(proj, scene_index)
    source = _get_source(proj, source_index, scene_index)
    dup = copy.deepcopy(source)
    dup["id"] = len(scene["sources"])
    dup["name"] = f"{source['name']} (Copy)"
    scene["sources"].append(dup)
    return dup


def set_source_property(proj: dict, source_index: int, prop: str, value, scene_index: int | None = None) -> dict:
    source = _get_source(proj, source_index, scene_index)
    if prop == "visible":
        if isinstance(value, str):
            source["visible"] = value.lower() == "true"
        else:
            source["visible"] = bool(value)
    else:
        source[prop] = value
    return source


def transform_source(
    proj: dict,
    source_index: int,
    *,
    position: dict | None = None,
    size: dict | None = None,
    crop: dict | None = None,
    rotation: float | None = None,
    scene_index: int | None = None,
) -> dict:
    source = _get_source(proj, source_index, scene_index)
    if position is not None:
        source["position"] = position
    if size is not None:
        source["size"] = size
    if crop is not None:
        for key in ("top", "bottom", "left", "right"):
            if key in crop and crop[key] < 0:
                raise ValueError(f"Crop {key} must be non-negative, got {crop[key]}")
        source["crop"] = {**source.get("crop", {}), **crop}
    if rotation is not None:
        source["rotation"] = rotation
    return source


def list_sources(session_or_proj, scene_name: str | None = None, scene_index: int | None = None):
    if isinstance(session_or_proj, Session):
        state = _get_state(session_or_proj)
        target_scene_name = scene_name or state["scenes"][state["active_scene"]]["name"]
        scene = _find_scene(state, target_scene_name)
        return {"scene": target_scene_name, "sources": scene["sources"]}
    proj = session_or_proj
    scene = _get_scene(proj, scene_index)
    return scene.get("sources", [])
