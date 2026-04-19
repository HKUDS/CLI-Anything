"""Export/render operations: encode projects to video files."""

import os
import subprocess
import shutil
from typing import Optional

from ..utils import mlt_xml
from ..utils.time import timecode_to_frames, frames_to_timecode
from .session import Session


# Export presets matching Shotcut's common presets
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

# Maps MLT filter service names to ffmpeg filter builders.
# Each builder takes the MLT filter's properties dict and returns
# an ffmpeg video or audio filter string (or None to skip).
_MLT_TO_FFMPEG_VIDEO = {
    "brightness": lambda p: _build_brightness(p),
    "frei0r.saturat0r": lambda p: f"eq=saturation={p.get('saturation', '1')}",
    "frei0r.hueshift0r": lambda p: f"hue=h={float(p.get('shift', '0')) * 360:.1f}",
    "sepia": lambda p: (
        f"colorchannelmixer="
        f"rr=0.393:rg=0.769:rb=0.189:"
        f"gr=0.349:gg=0.686:gb=0.168:"
        f"br=0.272:bg=0.534:bb=0.131"
    ),
    "charcoal": lambda p: "edgedetect=mode=colormix:high=0",
    "mirror": lambda p: "hflip" if p.get("mirror", "horizontal") == "horizontal" else "vflip",
    "crop": lambda p: (
        f"crop=iw-{int(p.get('left', 0))}-{int(p.get('right', 0))}:"
        f"ih-{int(p.get('top', 0))}-{int(p.get('bottom', 0))}:"
        f"{p.get('left', 0)}:{p.get('top', 0)}"
    ),
    "frei0r.glow": lambda p: f"gblur=sigma={float(p.get('blur', '0.5')) * 10:.1f}",
    "frei0r.IIRblur": lambda p: f"gblur=sigma={float(p.get('amount', '0.2')) * 20:.1f}",
    "dynamictext": lambda p: _build_drawtext(p),
    "greyscale": lambda p: "format=gray",
    "affine": lambda p: None,  # Complex — skip for now
    "timewarp": lambda p: f"setpts={1/float(p.get('speed', '1')):.4f}*PTS",
}

_MLT_TO_FFMPEG_AUDIO = {
    "volume": lambda p: _build_volume(p),
}


def _build_brightness(props: dict) -> str:
    """Convert MLT brightness filter to ffmpeg eq filter."""
    level = props.get("level", "1.0")
    # Check if it's a keyframed value (contains = and ;)
    if "=" in level and ";" in level:
        return _build_brightness_fade(level)
    val = float(level)
    # MLT brightness level: 1.0 = normal. ffmpeg eq brightness: 0 = normal.
    # MLT level 1.2 → ffmpeg brightness +0.08 (approximate)
    brightness = (val - 1.0) * 0.4
    return f"eq=brightness={brightness:.3f}"


def _build_brightness_fade(keyframes: str) -> Optional[str]:
    """Convert keyframed brightness to ffmpeg fade filter."""
    # Parse "00:00:00.000=0;00:00:01.000=1" format
    parts = keyframes.split(";")
    if len(parts) < 2:
        return None
    try:
        first_val = float(parts[0].split("=")[1])
        last_val = float(parts[-1].split("=")[1])
        last_tc = parts[-1].split("=")[0]
        # Parse duration
        duration = _tc_to_seconds(last_tc)
        if first_val < last_val:
            # Fade in
            return f"fade=t=in:st=0:d={duration:.3f}"
        else:
            # Fade out
            return f"fade=t=out:st=0:d={duration:.3f}"
    except (ValueError, IndexError):
        return None


def _build_volume(props: dict) -> Optional[str]:
    """Convert MLT volume filter to ffmpeg volume/afade."""
    level = props.get("level", props.get("gain", "1.0"))
    if "=" in level and ";" in level:
        return _build_volume_expression(level)
    # Check if gain in dB
    gain = props.get("gain")
    if gain:
        return f"volume={gain}dB"
    return f"volume={level}"


