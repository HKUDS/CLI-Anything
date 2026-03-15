"""GIMP CLI - Layer management module."""

import os
import copy
from typing import Dict, Any, List, Optional


# Valid blend modes
BLEND_MODES = [
    "normal", "multiply", "screen", "overlay", "soft_light", "hard_light",
    "difference", "darken", "lighten", "color_dodge", "color_burn",
    "addition", "subtract", "grain_merge", "grain_extract",
]


def add_layer(
    project: Dict[str, Any],
    name: str = "New Layer",
    layer_type: str = "image",
    source: Optional[str] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    fill: str = "transparent",
    opacity: float = 1.0,
    blend_mode: str = "normal",
    position: Optional[int] = None,
    offset_x: int = 0,
    offset_y: int = 0,
) -> Dict[str, Any]:
    """Add a new layer to the project.

    Args:
        project: The project dict
        name: Layer name
        layer_type: "image", "text", "solid"
        source: Path to source image file (for image layers)
        width: Layer width (defaults to canvas width)
        height: Layer height (defaults to canvas height)
        fill: Fill type for new layers: "transparent", "white", "black", or hex color
        opacity: Layer opacity (0.0-1.0)
        blend_mode: Compositing blend mode
        position: Insert position (0=top, None=top)
        offset_x: Horizontal offset from canvas origin
        offset_y: Vertical offset from canvas origin

    Returns:
        The new layer dict
    """
    if blend_mode not in BLEND_MODES:
        raise ValueError(f"Invalid blend mode '{blend_mode}'. Valid: {BLEND_MODES}")
    if not 0.0 <= opacity <= 1.0:
        raise ValueError(f"Opacity must be 0.0-1.0, got {opacity}")
    if layer_type not in ("image", "text", "solid"):
        raise ValueError(f"Invalid layer type '{layer_type}'. Use: image, text, solid")
    if layer_type == "image" and source and not os.path.exists(source):
        raise FileNotFoundError(f"Source image not found: {source}")

    canvas = project["canvas"]
    layer_w = width or canvas["width"]
    layer_h = height or canvas["height"]

    # Generate next layer ID
    existing_ids = [l.get("id", 0) for l in project.get("layers", [])]
    next_id = max(existing_ids, default=-1) + 1

    layer = {
        "id": next_id,
        "name": name,
        "type": layer_type,
        "width": layer_w,
        "height": layer_h,
        "visible": True,
        "opacity": opacity,
        "blend_mode": blend_mode,
        "offset_x": offset_x,
        "offset_y": offset_y,
        "filters": [],
    }

    if layer_type == "image":
        layer["source"] = source
        layer["fill"] = fill if not source else None
    elif layer_type == "solid":
        layer["fill"] = fill
    elif layer_type == "text":
        layer["text"] = ""
        layer["font"] = "Arial"
        layer["font_size"] = 24
        layer["color"] = "#000000"

    if "layers" not in project:
        project["layers"] = []

    if position is not None:
        position = max(0, min(position, len(project["layers"])))
        project["layers"].insert(position, layer)
    else:
        project["layers"].insert(0, layer)  # Top of stack

    return layer


def add_from_file(
    project: Dict[str, Any],
    path: str,
    name: Optional[str] = None,
    position: Optional[int] = None,
    opacity: float = 1.0,
    blend_mode: str = "normal",
) -> Dict[str, Any]:
    """Add a layer from an image file."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Image file not found: {path}")

    layer_name = name or os.path.basename(path)

    # Try to get image dimensions
    try:
        from PIL import Image
        with Image.open(path) as img:
            w, h = img.size
    except Exception as e:
        w = project["canvas"]["width"]
        h = project["canvas"]["height"]

    return add_layer(
        project,
        name=layer_name,
        layer_type="image",
        source=os.path.abspath(path),
        width=w,
        height=h,
        opacity=opacity,
        blend_mode=blend_mode,
        position=position,
    )


def remove_layer(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Remove a layer by index."""
    layers = project.get("layers", [])
    if not layers:
        raise ValueError("No layers to remove")
    if index < 0 or index >= len(layers):
        raise IndexError(f"Layer index {index} out of range (0-{len(layers)-1})")
    removed = layers.pop(index)
    return removed


