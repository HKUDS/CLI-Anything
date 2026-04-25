"""Export harness project to OBS Studio native scene collection format."""

from __future__ import annotations

import json
import uuid
from pathlib import Path


# Platform-specific source type mappings (Linux/PipeWire)
SOURCE_TYPE_MAP = {
    "display_capture": "pipewire-desktop-capture-source",
    "video_capture": "v4l2_input",
    "window_capture": "xcomposite_input",
    "image": "image_source",
    "text": "text_ft2_source_v2",
    "browser": "browser_source",
    "media": "ffmpeg_source",
    "color": "color_source_v3",
    "audio_input": "pulse_input_capture",
    "audio_output": "pulse_output_capture",
    "group": "group",
    "scene": "scene",
}

FILTER_TYPE_MAP = {
    "noise_suppress": "noise_suppress_filter_v2",
    "noise_gate": "noise_gate_filter",
    "gain": "gain_filter",
    "compressor": "compressor_filter",
    "limiter": "limiter_filter",
    "chroma_key": "chroma_key_filter_v2",
    "color_correction": "color_filter_v2",
    "color_key": "color_key_filter_v2",
    "sharpen": "sharpness_filter_v2",
    "scroll": "scroll_filter",
    "crop_pad": "crop_filter",
    "image_mask": "mask_filter_v2",
    "lut": "clut_filter",
}

_PREV_VER = 536870914


def _make_uuid() -> str:
    return str(uuid.uuid4())


def _base_source(name: str, source_id: str, settings: dict | None = None) -> dict:
    """Create an OBS-native source entry with all required fields."""
    return {
        "prev_ver": _PREV_VER,
        "name": name,
        "uuid": _make_uuid(),
        "id": source_id,
        "versioned_id": source_id,
        "settings": settings or {},
        "mixers": 255,
        "sync": 0,
        "flags": 0,
        "volume": 1.0,
        "balance": 0.5,
        "enabled": True,
        "muted": False,
        "push-to-mute": False,
        "push-to-mute-delay": 0,
        "push-to-talk": False,
        "push-to-talk-delay": 0,
        "hotkeys": {},
        "deinterlace_mode": 0,
        "deinterlace_field_order": 0,
        "monitoring_type": 0,
        "private_settings": {},
    }


def _convert_filters(harness_filters: list[dict]) -> list[dict]:
    """Convert harness filter list to OBS-native filter list."""
    obs_filters = []
    for f in harness_filters:
        ftype = f.get("type", "")
        obs_id = FILTER_TYPE_MAP.get(ftype, ftype)
        # Merge settings and params
        settings = {}
        settings.update(f.get("settings", {}))
        settings.update(f.get("params", {}))
        obs_filter = _base_source(
            name=ftype.replace("_", " ").title(),
            source_id=obs_id,
            settings=settings,
        )
        obs_filters.append(obs_filter)
    return obs_filters


def _convert_source(src: dict) -> dict:
    """Convert a harness source to an OBS-native flat source entry."""
    stype = src.get("type", "")
    obs_id = SOURCE_TYPE_MAP.get(stype, stype)

    # Build source-specific settings
    settings = dict(src.get("settings", {}))
    if stype == "image" and "file" in settings:
        settings["file"] = settings["file"]
    if stype == "text" and "text" in settings:
        settings["text"] = settings["text"]

    obs_src = _base_source(src["name"], obs_id, settings)

    # Audio sources use mixers=255, video sources use mixers=0
    if stype not in ("audio_input", "audio_output"):
        obs_src["mixers"] = 0

    # Add filters
    filters = _convert_filters(src.get("filters", []))
    if filters:
        obs_src["filters"] = filters

    return obs_src


