"""Export pipeline — render the final video from project state.

Strategy:
1. Read project editor state (zoom, speed, trim, crop, background, padding)
2. Split video into segments based on region boundaries
3. Render each segment with ffmpeg (crop for zoom, setpts for speed)
4. Concatenate segments
5. Composite onto background canvas with padding
6. Verify output with ffprobe
"""

import os
import tempfile
from typing import Optional, Callable

from .session import Session
from ..utils import ffmpeg_backend


ZOOM_SCALES = {1: 1.25, 2: 1.5, 3: 1.8, 4: 2.2, 5: 3.5, 6: 5.0}

ASPECT_DIMENSIONS = {
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
    "4:3": (1440, 1080),
    "4:5": (1080, 1350),
    "16:10": (1920, 1200),
    "10:16": (1200, 1920),
}

BG_COLORS = {
    "gradient_dark": "#1a1a2e",
    "solid_dark": "#1a1a2e",
    "gradient_light": "#fdf6f0",
    "solid_light": "#f5f5f5",
    "gradient_sunset": "#2d1b3d",
    "blur": "#1a1a2e",
}


def list_presets() -> list[dict]:
    """List available export presets."""
    return [
        {"name": "mp4_good", "format": "mp4", "quality": "good", "description": "MP4 H.264, balanced quality"},
        {"name": "mp4_source", "format": "mp4", "quality": "source", "description": "MP4 H.264, source quality"},
        {"name": "mp4_medium", "format": "mp4", "quality": "medium", "description": "MP4 H.264, smaller file"},
        {"name": "gif_medium", "format": "gif", "quality": "medium", "description": "GIF, 720p, 15fps"},
    ]


