"""OBS Studio CLI - JSON helpers and utilities."""

import json
import os
import copy
from typing import Dict, Any, List, Optional


def generate_id(items: List[Dict[str, Any]]) -> int:
    """Generate the next unique ID for a list of items."""
    if not items:
        return 0
    return max(item.get("id", 0) for item in items) + 1


def unique_name(name: str, items: List[Dict[str, Any]], key: str = "name") -> str:
    """Ensure a unique name among existing items."""
    existing = {item.get(key, "") for item in items}
    if name not in existing:
        return name
    i = 1
    while f"{name}.{i:03d}" in existing:
        i += 1
    return f"{name}.{i:03d}"


def validate_range(value: float, min_val: float, max_val: float, name: str) -> float:
    """Validate that a value is within range."""
    val = float(value)
    if val < min_val or val > max_val:
        raise ValueError(f"{name} must be between {min_val} and {max_val}, got {val}")
    return val


def validate_position(pos: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalize a position dict."""
    return {
        "x": float(pos.get("x", 0)),
        "y": float(pos.get("y", 0)),
    }


def validate_size(size: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalize a size dict."""
    w = int(size.get("width", 1920))
    h = int(size.get("height", 1080))
    if w < 1:
        raise ValueError(f"Width must be positive, got {w}")
    if h < 1:
        raise ValueError(f"Height must be positive, got {h}")
    return {"width": w, "height": h}


def validate_crop(crop: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalize a crop dict."""
    result = {}
    for key in ("top", "bottom", "left", "right"):
        val = int(crop.get(key, 0))
        if val < 0:
            raise ValueError(f"Crop {key} must be non-negative, got {val}")
        result[key] = val
    return result


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge two dicts, override takes precedence."""
    result = copy.deepcopy(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = copy.deepcopy(v)
    return result


def load_json(path: str) -> Dict[str, Any]:
    """Load a JSON file."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    with open(path, "r") as f:
        return json.load(f)


def save_json(data: Dict[str, Any], path: str) -> str:
    """Save data to a JSON file."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    return path


def find_by_name(items: List[Dict[str, Any]], name: str) -> Optional[int]:
    """Find an item index by name."""
    for i, item in enumerate(items):
        if item.get("name") == name:
            return i
    return None


def get_item(items: List[Dict[str, Any]], index: int, label: str = "item") -> Dict[str, Any]:
    """Get an item by index with bounds checking."""
    if not items:
        raise ValueError(f"No {label}s exist.")
    if index < 0 or index >= len(items):
        raise IndexError(f"{label} index {index} out of range (0-{len(items) - 1})")
    return items[index]
