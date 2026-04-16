"""Kdenlive CLI - Export module: JSON to MLT/Kdenlive XML generation."""

from typing import Dict, Any, List, Optional
from cli_anything.kdenlive.utils.mlt_xml import (
    xml_escape,
    seconds_to_frames,
    build_mlt_xml,
)


RENDER_PRESETS = {
    "h264_hq": {
        "description": "H.264 High Quality",
        "vcodec": "libx264",
        "acodec": "aac",
        "vbitrate": "8000k",
        "abitrate": "192k",
        "extension": "mp4",
    },
    "h264_fast": {
        "description": "H.264 Fast/Draft",
        "vcodec": "libx264",
        "acodec": "aac",
        "vbitrate": "4000k",
        "abitrate": "128k",
        "extension": "mp4",
    },
    "h265_hq": {
        "description": "H.265/HEVC High Quality",
        "vcodec": "libx265",
        "acodec": "aac",
        "vbitrate": "6000k",
        "abitrate": "192k",
        "extension": "mp4",
    },
    "webm_vp9": {
        "description": "WebM VP9",
        "vcodec": "libvpx-vp9",
        "acodec": "libvorbis",
        "vbitrate": "5000k",
        "abitrate": "192k",
        "extension": "webm",
    },
    "prores": {
        "description": "Apple ProRes 422",
        "vcodec": "prores_ks",
        "acodec": "pcm_s16le",
        "vbitrate": "0",
        "abitrate": "0",
        "extension": "mov",
    },
    "lossless": {
        "description": "FFV1 Lossless",
        "vcodec": "ffv1",
        "acodec": "flac",
        "vbitrate": "0",
        "abitrate": "0",
        "extension": "mkv",
    },
    "gif": {
        "description": "Animated GIF",
        "vcodec": "gif",
        "acodec": "none",
        "vbitrate": "0",
        "abitrate": "0",
        "extension": "gif",
    },
    "audio_only": {
        "description": "Audio Only (WAV)",
        "vcodec": "none",
        "acodec": "pcm_s16le",
        "vbitrate": "0",
        "abitrate": "0",
        "extension": "wav",
    },
}


def generate_kdenlive_xml(project: Dict[str, Any]) -> str:
    """Generate valid Kdenlive/MLT XML from the JSON project.

    Returns the XML string.
    """
    return build_mlt_xml(project)


def list_render_presets() -> List[Dict[str, Any]]:
    """List available render presets."""
    result = []
    for name, p in RENDER_PRESETS.items():
        result.append({
            "name": name,
            "description": p["description"],
            "vcodec": p["vcodec"],
            "acodec": p["acodec"],
            "extension": p["extension"],
        })
    return result
