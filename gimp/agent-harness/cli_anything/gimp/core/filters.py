"""GIMP CLI - Filter registry and application module."""

from typing import Dict, Any, List, Optional, Tuple


# Filter registry: maps CLI name -> implementation details
FILTER_REGISTRY = {
    # Image Adjustments
    "brightness": {
        "category": "adjustment",
        "description": "Adjust image brightness",
        "params": {"factor": {"type": "float", "default": 1.0, "min": 0.0, "max": 10.0,
                              "description": "1.0=neutral, >1=brighter, <1=darker"}},
        "engine": "pillow_enhance",
        "pillow_class": "Brightness",
    },
    "contrast": {
        "category": "adjustment",
        "description": "Adjust image contrast",
        "params": {"factor": {"type": "float", "default": 1.0, "min": 0.0, "max": 10.0,
                              "description": "1.0=neutral, >1=more contrast"}},
        "engine": "pillow_enhance",
        "pillow_class": "Contrast",
    },
    "saturation": {
        "category": "adjustment",
        "description": "Adjust color saturation",
        "params": {"factor": {"type": "float", "default": 1.0, "min": 0.0, "max": 10.0,
                              "description": "1.0=neutral, 0=grayscale, >1=vivid"}},
        "engine": "pillow_enhance",
        "pillow_class": "Color",
    },
    "sharpness": {
        "category": "adjustment",
        "description": "Adjust image sharpness",
        "params": {"factor": {"type": "float", "default": 1.0, "min": 0.0, "max": 10.0,
                              "description": "1.0=neutral, >1=sharper, 0=blurred"}},
        "engine": "pillow_enhance",
        "pillow_class": "Sharpness",
    },
    "autocontrast": {
        "category": "adjustment",
        "description": "Automatic contrast stretch",
        "params": {"cutoff": {"type": "float", "default": 0.0, "min": 0.0, "max": 49.0,
                              "description": "Percent of lightest/darkest pixels to clip"}},
        "engine": "pillow_ops",
        "pillow_func": "autocontrast",
    },
    "equalize": {
        "category": "adjustment",
        "description": "Equalize histogram",
        "params": {},
        "engine": "pillow_ops",
        "pillow_func": "equalize",
    },
    "invert": {
        "category": "adjustment",
        "description": "Invert colors (negative)",
        "params": {},
        "engine": "pillow_ops",
        "pillow_func": "invert",
    },
    "posterize": {
        "category": "adjustment",
        "description": "Reduce color depth (posterize)",
        "params": {"bits": {"type": "int", "default": 4, "min": 1, "max": 8,
                            "description": "Bits per channel (fewer = more posterized)"}},
        "engine": "pillow_ops",
        "pillow_func": "posterize",
    },
    "solarize": {
        "category": "adjustment",
        "description": "Solarize effect",
        "params": {"threshold": {"type": "int", "default": 128, "min": 0, "max": 255,
                                  "description": "Threshold for inversion"}},
        "engine": "pillow_ops",
        "pillow_func": "solarize",
    },
    "grayscale": {
        "category": "adjustment",
        "description": "Convert to grayscale",
        "params": {},
        "engine": "pillow_ops",
        "pillow_func": "grayscale",
    },
    "sepia": {
        "category": "adjustment",
        "description": "Apply sepia tone",
        "params": {"strength": {"type": "float", "default": 0.8, "min": 0.0, "max": 1.0,
                                "description": "Sepia effect strength"}},
        "engine": "custom",
        "custom_func": "apply_sepia",
    },
    # Blur & Sharpen
    "gaussian_blur": {
        "category": "blur",
        "description": "Gaussian blur",
        "params": {"radius": {"type": "float", "default": 2.0, "min": 0.1, "max": 100.0,
                              "description": "Blur radius in pixels"}},
        "engine": "pillow_filter",
        "pillow_filter": "GaussianBlur",
    },
    "box_blur": {
        "category": "blur",
        "description": "Box blur (uniform average)",
        "params": {"radius": {"type": "float", "default": 2.0, "min": 0.1, "max": 100.0,
                              "description": "Blur radius in pixels"}},
        "engine": "pillow_filter",
        "pillow_filter": "BoxBlur",
    },
    "unsharp_mask": {
        "category": "blur",
        "description": "Unsharp mask (sharpen via blur)",
        "params": {
            "radius": {"type": "float", "default": 2.0, "min": 0.1, "max": 100.0,
                       "description": "Blur radius"},
            "percent": {"type": "int", "default": 150, "min": 1, "max": 500,
                        "description": "Sharpening strength percent"},
            "threshold": {"type": "int", "default": 3, "min": 0, "max": 255,
                          "description": "Minimum brightness change to sharpen"},
        },
        "engine": "pillow_filter",
        "pillow_filter": "UnsharpMask",
    },
    "smooth": {
        "category": "blur",
        "description": "Smooth (reduce noise)",
        "params": {},
        "engine": "pillow_filter",
        "pillow_filter": "SMOOTH_MORE",
    },
    # Stylize
    "find_edges": {
        "category": "stylize",
        "description": "Edge detection",
        "params": {},
        "engine": "pillow_filter",
        "pillow_filter": "FIND_EDGES",
    },
    "emboss": {
        "category": "stylize",
        "description": "Emboss effect",
        "params": {},
        "engine": "pillow_filter",
        "pillow_filter": "EMBOSS",
    },
    "contour": {
        "category": "stylize",
        "description": "Contour tracing",
        "params": {},
        "engine": "pillow_filter",
        "pillow_filter": "CONTOUR",
    },
    "detail": {
        "category": "stylize",
        "description": "Enhance detail",
        "params": {},
        "engine": "pillow_filter",
        "pillow_filter": "DETAIL",
    },
    # Transform (applied at render time)
    "rotate": {
        "category": "transform",
        "description": "Rotate layer",
        "params": {
            "angle": {"type": "float", "default": 0.0, "min": -360.0, "max": 360.0,
                      "description": "Rotation angle in degrees"},
            "expand": {"type": "bool", "default": True,
                       "description": "Expand canvas to fit rotated image"},
        },
        "engine": "pillow_transform",
        "pillow_method": "rotate",
    },
    "flip_h": {
        "category": "transform",
        "description": "Flip horizontally",
        "params": {},
        "engine": "pillow_transform",
        "pillow_method": "flip_h",
    },
    "flip_v": {
        "category": "transform",
        "description": "Flip vertically",
        "params": {},
        "engine": "pillow_transform",
        "pillow_method": "flip_v",
    },
    "resize": {
        "category": "transform",
        "description": "Resize layer",
        "params": {
            "width": {"type": "int", "default": 0, "min": 1, "max": 65535,
                      "description": "Target width"},
            "height": {"type": "int", "default": 0, "min": 1, "max": 65535,
                       "description": "Target height"},
            "resample": {"type": "str", "default": "lanczos",
                         "description": "Resampling: nearest, bilinear, bicubic, lanczos"},
        },
        "engine": "pillow_transform",
        "pillow_method": "resize",
    },
    "crop": {
        "category": "transform",
        "description": "Crop layer",
        "params": {
            "left": {"type": "int", "default": 0, "min": 0, "max": 65535},
            "top": {"type": "int", "default": 0, "min": 0, "max": 65535},
            "right": {"type": "int", "default": 0, "min": 0, "max": 65535},
            "bottom": {"type": "int", "default": 0, "min": 0, "max": 65535},
        },
        "engine": "pillow_transform",
        "pillow_method": "crop",
    },
}