def duplicate_layer(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Duplicate a layer."""
    layers = project.get("layers", [])
    if index < 0 or index >= len(layers):
        raise IndexError(f"Layer index {index} out of range (0-{len(layers)-1})")

    original = layers[index]
    dup = copy.deepcopy(original)
    existing_ids = [l.get("id", 0) for l in layers]
    dup["id"] = max(existing_ids, default=-1) + 1
    dup["name"] = f"{original['name']} copy"
    layers.insert(index, dup)
    return dup


def move_layer(project: Dict[str, Any], index: int, to: int) -> None:
    """Move a layer to a new position."""
    layers = project.get("layers", [])
    if index < 0 or index >= len(layers):
        raise IndexError(f"Source layer index {index} out of range")
    to = max(0, min(to, len(layers) - 1))
    layer = layers.pop(index)
    layers.insert(to, layer)


def set_layer_property(
    project: Dict[str, Any], index: int, prop: str, value: Any
) -> None:
    """Set a layer property."""
    layers = project.get("layers", [])
    if index < 0 or index >= len(layers):
        raise IndexError(f"Layer index {index} out of range")

    layer = layers[index]

    if prop == "opacity":
        value = float(value)
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"Opacity must be 0.0-1.0, got {value}")
        layer["opacity"] = value
    elif prop == "visible":
        layer["visible"] = str(value).lower() in ("true", "1", "yes")
    elif prop == "blend_mode" or prop == "mode":
        if value not in BLEND_MODES:
            raise ValueError(f"Invalid blend mode '{value}'. Valid: {BLEND_MODES}")
        layer["blend_mode"] = value
    elif prop == "name":
        layer["name"] = str(value)
    elif prop == "offset_x":
        layer["offset_x"] = int(value)
    elif prop == "offset_y":
        layer["offset_y"] = int(value)
    else:
        raise ValueError(f"Unknown property: {prop}. Valid: name, opacity, visible, mode, offset_x, offset_y")


def get_layer(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Get a layer by index."""
    layers = project.get("layers", [])
    if index < 0 or index >= len(layers):
        raise IndexError(f"Layer index {index} out of range (0-{len(layers)-1})")
    return layers[index]


def list_layers(project: Dict[str, Any]) -> List[Dict[str, Any]]:
    """List all layers with summary info."""
    result = []
    for i, l in enumerate(project.get("layers", [])):
        result.append({
            "index": i,
            "id": l.get("id", i),
            "name": l.get("name", f"Layer {i}"),
            "type": l.get("type", "image"),
            "visible": l.get("visible", True),
            "opacity": l.get("opacity", 1.0),
            "blend_mode": l.get("blend_mode", "normal"),
            "size": f"{l.get('width', '?')}x{l.get('height', '?')}",
            "offset": f"({l.get('offset_x', 0)}, {l.get('offset_y', 0)})",
            "filter_count": len(l.get("filters", [])),
        })
    return result


def flatten_layers(project: Dict[str, Any]) -> None:
    """Mark project for flattening (merge all visible layers into one)."""
    visible = [l for l in project.get("layers", []) if l.get("visible", True)]
    if not visible:
        raise ValueError("No visible layers to flatten")
    # Create a single flattened layer marker
    project["_flatten_pending"] = True


def merge_down(project: Dict[str, Any], index: int) -> None:
    """Mark layers for merging (layer at index merges into the one below)."""
    layers = project.get("layers", [])
    if index < 0 or index >= len(layers):
        raise IndexError(f"Layer index {index} out of range")
    if index >= len(layers) - 1:
        raise ValueError("Cannot merge down the bottom layer")
    project["_merge_down_pending"] = index
