"""Krita CLI - Core project management module.

Manages a JSON-based project state file that tracks the user's work
and maps to Krita operations. Krita's native format is .kra (a ZIP
archive containing maindoc.xml, documentinfo.xml, and layer image data).
"""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from cli_anything.krita.utils.io import locked_save_json


PROJECT_VERSION = "1.0.0"

VALID_LAYER_TYPES = (
    "paintlayer",
    "grouplayer",
    "vectorlayer",
    "filterlayer",
    "filllayer",
    "clonelayer",
    "filelayer",
)

VALID_FILTERS = (
    "blur", "gaussian-blur", "motion-blur", "lens-blur",
    "sharpen", "unsharp-mask",
    "brightness-contrast", "levels", "curves", "hue-saturation",
    "color-balance", "desaturate", "invert", "posterize", "threshold",
    "auto-contrast", "normalize",
    "emboss", "edge-detection", "oil-paint", "pixelize",
    "noise-reduction", "halftone",
)

VALID_COLORSPACES = ("RGBA", "RGB", "GRAYA", "GRAY", "CMYKA", "CMYK")
VALID_DEPTHS = ("U8", "U16", "F16", "F32")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _find_layer(project: dict, name: str) -> Optional[dict]:
    """Find a layer by name in the project's layer stack."""
    for layer in project.get("layers", []):
        if layer["name"] == name:
            return layer
    return None


def _touch_modified(project: dict) -> None:
    """Update the 'modified' timestamp on the project."""
    project["modified"] = _now_iso()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_project(
    name: str,
    width: int = 1920,
    height: int = 1080,
    colorspace: str = "RGBA",
    depth: str = "U8",
    resolution: int = 300,
    profile: str = "sRGB-elle-V2-srgbtrc.icc",
) -> Dict[str, Any]:
    """Create a new project JSON with image settings.

    Parameters
    ----------
    name : str
        Project name.
    width, height : int
        Canvas dimensions in pixels.
    colorspace : str
        Colour model (RGBA, RGB, GRAYA, GRAY, CMYKA, CMYK).
    depth : str
        Bit depth (U8, U16, F16, F32).
    resolution : int
        Pixels per inch.
    profile : str
        ICC colour profile filename.

    Returns
    -------
    dict
        The new project dictionary.
    """
    if colorspace not in VALID_COLORSPACES:
        raise ValueError(
            f"Invalid colorspace '{colorspace}'. "
            f"Choose from: {', '.join(VALID_COLORSPACES)}"
        )
    if depth not in VALID_DEPTHS:
        raise ValueError(
            f"Invalid depth '{depth}'. Choose from: {', '.join(VALID_DEPTHS)}"
        )
    if width < 1 or height < 1:
        raise ValueError(f"Canvas dimensions must be positive: {width}x{height}")
    if resolution < 1:
        raise ValueError(f"Resolution must be positive: {resolution}")

    now = _now_iso()
    project: Dict[str, Any] = {
        "name": name,
        "version": PROJECT_VERSION,
        "created": now,
        "modified": now,
        "canvas": {
            "width": width,
            "height": height,
            "colorspace": colorspace,
            "depth": depth,
            "resolution": resolution,
            "profile": profile,
        },
        "layers": [
            {
                "name": "Background",
                "type": "paintlayer",
                "opacity": 255,
                "visible": True,
                "blending_mode": "normal",
                "locked": False,
                "filters": [],
            }
        ],
        "metadata": {
            "author": "",
            "description": "",
            "tags": [],
        },
    }
    return project


