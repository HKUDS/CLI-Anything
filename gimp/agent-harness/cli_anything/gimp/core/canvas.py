"""GIMP CLI - Canvas operations module."""

from typing import Dict, Any


VALID_MODES = ("RGB", "RGBA", "L", "LA", "CMYK", "P")
RESAMPLE_METHODS = ("nearest", "bilinear", "bicubic", "lanczos")


def resize_canvas(
    project: Dict[str, Any],
    width: int,
    height: int,
    anchor: str = "center",
) -> Dict[str, Any]:
    """Resize the canvas (does not scale content, adds/removes space).

    Args:
        project: The project dict
        width: New canvas width
        height: New canvas height
        anchor: Where to anchor existing content:
                "center", "top-left", "top-right", "bottom-left", "bottom-right",
                "top", "bottom", "left", "right"
    """
    if width < 1 or height < 1:
        raise ValueError(f"Canvas dimensions must be positive: {width}x{height}")

    valid_anchors = [
        "center", "top-left", "top-right", "bottom-left", "bottom-right",
        "top", "bottom", "left", "right",
    ]
    if anchor not in valid_anchors:
        raise ValueError(f"Invalid anchor: {anchor}. Valid: {valid_anchors}")

    old_w = project["canvas"]["width"]
    old_h = project["canvas"]["height"]

    # Calculate offset for existing layers based on anchor
    dx, dy = _anchor_offset(old_w, old_h, width, height, anchor)

    project["canvas"]["width"] = width
    project["canvas"]["height"] = height

    # Adjust layer offsets
    for layer in project.get("layers", []):
        layer["offset_x"] = layer.get("offset_x", 0) + dx
        layer["offset_y"] = layer.get("offset_y", 0) + dy

    return {
        "old_size": f"{old_w}x{old_h}",
        "new_size": f"{width}x{height}",
        "anchor": anchor,
        "offset_applied": f"({dx}, {dy})",
    }


def scale_canvas(
    project: Dict[str, Any],
    width: int,
    height: int,
    resample: str = "lanczos",
) -> Dict[str, Any]:
    """Scale the canvas and all layers proportionally.

    This marks layers for rescaling at render time.
    """
    if width < 1 or height < 1:
        raise ValueError(f"Canvas dimensions must be positive: {width}x{height}")
    if resample not in RESAMPLE_METHODS:
        raise ValueError(f"Invalid resample method: {resample}. Valid: {list(RESAMPLE_METHODS)}")

    old_w = project["canvas"]["width"]
    old_h = project["canvas"]["height"]
    scale_x = width / old_w
    scale_y = height / old_h

    project["canvas"]["width"] = width
    project["canvas"]["height"] = height

    # Mark layers for proportional scaling
    for layer in project.get("layers", []):
        layer["_scale_x"] = scale_x
        layer["_scale_y"] = scale_y
        layer["_resample"] = resample
        layer["offset_x"] = round(layer.get("offset_x", 0) * scale_x)
        layer["offset_y"] = round(layer.get("offset_y", 0) * scale_y)
        if "width" in layer:
            layer["width"] = round(layer["width"] * scale_x)
        if "height" in layer:
            layer["height"] = round(layer["height"] * scale_y)

    return {
        "old_size": f"{old_w}x{old_h}",
        "new_size": f"{width}x{height}",
        "scale": f"({scale_x:.3f}, {scale_y:.3f})",
        "resample": resample,
    }


def crop_canvas(
    project: Dict[str, Any],
    left: int,
    top: int,
    right: int,
    bottom: int,
) -> Dict[str, Any]:
    """Crop the canvas to a rectangle."""
    if left < 0 or top < 0:
        raise ValueError(f"Crop coordinates must be non-negative: left={left}, top={top}")
    if right <= left or bottom <= top:
        raise ValueError(f"Invalid crop region: ({left},{top})-({right},{bottom})")

    old_w = project["canvas"]["width"]
    old_h = project["canvas"]["height"]

    if right > old_w or bottom > old_h:
        raise ValueError(
            f"Crop region ({left},{top})-({right},{bottom}) exceeds canvas {old_w}x{old_h}"
        )

    new_w = right - left
    new_h = bottom - top

    project["canvas"]["width"] = new_w
    project["canvas"]["height"] = new_h

    # Adjust layer offsets
    for layer in project.get("layers", []):
        layer["offset_x"] = layer.get("offset_x", 0) - left
        layer["offset_y"] = layer.get("offset_y", 0) - top

    return {
        "old_size": f"{old_w}x{old_h}",
        "new_size": f"{new_w}x{new_h}",
        "crop_region": f"({left},{top})-({right},{bottom})",
    }


def set_mode(project: Dict[str, Any], mode: str) -> Dict[str, Any]:
    """Set the canvas color mode."""
    mode = mode.upper()
    if mode not in VALID_MODES:
        raise ValueError(f"Invalid color mode: {mode}. Valid: {list(VALID_MODES)}")
    old_mode = project["canvas"].get("color_mode", "RGB")
    project["canvas"]["color_mode"] = mode
    return {"old_mode": old_mode, "new_mode": mode}


def set_dpi(project: Dict[str, Any], dpi: int) -> Dict[str, Any]:
    """Set the canvas DPI (dots per inch)."""
    if dpi < 1:
        raise ValueError(f"DPI must be positive: {dpi}")
    old_dpi = project["canvas"].get("dpi", 72)
    project["canvas"]["dpi"] = dpi
    return {"old_dpi": old_dpi, "new_dpi": dpi}


def get_canvas_info(project: Dict[str, Any]) -> Dict[str, Any]:
    """Get canvas information."""
    c = project["canvas"]
    w, h = c["width"], c["height"]
    dpi = c.get("dpi", 72)
    return {
        "width": w,
        "height": h,
        "color_mode": c.get("color_mode", "RGB"),
        "background": c.get("background", "#ffffff"),
        "dpi": dpi,
        "size_inches": f"{w/dpi:.2f} x {h/dpi:.2f}",
        "megapixels": f"{w * h / 1_000_000:.2f} MP",
    }


def _anchor_offset(
    old_w: int, old_h: int, new_w: int, new_h: int, anchor: str
) -> tuple:
    """Calculate pixel offset for content based on anchor position."""
    dx_map = {
        "top-left": 0, "left": 0, "bottom-left": 0,
        "top": (new_w - old_w) // 2, "center": (new_w - old_w) // 2,
        "bottom": (new_w - old_w) // 2,
        "top-right": new_w - old_w, "right": new_w - old_w,
        "bottom-right": new_w - old_w,
    }
    dy_map = {
        "top-left": 0, "top": 0, "top-right": 0,
        "left": (new_h - old_h) // 2, "center": (new_h - old_h) // 2,
        "right": (new_h - old_h) // 2,
        "bottom-left": new_h - old_h, "bottom": new_h - old_h,
        "bottom-right": new_h - old_h,
    }
    return dx_map.get(anchor, 0), dy_map.get(anchor, 0)
