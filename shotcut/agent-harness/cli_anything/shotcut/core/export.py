"""Export/render operations: encode projects to video files."""

import os
import subprocess
import shutil
from typing import Optional

from ..utils import mlt_xml
from .session import Session


EXPORT_PRESETS = {
    "default": {
        "description": "H.264 High Profile, AAC (default quality)",
        "vcodec": "libx264",
        "acodec": "aac",
        "vb": "0",
        "crf": "21",
        "preset": "medium",
        "ab": "384k",
        "ar": "48000",
        "channels": "2",
        "format": "mp4",
    },
    "h264-high": {
        "description": "H.264 High Profile, high quality",
        "vcodec": "libx264",
        "acodec": "aac",
        "vb": "0",
        "crf": "15",
        "preset": "slow",
        "ab": "384k",
        "ar": "48000",
        "channels": "2",
        "format": "mp4",
    },
    "h264-fast": {
        "description": "H.264 High Profile, fast encoding",
        "vcodec": "libx264",
        "acodec": "aac",
        "vb": "0",
        "crf": "23",
        "preset": "ultrafast",
        "ab": "256k",
        "ar": "48000",
        "channels": "2",
        "format": "mp4",
    },
    "h265": {
        "description": "H.265/HEVC, good compression",
        "vcodec": "libx265",
        "acodec": "aac",
        "vb": "0",
        "crf": "23",
        "preset": "medium",
        "ab": "384k",
        "ar": "48000",
        "channels": "2",
        "format": "mp4",
    },
    "webm-vp9": {
        "description": "VP9 WebM for web delivery",
        "vcodec": "libvpx-vp9",
        "acodec": "libvorbis",
        "vb": "2M",
        "crf": "30",
        "ab": "192k",
        "ar": "48000",
        "channels": "2",
        "format": "webm",
    },
    "prores": {
        "description": "Apple ProRes 422 (intermediate/editing)",
        "vcodec": "prores_ks",
        "acodec": "pcm_s16le",
        "profile:v": "2",
        "ab": "",
        "ar": "48000",
        "channels": "2",
        "format": "mov",
    },
    "gif": {
        "description": "Animated GIF",
        "vcodec": "gif",
        "acodec": "",
        "format": "gif",
    },
    "audio-mp3": {
        "description": "MP3 audio only",
        "vcodec": "",
        "acodec": "libmp3lame",
        "ab": "320k",
        "ar": "48000",
        "channels": "2",
        "format": "mp3",
    },
    "audio-wav": {
        "description": "WAV audio only (lossless)",
        "vcodec": "",
        "acodec": "pcm_s16le",
        "ar": "48000",
        "channels": "2",
        "format": "wav",
    },
    "png-sequence": {
        "description": "PNG image sequence",
        "vcodec": "png",
        "acodec": "",
        "format": "png",
    },
}


def list_presets() -> list[dict]:
    """List all available export presets."""
    result = []
    for name, preset in sorted(EXPORT_PRESETS.items()):
        result.append({
            "name": name,
            "description": preset["description"],
            "format": preset.get("format", ""),
            "vcodec": preset.get("vcodec", ""),
            "acodec": preset.get("acodec", ""),
        })
    return result


def get_preset_info(preset_name: str) -> dict:
    """Get detailed info about an export preset."""
    if preset_name not in EXPORT_PRESETS:
        available = ", ".join(sorted(EXPORT_PRESETS.keys()))
        raise ValueError(f"Unknown preset: {preset_name!r}. Available: {available}")
    info = dict(EXPORT_PRESETS[preset_name])
    info["name"] = preset_name
    return info


def render(session: Session, output_path: str,
           preset: str = "default",
           width: Optional[int] = None,
           height: Optional[int] = None,
           overwrite: bool = False,
           extra_args: Optional[list[str]] = None,
           prefer_ffmpeg: bool = False) -> dict:
    """Render the project to an output file.

    This works by:
    1. Saving the current project to a temporary .mlt file
    2. Using melt to render it

    Args:
        session: Active session with an open project
        output_path: Path for the output file
        preset: Export preset name
        width: Override output width
        height: Override output height
        overwrite: Overwrite existing output file
        extra_args: Additional command-line arguments for the encoder
        prefer_ffmpeg: Backward-compatible preview hint; melt remains the
            render backend because it natively interprets MLT projects.
    """
    if not session.is_open:
        raise RuntimeError("No project is open")

    output_path = os.path.abspath(output_path)
    if os.path.exists(output_path) and not overwrite:
        raise FileExistsError(
            f"Output file already exists: {output_path}. Use --overwrite to replace."
        )

    if preset not in EXPORT_PRESETS:
        available = ", ".join(sorted(EXPORT_PRESETS.keys()))
        raise ValueError(f"Unknown preset: {preset!r}. Available: {available}")

    melt = shutil.which("melt")
    if not melt:
        raise RuntimeError(
            "melt is required for rendering but not found. "
            "Install it with: apt install melt  (or equivalent for your OS)"
        )
    # No ffmpeg fallback — melt is the only render path because it natively
    # reads MLT XML and handles all project features (transitions, compositing,
    # multi-track). Direct ffmpeg encoding cannot interpret MLT projects.

    preset_config = EXPORT_PRESETS[preset]

    output_ext = os.path.splitext(output_path)[1].lower()
    if not output_ext:
        fmt = preset_config.get("format", "mp4")
        output_path += f".{fmt}"

    return _render_with_melt(session, output_path, preset_config, melt,
                             width, height, extra_args)


def _render_with_melt(session: Session, output_path: str,
                      preset: dict, melt_path: str,
                      width: Optional[int], height: Optional[int],
                      extra_args: Optional[list[str]]) -> dict:
    import tempfile

    root = session.root
    assert root is not None

    from .timeline import _update_tractor_out
    _update_tractor_out(session)

    old_producer = root.get("producer", "main_bin")
    tractor = mlt_xml.get_main_tractor(root)
    tractor_id = tractor.get("id", "tractor0") if tractor is not None else "tractor0"
    root.set("producer", tractor_id)

    try:
        with tempfile.NamedTemporaryFile(suffix=".mlt", delete=False, mode="w") as f:
            temp_mlt = f.name
            mlt_xml.write_mlt(root, temp_mlt)
    finally:
        root.set("producer", old_producer)

    try:
        cmd = [melt_path, temp_mlt, "-consumer"]

        consumer = f"avformat:{output_path}"
        cmd.append(consumer)

        vcodec = preset.get("vcodec", "")
        acodec = preset.get("acodec", "")
        if vcodec:
            cmd.extend(["vcodec=" + vcodec])
        if acodec:
            cmd.extend(["acodec=" + acodec])
        if preset.get("vb"):
            cmd.extend(["vb=" + preset["vb"]])
        if preset.get("crf"):
            cmd.extend(["crf=" + preset["crf"]])
        if preset.get("preset"):
            cmd.extend(["preset=" + preset["preset"]])
        if preset.get("ab"):
            cmd.extend(["ab=" + preset["ab"]])
        if preset.get("ar"):
            cmd.extend(["ar=" + preset["ar"]])

        if width and height:
            cmd.extend([f"width={width}", f"height={height}"])

        if extra_args:
            cmd.extend(extra_args)

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=3600
        )

        if result.returncode != 0:
            raise RuntimeError(f"melt render failed: {result.stderr}")

        return {
            "action": "render",
            "output": output_path,
            "method": "melt",
            "success": True,
            "size_bytes": os.path.getsize(output_path) if os.path.exists(output_path) else 0,
        }
    finally:
        os.unlink(temp_mlt)
