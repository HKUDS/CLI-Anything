"""Kdenlive CLI - Filter (effect) management module."""

from typing import Dict, Any, List, Optional


FILTER_REGISTRY = {
    "brightness": {
        "mlt_service": "brightness",
        "category": "color",
        "params": {
            "level": {"type": "float", "default": 1.0, "min": 0.0, "max": 5.0},
        },
    },
    "contrast": {
        "mlt_service": "brightness",
        "category": "color",
        "params": {
            "level": {"type": "float", "default": 1.0, "min": 0.0, "max": 5.0},
        },
    },
    "saturation": {
        "mlt_service": "avfilter.eq",
        "category": "color",
        "params": {
            "saturation": {"type": "float", "default": 1.0, "min": 0.0, "max": 3.0},
        },
    },
    "blur": {
        "mlt_service": "boxblur",
        "category": "effect",
        "params": {
            "hblur": {"type": "int", "default": 2, "min": 0, "max": 100},
            "vblur": {"type": "int", "default": 2, "min": 0, "max": 100},
        },
    },
    "fade_in_video": {
        "mlt_service": "brightness",
        "category": "transition",
        "params": {
            "duration": {"type": "float", "default": 1.0, "min": 0.01, "max": 60.0},
        },
    },
    "fade_out_video": {
        "mlt_service": "brightness",
        "category": "transition",
        "params": {
            "duration": {"type": "float", "default": 1.0, "min": 0.01, "max": 60.0},
        },
    },
    "fade_in_audio": {
        "mlt_service": "volume",
        "category": "transition",
        "params": {
            "duration": {"type": "float", "default": 1.0, "min": 0.01, "max": 60.0},
        },
    },
    "fade_out_audio": {
        "mlt_service": "volume",
        "category": "transition",
        "params": {
            "duration": {"type": "float", "default": 1.0, "min": 0.01, "max": 60.0},
        },
    },
    "volume": {
        "mlt_service": "volume",
        "category": "audio",
        "params": {
            "gain": {"type": "float", "default": 1.0, "min": 0.0, "max": 10.0},
        },
    },
    "crop": {
        "mlt_service": "crop",
        "category": "effect",
        "params": {
            "left": {"type": "int", "default": 0, "min": 0, "max": 9999},
            "right": {"type": "int", "default": 0, "min": 0, "max": 9999},
            "top": {"type": "int", "default": 0, "min": 0, "max": 9999},
            "bottom": {"type": "int", "default": 0, "min": 0, "max": 9999},
        },
    },
    "rotate": {
        "mlt_service": "affine",
        "category": "effect",
        "params": {
            "angle": {"type": "float", "default": 0.0, "min": -360.0, "max": 360.0},
        },
    },
    "speed": {
        "mlt_service": "timewarp",
        "category": "effect",
        "params": {
            "speed": {"type": "float", "default": 1.0, "min": 0.01, "max": 100.0},
        },
    },
    "chroma_key": {
        "mlt_service": "frei0r.select0r",
        "category": "keying",
        "params": {
            "color": {"type": "str", "default": "#00ff00"},
            "variance": {"type": "float", "default": 0.15, "min": 0.0, "max": 1.0},
        },
    },
}


