"""GIMP CLI - Core project management module."""

import json
import os
import copy
from datetime import datetime
from typing import Optional, Dict, Any, List


# Default canvas profiles
PROFILES = {
    "hd1080p": {"width": 1920, "height": 1080, "dpi": 72},
    "hd720p": {"width": 1280, "height": 720, "dpi": 72},
    "4k": {"width": 3840, "height": 2160, "dpi": 72},
    "square1080": {"width": 1080, "height": 1080, "dpi": 72},
    "a4_300dpi": {"width": 2480, "height": 3508, "dpi": 300},
    "a4_150dpi": {"width": 1240, "height": 1754, "dpi": 150},
    "letter_300dpi": {"width": 2550, "height": 3300, "dpi": 300},
    "web_banner": {"width": 1200, "height": 628, "dpi": 72},
    "instagram_post": {"width": 1080, "height": 1080, "dpi": 72},
    "instagram_story": {"width": 1080, "height": 1920, "dpi": 72},
    "twitter_header": {"width": 1500, "height": 500, "dpi": 72},
    "youtube_thumb": {"width": 1280, "height": 720, "dpi": 72},
    "icon_256": {"width": 256, "height": 256, "dpi": 72},
    "icon_512": {"width": 512, "height": 512, "dpi": 72},
}

PROJECT_VERSION = "1.0"


def create_project(
    width: int = 1920,
    height: int = 1080,
    color_mode: str = "RGB",
    background: str = "#ffffff",
    dpi: int = 72,
    name: str = "untitled",
    profile: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new GIMP CLI project."""
    if profile and profile in PROFILES:
        p = PROFILES[profile]
        width = p["width"]
        height = p["height"]
        dpi = p["dpi"]

    if color_mode not in ("RGB", "RGBA", "L", "LA"):
        raise ValueError(f"Invalid color mode: {color_mode}. Use RGB, RGBA, L, or LA.")
    if width < 1 or height < 1:
        raise ValueError(f"Canvas dimensions must be positive: {width}x{height}")
    if dpi < 1:
        raise ValueError(f"DPI must be positive: {dpi}")

    project = {
        "version": PROJECT_VERSION,
        "name": name,
        "canvas": {
            "width": width,
            "height": height,
            "color_mode": color_mode,
            "background": background,
            "dpi": dpi,
        },
        "layers": [],
        "selection": None,
        "guides": [],
        "metadata": {
            "created": datetime.now().isoformat(),
            "modified": datetime.now().isoformat(),
            "software": "gimp-cli 1.0",
        },
    }
    return project


def open_project(path: str) -> Dict[str, Any]:
    """Open a .gimp-cli.json project file."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Project file not found: {path}")
    with open(path, "r") as f:
        project = json.load(f)
    if "version" not in project or "canvas" not in project:
        raise ValueError(f"Invalid project file: {path}")
    return project


def save_project(project: Dict[str, Any], path: str) -> str:
    """Save project to a .gimp-cli.json file."""
    project["metadata"]["modified"] = datetime.now().isoformat()
    with open(path, "w") as f:
        json.dump(project, f, indent=2, default=str)
    return path


def get_project_info(project: Dict[str, Any]) -> Dict[str, Any]:
    """Get summary information about the project."""
    canvas = project["canvas"]
    layers = project.get("layers", [])
    return {
        "name": project.get("name", "untitled"),
        "version": project.get("version", "unknown"),
        "canvas": {
            "width": canvas["width"],
            "height": canvas["height"],
            "color_mode": canvas.get("color_mode", "RGB"),
            "background": canvas.get("background", "#ffffff"),
            "dpi": canvas.get("dpi", 72),
        },
        "layer_count": len(layers),
        "layers": [
            {
                "id": l.get("id", i),
                "name": l.get("name", f"Layer {i}"),
                "type": l.get("type", "image"),
                "visible": l.get("visible", True),
                "opacity": l.get("opacity", 1.0),
                "blend_mode": l.get("blend_mode", "normal"),
                "filter_count": len(l.get("filters", [])),
            }
            for i, l in enumerate(layers)
        ],
        "metadata": project.get("metadata", {}),
    }


def list_profiles() -> List[Dict[str, Any]]:
    """List all available canvas profiles."""
    result = []
    for name, p in PROFILES.items():
        result.append({"name": name, "width": p["width"], "height": p["height"], "dpi": p["dpi"]})
    return result
