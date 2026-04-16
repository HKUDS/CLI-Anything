"""OBS Studio CLI - Filter management."""

import copy
from typing import Dict, Any, List, Optional
from cli_anything.obs_studio.utils.obs_utils import generate_id, unique_name, get_item, validate_range


FILTER_TYPES = {
    "color_correction": {
        "label": "Color Correction",
        "category": "video",
        "params": {
            "gamma": {"type": "float", "default": 0.0, "min": -3.0, "max": 3.0},
            "contrast": {"type": "float", "default": 0.0, "min": -4.0, "max": 4.0},
            "brightness": {"type": "float", "default": 0.0, "min": -1.0, "max": 1.0},
            "saturation": {"type": "float", "default": 0.0, "min": -1.0, "max": 5.0},
            "hue_shift": {"type": "float", "default": 0.0, "min": -180.0, "max": 180.0},
            "opacity": {"type": "float", "default": 1.0, "min": 0.0, "max": 1.0},
        },
    },
    "chroma_key": {
        "label": "Chroma Key",
        "category": "video",
        "params": {
            "key_color_type": {"type": "str", "default": "green", "values": ["green", "blue", "magenta", "custom"]},
            "similarity": {"type": "int", "default": 400, "min": 1, "max": 1000},
            "smoothness": {"type": "int", "default": 80, "min": 1, "max": 1000},
            "spill": {"type": "int", "default": 100, "min": 1, "max": 1000},
        },
    },
    "color_key": {
        "label": "Color Key",
        "category": "video",
        "params": {
            "key_color": {"type": "str", "default": "#00FF00"},
            "similarity": {"type": "int", "default": 400, "min": 1, "max": 1000},
            "smoothness": {"type": "int", "default": 80, "min": 1, "max": 1000},
        },
    },
    "lut": {
        "label": "Apply LUT",
        "category": "video",
        "params": {
            "path": {"type": "str", "default": ""},
            "amount": {"type": "float", "default": 1.0, "min": 0.0, "max": 1.0},
        },
    },
    "image_mask": {
        "label": "Image Mask/Blend",
        "category": "video",
        "params": {
            "path": {"type": "str", "default": ""},
            "type": {"type": "str", "default": "alpha", "values": ["alpha", "blend"]},
        },
    },
    "crop_pad": {
        "label": "Crop/Pad",
        "category": "video",
        "params": {
            "top": {"type": "int", "default": 0, "min": 0, "max": 8192},
            "bottom": {"type": "int", "default": 0, "min": 0, "max": 8192},
            "left": {"type": "int", "default": 0, "min": 0, "max": 8192},
            "right": {"type": "int", "default": 0, "min": 0, "max": 8192},
        },
    },
    "scroll": {
        "label": "Scroll",
        "category": "video",
        "params": {
            "speed_x": {"type": "float", "default": 0.0, "min": -5000.0, "max": 5000.0},
            "speed_y": {"type": "float", "default": 0.0, "min": -5000.0, "max": 5000.0},
            "loop": {"type": "bool", "default": True},
        },
    },
    "sharpen": {
        "label": "Sharpen",
        "category": "video",
        "params": {
            "sharpness": {"type": "float", "default": 0.08, "min": 0.0, "max": 1.0},
        },
    },
    "noise_suppress": {
        "label": "Noise Suppression",
        "category": "audio",
        "params": {
            "method": {"type": "str", "default": "rnnoise", "values": ["rnnoise", "speex", "nvafx"]},
            "suppress_level": {"type": "int", "default": -30, "min": -60, "max": 0},
        },
    },
    "gain": {
        "label": "Gain",
        "category": "audio",
        "params": {
            "db": {"type": "float", "default": 0.0, "min": -30.0, "max": 30.0},
        },
    },
    "compressor": {
        "label": "Compressor",
        "category": "audio",
        "params": {
            "ratio": {"type": "float", "default": 10.0, "min": 1.0, "max": 32.0},
            "threshold": {"type": "float", "default": -18.0, "min": -60.0, "max": 0.0},
            "attack": {"type": "int", "default": 6, "min": 1, "max": 500},
            "release": {"type": "int", "default": 60, "min": 1, "max": 1000},
            "output_gain": {"type": "float", "default": 0.0, "min": -30.0, "max": 30.0},
        },
    },
    "noise_gate": {
        "label": "Noise Gate",
        "category": "audio",
        "params": {
            "open_threshold": {"type": "float", "default": -26.0, "min": -96.0, "max": 0.0},
            "close_threshold": {"type": "float", "default": -32.0, "min": -96.0, "max": 0.0},
            "attack": {"type": "int", "default": 25, "min": 1, "max": 500},
            "hold": {"type": "int", "default": 200, "min": 1, "max": 1000},
            "release": {"type": "int", "default": 150, "min": 1, "max": 1000},
        },
    },
    "limiter": {
        "label": "Limiter",
        "category": "audio",
        "params": {
            "threshold": {"type": "float", "default": -6.0, "min": -60.0, "max": 0.0},
            "release": {"type": "int", "default": 60, "min": 1, "max": 1000},
        },
    },
}


