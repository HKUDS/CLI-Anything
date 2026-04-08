"""Media operations — probe input files, extract thumbnails."""

import os

from ..utils import ffmpeg_backend


def probe(path: str) -> dict:
    """Probe a media file and return metadata.

    Returns dict with: width, height, duration, fps, codec,
    has_audio, file_size, path.
    """
    return ffmpeg_backend.probe(path)


def check_video(path: str) -> dict:
    """Check if a video file is valid and usable.

    Returns dict with validity status and metadata.
    """
    if not os.path.isfile(path):
        return {"valid": False, "error": f"File not found: {path}"}

    try:
        meta = ffmpeg_backend.probe(path)
        return {
            "valid": True,
            "width": meta["width"],
            "height": meta["height"],
            "duration": meta["duration"],
            "fps": meta["fps"],
            "codec": meta["codec"],
            "has_audio": meta["has_audio"],
            "file_size": meta["file_size"],
        }
    except Exception as e:
        return {"valid": False, "error": str(e)}


def extract_thumbnail(input_path: str, output_path: str,
                      time_s: float = 0.0) -> dict:
    """Extract a single frame as a JPEG thumbnail.

    Args:
        input_path: Source video.
        output_path: Destination JPEG path.
        time_s: Timestamp to capture (seconds).

    Returns:
        Dict with output path and file_size.
    """
    import subprocess

    exe = ffmpeg_backend.find_ffmpeg()
    cmd = [
        exe, "-y", "-ss", str(time_s),
        "-i", input_path,
        "-frames:v", "1",
        "-q:v", "2",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"Thumbnail extraction failed: {result.stderr[:500]}")

    return {
        "output": os.path.abspath(output_path),
        "file_size": os.path.getsize(output_path),
        "time_s": time_s,
    }
