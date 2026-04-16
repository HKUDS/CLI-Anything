"""OBS Studio CLI - Project/scene collection management."""

import json
import os
import copy
from datetime import datetime
from typing import Optional, Dict, Any, List


PROJECT_VERSION = "1.0"


def _default_project(name: str = "untitled") -> Dict[str, Any]:
    """Return the default project structure."""
    return {
        "version": PROJECT_VERSION,
        "name": name,
        "settings": {
            "output_width": 1920,
            "output_height": 1080,
            "fps": 30,
            "video_bitrate": 6000,
            "audio_bitrate": 160,
            "encoder": "x264",
        },
        "scenes": [
            {
                "id": 0,
                "name": "Scene",
                "sources": [],
            }
        ],
        "transitions": [
            {"name": "Cut", "type": "cut", "duration": 0},
            {"name": "Fade", "type": "fade", "duration": 300},
        ],
        "active_scene": 0,
        "audio_sources": [],
        "streaming": {
            "service": "twitch",
            "server": "auto",
            "key": "",
        },
        "recording": {
            "path": "./recordings/",
            "format": "mkv",
            "quality": "high",
        },
        "metadata": {
            "created": datetime.now().isoformat(),
            "modified": datetime.now().isoformat(),
            "software": "obs-cli 1.0",
        },
    }


def create_project(
    name: str = "untitled",
    output_width: int = 1920,
    output_height: int = 1080,
    fps: int = 30,
    video_bitrate: int = 6000,
    audio_bitrate: int = 160,
    encoder: str = "x264",
) -> Dict[str, Any]:
    """Create a new OBS scene collection project."""
    if output_width < 1 or output_height < 1:
        raise ValueError(f"Resolution must be positive: {output_width}x{output_height}")
    if fps < 1:
        raise ValueError(f"FPS must be positive: {fps}")
    if video_bitrate < 100:
        raise ValueError(f"Video bitrate must be at least 100: {video_bitrate}")
    if audio_bitrate < 32:
        raise ValueError(f"Audio bitrate must be at least 32: {audio_bitrate}")

    valid_encoders = ("x264", "x265", "nvenc", "qsv", "amd", "svt-av1")
    if encoder not in valid_encoders:
        raise ValueError(f"Invalid encoder: {encoder}. Valid: {', '.join(valid_encoders)}")

    proj = _default_project(name)
    proj["settings"].update({
        "output_width": output_width,
        "output_height": output_height,
        "fps": fps,
        "video_bitrate": video_bitrate,
        "audio_bitrate": audio_bitrate,
        "encoder": encoder,
    })
    return proj


def open_project(path: str) -> Dict[str, Any]:
    """Open an existing OBS scene collection file."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Project file not found: {path}")
    with open(path, "r") as f:
        project = json.load(f)
    if "version" not in project or "scenes" not in project:
        raise ValueError(f"Invalid OBS project file: {path}")
    return project


def save_project(project: Dict[str, Any], path: str) -> str:
    """Save project to a JSON file."""
    project["metadata"]["modified"] = datetime.now().isoformat()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as f:
        json.dump(project, f, indent=2, default=str)
    return path


def get_project_info(project: Dict[str, Any]) -> Dict[str, Any]:
    """Get summary information about the project."""
    settings = project.get("settings", {})
    scenes = project.get("scenes", [])
    transitions = project.get("transitions", [])
    audio_sources = project.get("audio_sources", [])
    streaming = project.get("streaming", {})
    recording = project.get("recording", {})

    total_sources = sum(len(s.get("sources", [])) for s in scenes)

    active_idx = project.get("active_scene", 0)
    active_name = scenes[active_idx]["name"] if active_idx < len(scenes) else "None"

    return {
        "name": project.get("name", "untitled"),
        "version": project.get("version", "unknown"),
        "settings": {
            "resolution": f"{settings.get('output_width', 1920)}x{settings.get('output_height', 1080)}",
            "fps": settings.get("fps", 30),
            "encoder": settings.get("encoder", "x264"),
            "video_bitrate": settings.get("video_bitrate", 6000),
            "audio_bitrate": settings.get("audio_bitrate", 160),
        },
        "counts": {
            "scenes": len(scenes),
            "total_sources": total_sources,
            "transitions": len(transitions),
            "audio_sources": len(audio_sources),
        },
        "active_scene": active_name,
        "scenes": [
            {
                "id": s.get("id", i),
                "name": s.get("name", f"Scene {i}"),
                "source_count": len(s.get("sources", [])),
            }
            for i, s in enumerate(scenes)
        ],
        "streaming": {
            "service": streaming.get("service", "twitch"),
            "server": streaming.get("server", "auto"),
        },
        "recording": {
            "path": recording.get("path", "./recordings/"),
            "format": recording.get("format", "mkv"),
            "quality": recording.get("quality", "high"),
        },
        "metadata": project.get("metadata", {}),
    }