def open_project(path: str) -> Dict[str, Any]:
    """Load a project JSON file.

    Parameters
    ----------
    path : str
        Path to the project JSON file.

    Returns
    -------
    dict
        The loaded project dictionary.

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    ValueError
        If the file does not look like a valid project.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Project file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        project = json.load(f)
    # Basic sanity checks
    if "version" not in project or "canvas" not in project:
        raise ValueError(f"Invalid project file (missing version/canvas): {path}")
    return project


def save_project(project: Dict[str, Any], path: Optional[str] = None) -> str:
    """Save project to a JSON file using atomic file locking.

    Parameters
    ----------
    project : dict
        The project dictionary to persist.
    path : str, optional
        Destination path.  If *None*, defaults to ``<project_name>.krita.json``
        in the current working directory.

    Returns
    -------
    str
        The absolute path of the saved file.
    """
    if path is None:
        safe_name = project.get("name", "untitled").replace(" ", "_")
        path = os.path.join(os.getcwd(), f"{safe_name}.krita.json")

    _touch_modified(project)
    locked_save_json(path, project, indent=2, default=str)
    return os.path.abspath(path)


def project_info(project: Dict[str, Any]) -> Dict[str, Any]:
    """Return summary info about the project.

    Returns
    -------
    dict
        A lightweight summary suitable for display.
    """
    canvas = project.get("canvas", {})
    layers = project.get("layers", [])
    return {
        "name": project.get("name", "untitled"),
        "version": project.get("version", "unknown"),
        "created": project.get("created"),
        "modified": project.get("modified"),
        "canvas": {
            "width": canvas.get("width"),
            "height": canvas.get("height"),
            "colorspace": canvas.get("colorspace", "RGBA"),
            "depth": canvas.get("depth", "U8"),
            "resolution": canvas.get("resolution", 300),
            "profile": canvas.get("profile"),
        },
        "layer_count": len(layers),
        "layers_summary": [
            {
                "name": ly.get("name"),
                "type": ly.get("type"),
                "visible": ly.get("visible", True),
                "opacity": ly.get("opacity", 255),
                "blending_mode": ly.get("blending_mode", "normal"),
                "filter_count": len(ly.get("filters", [])),
            }
            for ly in layers
        ],
        "metadata": project.get("metadata", {}),
    }


def add_layer(
    project: Dict[str, Any],
    name: str,
    layer_type: str = "paintlayer",
    opacity: int = 255,
    visible: bool = True,
    blending_mode: str = "normal",
) -> Dict[str, Any]:
    """Add a layer to the project's layer stack.

    Parameters
    ----------
    project : dict
        The project to modify (mutated in-place and returned).
    name : str
        Layer name (must be unique within the stack).
    layer_type : str
        One of: paintlayer, grouplayer, vectorlayer, filterlayer,
        filllayer, clonelayer, filelayer.
    opacity : int
        Layer opacity 0-255.
    visible : bool
        Whether the layer is visible.
    blending_mode : str
        Blending / compositing mode name.

    Returns
    -------
    dict
        The updated project.
    """
    if layer_type not in VALID_LAYER_TYPES:
        raise ValueError(
            f"Invalid layer type '{layer_type}'. "
            f"Choose from: {', '.join(VALID_LAYER_TYPES)}"
        )
    if not 0 <= opacity <= 255:
        raise ValueError(f"Opacity must be 0-255, got {opacity}")
    if _find_layer(project, name) is not None:
        raise ValueError(f"A layer named '{name}' already exists")

    layer: Dict[str, Any] = {
        "name": name,
        "type": layer_type,
        "opacity": opacity,
        "visible": visible,
        "blending_mode": blending_mode,
        "locked": False,
        "filters": [],
    }
    project.setdefault("layers", []).append(layer)
    _touch_modified(project)
    return project


def remove_layer(project: Dict[str, Any], name: str) -> Dict[str, Any]:
    """Remove a layer by name.

    Parameters
    ----------
    project : dict
        The project to modify.
    name : str
        Name of the layer to remove.

    Returns
    -------
    dict
        The updated project.

    Raises
    ------
    KeyError
        If no layer with the given name exists.
    """
    layers: List[dict] = project.get("layers", [])
    for i, layer in enumerate(layers):
        if layer["name"] == name:
            layers.pop(i)
            _touch_modified(project)
            return project
    raise KeyError(f"Layer not found: '{name}'")


def list_layers(project: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return list of layers with their properties.

    Returns
    -------
    list[dict]
        Each element is a copy of the layer dictionary.
    """
    return [dict(ly) for ly in project.get("layers", [])]


def set_layer_property(
    project: Dict[str, Any],
    layer_name: str,
    property_name: str,
    value: Any,
) -> Dict[str, Any]:
    """Set a property on a layer.

    Supported properties include: opacity, visible, blending_mode,
    locked, name, type.

    Parameters
    ----------
    project : dict
        The project to modify.
    layer_name : str
        Target layer.
    property_name : str
        Property key to set.
    value
        New value.

    Returns
    -------
    dict
        The updated project.
    """
    layer = _find_layer(project, layer_name)
    if layer is None:
        raise KeyError(f"Layer not found: '{layer_name}'")

    # Validate specific properties
    if property_name == "opacity" and not (0 <= int(value) <= 255):
        raise ValueError(f"Opacity must be 0-255, got {value}")
    if property_name == "type" and value not in VALID_LAYER_TYPES:
        raise ValueError(
            f"Invalid layer type '{value}'. "
            f"Choose from: {', '.join(VALID_LAYER_TYPES)}"
        )

    layer[property_name] = value
    _touch_modified(project)
    return project


def add_filter(
    project: Dict[str, Any],
    layer_name: str,
    filter_name: str,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Add a filter to be applied on a layer.

    Parameters
    ----------
    project : dict
        The project to modify.
    layer_name : str
        Target layer name.
    filter_name : str
        Filter identifier (e.g. blur, sharpen, desaturate, levels, curves,
        brightness-contrast, hue-saturation, color-balance, unsharp-mask,
        posterize, threshold).
    config : dict, optional
        Filter-specific configuration parameters.

    Returns
    -------
    dict
        The updated project.
    """
    layer = _find_layer(project, layer_name)
    if layer is None:
        raise KeyError(f"Layer not found: '{layer_name}'")

    if filter_name not in VALID_FILTERS:
        raise ValueError(
            f"Unknown filter '{filter_name}'. "
            f"Choose from: {', '.join(VALID_FILTERS)}"
        )

    filter_entry: Dict[str, Any] = {
        "name": filter_name,
        "config": config or {},
    }
    layer.setdefault("filters", []).append(filter_entry)
    _touch_modified(project)
    return project


def set_canvas(
    project: Dict[str, Any],
    width: Optional[int] = None,
    height: Optional[int] = None,
    resolution: Optional[int] = None,
) -> Dict[str, Any]:
    """Update canvas properties.

    Only supplied keyword arguments are changed; others are left untouched.

    Parameters
    ----------
    project : dict
        The project to modify.
    width : int, optional
        New canvas width in pixels.
    height : int, optional
        New canvas height in pixels.
    resolution : int, optional
        New resolution (ppi).

    Returns
    -------
    dict
        The updated project.
    """
    canvas = project.setdefault("canvas", {})

    if width is not None:
        if width < 1:
            raise ValueError(f"Width must be positive, got {width}")
        canvas["width"] = width

    if height is not None:
        if height < 1:
            raise ValueError(f"Height must be positive, got {height}")
        canvas["height"] = height

    if resolution is not None:
        if resolution < 1:
            raise ValueError(f"Resolution must be positive, got {resolution}")
        canvas["resolution"] = resolution

    _touch_modified(project)
    return project
