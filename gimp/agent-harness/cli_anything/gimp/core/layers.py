"""GIMP CLI - Layer management module."""

import os
import copy
import struct
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

    dims = _read_image_dimensions(path)
    if dims:
        w, h = dims
    else:
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


def _read_image_dimensions(path: str) -> Optional[tuple]:
    """Read image width/height from file headers without external dependencies.

    Supports PNG, JPEG, GIF, BMP, WEBP, and TIFF.
    Returns (width, height) or None if the format is unrecognised.
    """
    try:
        with open(path, "rb") as f:
            header = f.read(32)

        if len(header) < 8:
            return None

        # PNG: 8-byte signature, then IHDR chunk with w/h at bytes 16-24
        if header[:8] == b"\x89PNG\r\n\x1a\n":
            w, h = struct.unpack(">II", header[16:24])
            return (w, h)

        # GIF: signature + logical screen descriptor
        if header[:6] in (b"GIF87a", b"GIF89a"):
            w, h = struct.unpack("<HH", header[6:10])
            return (w, h)

        # BMP: 'BM' header, w/h as signed int32 at bytes 18-26
        if header[:2] == b"BM" and len(header) >= 26:
            w, h = struct.unpack("<ii", header[18:26])
            return (w, abs(h))

        # TIFF: byte-order mark then magic 42
        if header[:4] in (b"II\x2a\x00", b"MM\x00\x2a"):
            return _read_tiff_dimensions(path, header)

        # JPEG: starts with SOI marker 0xFFD8
        if header[:2] == b"\xff\xd8":
            return _read_jpeg_dimensions(path)

        # WEBP: RIFF container with 'WEBP' fourcc
        if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
            return _read_webp_dimensions(path)

    except (OSError, struct.error):
        pass
    return None


def _read_jpeg_dimensions(path: str) -> Optional[tuple]:
    """Scan JPEG markers for the SOF frame that carries width/height."""
    try:
        with open(path, "rb") as f:
            f.read(2)  # skip SOI
            while True:
                b = f.read(1)
                if not b:
                    break
                if b != b"\xff":
                    continue
                marker = f.read(1)
                if not marker:
                    break
                code = marker[0]
                if code == 0xD9:  # EOI
                    break
                # Restart markers and bare 0xFF padding carry no length
                if code in range(0xD0, 0xD8) or code == 0x00 or code == 0x01:
                    continue
                length_data = f.read(2)
                if len(length_data) < 2:
                    break
                seg_len = struct.unpack(">H", length_data)[0]
                # SOF0-SOF3 contain the image dimensions
                if 0xC0 <= code <= 0xC3:
                    sof_data = f.read(min(seg_len - 2, 5))
                    if len(sof_data) >= 5:
                        h, w = struct.unpack(">HH", sof_data[1:5])
                        return (w, h)
                    break
                f.seek(seg_len - 2, 1)
    except (OSError, struct.error):
        pass
    return None


def _read_webp_dimensions(path: str) -> Optional[tuple]:
    """Read WebP dimensions from the VP8/VP8L chunk header."""
    try:
        with open(path, "rb") as f:
            data = f.read(30)
        if len(data) < 30:
            return None
        chunk = data[12:16]
        if chunk == b"VP8 ":
            w = struct.unpack("<H", data[26:28])[0] & 0x3FFF
            h = struct.unpack("<H", data[28:30])[0] & 0x3FFF
            return (w, h)
        if chunk == b"VP8L":
            bits = struct.unpack("<I", data[21:25])[0]
            w = (bits & 0x3FFF) + 1
            h = ((bits >> 14) & 0x3FFF) + 1
            return (w, h)
    except (OSError, struct.error):
        pass
    return None


def _read_tiff_dimensions(path: str, header: bytes) -> Optional[tuple]:
    """Read TIFF dimensions from the first IFD."""
    try:
        big = header[:2] == b"MM"
        fmt_h, fmt_i = (">H", ">I") if big else ("<H", "<I")
        ifd_offset = struct.unpack(fmt_i, header[4:8])[0]
        with open(path, "rb") as f:
            f.seek(ifd_offset)
            (n_entries,) = struct.unpack(fmt_h, f.read(2))
            w = h = None
            for _ in range(n_entries):
                entry = f.read(12)
                if len(entry) < 12:
                    break
                tag = struct.unpack(fmt_h, entry[0:2])[0]
                typ = struct.unpack(fmt_h, entry[2:4])[0]
                if tag == 256:  # ImageWidth
                    w = struct.unpack(fmt_i if typ == 4 else fmt_h, entry[8:12 if typ == 4 else 10])[0]
                elif tag == 257:  # ImageLength
                    h = struct.unpack(fmt_i if typ == 4 else fmt_h, entry[8:12 if typ == 4 else 10])[0]
                if w and h:
                    return (w, h)
    except (OSError, struct.error):
        pass
    return None
