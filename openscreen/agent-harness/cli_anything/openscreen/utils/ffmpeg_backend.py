"""ffmpeg backend — subprocess wrapper for video processing.

Openscreen's GUI uses WebCodecs + PixiJS for rendering, but the CLI
harness delegates to ffmpeg for all video operations: probe, crop,
zoom (via crop+scale), speed changes, trim, background compositing,
and final export.
"""

import json
import os
import shutil
import subprocess
from typing import Optional


def find_ffmpeg() -> str:
    """Find the ffmpeg executable. Raises RuntimeError if not found."""
    path = shutil.which("ffmpeg")
    if path:
        return path
    raise RuntimeError(
        "ffmpeg is not installed.\n"
        "  macOS:  brew install ffmpeg\n"
        "  Linux:  apt install ffmpeg\n"
        "  Windows: winget install ffmpeg"
    )


def find_ffprobe() -> str:
    """Find the ffprobe executable. Raises RuntimeError if not found."""
    path = shutil.which("ffprobe")
    if path:
        return path
    raise RuntimeError(
        "ffprobe is not installed (usually bundled with ffmpeg).\n"
        "  macOS:  brew install ffmpeg\n"
        "  Linux:  apt install ffmpeg"
    )


def probe(input_path: str) -> dict:
    """Probe a media file and return its metadata.

    Returns dict with keys: width, height, duration, fps, codec,
    has_audio, file_size, path.
    """
    exe = find_ffprobe()
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"File not found: {input_path}")

    cmd = [
        exe, "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        input_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr[:500]}")

    data = json.loads(result.stdout)

    video_stream = None
    has_audio = False
    for s in data.get("streams", []):
        if s.get("codec_type") == "video" and video_stream is None:
            video_stream = s
        if s.get("codec_type") == "audio":
            has_audio = True

    if not video_stream:
        raise ValueError(f"No video stream in {input_path}")

    width = int(video_stream["width"])
    height = int(video_stream["height"])

    duration = float(data["format"].get("duration", 0))
    if duration == 0 and "duration" in video_stream:
        duration = float(video_stream["duration"])

    r_frame_rate = video_stream.get("r_frame_rate", "30/1")
    num, den = r_frame_rate.split("/")
    fps = float(num) / float(den) if float(den) != 0 else 30.0

    return {
        "width": width,
        "height": height,
        "duration": round(duration, 3),
        "fps": round(fps, 2),
        "codec": video_stream.get("codec_name", "unknown"),
        "has_audio": has_audio,
        "file_size": os.path.getsize(input_path),
        "path": os.path.abspath(input_path),
    }


def render_segment(
    input_path: str,
    output_path: str,
    start_s: float,
    end_s: float,
    target_w: int,
    target_h: int,
    fps: int = 30,
    speed: float = 1.0,
    crop: Optional[dict] = None,
    overwrite: bool = True,
    timeout: int = 300,
) -> dict:
    """Render a video segment with optional crop and speed change.

    Args:
        input_path: Source video file.
        output_path: Destination MP4 file.
        start_s: Start time in seconds.
        end_s: End time in seconds.
        target_w: Output width.
        target_h: Output height.
        fps: Output frame rate.
        speed: Playback speed multiplier.
        crop: Optional dict with keys w, h, x, y (pixel values).
        overwrite: Whether to overwrite existing output.
        timeout: Subprocess timeout in seconds.

    Returns:
        Dict with output path, file_size, method.
    """
    exe = find_ffmpeg()
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"Input not found: {input_path}")
    if os.path.exists(output_path) and not overwrite:
        raise FileExistsError(f"Output exists: {output_path}")

    vf_parts = []
    if crop:
        vf_parts.append(f"crop={crop['w']}:{crop['h']}:{crop['x']}:{crop['y']}")
    vf_parts.append(f"scale={target_w}:{target_h}:flags=lanczos")
    if speed != 1.0:
        vf_parts.append(f"setpts={1.0/speed}*PTS")

    af = None
    if speed != 1.0:
        af_parts = []
        s = speed
        while s > 2.0:
            af_parts.append("atempo=2.0")
            s /= 2.0
        while s < 0.5:
            af_parts.append("atempo=0.5")
            s *= 2.0
        af_parts.append(f"atempo={s:.4f}")
        af = ",".join(af_parts)

    cmd = [
        exe, "-y" if overwrite else "-n",
        "-ss", str(start_s), "-to", str(end_s),
        "-i", input_path,
        "-vf", ",".join(vf_parts),
    ]
    if af:
        cmd += ["-af", af]
    cmd += [
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k",
        "-r", str(fps), "-pix_fmt", "yuv420p",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg render failed (exit {result.returncode}):\n"
            f"  stderr: {result.stderr[-500:]}"
        )
    if not os.path.exists(output_path):
        raise RuntimeError(f"ffmpeg produced no output: {output_path}")

    return {
        "output": os.path.abspath(output_path),
        "file_size": os.path.getsize(output_path),
        "method": "ffmpeg",
    }


