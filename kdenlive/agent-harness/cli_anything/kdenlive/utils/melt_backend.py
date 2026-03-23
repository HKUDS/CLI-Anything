"""MLT/melt backend — invoke melt for rendering MLT XML projects.

Shotcut and Kdenlive both use the MLT framework. The `melt` command-line
tool can render MLT XML projects to video files.

Requires: melt (system package)
    apt install melt
"""

import os
import shutil
import subprocess
import tempfile
from typing import Optional


# Allowlisted codecs for melt/ffmpeg rendering.
# An AI agent controls the codec parameters — accepting arbitrary strings
# could let a compromised or prompt-injected agent pass crafted values to
# the melt subprocess.  Only codecs known to produce valid output are
# permitted; callers can extend ALLOWED_VCODECS / ALLOWED_ACODECS if needed.
ALLOWED_VCODECS = frozenset({
    "libx264", "libx265", "libvpx", "libvpx-vp9",
    "mpeg4", "mpeg2video", "mjpeg", "huffyuv", "ffv1",
    "prores", "prores_ks", "dnxhd",
    "png", "gif", "rawvideo",
    "libaom-av1", "libsvtav1",
    "h264_nvenc", "hevc_nvenc", "h264_vaapi", "hevc_vaapi",
})

ALLOWED_ACODECS = frozenset({
    "aac", "libmp3lame", "libvorbis", "libopus",
    "pcm_s16le", "pcm_s24le", "pcm_s32le", "pcm_f32le",
    "flac", "alac", "ac3", "eac3",
    "wmav2",
})


def _validate_codec(value: str, allowed: frozenset, label: str) -> str:
    """Validate that a codec name is in the allowlist."""
    if not value:
        return value
    if value not in allowed:
        raise ValueError(
            f"Unsupported {label}: '{value}'. "
            f"Allowed values: {sorted(allowed)}"
        )
    return value


# Arguments that could override validated codec or consumer settings.
_BLOCKED_ARG_PREFIXES = ("vcodec=", "acodec=", "-consumer")


def _validate_extra_args(extra_args: list) -> list:
    """Reject extra_args that would bypass codec or consumer validation."""
    for arg in extra_args:
        for prefix in _BLOCKED_ARG_PREFIXES:
            if arg.startswith(prefix):
                raise ValueError(
                    f"extra_args cannot override '{prefix.rstrip('=')}'. "
                    f"Use the dedicated parameter instead."
                )
    return extra_args


def find_melt() -> str:
    """Find the melt executable. Raises RuntimeError if not found."""
    path = shutil.which("melt")
    if path:
        return path
    raise RuntimeError(
        "melt is not installed. Install it with:\n"
        "  apt install melt   # Debian/Ubuntu"
    )


def find_ffmpeg() -> str:
    """Find ffmpeg executable."""
    path = shutil.which("ffmpeg")
    if path:
        return path
    raise RuntimeError("ffmpeg is not installed. apt install ffmpeg")


def get_melt_version() -> str:
    """Get the installed melt version string."""
    melt = find_melt()
    result = subprocess.run(
        [melt, "--version"],
        capture_output=True, text=True, timeout=10,
    )
    # melt outputs version info differently
    output = result.stdout.strip() or result.stderr.strip()
    return output.split("\n")[0] if output else "unknown"


def render_mlt(
    mlt_path: str,
    output_path: str,
    vcodec: str = "libx264",
    acodec: str = "aac",
    overwrite: bool = False,
    timeout: int = 300,
    extra_args: Optional[list] = None,
) -> dict:
    """Render an MLT XML file to a video using melt.

    Args:
        mlt_path: Path to the .mlt XML file
        output_path: Output video file path
        vcodec: Video codec
        acodec: Audio codec
        overwrite: Allow overwriting existing files
        timeout: Maximum seconds
        extra_args: Additional melt arguments

    Returns:
        Dict with output path, file size, method
    """
    _validate_codec(vcodec, ALLOWED_VCODECS, "video codec")
    _validate_codec(acodec, ALLOWED_ACODECS, "audio codec")

    if not os.path.exists(mlt_path):
        raise FileNotFoundError(f"MLT file not found: {mlt_path}")

    if os.path.exists(output_path) and not overwrite:
        raise FileExistsError(f"Output file exists: {output_path}")

    melt = find_melt()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    cmd = [
        melt, mlt_path,
        "-consumer", f"avformat:{output_path}",
        f"vcodec={vcodec}",
        f"acodec={acodec}",
    ]

    if extra_args:
        _validate_extra_args(extra_args)
        cmd.extend(extra_args)

    result = subprocess.run(
        cmd,
        capture_output=True, text=True,
        timeout=timeout,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"melt render failed (exit {result.returncode}):\n"
            f"  stderr: {result.stderr[-500:]}"
        )

    if not os.path.exists(output_path):
        raise RuntimeError(
            f"melt produced no output file.\n"
            f"  Expected: {output_path}\n"
            f"  stdout: {result.stdout[-500:]}"
        )

    return {
        "output": os.path.abspath(output_path),
        "format": os.path.splitext(output_path)[1].lstrip("."),
        "method": "melt",
        "file_size": os.path.getsize(output_path),
    }


def render_color_bars(
    output_path: str,
    duration: int = 3,
    width: int = 320,
    height: int = 240,
    fps: int = 25,
    vcodec: str = "libx264",
    acodec: str = "aac",
    overwrite: bool = False,
    timeout: int = 120,
) -> dict:
    """Render a color bars test video using melt's built-in producer.

    This doesn't require any input files — perfect for E2E testing.
    """
    _validate_codec(vcodec, ALLOWED_VCODECS, "video codec")
    _validate_codec(acodec, ALLOWED_ACODECS, "audio codec")

    if os.path.exists(output_path) and not overwrite:
        raise FileExistsError(f"Output file exists: {output_path}")

    melt = find_melt()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    frames = duration * fps
    cmd = [
        melt,
        f"color:red", f"out={fps - 1}",
        f"color:green", f"out={fps - 1}",
        f"color:blue", f"out={fps - 1}",
        "-consumer", f"avformat:{output_path}",
        f"width={width}", f"height={height}",
        f"frame_rate_num={fps}",
        f"vcodec={vcodec}",
        f"acodec={acodec}",
        "ar=48000", "channels=2",
    ]

    result = subprocess.run(
        cmd,
        capture_output=True, text=True,
        timeout=timeout,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"melt render failed (exit {result.returncode}):\n"
            f"  stderr: {result.stderr[-500:]}"
        )

    if not os.path.exists(output_path):
        raise RuntimeError(f"melt produced no output: {output_path}")

    return {
        "output": os.path.abspath(output_path),
        "format": os.path.splitext(output_path)[1].lstrip("."),
        "method": "melt",
        "file_size": os.path.getsize(output_path),
        "duration_seconds": duration,
    }