def _build_volume_expression(keyframes: str) -> Optional[str]:
    """Convert keyframed volume to an ffmpeg volume expression."""
    parts = [part for part in keyframes.split(";") if part]
    if not parts:
        return None
    try:
        points = []
        for part in parts:
            timecode, value = part.split("=", 1)
            points.append((_tc_to_seconds(timecode), float(value)))
        if len(points) == 1:
            return f"volume={points[0][1]}"

        def _segment(index: int) -> str:
            current_t, current_val = points[index]
            next_t, next_val = points[index + 1]
            if next_t <= current_t:
                return _segment(index + 1)
            linear = (
                f"({current_val:.6f}+({next_val:.6f}-{current_val:.6f})"
                f"*(t-{current_t:.6f})/{(next_t - current_t):.6f})"
            )
            if index + 1 == len(points) - 1:
                return linear
            return f"if(lt(t,{next_t:.6f}),{linear},{_segment(index + 1)})"

        return f"volume='if(lt(t,{points[0][0]:.6f}),{points[0][1]:.6f},{_segment(0)})'"
    except (ValueError, IndexError):
        return None


def _build_drawtext(props: dict) -> str:
    """Convert MLT dynamictext to ffmpeg drawtext."""
    text = props.get("argument", "").replace("'", "\\'").replace(":", "\\:")
    size = props.get("size", "48")
    color = props.get("fgcolour", "#ffffffff")
    # Convert #AARRGGBB to ffmpeg format
    if len(color) == 9 and color.startswith("#"):
        color = f"#{color[3:9]}"  # Strip alpha, keep RRGGBB
    halign = props.get("halign", "center")
    valign = props.get("valign", "middle")

    x = {"left": "10", "center": "(w-text_w)/2", "right": "w-text_w-10"}.get(halign, "(w-text_w)/2")
    y = {"top": "10", "middle": "(h-text_h)/2", "bottom": "h-text_h-10"}.get(valign, "(h-text_h)/2")

    return f"drawtext=text='{text}':fontsize={size}:fontcolor={color}:x={x}:y={y}"


def _tc_to_seconds(tc: str) -> float:
    """Quick timecode to seconds parser for filter keyframes."""
    parts = tc.strip().split(":")
    if len(parts) == 3:
        h, m, rest = parts
        if "." in rest:
            s, ms = rest.split(".")
            return int(h) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")[:3]) / 1000
        return int(h) * 3600 + int(m) * 60 + int(rest)
    return float(tc)


def _merge_eq_filters(filters: list[str]) -> list[str]:
    """Merge multiple ffmpeg eq= filters into a single one.

    ffmpeg only allows one eq filter per chain. So:
        eq=brightness=0.06, eq=saturation=1.3
    becomes:
        eq=brightness=0.06:saturation=1.3
    """
    eq_params = {}
    result = []
    for f in filters:
        if f.startswith("eq="):
            # Parse eq params
            for part in f[3:].split(":"):
                if "=" in part:
                    k, v = part.split("=", 1)
                    eq_params[k] = v
        else:
            result.append(f)

    if eq_params:
        eq_str = "eq=" + ":".join(f"{k}={v}" for k, v in eq_params.items())
        # Insert eq early in the chain (after scale/trim but before fades/text)
        result.insert(0, eq_str)

    return result


def _get_clip_filters(session: Session, producer_id: str) -> tuple[list[str], list[str]]:
    """Extract ffmpeg video and audio filter strings from a producer's MLT filters.

    Returns (video_filters, audio_filters).
    """
    producer = mlt_xml.find_element_by_id(session.root, producer_id)
    if producer is None:
        return [], []

    vfilters = []
    afilters = []
    for filt in producer.findall("filter"):
        service = mlt_xml.get_property(filt, "mlt_service", "")
        # Collect all properties
        props = {}
        for prop in filt.findall("property"):
            name = prop.get("name", "")
            if name and name != "mlt_service":
                props[name] = prop.text or ""

        # Try video filter mapping
        if service in _MLT_TO_FFMPEG_VIDEO:
            result = _MLT_TO_FFMPEG_VIDEO[service](props)
            if result:
                vfilters.append(result)
        # Try audio filter mapping
        if service in _MLT_TO_FFMPEG_AUDIO:
            result = _MLT_TO_FFMPEG_AUDIO[service](props)
            if result:
                afilters.append(result)

    return vfilters, afilters


