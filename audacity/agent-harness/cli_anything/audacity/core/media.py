"""Audacity CLI - Audio probing and media analysis module.

Uses the wave module (stdlib) to probe WAV files and extract
metadata such as sample rate, channels, duration, bit depth.
"""

import os
import wave
import struct
from typing import Dict, Any, Optional


def probe_audio(path: str) -> Dict[str, Any]:
    """Analyze an audio file and return metadata."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Audio file not found: {path}")

    abs_path = os.path.abspath(path)
    info = {
        "path": abs_path,
        "filename": os.path.basename(path),
        "file_size": os.path.getsize(abs_path),
        "file_size_human": _human_size(os.path.getsize(abs_path)),
    }

    ext = os.path.splitext(path)[1].lower()
    info["extension"] = ext

    # Try WAV probing (stdlib)
    if ext in (".wav",):
        try:
            with wave.open(abs_path, "r") as wf:
                info["format"] = "WAV"
                info["sample_rate"] = wf.getframerate()
                info["channels"] = wf.getnchannels()
                info["sample_width"] = wf.getsampwidth()
                info["bit_depth"] = wf.getsampwidth() * 8
                info["frames"] = wf.getnframes()
                info["duration"] = wf.getnframes() / wf.getframerate()
                info["duration_human"] = _format_time(info["duration"])
                info["compression_type"] = wf.getcomptype()
                info["compression_name"] = wf.getcompname()

                # Calculate bitrate
                info["bitrate"] = (
                    wf.getframerate() * wf.getnchannels() * wf.getsampwidth() * 8
                )
                info["bitrate_human"] = f"{info['bitrate'] / 1000:.0f} kbps"
        except (wave.Error, EOFError, struct.error) as e:
            info["error"] = f"Could not read WAV: {e}"
            info["format"] = "WAV (invalid)"
    else:
        info["format"] = _guess_format(ext)
        info["note"] = "Detailed probing only available for WAV files"

    return info


def check_media(project: Dict[str, Any]) -> Dict[str, Any]:
    """Check that all referenced audio files exist."""
    sources = []
    for track in project.get("tracks", []):
        for clip in track.get("clips", []):
            source = clip.get("source", "")
            if source:
                sources.append({
                    "track": track.get("name", ""),
                    "clip": clip.get("name", ""),
                    "source": source,
                    "exists": os.path.exists(source),
                })

    missing = [s for s in sources if not s["exists"]]
    return {
        "total": len(sources),
        "found": len(sources) - len(missing),
        "missing": len(missing),
        "missing_files": [s["source"] for s in missing],
        "status": "ok" if not missing else "missing_files",
    }


def get_duration(path: str) -> float:
    """Get the duration of an audio file in seconds."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Audio file not found: {path}")

    try:
        with wave.open(path, "r") as wf:
            return wf.getnframes() / wf.getframerate()
    except (wave.Error, EOFError, struct.error):
        return 0.0


def _guess_format(ext: str) -> str:
    """Guess audio format from extension."""
    fmt_map = {
        ".wav": "WAV", ".mp3": "MP3", ".flac": "FLAC",
        ".ogg": "OGG", ".aiff": "AIFF", ".aif": "AIFF",
        ".m4a": "M4A", ".wma": "WMA", ".opus": "OPUS",
    }
    return fmt_map.get(ext, "unknown")


def _human_size(nbytes: int) -> str:
    """Convert byte count to human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if nbytes < 1024:
            return f"{nbytes:.1f} {unit}"
        nbytes /= 1024
    return f"{nbytes:.1f} TB"


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