def _get_source_filters(project: Dict[str, Any], source_index: int, scene_index: int = 0) -> List[Dict[str, Any]]:
    """Get the filter list for a source."""
    scenes = project.get("scenes", [])
    scene = get_item(scenes, scene_index, "scene")
    sources = scene.get("sources", [])
    source = get_item(sources, source_index, "source")
    return source.setdefault("filters", [])


def _validate_filter_params(filter_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and fill defaults for filter parameters."""
    spec = FILTER_TYPES[filter_type]
    param_specs = spec["params"]

    # Check for unknown params
    unknown = set(params.keys()) - set(param_specs.keys())
    if unknown:
        raise ValueError(f"Unknown parameters for {filter_type}: {', '.join(unknown)}")

    result = {}
    for pname, pspec in param_specs.items():
        if pname in params:
            val = params[pname]
            ptype = pspec["type"]
            if ptype == "float":
                val = float(val)
                if "min" in pspec and "max" in pspec:
                    val = validate_range(val, pspec["min"], pspec["max"], pname)
            elif ptype == "int":
                val = int(val)
                if "min" in pspec and "max" in pspec:
                    if val < pspec["min"] or val > pspec["max"]:
                        raise ValueError(f"{pname} must be between {pspec['min']} and {pspec['max']}, got {val}")
            elif ptype == "str":
                val = str(val)
                if "values" in pspec and val not in pspec["values"]:
                    raise ValueError(f"{pname} must be one of {pspec['values']}, got {val}")
            elif ptype == "bool":
                if isinstance(val, str):
                    val = val.lower() in ("true", "1", "yes")
                val = bool(val)
            result[pname] = val
        else:
            result[pname] = pspec["default"]
    return result


def add_filter(
    project: Dict[str, Any],
    filter_type: str,
    source_index: int,
    scene_index: int = 0,
    name: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Add a filter to a source."""
    if filter_type not in FILTER_TYPES:
        raise ValueError(
            f"Unknown filter type: {filter_type}. Valid: {', '.join(sorted(FILTER_TYPES.keys()))}"
        )

    filters = _get_source_filters(project, source_index, scene_index)
    if name is None:
        name = FILTER_TYPES[filter_type]["label"]
    name = unique_name(name, filters)

    validated_params = _validate_filter_params(filter_type, params or {})

    filt = {
        "id": generate_id(filters),
        "name": name,
        "type": filter_type,
        "enabled": True,
        "params": validated_params,
    }
    filters.append(filt)
    return filt


def remove_filter(
    project: Dict[str, Any],
    filter_index: int,
    source_index: int,
    scene_index: int = 0,
) -> Dict[str, Any]:
    """Remove a filter from a source."""
    filters = _get_source_filters(project, source_index, scene_index)
    filt = get_item(filters, filter_index, "filter")
    return filters.pop(filter_index)


def set_filter_param(
    project: Dict[str, Any],
    filter_index: int,
    param: str,
    value: Any,
    source_index: int,
    scene_index: int = 0,
) -> Dict[str, Any]:
    """Set a parameter on a filter."""
    filters = _get_source_filters(project, source_index, scene_index)
    filt = get_item(filters, filter_index, "filter")

    filter_type = filt["type"]
    spec = FILTER_TYPES.get(filter_type)
    if not spec:
        raise ValueError(f"Unknown filter type: {filter_type}")

    param_specs = spec["params"]
    if param not in param_specs:
        raise ValueError(f"Unknown parameter '{param}' for filter type '{filter_type}'. Valid: {', '.join(param_specs.keys())}")

    # Validate the single param
    validated = _validate_filter_params(filter_type, {param: value})
    filt["params"][param] = validated[param]
    return filt


def list_filters(
    project: Dict[str, Any],
    source_index: int,
    scene_index: int = 0,
) -> List[Dict[str, Any]]:
    """List all filters on a source."""
    filters = _get_source_filters(project, source_index, scene_index)
    return [
        {
            "index": i,
            "id": f.get("id", i),
            "name": f.get("name", f"Filter {i}"),
            "type": f.get("type", "unknown"),
            "enabled": f.get("enabled", True),
        }
        for i, f in enumerate(filters)
    ]


def list_available_filters(category: Optional[str] = None) -> List[Dict[str, Any]]:
    """List all available filter types."""
    result = []
    for name, spec in FILTER_TYPES.items():
        if category and spec.get("category") != category:
            continue
        result.append({
            "name": name,
            "label": spec["label"],
            "category": spec["category"],
            "params": list(spec["params"].keys()),
        })
    return result