def _get_track_filters(session: Session, playlist_id: str) -> tuple[list[str], list[str]]:
    """Extract ffmpeg filter strings from a track-level playlist's filters."""
    playlist = mlt_xml.find_element_by_id(session.root, playlist_id)
    if playlist is None:
        return [], []

    vfilters = []
    afilters = []
    for filt in playlist.findall("filter"):
        service = mlt_xml.get_property(filt, "mlt_service", "")
        props = {}
        for prop in filt.findall("property"):
            name = prop.get("name", "")
            if name and name != "mlt_service":
                props[name] = prop.text or ""

        if service in _MLT_TO_FFMPEG_VIDEO:
            result = _MLT_TO_FFMPEG_VIDEO[service](props)
            if result:
                vfilters.append(result)
        if service in _MLT_TO_FFMPEG_AUDIO:
            result = _MLT_TO_FFMPEG_AUDIO[service](props)
            if result:
                afilters.append(result)

    return vfilters, afilters


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
           extra_args: Optional[list[str]] = None) -> dict:
    """Render the project to an output file.

    This works by:
    1. Saving the current project to a temporary .mlt file
    2. Using melt (if available) or ffmpeg to render it
    3. For melt-less environments, generating an ffmpeg concat/filter script

    Args:
        session: Active session with an open project
        output_path: Path for the output file
        preset: Export preset name
        width: Override output width
        height: Override output height
        overwrite: Overwrite existing output file
        extra_args: Additional command-line arguments for the encoder
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

    preset_config = EXPORT_PRESETS[preset]

    # Determine output format from preset or filename
    output_ext = os.path.splitext(output_path)[1].lower()
    if not output_ext:
        fmt = preset_config.get("format", "mp4")
        output_path += f".{fmt}"

    # Try melt first, then ffmpeg
    melt = shutil.which("melt")
    if melt:
        return _render_with_melt(session, output_path, preset_config, melt,
                                 width, height, extra_args)

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return _render_with_ffmpeg(session, output_path, preset_config, ffmpeg,
                                   width, height, extra_args)

    # Generate the render command for the user to run
    return _generate_render_script(session, output_path, preset_config,
                                   width, height)


def _set_tractor_out(session: Session) -> None:
    """Set tractor out= to actual timeline duration before passing to melt.

    The tractor is created with out="00:00:00.000" and never updated as clips
    are added. Without this fix, melt falls back to the longest track in the
    multitrack — the 4-hour black background — and renders a 4-hour file.
    """
    profile = session.get_profile()
    fps_num = int(profile.get("frame_rate_num", 30000))
    fps_den = int(profile.get("frame_rate_den", 1001))

    tractor = mlt_xml.get_main_tractor(session.root)
    if tractor is None:
        return

    tracks = mlt_xml.get_tractor_tracks(tractor)
    max_frames = 0
    for te in tracks:
        prod_id = te.get("producer", "")
        if prod_id == "background":
            continue
        playlist = mlt_xml.find_element_by_id(session.root, prod_id)
        if playlist is None:
            continue
        total = 0
        for child in playlist:
            if child.tag == "entry":
                in_f = timecode_to_frames(child.get("in", "0"), fps_num, fps_den)
                out_f = timecode_to_frames(child.get("out", "0"), fps_num, fps_den)
                total += max(0, out_f - in_f + 1)
            elif child.tag == "blank":
                try:
                    total += timecode_to_frames(child.get("length", "0"), fps_num, fps_den)
                except Exception:
                    pass
        max_frames = max(max_frames, total)

    if max_frames > 0:
        out_tc = frames_to_timecode(max_frames - 1, fps_num, fps_den)
        tractor.set("out", out_tc)
        # Cap the background track to the same duration so melt doesn't
        # extend the render to the 4-hour background default.
        bg_playlist = mlt_xml.find_element_by_id(session.root, "background")
        if bg_playlist is not None:
            for entry in bg_playlist.findall("entry"):
                entry.set("out", out_tc)
        black_producer = session.root.find(".//producer[@id='black']")
        if black_producer is not None:
            black_producer.set("out", out_tc)


def _render_with_melt(session: Session, output_path: str,
                      preset: dict, melt_path: str,
                      width: Optional[int], height: Optional[int],
                      extra_args: Optional[list[str]]) -> dict:
    """Render using melt command."""
    import tempfile

    # Fix tractor out before rendering — without this melt renders the full
    # 4-hour background track instead of the actual content duration.
    _set_tractor_out(session)

    # Save project to temp file
    with tempfile.NamedTemporaryFile(suffix=".mlt", delete=False, mode="w") as f:
        temp_mlt = f.name
        mlt_xml.write_mlt(session.root, temp_mlt)

    try:
        cmd = [melt_path, temp_mlt, "-consumer"]

        # Build consumer string
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


def _render_with_ffmpeg(session: Session, output_path: str,
                        preset: dict, ffmpeg_path: str,
                        width: Optional[int], height: Optional[int],
                        extra_args: Optional[list[str]]) -> dict:
    """Render using ffmpeg with filter_complex to apply MLT filters.

    Reads all clips and their attached MLT filters, translates them
    to an ffmpeg filter_complex graph, and renders.
    """
    profile = session.get_profile()
    proj_width = width or int(profile.get("width", 1920))
    proj_height = height or int(profile.get("height", 1080))

    # Gather clips from all non-background tracks (video tracks with entries)
    tractor = session.get_main_tractor()
    tracks = mlt_xml.get_tractor_tracks(tractor)

    # Collect clips with their filters
    clips = []  # list of {file, in, out, producer_id, playlist_id, vfilters, afilters}
    for te in tracks:
        prod_id = te.get("producer", "")
        if prod_id == "background":
            continue
        playlist = mlt_xml.find_element_by_id(session.root, prod_id)
        if playlist is None:
            continue

        # Get track-level filters
        track_vf, track_af = _get_track_filters(session, prod_id)

        entries = mlt_xml.get_playlist_entries(playlist)
        for entry in entries:
            if entry["type"] != "entry":
                continue
            producer = mlt_xml.find_element_by_id(session.root, entry["producer"])
            if producer is None:
                continue
            resource = mlt_xml.get_property(producer, "resource", "")
            if not resource or not os.path.isfile(resource):
                continue

            # Get clip-level filters
            clip_vf, clip_af = _get_clip_filters(session, entry["producer"])

            clips.append({
                "file": resource,
                "in": entry.get("in"),
                "out": entry.get("out"),
                "producer_id": entry["producer"],
                "playlist_id": prod_id,
                "vfilters": clip_vf + track_vf,
                "afilters": clip_af + track_af,
            })

    if not clips:
        raise RuntimeError("No renderable clips found in the project")

    # Build ffmpeg command with filter_complex
    cmd = [ffmpeg_path, "-y"]

    # Add each clip as a separate input with trim points
    for clip in clips:
        if clip["in"]:
            cmd.extend(["-ss", clip["in"]])
        cmd.extend(["-i", clip["file"]])
        if clip["out"] and clip["in"]:
            # Duration = out - in; ffmpeg -t is relative to -ss
            # We'll handle this in the filter_complex via trim instead
            pass

    # Build filter_complex
    n = len(clips)
    filter_parts = []
    video_labels = []
    audio_labels = []

    for i, clip in enumerate(clips):
        vlabel = f"v{i}"
        alabel = f"a{i}"

        # Start with input stream, scale to project resolution
        vchain = [f"[{i}:v]scale={proj_width}:{proj_height}:force_original_aspect_ratio=decrease,"
                  f"pad={proj_width}:{proj_height}:(ow-iw)/2:(oh-ih)/2"]

        # Apply trim if we have out point (since -ss already handles in)
        if clip["out"] and clip["in"]:
            in_sec = _tc_to_seconds(clip["in"])
            out_sec = _tc_to_seconds(clip["out"])
            duration = out_sec - in_sec
            if duration > 0:
                vchain.append(f"trim=duration={duration:.3f},setpts=PTS-STARTPTS")

        # Apply video filters — merge multiple eq= into one
        merged_vf = _merge_eq_filters(clip["vfilters"])
        for vf in merged_vf:
            vchain.append(vf)

        filter_parts.append(",".join(vchain) + f"[{vlabel}]")
        video_labels.append(f"[{vlabel}]")

        # Audio chain
        achain = [f"[{i}:a]asetpts=PTS-STARTPTS"]
        if clip["out"] and clip["in"]:
            in_sec = _tc_to_seconds(clip["in"])
            out_sec = _tc_to_seconds(clip["out"])
            duration = out_sec - in_sec
            if duration > 0:
                achain.append(f"atrim=duration={duration:.3f},asetpts=PTS-STARTPTS")

        for af in clip["afilters"]:
            achain.append(af)

        filter_parts.append(",".join(achain) + f"[{alabel}]")
        audio_labels.append(f"[{alabel}]")

    # Concat all segments — interleaved order: [v0][a0][v1][a1]...
    if n > 1:
        concat_in = "".join(
            f"{video_labels[i]}{audio_labels[i]}" for i in range(n)
        )
        filter_parts.append(
            f"{concat_in}concat=n={n}:v=1:a=1[vout][aout]"
        )
        map_video = "[vout]"
        map_audio = "[aout]"
    else:
        map_video = video_labels[0]
        map_audio = audio_labels[0]

    filter_complex = ";".join(filter_parts)

    cmd.extend(["-filter_complex", filter_complex])
    cmd.extend(["-map", map_video, "-map", map_audio])

    # Encoding settings from preset
    vcodec = preset.get("vcodec", "")
    acodec = preset.get("acodec", "")
    if vcodec:
        cmd.extend(["-c:v", vcodec])
    if acodec:
        cmd.extend(["-c:a", acodec])
    if preset.get("crf"):
        cmd.extend(["-crf", preset["crf"]])
    if preset.get("preset"):
        cmd.extend(["-preset", preset["preset"]])
    if preset.get("ab"):
        cmd.extend(["-b:a", preset["ab"]])

    cmd.extend(["-movflags", "+faststart"])

    if extra_args:
        cmd.extend(extra_args)
    cmd.append(output_path)

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg render failed:\n{result.stderr[-1000:]}\n\n"
            f"Command: {' '.join(cmd)}"
        )

    return {
        "action": "render",
        "output": output_path,
        "method": "ffmpeg-filtergraph",
        "success": True,
        "clip_count": n,
        "filters_applied": sum(len(c["vfilters"]) + len(c["afilters"]) for c in clips),
        "size_bytes": os.path.getsize(output_path) if os.path.exists(output_path) else 0,
    }


def _generate_render_script(session: Session, output_path: str,
                            preset: dict,
                            width: Optional[int], height: Optional[int]) -> dict:
    """When no rendering tools are available, save the project and generate instructions."""
    # Save the project to a known location
    project_dir = os.path.dirname(output_path)
    project_file = os.path.join(project_dir, "_render_project.mlt")
    mlt_xml.write_mlt(session.root, project_file)

    vcodec = preset.get("vcodec", "libx264")
    acodec = preset.get("acodec", "aac")

    melt_cmd = (
        f"melt {project_file} -consumer avformat:{output_path} "
        f"vcodec={vcodec} acodec={acodec}"
    )
    if preset.get("crf"):
        melt_cmd += f" crf={preset['crf']}"
    if preset.get("preset"):
        melt_cmd += f" preset={preset['preset']}"

    return {
        "action": "render_script",
        "project_file": project_file,
        "output": output_path,
        "melt_command": melt_cmd,
        "note": "Neither melt nor ffmpeg found. Install one and run the command above.",
        "install_hint": "apt install melt ffmpeg  # or equivalent for your OS",
    }
