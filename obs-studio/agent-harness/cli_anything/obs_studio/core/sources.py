"""OBS Studio CLI - Source management."""

import copy
from typing import Dict, Any, List, Optional
from cli_anything.obs_studio.utils.obs_utils import generate_id, unique_name, get_item, validate_range


SOURCE_TYPES = {
    "video_capture": {
        "label": "Video Capture Device",
        "category": "video",
        "default_settings": {"device": "", "resolution": "1920x1080", "fps": 30},
    },
    "display_capture": {
        "label": "Display Capture",
        "category": "video",
        "default_settings": {"display": 0, "capture_cursor": True},
    },
    "window_capture": {
        "label": "Window Capture",
        "category": "video",
        "default_settings": {"window": "", "capture_cursor": True},
    },
    "image": {
        "label": "Image",
        "category": "media",
        "default_settings": {"file": "", "unload_when_hidden": True},
    },
    "media": {
        "label": "Media Source",
        "category": "media",
        "default_settings": {"local_file": "", "looping": False, "restart_on_activate": True},
    },
    "browser": {
        "label": "Browser Source",
        "category": "web",
        "default_settings": {"url": "", "width": 800, "height": 600, "css": ""},
    },
    "text": {
        "label": "Text (FreeType 2)",
        "category": "text",
        "default_settings": {"text": "", "font": "Sans Serif", "size": 36, "color": "#FFFFFF"},
    },
    "color": {
        "label": "Color Source",
        "category": "utility",
        "default_settings": {"color": "#000000", "width": 1920, "height": 1080},
    },
    "audio_input": {
        "label": "Audio Input Capture",
        "category": "audio",
        "default_settings": {"device": ""},
    },
    "audio_output": {
        "label": "Audio Output Capture",
        "category": "audio",
        "default_settings": {"device": ""},
    },
    "group": {
        "label": "Group",
        "category": "utility",
        "default_settings": {"items": []},
    },
    "scene": {
        "label": "Scene",
        "category": "utility",
        "default_settings": {"scene_name": ""},
    },
}


def _get_scene_sources(project: Dict[str, Any], scene_index: int) -> List[Dict[str, Any]]:
    """Get sources for a scene."""
    scenes = project.get("scenes", [])
    scene = get_item(scenes, scene_index, "scene")
    return scene.setdefault("sources", [])


def _default_source(name: str, source_type: str) -> Dict[str, Any]:
    """Create a default source dict."""
    type_info = SOURCE_TYPES.get(source_type, {})
    default_settings = copy.deepcopy(type_info.get("default_settings", {}))
    return {
        "id": 0,
        "name": name,
        "type": source_type,
        "visible": True,
        "locked": False,
        "position": {"x": 0, "y": 0},
        "size": {"width": 1920, "height": 1080},
        "crop": {"top": 0, "bottom": 0, "left": 0, "right": 0},
        "rotation": 0,
        "opacity": 1.0,
        "filters": [],
        "settings": default_settings,
    }