def list_available(category: Optional[str] = None) -> List[Dict[str, Any]]:
    """List available filters, optionally filtered by category."""
    result = []
    for name, info in FILTER_REGISTRY.items():
        if category and info["category"] != category:
            continue
        result.append({
            "name": name,
            "category": info["category"],
            "description": info["description"],
            "param_count": len(info["params"]),
        })
    return result


def get_filter_info(name: str) -> Dict[str, Any]:
    """Get detailed info about a filter."""
    if name not in FILTER_REGISTRY:
        raise ValueError(f"Unknown filter: {name}. Use 'filter list-available' to see options.")
    info = FILTER_REGISTRY[name]
    return {
        "name": name,
        "category": info["category"],
        "description": info["description"],
        "params": info["params"],
        "engine": info["engine"],
    }


def validate_params(name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and fill defaults for filter parameters."""
    if name not in FILTER_REGISTRY:
        raise ValueError(f"Unknown filter: {name}")

    spec = FILTER_REGISTRY[name]["params"]
    result = {}

    for pname, pspec in spec.items():
        if pname in params:
            val = params[pname]
            ptype = pspec["type"]
            if ptype == "float":
                val = float(val)
                if "min" in pspec and val < pspec["min"]:
                    raise ValueError(f"Parameter '{pname}' minimum is {pspec['min']}, got {val}")
                if "max" in pspec and val > pspec["max"]:
                    raise ValueError(f"Parameter '{pname}' maximum is {pspec['max']}, got {val}")
            elif ptype == "int":
                val = int(val)
                if "min" in pspec and val < pspec["min"]:
                    raise ValueError(f"Parameter '{pname}' minimum is {pspec['min']}, got {val}")
                if "max" in pspec and val > pspec["max"]:
                    raise ValueError(f"Parameter '{pname}' maximum is {pspec['max']}, got {val}")
            elif ptype == "bool":
                val = str(val).lower() in ("true", "1", "yes")
            elif ptype == "str":
                val = str(val)
            result[pname] = val
        else:
            result[pname] = pspec.get("default")

    # Warn about unknown params
    unknown = set(params.keys()) - set(spec.keys())
    if unknown:
        raise ValueError(f"Unknown parameters for filter '{name}': {unknown}")

    return result


def add_filter(
    project: Dict[str, Any],
    name: str,
    layer_index: int = 0,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Add a filter to a layer."""
    layers = project.get("layers", [])
    if layer_index < 0 or layer_index >= len(layers):
        raise IndexError(f"Layer index {layer_index} out of range (0-{len(layers)-1})")

    if name not in FILTER_REGISTRY:
        raise ValueError(f"Unknown filter: {name}")

    validated = validate_params(name, params or {})

    filter_entry = {
        "name": name,
        "params": validated,
    }

    layer = layers[layer_index]
    if "filters" not in layer:
        layer["filters"] = []
    layer["filters"].append(filter_entry)

    return filter_entry


def remove_filter(
    project: Dict[str, Any],
    filter_index: int,
    layer_index: int = 0,
) -> Dict[str, Any]:
    """Remove a filter from a layer by index."""
    layers = project.get("layers", [])
    if layer_index < 0 or layer_index >= len(layers):
        raise IndexError(f"Layer index {layer_index} out of range")

    layer = layers[layer_index]
    filters = layer.get("filters", [])
    if filter_index < 0 or filter_index >= len(filters):
        raise IndexError(f"Filter index {filter_index} out of range (0-{len(filters)-1})")

    return filters.pop(filter_index)


def set_filter_param(
    project: Dict[str, Any],
    filter_index: int,
    param: str,
    value: Any,
    layer_index: int = 0,
) -> None:
    """Set a filter parameter value."""
    layers = project.get("layers", [])
    if layer_index < 0 or layer_index >= len(layers):
        raise IndexError(f"Layer index {layer_index} out of range")

    layer = layers[layer_index]
    filters = layer.get("filters", [])
    if filter_index < 0 or filter_index >= len(filters):
        raise IndexError(f"Filter index {filter_index} out of range")

    filt = filters[filter_index]
    name = filt["name"]
    spec = FILTER_REGISTRY[name]["params"]

    if param not in spec:
        raise ValueError(f"Unknown parameter '{param}' for filter '{name}'. Valid: {list(spec.keys())}")

    # Validate using the spec
    test_params = dict(filt["params"])
    test_params[param] = value
    validated = validate_params(name, test_params)
    filt["params"] = validated


def list_filters(
    project: Dict[str, Any],
    layer_index: int = 0,
) -> List[Dict[str, Any]]:
    """List filters on a layer."""
    layers = project.get("layers", [])
    if layer_index < 0 or layer_index >= len(layers):
        raise IndexError(f"Layer index {layer_index} out of range")

    layer = layers[layer_index]
    result = []
    for i, f in enumerate(layer.get("filters", [])):
        result.append({
            "index": i,
            "name": f["name"],
            "params": f["params"],
            "category": FILTER_REGISTRY.get(f["name"], {}).get("category", "unknown"),
        })
    return result