def render(
    session: Session,
    output_path: str,
    on_progress: Optional[Callable] = None,
) -> dict:
    """Render the project to a final video file.

    Args:
        session: Active session with open project.
        output_path: Destination file path.
        on_progress: Optional callback(stage, message).

    Returns:
        Dict with output path, file_size, duration, resolution.
    """
    if not session.is_open:
        raise RuntimeError("No project is open")

    editor = session.editor
    media = session.data.get("media", {})
    video_path = media.get("screenVideoPath")
    if not video_path:
        video_path = session.data.get("videoPath")
    if not video_path or not os.path.isfile(video_path):
        raise FileNotFoundError(
            f"Source video not found: {video_path}. "
            "Set it with: project set-video <path>"
        )

    # Probe source
    if on_progress:
        on_progress("probe", "Probing source video...")
    meta = ffmpeg_backend.probe(video_path)
    src_w, src_h = meta["width"], meta["height"]
    duration = meta["duration"]
    fps = min(int(meta["fps"]), 30)

    # Read editor state
    zoom_regions = editor.get("zoomRegions", [])
    speed_regions = editor.get("speedRegions", [])
    trim_regions = editor.get("trimRegions", [])
    crop_region = editor.get("cropRegion", {"x": 0, "y": 0, "width": 1, "height": 1})
    aspect_ratio = editor.get("aspectRatio", "16:9")
    padding_pct = editor.get("padding", 50)
    background = editor.get("wallpaper", "gradient_dark")

    # Calculate dimensions
    out_w, out_h = ASPECT_DIMENSIONS.get(aspect_ratio, (1920, 1080))
    padding_scale = 1.0 - (padding_pct / 100.0) * 0.4
    vid_w = int(out_w * padding_scale)
    vid_h = int(out_h * padding_scale)

    # Apply crop to source dimensions
    crop_x = int(crop_region["x"] * src_w)
    crop_y = int(crop_region["y"] * src_h)
    crop_w = int(crop_region["width"] * src_w)
    crop_h = int(crop_region["height"] * src_h)
    effective_w = crop_w
    effective_h = crop_h

    # Maintain aspect ratio within padded area
    src_ar = effective_w / effective_h
    if vid_w / vid_h > src_ar:
        vid_w = int(vid_h * src_ar)
    else:
        vid_h = int(vid_w / src_ar)
    vid_w -= vid_w % 2
    vid_h -= vid_h % 2
    out_w -= out_w % 2
    out_h -= out_h % 2

    # Build timeline segments
    trim_ranges = [(t["startMs"] / 1000, t["endMs"] / 1000) for t in trim_regions]

    def is_trimmed(t):
        return any(ts <= t <= te for ts, te in trim_ranges)

    def get_speed_at(t):
        for sr in speed_regions:
            if sr["startMs"] / 1000 <= t < sr["endMs"] / 1000:
                return sr["speed"]
        return 1.0

    def get_zoom_at(t):
        for zr in zoom_regions:
            if zr["startMs"] / 1000 <= t < zr["endMs"] / 1000:
                return zr
        return None

    # Event boundaries
    events = sorted(set(
        [0.0, duration]
        + [z["startMs"] / 1000 for z in zoom_regions]
        + [z["endMs"] / 1000 for z in zoom_regions]
        + [s["startMs"] / 1000 for s in speed_regions]
        + [s["endMs"] / 1000 for s in speed_regions]
        + [t["startMs"] / 1000 for t in trim_regions]
        + [t["endMs"] / 1000 for t in trim_regions]
    ))
    events = [e for e in events if 0 <= e <= duration]

    segments = []
    for i in range(len(events) - 1):
        s, e = events[i], events[i + 1]
        if e - s < 0.05:
            continue
        mid = (s + e) / 2
        if is_trimmed(mid):
            continue
        segments.append({
            "start": s, "end": e,
            "speed": get_speed_at(mid),
            "zoom": get_zoom_at(mid),
        })

    if not segments:
        segments = [{"start": 0, "end": duration, "speed": 1.0, "zoom": None}]

    if on_progress:
        on_progress("timeline", f"Built {len(segments)} segments")

    # Render segments
    tmpdir = tempfile.mkdtemp(prefix="openscreen_export_")
    seg_files = []

    for idx, seg in enumerate(segments):
        seg_file = os.path.join(tmpdir, f"seg_{idx:04d}.mp4")
        if on_progress:
            on_progress("segment", f"Segment {idx+1}/{len(segments)}")

        crop = None
        if seg["zoom"]:
            zr = seg["zoom"]
            zscale = ZOOM_SCALES.get(zr.get("depth", 3), 1.8)
            fx = max(0.05, min(0.95, zr["focus"]["cx"]))
            fy = max(0.05, min(0.95, zr["focus"]["cy"]))

            zw = int(effective_w / zscale)
            zh = int(effective_h / zscale)
            zw -= zw % 2
            zh -= zh % 2
            zx = max(0, min(effective_w - zw, int(fx * effective_w - zw / 2)))
            zy = max(0, min(effective_h - zh, int(fy * effective_h - zh / 2)))

            # Offset by crop region
            crop = {
                "w": zw, "h": zh,
                "x": crop_x + zx, "y": crop_y + zy,
            }
        elif crop_region != {"x": 0, "y": 0, "width": 1, "height": 1}:
            crop = {"w": crop_w, "h": crop_h, "x": crop_x, "y": crop_y}

        ffmpeg_backend.render_segment(
            input_path=video_path,
            output_path=seg_file,
            start_s=seg["start"],
            end_s=seg["end"],
            target_w=vid_w,
            target_h=vid_h,
            fps=fps,
            speed=seg["speed"],
            crop=crop,
        )
        if os.path.exists(seg_file):
            seg_files.append(seg_file)

    if not seg_files:
        raise RuntimeError("No segments rendered successfully")

    # Concat
    if on_progress:
        on_progress("concat", f"Concatenating {len(seg_files)} segments")

    concat_out = os.path.join(tmpdir, "concat.mp4")
    ffmpeg_backend.concat_segments(seg_files, concat_out)

    # Composite on background
    if on_progress:
        on_progress("composite", "Adding background and padding")

    bg_color = BG_COLORS.get(background, "#1a1a2e")
    ffmpeg_backend.composite_on_background(
        input_path=concat_out,
        output_path=output_path,
        canvas_w=out_w,
        canvas_h=out_h,
        video_w=vid_w,
        video_h=vid_h,
        bg_color=bg_color,
        fps=fps,
    )

    # Verify output
    if on_progress:
        on_progress("verify", "Verifying output...")

    out_meta = ffmpeg_backend.probe(output_path)

    # Cleanup
    for f in seg_files + [concat_out]:
        try:
            os.remove(f)
        except OSError:
            pass
    try:
        os.rmdir(tmpdir)
    except OSError:
        pass

    return {
        "output": os.path.abspath(output_path),
        "file_size": out_meta["file_size"],
        "duration": out_meta["duration"],
        "width": out_meta["width"],
        "height": out_meta["height"],
        "codec": out_meta["codec"],
        "segments_rendered": len(seg_files),
    }
