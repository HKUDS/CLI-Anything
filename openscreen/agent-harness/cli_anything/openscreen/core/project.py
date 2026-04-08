"""Project operations — new, open, save, info, set video source."""

import os
from typing import Optional

from .session import Session
from ..utils import ffmpeg_backend


# ── Aspect ratio presets ────────────────────────────────────────────────
ASPECT_RATIOS = {
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
    "4:3": (1440, 1080),
    "4:5": (1080, 1350),
    "16:10": (1920, 1200),
    "10:16": (1200, 1920),
}

BACKGROUNDS = [
    "gradient_dark", "gradient_light", "gradient_sunset",
    "solid_dark", "solid_light", "blur",
]

EXPORT_QUALITIES = ["medium", "good", "source"]
EXPORT_FORMATS = ["mp4", "gif"]


def new_project(session: Session, video_path: Optional[str] = None) -> dict:
    """Create a new Openscreen project.

    Args:
        session: The active session.
        video_path: Optional path to a screen recording to attach.

    Returns:
        Project info dict.
    """
    session.new_project(video_path)
    result = {"status": "created", "video": None}
    if video_path:
        result["video"] = os.path.abspath(video_path)
    return result


def open_project(session: Session, path: str) -> dict:
    """Open an existing .openscreen project file.

    Returns:
        Project info dict.
    """
    session.open_project(path)
    return info(session)


def save_project(session: Session, path: Optional[str] = None) -> dict:
    """Save the current project.

    Returns:
        Dict with saved path.
    """
    saved = session.save_project(path)
    return {"status": "saved", "path": saved}


def info(session: Session) -> dict:
    """Get project information.

    Returns:
        Dict with project metadata and editor state summary.
    """
    if not session.is_open:
        raise RuntimeError("No project is open")

    editor = session.editor
    media = session.data.get("media", {})

    return {
        "version": session.data.get("version", 1),
        "project_path": session.project_path,
        "modified": session.is_modified,
        "video": media.get("screenVideoPath"),
        "webcam_video": media.get("webcamVideoPath"),
        "aspect_ratio": editor.get("aspectRatio", "16:9"),
        "background": editor.get("wallpaper", "gradient_dark"),
        "padding": editor.get("padding", 50),
        "border_radius": editor.get("borderRadius", 12),
        "shadow_intensity": editor.get("shadowIntensity", 0),
        "motion_blur": editor.get("motionBlurAmount", 0),
        "export_quality": editor.get("exportQuality", "good"),
        "export_format": editor.get("exportFormat", "mp4"),
        "zoom_regions": len(editor.get("zoomRegions", [])),
        "speed_regions": len(editor.get("speedRegions", [])),
        "trim_regions": len(editor.get("trimRegions", [])),
        "annotations": len(editor.get("annotationRegions", [])),
    }


def set_video(session: Session, video_path: str) -> dict:
    """Set the source video for the project."""
    if not session.is_open:
        raise RuntimeError("No project is open")

    path = os.path.abspath(video_path)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Video file not found: {path}")

    session.checkpoint()
    if "media" not in session.data:
        session.data["media"] = {}
    session.data["media"]["screenVideoPath"] = path
    return {"status": "ok", "video": path}


def _validate_crop_region(region) -> None:
    """Validate a cropRegion dict.

    All four fields (x, y, width, height) must be present and in [0, 1].
    x + width must be <= 1 and y + height must be <= 1.

    Raises:
        ValueError: If validation fails.
    """
    if not isinstance(region, dict):
        raise ValueError("cropRegion must be a dict with x, y, width, height.")
    for field in ("x", "y", "width", "height"):
        if field not in region:
            raise ValueError(f"cropRegion missing field '{field}'")
        v = float(region[field])
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"cropRegion.{field} must be 0.0-1.0, got {v}")
    if float(region["x"]) + float(region["width"]) > 1.0 + 1e-9:
        raise ValueError("cropRegion x + width must be <= 1.0")
    if float(region["y"]) + float(region["height"]) > 1.0 + 1e-9:
        raise ValueError("cropRegion y + height must be <= 1.0")


def set_setting(session: Session, key: str, value) -> dict:
    """Set a project editor setting.

    Supported keys: aspectRatio, wallpaper, padding, borderRadius,
    shadowIntensity, motionBlurAmount, showBlur, exportQuality,
    exportFormat, gifFrameRate, gifLoop, gifSizePreset,
    webcamLayoutPreset, webcamMaskShape, cropRegion.
    """
    if not session.is_open:
        raise RuntimeError("No project is open")

    editor = session.editor
    VALID_KEYS = {
        "aspectRatio", "wallpaper", "padding", "borderRadius",
        "shadowIntensity", "motionBlurAmount", "showBlur",
        "exportQuality", "exportFormat",
        "gifFrameRate", "gifLoop", "gifSizePreset",
        "webcamLayoutPreset", "webcamMaskShape",
        "cropRegion",
    }
    if key not in VALID_KEYS:
        raise ValueError(f"Unknown setting: {key}. Valid: {sorted(VALID_KEYS)}")

    if key == "aspectRatio" and value not in ASPECT_RATIOS:
        raise ValueError(
            f"Invalid aspectRatio '{value}'. Valid: {', '.join(ASPECT_RATIOS)}"
        )

    if key == "exportQuality" and value not in EXPORT_QUALITIES:
        raise ValueError(
            f"Invalid exportQuality '{value}'. Valid: {', '.join(EXPORT_QUALITIES)}"
        )

    if key == "exportFormat" and value not in EXPORT_FORMATS:
        raise ValueError(
            f"Invalid exportFormat '{value}'. Valid: {', '.join(EXPORT_FORMATS)}"
        )

    if key == "padding":
        v = int(value)
        if not (0 <= v <= 100):
            raise ValueError(f"padding must be 0-100, got {v}")

    if key == "shadowIntensity":
        v = float(value)
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"shadowIntensity must be 0.0-1.0, got {v}")

    if key == "motionBlurAmount":
        v = float(value)
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"motionBlurAmount must be 0.0-1.0, got {v}")

    if key == "borderRadius":
        v = int(value)
        if v < 0:
            raise ValueError(f"borderRadius must be >= 0, got {v}")

    if key == "cropRegion":
        _validate_crop_region(value)

    session.checkpoint()
    editor[key] = value
    return {"status": "ok", "key": key, "value": value}
