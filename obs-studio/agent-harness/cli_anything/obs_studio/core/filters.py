"""Filter operations."""

from __future__ import annotations

from .session import Session
from .scenes import _find_scene
from .sources import _parse_setting_pairs, _get_scene, _get_source

FILTER_TYPES = [
    "color_correction", "chroma_key", "color_key", "lut", "image_mask",
    "crop_pad", "scroll", "sharpen", "noise_suppress", "gain",
    "compressor", "noise_gate", "limiter",
]

_CHROMA_KEY_VALID_COLORS = {"green", "blue", "custom"}


def _get_state(session: Session) -> dict:
    if not session.is_open or session.state is None:
        raise RuntimeError("No project is open")
    return session.state


def _find_source(scene: dict, source_name: str) -> dict:
    for source in scene["sources"]:
        if source["name"] == source_name:
            return source
    raise ValueError(f"Source not found: {source_name}")


def _validate_filter_params(filter_type: str, params: dict) -> None:
    if filter_type == "chroma_key" and "key_color_type" in params:
        if params["key_color_type"] not in _CHROMA_KEY_VALID_COLORS:
            raise ValueError(
                f"Invalid key_color_type: {params['key_color_type']}. "
                f"Valid: {', '.join(sorted(_CHROMA_KEY_VALID_COLORS))}"
            )


def add_filter(
    session_or_proj,
    filter_type: str | None = None,
    source_name_or_index=None,
    *,
    source_name: str | None = None,
    source_index: int | None = None,
    scene_name: str | None = None,
    scene_index: int | None = None,
    settings: tuple[str, ...] = (),
    params: dict | None = None,
) -> dict:
    if isinstance(session_or_proj, Session):
        state = _get_state(session_or_proj)
        target_scene_name = scene_name or state["scenes"][state["active_scene"]]["name"]
        scene = _find_scene(state, target_scene_name)
        sname = source_name or source_name_or_index
        source = _find_source(scene, sname)
        session_or_proj.checkpoint()
        filter_item = {
            "id": len(source["filters"]),
            "type": filter_type,
            "settings": _parse_setting_pairs(settings),
        }
        source["filters"].append(filter_item)
        return {
            "action": "add_filter",
            "scene": target_scene_name,
            "source": sname,
            "filter": filter_item,
        }

    proj = session_or_proj
    idx = source_name_or_index if isinstance(source_name_or_index, int) else (source_index or 0)
    if idx is not None and isinstance(idx, int):
        scene = _get_scene(proj, scene_index)
        sources = scene.get("sources", [])
        if idx < 0 or idx >= len(sources):
            raise ValueError(f"Source index {idx} out of range")
        source = sources[idx]
    filter_params = params or {}
    _validate_filter_params(filter_type, filter_params)
    filter_item = {
        "id": len(source.get("filters", [])),
        "type": filter_type,
        "params": filter_params,
    }
    source.setdefault("filters", []).append(filter_item)
    return filter_item


def remove_filter(proj: dict, filter_index: int, source_index: int, scene_index: int | None = None) -> dict:
    source = _get_source(proj, source_index, scene_index)
    filters = source.get("filters", [])
    if filter_index < 0 or filter_index >= len(filters):
        raise IndexError(f"Filter index {filter_index} out of range")
    return filters.pop(filter_index)


def set_filter_param(proj: dict, filter_index: int, param_name: str, value, source_index: int = 0, scene_index: int | None = None) -> dict:
    source = _get_source(proj, source_index, scene_index)
    filters = source.get("filters", [])
    if filter_index < 0 or filter_index >= len(filters):
        raise IndexError(f"Filter index {filter_index} out of range")
    filt = filters[filter_index]
    filt.setdefault("params", {})[param_name] = value
    return filt


def list_filters(session_or_proj, source_name_or_index=None, *, scene_name: str | None = None, scene_index: int | None = None):
    if isinstance(session_or_proj, Session):
        state = _get_state(session_or_proj)
        target_scene_name = scene_name or state["scenes"][state["active_scene"]]["name"]
        scene = _find_scene(state, target_scene_name)
        source = _find_source(scene, source_name_or_index)
        return {"scene": target_scene_name, "source": source_name_or_index, "filters": source["filters"]}

    proj = session_or_proj
    idx = source_name_or_index if isinstance(source_name_or_index, int) else 0
    source = _get_source(proj, idx, scene_index)
    return source.get("filters", [])