def _make_scene_item(src: dict, source_uuid: str, item_id: int) -> dict:
    """Create an OBS-native scene item referencing a source by UUID."""
    pos = src.get("position", {"x": 0, "y": 0})
    size = src.get("size", {"width": 1920, "height": 1080})
    crop = src.get("crop", {})
    rotation = src.get("rotation", 0)

    # Calculate scale from target size vs native (assume 1:1 if source matches canvas)
    scale_x = size.get("width", 1920) / 1920
    scale_y = size.get("height", 1080) / 1080

    return {
        "name": src["name"],
        "source_uuid": source_uuid,
        "visible": src.get("visible", True),
        "locked": src.get("locked", False),
        "rot": float(rotation),
        "align": 5,
        "bounds_type": 0,
        "bounds_align": 0,
        "bounds_crop": False,
        "crop_left": crop.get("left", 0),
        "crop_top": crop.get("top", 0),
        "crop_right": crop.get("right", 0),
        "crop_bottom": crop.get("bottom", 0),
        "id": item_id,
        "group_item_backup": False,
        "pos": {"x": float(pos.get("x", 0)), "y": float(pos.get("y", 0))},
        "scale": {"x": scale_x, "y": scale_y},
        "bounds": {"x": 0.0, "y": 0.0},
        "scale_filter": "disable",
        "blend_method": "default",
        "blend_type": "normal",
        "show_transition": {"duration": 0},
        "hide_transition": {"duration": 0},
        "private_settings": {},
    }


def export_to_obs(proj: dict, output_path: str) -> str:
    """Export a harness project dict to OBS Studio native scene collection JSON."""
    scenes = proj.get("scenes", [])
    canvas_uuid = _make_uuid()

    # Collect all non-scene sources across all scenes (deduplicate by name)
    all_sources: dict[str, dict] = {}  # name -> obs source dict
    scene_items_map: dict[str, list[dict]] = {}  # scene name -> list of scene items

    for scene in scenes:
        items = []
        item_counter = 0
        for src in scene.get("sources", []):
            sname = src["name"]
            if sname not in all_sources:
                all_sources[sname] = _convert_source(src)
            source_uuid = all_sources[sname]["uuid"]
            item_counter += 1
            items.append(_make_scene_item(src, source_uuid, item_counter))
        scene_items_map[scene["name"]] = items

    # Build flat sources list: scene sources first, then non-scene sources
    obs_sources = []
    for scene in scenes:
        scene_name = scene["name"]
        scene_src = _base_source(scene_name, "scene", {
            "id_counter": len(scene_items_map.get(scene_name, [])),
            "custom_size": False,
            "items": scene_items_map.get(scene_name, []),
        })
        scene_src["mixers"] = 0
        scene_src["canvas_uuid"] = canvas_uuid
        scene_src["hotkeys"] = {"OBSBasic.SelectScene": []}
        obs_sources.append(scene_src)

    for obs_src in all_sources.values():
        obs_sources.append(obs_src)

    # Build audio device entries
    audio_devices = {}
    desktop_idx = 1
    aux_idx = 1
    for src_name, obs_src in all_sources.items():
        if obs_src["id"] == "pulse_output_capture":
            audio_devices[f"DesktopAudioDevice{desktop_idx}"] = _base_source(
                src_name, "pulse_output_capture", {"device_id": "default"}
            )
            desktop_idx += 1
        elif obs_src["id"] == "pulse_input_capture":
            audio_devices[f"AuxAudioDevice{aux_idx}"] = _base_source(
                src_name, "pulse_input_capture", {"device_id": "default"}
            )
            aux_idx += 1

    # Determine active scene
    active_idx = proj.get("active_scene", 0)
    active_scene_name = scenes[active_idx]["name"] if active_idx < len(scenes) else "Main Scene"

    # Build scene order
    scene_order = [{"name": s["name"]} for s in scenes]

    # Assemble native format
    native: dict = {}
    native.update(audio_devices)
    native.update({
        "current_scene": active_scene_name,
        "current_program_scene": active_scene_name,
        "scene_order": scene_order,
        "name": proj.get("name", "Untitled"),
        "sources": obs_sources,
        "groups": [],
        "quick_transitions": [
            {"name": "Cut", "duration": 300, "hotkeys": [], "id": 1, "fade_to_black": False},
            {"name": "Fade", "duration": 300, "hotkeys": [], "id": 2, "fade_to_black": False},
            {"name": "Fade", "duration": 300, "hotkeys": [], "id": 3, "fade_to_black": True},
        ],
        "transitions": [],
        "saved_projectors": [],
        "canvases": [],
        "current_transition": "Fade",
        "transition_duration": 300,
        "preview_locked": False,
        "scaling_enabled": False,
        "scaling_level": -12,
        "scaling_off_x": 0.0,
        "scaling_off_y": 0.0,
        "modules": {},
        "version": 1,
    })

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(native, indent=4), encoding="utf-8")
    return str(out)
