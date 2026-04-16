"""OBS Studio CLI - Output/streaming/recording configuration."""

from typing import Dict, Any, List, Optional
from cli_anything.obs_studio.utils.obs_utils import validate_range


ENCODING_PRESETS = {
    "ultrafast": {"encoder": "x264", "video_bitrate": 2500, "audio_bitrate": 128, "preset_label": "Ultra Fast"},
    "fast": {"encoder": "x264", "video_bitrate": 4500, "audio_bitrate": 160, "preset_label": "Fast"},
    "balanced": {"encoder": "x264", "video_bitrate": 6000, "audio_bitrate": 160, "preset_label": "Balanced"},
    "quality": {"encoder": "x264", "video_bitrate": 8000, "audio_bitrate": 192, "preset_label": "Quality"},
    "high_quality": {"encoder": "x264", "video_bitrate": 12000, "audio_bitrate": 320, "preset_label": "High Quality"},
    "nvenc_fast": {"encoder": "nvenc", "video_bitrate": 6000, "audio_bitrate": 160, "preset_label": "NVENC Fast"},
    "nvenc_quality": {"encoder": "nvenc", "video_bitrate": 10000, "audio_bitrate": 192, "preset_label": "NVENC Quality"},
    "recording_high": {"encoder": "x264", "video_bitrate": 20000, "audio_bitrate": 320, "preset_label": "Recording High"},
}

VALID_SERVICES = ("twitch", "youtube", "facebook", "custom")
VALID_RECORDING_FORMATS = ("mkv", "mp4", "mov", "flv", "ts")
VALID_RECORDING_QUALITIES = ("low", "medium", "high", "lossless")


def set_streaming(
    project: Dict[str, Any],
    service: Optional[str] = None,
    server: Optional[str] = None,
    key: Optional[str] = None,
) -> Dict[str, Any]:
    """Configure streaming settings."""
    streaming = project.setdefault("streaming", {})

    if service is not None:
        if service not in VALID_SERVICES:
            raise ValueError(f"Invalid streaming service: {service}. Valid: {', '.join(VALID_SERVICES)}")
        streaming["service"] = service
    if server is not None:
        streaming["server"] = server
    if key is not None:
        streaming["key"] = key

    return streaming


def set_recording(
    project: Dict[str, Any],
    path: Optional[str] = None,
    fmt: Optional[str] = None,
    quality: Optional[str] = None,
) -> Dict[str, Any]:
    """Configure recording settings."""
    recording = project.setdefault("recording", {})

    if path is not None:
        recording["path"] = path
    if fmt is not None:
        if fmt not in VALID_RECORDING_FORMATS:
            raise ValueError(f"Invalid recording format: {fmt}. Valid: {', '.join(VALID_RECORDING_FORMATS)}")
        recording["format"] = fmt
    if quality is not None:
        if quality not in VALID_RECORDING_QUALITIES:
            raise ValueError(f"Invalid recording quality: {quality}. Valid: {', '.join(VALID_RECORDING_QUALITIES)}")
        recording["quality"] = quality

    return recording


def set_output_settings(
    project: Dict[str, Any],
    output_width: Optional[int] = None,
    output_height: Optional[int] = None,
    fps: Optional[int] = None,
    video_bitrate: Optional[int] = None,
    audio_bitrate: Optional[int] = None,
    encoder: Optional[str] = None,
    preset: Optional[str] = None,
) -> Dict[str, Any]:
    """Configure output settings. Optionally apply an encoding preset."""
    settings = project.setdefault("settings", {})

    if preset is not None:
        if preset not in ENCODING_PRESETS:
            raise ValueError(f"Unknown encoding preset: {preset}. Valid: {', '.join(sorted(ENCODING_PRESETS.keys()))}")
        p = ENCODING_PRESETS[preset]
        settings["encoder"] = p["encoder"]
        settings["video_bitrate"] = p["video_bitrate"]
        settings["audio_bitrate"] = p["audio_bitrate"]

    if output_width is not None:
        if output_width < 1:
            raise ValueError(f"Output width must be positive: {output_width}")
        settings["output_width"] = output_width
    if output_height is not None:
        if output_height < 1:
            raise ValueError(f"Output height must be positive: {output_height}")
        settings["output_height"] = output_height
    if fps is not None:
        if fps < 1:
            raise ValueError(f"FPS must be positive: {fps}")
        settings["fps"] = fps
    if video_bitrate is not None:
        if video_bitrate < 100:
            raise ValueError(f"Video bitrate must be at least 100: {video_bitrate}")
        settings["video_bitrate"] = video_bitrate
    if audio_bitrate is not None:
        if audio_bitrate < 32:
            raise ValueError(f"Audio bitrate must be at least 32: {audio_bitrate}")
        settings["audio_bitrate"] = audio_bitrate
    if encoder is not None:
        valid_encoders = ("x264", "x265", "nvenc", "qsv", "amd", "svt-av1")
        if encoder not in valid_encoders:
            raise ValueError(f"Invalid encoder: {encoder}. Valid: {', '.join(valid_encoders)}")
        settings["encoder"] = encoder

    return settings


def get_output_info(project: Dict[str, Any]) -> Dict[str, Any]:
    """Get full output configuration info."""
    settings = project.get("settings", {})
    streaming = project.get("streaming", {})
    recording = project.get("recording", {})

    return {
        "settings": {
            "resolution": f"{settings.get('output_width', 1920)}x{settings.get('output_height', 1080)}",
            "fps": settings.get("fps", 30),
            "encoder": settings.get("encoder", "x264"),
            "video_bitrate": settings.get("video_bitrate", 6000),
            "audio_bitrate": settings.get("audio_bitrate", 160),
        },
        "streaming": {
            "service": streaming.get("service", "twitch"),
            "server": streaming.get("server", "auto"),
            "has_key": bool(streaming.get("key", "")),
        },
        "recording": {
            "path": recording.get("path", "./recordings/"),
            "format": recording.get("format", "mkv"),
            "quality": recording.get("quality", "high"),
        },
    }


def list_encoding_presets() -> List[Dict[str, Any]]:
    """List all available encoding presets."""
    return [
        {
            "name": name,
            "label": spec["preset_label"],
            "encoder": spec["encoder"],
            "video_bitrate": spec["video_bitrate"],
            "audio_bitrate": spec["audio_bitrate"],
        }
        for name, spec in ENCODING_PRESETS.items()
    ]
