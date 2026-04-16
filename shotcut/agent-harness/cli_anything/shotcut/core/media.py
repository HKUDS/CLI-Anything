"""Media file operations: probe, import, list."""

import os
import subprocess
import json
import shutil
from typing import Optional

from ..utils import mlt_xml
from .session import Session


def _find_tool(name: str) -> Optional[str]:
    """Find a tool in PATH."""
    return shutil.which(name)


def probe_media(filepath: str) -> dict:
    """Probe a media file for its properties using ffprobe.

    Falls back to basic file info if ffprobe is not available.

    Returns:
        Dict with media properties (duration, codecs, resolution, etc.)
    """
    filepath = os.path.abspath(filepath)
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    ffprobe = _find_tool("ffprobe")
    if ffprobe:
        return _probe_with_ffprobe(ffprobe, filepath)
    else:
        return _probe_basic(filepath)


def _probe_with_ffprobe(ffprobe: str, filepath: str) -> dict:
    """Probe media using ffprobe."""
    try:
        result = subprocess.run(
            [ffprobe, "-v", "quiet", "-print_format", "json",
             "-show_format", "-show_streams", filepath],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return _probe_basic(filepath)

        data = json.loads(result.stdout)

        info = {
            "path": filepath,
            "filename": os.path.basename(filepath),
            "size_bytes": os.path.getsize(filepath),
        }

        # Format info
        fmt = data.get("format", {})
        info["format"] = fmt.get("format_long_name", fmt.get("format_name", "unknown"))
        info["duration_seconds"] = float(fmt.get("duration", 0))
        info["bitrate"] = int(fmt.get("bit_rate", 0))

        # Stream info
        streams = data.get("streams", [])
        video_streams = []
        audio_streams = []

        for stream in streams:
            codec_type = stream.get("codec_type")
            if codec_type == "video":
                video_streams.append({
                    "codec": stream.get("codec_name", ""),
                    "width": int(stream.get("width", 0)),
                    "height": int(stream.get("height", 0)),
                    "fps": _parse_fps(stream.get("r_frame_rate", "0/1")),
                    "pix_fmt": stream.get("pix_fmt", ""),
                    "duration": float(stream.get("duration", 0)),
                })
            elif codec_type == "audio":
                audio_streams.append({
                    "codec": stream.get("codec_name", ""),
                    "sample_rate": int(stream.get("sample_rate", 0)),
                    "channels": int(stream.get("channels", 0)),
                    "channel_layout": stream.get("channel_layout", ""),
                    "duration": float(stream.get("duration", 0)),
                })

        info["video_streams"] = video_streams
        info["audio_streams"] = audio_streams

        return info

    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return _probe_basic(filepath)


def _probe_basic(filepath: str) -> dict:
    """Basic file info without ffprobe."""
    stat = os.stat(filepath)
    ext = os.path.splitext(filepath)[1].lower()

    media_type = "unknown"
    if ext in (".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv", ".m4v", ".ts", ".mts"):
        media_type = "video"
    elif ext in (".mp3", ".wav", ".flac", ".ogg", ".aac", ".m4a", ".wma", ".opus"):
        media_type = "audio"
    elif ext in (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp", ".svg"):
        media_type = "image"
    elif ext in (".mlt",):
        media_type = "mlt_project"

    return {
        "path": filepath,
        "filename": os.path.basename(filepath),
        "size_bytes": stat.st_size,
        "media_type": media_type,
        "extension": ext,
        "note": "Install ffprobe for detailed media analysis",
    }


def _parse_fps(fps_str: str) -> float:
    """Parse FPS from ffprobe format like '30000/1001'."""
    try:
        if "/" in fps_str:
            num, den = fps_str.split("/")
            return round(int(num) / int(den), 3)
        return round(float(fps_str), 3)
    except (ValueError, ZeroDivisionError):
        return 0.0


def list_media(session: Session) -> list[dict]:
    """List all media producers in the current project.

    Returns:
        List of media clip info dicts
    """
    if not session.is_open:
        raise RuntimeError("No project is open")

    producers = mlt_xml.get_all_producers(session.root)
    result = []

    for prod in producers:
        service = mlt_xml.get_property(prod, "mlt_service", "")
        resource = mlt_xml.get_property(prod, "resource", "")

        # Skip internal producers (black background, etc.)
        if service in ("color", "colour") or resource in ("0", ""):
            continue

        result.append({
            "id": prod.get("id"),
            "resource": resource,
            "caption": mlt_xml.get_property(prod, "shotcut:caption", ""),
            "service": service or "avformat",
            "in": prod.get("in", ""),
            "out": prod.get("out", ""),
            "exists": os.path.isfile(resource) if resource else False,
        })

    return result


def check_media_files(session: Session) -> dict:
    """Check all media files in the project for existence.

    Returns:
        Dict with lists of found and missing files
    """
    media = list_media(session)
    found = []
    missing = []

    for m in media:
        if m["exists"]:
            found.append(m["resource"])
        else:
            missing.append(m["resource"])

    return {
        "total": len(media),
        "found": found,
        "missing": missing,
        "all_present": len(missing) == 0,
    }


def generate_thumbnail(filepath: str, output: str,
                       time: str = "00:00:01.000",
                       width: int = 320, height: int = 180) -> dict:
    """Generate a thumbnail from a video file.

    Requires ffmpeg to be available.
    """
    filepath = os.path.abspath(filepath)
    output = os.path.abspath(output)

    ffmpeg = _find_tool("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required for thumbnail generation")

    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    result = subprocess.run(
        [ffmpeg, "-y", "-ss", time, "-i", filepath,
         "-vframes", "1", "-s", f"{width}x{height}",
         output],
        capture_output=True, text=True, timeout=30,
    )

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")

    return {
        "action": "generate_thumbnail",
        "source": filepath,
        "output": output,
        "time": time,
        "size": f"{width}x{height}",
    }
