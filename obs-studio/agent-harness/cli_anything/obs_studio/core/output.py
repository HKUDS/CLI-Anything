"""Streaming and recording configuration operations."""

from __future__ import annotations

from .session import Session

PRESETS = {
    "performance": {
        "output_width": 1280, "output_height": 720, "fps": 30,
        "video_bitrate": 3000, "audio_bitrate": 128, "encoder": "x264",
    },
    "balanced": {
        "output_width": 1920, "output_height": 1080, "fps": 30,
        "video_bitrate": 6000, "audio_bitrate": 160, "encoder": "x264",
    },
    "quality": {
        "output_width": 1920, "output_height": 1080, "fps": 60,
        "video_bitrate": 8000, "audio_bitrate": 320, "encoder": "x264",
    },
}


def _get_state(session: Session) -> dict:
    if not session.is_open or session.state is None:
        raise RuntimeError("No project is open")
    return session.state


def configure_streaming(session: Session, service: str, key: str, server: str = "auto") -> dict:
    state = _get_state(session)
    session.checkpoint()
    state["streaming"] = {"service": service, "server": server, "key": key}
    return {"action": "configure_streaming", "streaming": state["streaming"]}


def configure_recording(
    session: Session,
    path: str | None = None,
    format_name: str = "mkv",
    quality: str = "high",
) -> dict:
    state = _get_state(session)
    session.checkpoint()
    if path:
        state["recording"]["path"] = path
    state["recording"]["format"] = format_name
    state["recording"]["quality"] = quality
    return {"action": "configure_recording", "recording": state["recording"]}


def configure_output_settings(
    session: Session,
    preset: str | None = None,
    fps: int | None = None,
    output_width: int | None = None,
    output_height: int | None = None,
    video_bitrate: int | None = None,
    audio_bitrate: int | None = None,
    encoder: str | None = None,
) -> dict:
    state = _get_state(session)
    session.checkpoint()
    updates = {
        "preset": preset,
        "fps": fps,
        "output_width": output_width,
        "output_height": output_height,
        "video_bitrate": video_bitrate,
        "audio_bitrate": audio_bitrate,
        "encoder": encoder,
    }
    for key, value in updates.items():
        if value is not None:
            state["settings"][key] = value
    return {"action": "configure_output_settings", "settings": state["settings"]}


# Standalone dict-based API

def set_streaming(proj: dict, service: str = "", server: str = "auto", key: str = "") -> dict:
    proj["streaming"] = {"service": service, "server": server, "key": key}
    return proj["streaming"]


def set_recording(proj: dict, path: str | None = None, fmt: str = "mkv", quality: str = "high") -> dict:
    if path is not None:
        proj["recording"]["path"] = path
    proj["recording"]["format"] = fmt
    proj["recording"]["quality"] = quality
    return proj["recording"]


def set_output_settings(
    proj: dict,
    preset: str | None = None,
    fps: int | None = None,
    output_width: int | None = None,
    output_height: int | None = None,
    video_bitrate: int | None = None,
    audio_bitrate: int | None = None,
    encoder: str | None = None,
) -> dict:
    if preset is not None and preset in PRESETS:
        proj["settings"].update(PRESETS[preset])
    overrides = {
        "fps": fps,
        "output_width": output_width,
        "output_height": output_height,
        "video_bitrate": video_bitrate,
        "audio_bitrate": audio_bitrate,
        "encoder": encoder,
    }
    for key, value in overrides.items():
        if value is not None:
            proj["settings"][key] = value
    return proj["settings"]


def get_output_info(proj: dict) -> dict:
    return {
        "streaming": proj.get("streaming", {}),
        "recording": proj.get("recording", {}),
        "settings": proj.get("settings", {}),
    }