def concat_segments(
    segment_paths: list[str],
    output_path: str,
    overwrite: bool = True,
    timeout: int = 300,
) -> dict:
    """Concatenate multiple video segments into one file.

    Args:
        segment_paths: List of MP4 file paths to concatenate in order.
        output_path: Output MP4 path.

    Returns:
        Dict with output path, file_size, segment_count.
    """
    exe = find_ffmpeg()
    if not segment_paths:
        raise ValueError("No segments to concatenate")

    import tempfile
    concat_file = tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False
    )
    try:
        for sp in segment_paths:
            concat_file.write(f"file '{os.path.abspath(sp)}'\n")
        concat_file.close()

        cmd = [
            exe, "-y" if overwrite else "-n",
            "-f", "concat", "-safe", "0",
            "-i", concat_file.name,
            "-c", "copy",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg concat failed: {result.stderr[-500:]}")
    finally:
        os.unlink(concat_file.name)

    return {
        "output": os.path.abspath(output_path),
        "file_size": os.path.getsize(output_path),
        "segment_count": len(segment_paths),
        "method": "ffmpeg-concat",
    }


def composite_on_background(
    input_path: str,
    output_path: str,
    canvas_w: int,
    canvas_h: int,
    video_w: int,
    video_h: int,
    bg_color: str = "#1a1a2e",
    fps: int = 30,
    overwrite: bool = True,
    timeout: int = 300,
) -> dict:
    """Composite a video centered on a solid-color background.

    Args:
        input_path: Source video (already scaled to video_w x video_h).
        output_path: Output MP4 path.
        canvas_w, canvas_h: Full output canvas size.
        video_w, video_h: Video size within canvas.
        bg_color: Hex color for background.
        fps: Output frame rate.
    """
    exe = find_ffmpeg()
    x_off = (canvas_w - video_w) // 2
    y_off = (canvas_h - video_h) // 2

    cmd = [
        exe, "-y" if overwrite else "-n",
        "-f", "lavfi", "-i",
        f"color=c='{bg_color}':s={canvas_w}x{canvas_h}:r={fps}",
        "-i", input_path,
        "-filter_complex",
        f"[1:v]scale={video_w}:{video_h}[fg];"
        f"[0:v][fg]overlay={x_off}:{y_off}:shortest=1",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-map", "1:a?",
        "-pix_fmt", "yuv420p",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg composite failed: {result.stderr[-500:]}")

    return {
        "output": os.path.abspath(output_path),
        "file_size": os.path.getsize(output_path),
        "method": "ffmpeg-composite",
    }


def extract_frames(
    input_path: str,
    output_dir: str,
    fps: float = 2.0,
    max_frames: int = 60,
    scale_width: int = 960,
) -> list[str]:
    """Extract frames from a video for analysis.

    Returns list of JPEG file paths.
    """
    exe = find_ffmpeg()
    os.makedirs(output_dir, exist_ok=True)

    cmd = [
        exe, "-y", "-i", input_path,
        "-vf", f"fps={fps},scale={scale_width}:-1",
        "-frames:v", str(max_frames),
        "-q:v", "3",
        os.path.join(output_dir, "frame_%04d.jpg"),
    ]
    subprocess.run(cmd, capture_output=True, check=True, timeout=120)

    return sorted([
        os.path.join(output_dir, f)
        for f in os.listdir(output_dir)
        if f.startswith("frame_") and f.endswith(".jpg")
    ])
