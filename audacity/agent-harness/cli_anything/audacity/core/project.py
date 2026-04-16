"""Audacity CLI - Core project management module.

Handles create, open, save, info, and settings for audio projects.
The project format is a JSON file that tracks tracks, clips, effects,
labels, selection, and metadata.
"""

import json
import os
import copy
from datetime import datetime
from typing import Optional, Dict, Any, List


PROJECT_VERSION = "1.0"

# Default project settings
DEFAULT_SETTINGS = {
    "sample_rate": 44100,
    "bit_depth": 16,
    "channels": 2,
}


def create_project(
    name: str = "untitled",
    sample_rate: int = 44100,
    bit_depth: int = 16,
    channels: int = 2,
) -> Dict[str, Any]:
    """Create a new Audacity CLI project."""
    if sample_rate not in (8000, 11025, 16000, 22050, 44100, 48000, 88200, 96000, 192000):
        raise ValueError(
            f"Invalid sample rate: {sample_rate}. "
            "Use one of: 8000, 11025, 16000, 22050, 44100, 48000, 88200, 96000, 192000"
        )
    if bit_depth not in (8, 16, 24, 32):
        raise ValueError(f"Invalid bit depth: {bit_depth}. Use 8, 16, 24, or 32.")
    if channels not in (1, 2):
        raise ValueError(f"Invalid channel count: {channels}. Use 1 (mono) or 2 (stereo).")

    project = {
        "version": PROJECT_VERSION,
        "name": name,
        "settings": {
            "sample_rate": sample_rate,
            "bit_depth": bit_depth,
            "channels": channels,
        },
        "tracks": [],
        "labels": [],
        "selection": {"start": 0.0, "end": 0.0},
        "metadata": {
            "title": "",
            "artist": "",
            "album": "",
            "genre": "",
            "year": "",
            "created": datetime.now().isoformat(),
            "modified": datetime.now().isoformat(),
            "software": "audacity-cli 1.0",
        },
    }
    return project


def open_project(path: str) -> Dict[str, Any]:
    """Open an .audacity-cli.json project file."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Project file not found: {path}")
    with open(path, "r") as f:
        project = json.load(f)
    if "version" not in project or "settings" not in project:
        raise ValueError(f"Invalid project file: {path}")
    return project


def save_project(project: Dict[str, Any], path: str) -> str:
    """Save project to an .audacity-cli.json file."""
    project["metadata"]["modified"] = datetime.now().isoformat()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as f:
        json.dump(project, f, indent=2, default=str)
    return path


def get_project_info(project: Dict[str, Any]) -> Dict[str, Any]:
    """Get summary information about the project."""
    settings = project.get("settings", DEFAULT_SETTINGS)
    tracks = project.get("tracks", [])
    labels = project.get("labels", [])

    total_clips = sum(len(t.get("clips", [])) for t in tracks)
    total_effects = sum(len(t.get("effects", [])) for t in tracks)

    # Calculate total duration from tracks
    max_end = 0.0
    for t in tracks:
        for c in t.get("clips", []):
            end = c.get("end_time", 0.0)
            if end > max_end:
                max_end = end

    return {
        "name": project.get("name", "untitled"),
        "version": project.get("version", "unknown"),
        "settings": {
            "sample_rate": settings.get("sample_rate", 44100),
            "bit_depth": settings.get("bit_depth", 16),
            "channels": settings.get("channels", 2),
        },
        "track_count": len(tracks),
        "clip_count": total_clips,
        "effect_count": total_effects,
        "label_count": len(labels),
        "duration": round(max_end, 3),
        "duration_human": _format_time(max_end),
        "tracks": [
            {
                "id": t.get("id", i),
                "name": t.get("name", f"Track {i}"),
                "type": t.get("type", "audio"),
                "mute": t.get("mute", False),
                "solo": t.get("solo", False),
                "volume": t.get("volume", 1.0),
                "pan": t.get("pan", 0.0),
                "clip_count": len(t.get("clips", [])),
                "effect_count": len(t.get("effects", [])),
            }
            for i, t in enumerate(tracks)
        ],
        "selection": project.get("selection", {"start": 0.0, "end": 0.0}),
        "metadata": project.get("metadata", {}),
    }


def set_settings(
    project: Dict[str, Any],
    sample_rate: Optional[int] = None,
    bit_depth: Optional[int] = None,
    channels: Optional[int] = None,
) -> Dict[str, Any]:
    """Update project settings."""
    settings = project.setdefault("settings", dict(DEFAULT_SETTINGS))

    if sample_rate is not None:
        if sample_rate not in (8000, 11025, 16000, 22050, 44100, 48000, 88200, 96000, 192000):
            raise ValueError(f"Invalid sample rate: {sample_rate}")
        settings["sample_rate"] = sample_rate

    if bit_depth is not None:
        if bit_depth not in (8, 16, 24, 32):
            raise ValueError(f"Invalid bit depth: {bit_depth}")
        settings["bit_depth"] = bit_depth

    if channels is not None:
        if channels not in (1, 2):
            raise ValueError(f"Invalid channel count: {channels}")
        settings["channels"] = channels

    return settings


def _format_time(seconds: float) -> str:
    """Format seconds to HH:MM:SS.mmm."""
    if seconds < 0:
        seconds = 0.0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:06.3f}"
    return f"{m:02d}:{s:06.3f}"