def add_source(
    project: Dict[str, Any],
    source_type: str,
    scene_index: int = 0,
    name: Optional[str] = None,
    position: Optional[Dict[str, Any]] = None,
    size: Optional[Dict[str, Any]] = None,
    visible: bool = True,
    settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Add a source to a scene."""
    if source_type not in SOURCE_TYPES:
        raise ValueError(
            f"Unknown source type: {source_type}. Valid: {', '.join(sorted(SOURCE_TYPES.keys()))}"
        )

    sources = _get_scene_sources(project, scene_index)
    if name is None:
        name = SOURCE_TYPES[source_type]["label"]
    name = unique_name(name, sources)

    src = _default_source(name, source_type)
    src["id"] = generate_id(sources)
    src["visible"] = visible

    if position:
        src["position"] = {"x": float(position.get("x", 0)), "y": float(position.get("y", 0))}
    if size:
        w = int(size.get("width", 1920))
        h = int(size.get("height", 1080))
        if w < 1 or h < 1:
            raise ValueError(f"Size must be positive: {w}x{h}")
        src["size"] = {"width": w, "height": h}
    if settings:
        src["settings"].update(settings)

    sources.append(src)
    return src


def remove_source(project: Dict[str, Any], source_index: int, scene_index: int = 0) -> Dict[str, Any]:
    """Remove a source from a scene."""
    sources = _get_scene_sources(project, scene_index)
    source = get_item(sources, source_index, "source")
    return sources.pop(source_index)


def duplicate_source(project: Dict[str, Any], source_index: int, scene_index: int = 0) -> Dict[str, Any]:
    """Duplicate a source within a scene."""
    sources = _get_scene_sources(project, scene_index)
    original = get_item(sources, source_index, "source")
    dup = copy.deepcopy(original)
    dup["id"] = generate_id(sources)
    dup["name"] = unique_name(original["name"] + " (Copy)", sources)
    sources.append(dup)
    return dup


def set_source_property(
    project: Dict[str, Any],
    source_index: int,
    prop: str,
    value: Any,
    scene_index: int = 0,
) -> Dict[str, Any]:
    """Set a property on a source."""
    sources = _get_scene_sources(project, scene_index)
    source = get_item(sources, source_index, "source")

    valid_props = ("name", "visible", "locked", "opacity", "rotation")
    if prop not in valid_props:
        raise ValueError(f"Unknown source property: {prop}. Valid: {', '.join(valid_props)}")

    if prop == "visible":
        if isinstance(value, str):
            value = value.lower() in ("true", "1", "yes")
        source["visible"] = bool(value)
    elif prop == "locked":
        if isinstance(value, str):
            value = value.lower() in ("true", "1", "yes")
        source["locked"] = bool(value)
    elif prop == "opacity":
        source["opacity"] = validate_range(value, 0.0, 1.0, "Opacity")
    elif prop == "rotation":
        source["rotation"] = float(value)
    elif prop == "name":
        source["name"] = str(value)

    return source


def transform_source(
    project: Dict[str, Any],
    source_index: int,
    scene_index: int = 0,
    position: Optional[Dict[str, Any]] = None,
    size: Optional[Dict[str, Any]] = None,
    crop: Optional[Dict[str, Any]] = None,
    rotation: Optional[float] = None,
) -> Dict[str, Any]:
    """Transform a source (position, size, crop, rotation)."""
    sources = _get_scene_sources(project, scene_index)
    source = get_item(sources, source_index, "source")

    if position:
        source["position"] = {
            "x": float(position.get("x", source["position"]["x"])),
            "y": float(position.get("y", source["position"]["y"])),
        }
    if size:
        w = int(size.get("width", source["size"]["width"]))
        h = int(size.get("height", source["size"]["height"]))
        if w < 1 or h < 1:
            raise ValueError(f"Size must be positive: {w}x{h}")
        source["size"] = {"width": w, "height": h}
    if crop:
        for key in ("top", "bottom", "left", "right"):
            if key in crop:
                val = int(crop[key])
                if val < 0:
                    raise ValueError(f"Crop {key} must be non-negative, got {val}")
                source["crop"][key] = val
    if rotation is not None:
        source["rotation"] = float(rotation)

    return source


def list_sources(project: Dict[str, Any], scene_index: int = 0) -> List[Dict[str, Any]]:
    """List all sources in a scene."""
    sources = _get_scene_sources(project, scene_index)
    return [
        {
            "index": i,
            "id": s.get("id", i),
            "name": s.get("name", f"Source {i}"),
            "type": s.get("type", "unknown"),
            "visible": s.get("visible", True),
            "locked": s.get("locked", False),
            "position": s.get("position", {"x": 0, "y": 0}),
            "size": s.get("size", {"width": 0, "height": 0}),
        }
        for i, s in enumerate(sources)
    ]


def get_source(project: Dict[str, Any], source_index: int, scene_index: int = 0) -> Dict[str, Any]:
    """Get detailed info about a source."""
    sources = _get_scene_sources(project, scene_index)
    return get_item(sources, source_index, "source")