def _validate_filter_params(filter_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and fill defaults for filter parameters."""
    spec = FILTER_REGISTRY[filter_name]
    param_specs = spec["params"]

    unknown = set(params.keys()) - set(param_specs.keys())
    if unknown:
        raise ValueError(
            f"Unknown parameters for '{filter_name}': {', '.join(unknown)}. "
            f"Valid: {', '.join(param_specs.keys())}"
        )

    result = {}
    for pname, pspec in param_specs.items():
        value = params.get(pname, pspec["default"])
        ptype = pspec["type"]

        if ptype == "float":
            value = float(value)
            if value < pspec["min"] or value > pspec["max"]:
                raise ValueError(
                    f"Parameter '{pname}' value {value} out of range "
                    f"[{pspec['min']}, {pspec['max']}]."
                )
        elif ptype == "int":
            value = int(value)
            if value < pspec["min"] or value > pspec["max"]:
                raise ValueError(
                    f"Parameter '{pname}' value {value} out of range "
                    f"[{pspec['min']}, {pspec['max']}]."
                )
        elif ptype == "str":
            value = str(value)

        result[pname] = value

    return result


def add_filter(
    project: Dict[str, Any],
    track_id: int,
    clip_index: int,
    filter_name: str,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Add a filter to a clip on a track."""
    if filter_name not in FILTER_REGISTRY:
        raise ValueError(
            f"Unknown filter: {filter_name}. "
            f"Available: {', '.join(FILTER_REGISTRY.keys())}"
        )

    tracks = project.get("tracks", [])
    track = None
    for t in tracks:
        if t["id"] == track_id:
            track = t
            break
    if track is None:
        raise ValueError(f"Track not found: {track_id}")

    clips = track.get("clips", [])
    if clip_index < 0 or clip_index >= len(clips):
        raise IndexError(f"Clip index {clip_index} out of range (0-{len(clips)-1}).")

    validated_params = _validate_filter_params(filter_name, params or {})

    spec = FILTER_REGISTRY[filter_name]
    filter_entry = {
        "name": filter_name,
        "mlt_service": spec["mlt_service"],
        "params": validated_params,
        "enabled": True,
    }

    clips[clip_index].setdefault("filters", []).append(filter_entry)
    return filter_entry


def remove_filter(
    project: Dict[str, Any],
    track_id: int,
    clip_index: int,
    filter_index: int,
) -> Dict[str, Any]:
    """Remove a filter from a clip."""
    tracks = project.get("tracks", [])
    track = None
    for t in tracks:
        if t["id"] == track_id:
            track = t
            break
    if track is None:
        raise ValueError(f"Track not found: {track_id}")

    clips = track.get("clips", [])
    if clip_index < 0 or clip_index >= len(clips):
        raise IndexError(f"Clip index {clip_index} out of range.")

    filters = clips[clip_index].get("filters", [])
    if filter_index < 0 or filter_index >= len(filters):
        raise IndexError(f"Filter index {filter_index} out of range (0-{len(filters)-1}).")

    return filters.pop(filter_index)


def set_filter_param(
    project: Dict[str, Any],
    track_id: int,
    clip_index: int,
    filter_index: int,
    param_name: str,
    value: Any,
) -> Dict[str, Any]:
    """Set a parameter on a filter."""
    tracks = project.get("tracks", [])
    track = None
    for t in tracks:
        if t["id"] == track_id:
            track = t
            break
    if track is None:
        raise ValueError(f"Track not found: {track_id}")

    clips = track.get("clips", [])
    if clip_index < 0 or clip_index >= len(clips):
        raise IndexError(f"Clip index {clip_index} out of range.")

    filters = clips[clip_index].get("filters", [])
    if filter_index < 0 or filter_index >= len(filters):
        raise IndexError(f"Filter index {filter_index} out of range.")

    filt = filters[filter_index]
    fname = filt["name"]
    spec = FILTER_REGISTRY.get(fname, {})
    param_specs = spec.get("params", {})

    if param_name not in param_specs:
        raise ValueError(
            f"Unknown parameter '{param_name}' for filter '{fname}'. "
            f"Valid: {', '.join(param_specs.keys())}"
        )

    pspec = param_specs[param_name]
    ptype = pspec["type"]
    if ptype == "float":
        value = float(value)
        if value < pspec["min"] or value > pspec["max"]:
            raise ValueError(
                f"Parameter '{param_name}' value {value} out of range "
                f"[{pspec['min']}, {pspec['max']}]."
            )
    elif ptype == "int":
        value = int(value)
        if value < pspec["min"] or value > pspec["max"]:
            raise ValueError(
                f"Parameter '{param_name}' value {value} out of range "
                f"[{pspec['min']}, {pspec['max']}]."
            )

    filt["params"][param_name] = value
    return dict(filt)


def list_filters(
    project: Dict[str, Any],
    track_id: int,
    clip_index: int,
) -> List[Dict[str, Any]]:
    """List filters on a clip."""
    tracks = project.get("tracks", [])
    track = None
    for t in tracks:
        if t["id"] == track_id:
            track = t
            break
    if track is None:
        raise ValueError(f"Track not found: {track_id}")

    clips = track.get("clips", [])
    if clip_index < 0 or clip_index >= len(clips):
        raise IndexError(f"Clip index {clip_index} out of range.")

    return [
        {
            "index": i,
            "name": f["name"],
            "mlt_service": f.get("mlt_service", ""),
            "params": f.get("params", {}),
            "enabled": f.get("enabled", True),
        }
        for i, f in enumerate(clips[clip_index].get("filters", []))
    ]


def list_available(category: Optional[str] = None) -> List[Dict[str, Any]]:
    """List all available filters."""
    result = []
    for name, spec in FILTER_REGISTRY.items():
        if category and spec.get("category") != category:
            continue
        result.append({
            "name": name,
            "mlt_service": spec["mlt_service"],
            "category": spec.get("category", ""),
            "params": {
                k: {"type": v["type"], "default": v["default"]}
                for k, v in spec["params"].items()
            },
        })
    return result
