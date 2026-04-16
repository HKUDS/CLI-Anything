"""Kdenlive CLI - MLT XML generation helpers and timecode conversions."""

import re
from typing import Dict, Any, Optional


def xml_escape(s: str) -> str:
    """Escape special characters for XML."""
    s = s.replace("&", "&amp;")
    s = s.replace("<", "&lt;")
    s = s.replace(">", "&gt;")
    s = s.replace('"', "&quot;")
    s = s.replace("'", "&apos;")
    return s


def seconds_to_timecode(seconds: float) -> str:
    """Convert seconds (float) to HH:MM:SS.mmm timecode string."""
    if seconds < 0:
        raise ValueError(f"Seconds must be non-negative: {seconds}")
    hours = int(seconds // 3600)
    remainder = seconds - hours * 3600
    minutes = int(remainder // 60)
    remainder = remainder - minutes * 60
    secs = int(remainder)
    millis = int(round((remainder - secs) * 1000))
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def timecode_to_seconds(tc: str) -> float:
    """Convert HH:MM:SS.mmm timecode to seconds (float).

    Also accepts plain float strings.
    """
    # Try plain float first
    try:
        return float(tc)
    except ValueError:
        pass

    pattern = r'^(\d{1,2}):(\d{2}):(\d{2})(?:\.(\d{1,3}))?$'
    m = re.match(pattern, tc)
    if not m:
        raise ValueError(f"Invalid timecode format: {tc}. Expected HH:MM:SS.mmm or seconds.")
    hours = int(m.group(1))
    minutes = int(m.group(2))
    secs = int(m.group(3))
    millis = int(m.group(4)) if m.group(4) else 0
    # Pad millis to 3 digits
    millis_str = m.group(4) if m.group(4) else "0"
    millis = int(millis_str.ljust(3, '0'))
    return hours * 3600 + minutes * 60 + secs + millis / 1000.0


def seconds_to_frames(seconds: float, fps_num: int = 30, fps_den: int = 1) -> int:
    """Convert seconds to frame count."""
    fps = fps_num / max(fps_den, 1)
    return int(round(seconds * fps))


def frames_to_seconds(frames: int, fps_num: int = 30, fps_den: int = 1) -> float:
    """Convert frame count to seconds."""
    fps = fps_num / max(fps_den, 1)
    return frames / fps


def _indent(text: str, level: int) -> str:
    """Indent text by level."""
    prefix = "  " * level
    return prefix + text


def build_mlt_xml(project: Dict[str, Any]) -> str:
    """Build a complete MLT XML document from a project dictionary.

    Generates valid MLT XML with Kdenlive metadata, suitable for
    opening in Kdenlive or processing with melt.
    """
    profile = project.get("profile", {})
    width = profile.get("width", 1920)
    height = profile.get("height", 1080)
    fps_num = profile.get("fps_num", 30)
    fps_den = profile.get("fps_den", 1)
    progressive = profile.get("progressive", True)
    dar_num = profile.get("dar_num", 16)
    dar_den = profile.get("dar_den", 9)

    # Calculate SAR (sample aspect ratio)
    sar_num = dar_num * height
    sar_den = dar_den * width

    lines = []
    lines.append('<?xml version="1.0" encoding="utf-8"?>')
    lines.append('<mlt LC_NUMERIC="C" version="7.0.0" '
                 f'title="{xml_escape(project.get("name", "untitled"))}" '
                 f'producer="kdenlive-cli">')

    # Profile
    lines.append(f'  <profile description="{xml_escape(profile.get("name", "custom"))}" '
                 f'width="{width}" height="{height}" '
                 f'progressive="{1 if progressive else 0}" '
                 f'sample_aspect_num="{sar_num}" sample_aspect_den="{sar_den}" '
                 f'display_aspect_num="{dar_num}" display_aspect_den="{dar_den}" '
                 f'frame_rate_num="{fps_num}" frame_rate_den="{fps_den}" '
                 f'colorspace="709"/>')

    # Producers from bin
    bin_clips = project.get("bin", [])
    for clip in bin_clips:
        clip_id = xml_escape(clip["id"])
        source = xml_escape(clip.get("source", ""))
        duration_frames = seconds_to_frames(clip.get("duration", 0), fps_num, fps_den)
        lines.append(f'  <producer id="{clip_id}" in="0" out="{max(duration_frames - 1, 0)}">')
        lines.append(f'    <property name="resource">{source}</property>')
        lines.append(f'    <property name="kdenlive:clipname">{xml_escape(clip.get("name", ""))}</property>')
        lines.append(f'    <property name="kdenlive:clip_type">{_clip_type_num(clip.get("type", "video"))}</property>')
        lines.append(f'    <property name="length">{duration_frames}</property>')
        lines.append('  </producer>')

    # Playlists for each track
    tracks = project.get("tracks", [])
    for track in tracks:
        track_id = f"playlist{track['id']}"
        lines.append(f'  <playlist id="{xml_escape(track_id)}">')
        lines.append(f'    <property name="kdenlive:track_name">{xml_escape(track.get("name", ""))}</property>')

        hide_val = ""
        if track.get("mute", False) and track.get("hide", False):
            hide_val = "both"
        elif track.get("mute", False):
            hide_val = "audio"
        elif track.get("hide", False):
            hide_val = "video"
        if hide_val:
            lines.append(f'    <property name="hide">{hide_val}</property>')

        prev_end = 0.0
        for clip_entry in track.get("clips", []):
            pos = clip_entry.get("position", 0.0)
            # Insert blank for gap
            gap = pos - prev_end
            if gap > 0.001:
                gap_frames = seconds_to_frames(gap, fps_num, fps_den)
                lines.append(f'    <blank length="{gap_frames}"/>')

            in_frames = seconds_to_frames(clip_entry.get("in", 0), fps_num, fps_den)
            out_frames = seconds_to_frames(clip_entry.get("out", 0), fps_num, fps_den)
            clip_ref = xml_escape(clip_entry.get("clip_id", ""))
            lines.append(f'    <entry producer="{clip_ref}" in="{in_frames}" out="{max(out_frames - 1, 0)}">')

            # Filters on this clip entry
            for filt in clip_entry.get("filters", []):
                mlt_svc = xml_escape(filt.get("mlt_service", ""))
                lines.append(f'      <filter mlt_service="{mlt_svc}">')
                lines.append(f'        <property name="kdenlive:filter_name">{xml_escape(filt.get("name", ""))}</property>')
                for pk, pv in filt.get("params", {}).items():
                    lines.append(f'        <property name="{xml_escape(pk)}">{xml_escape(str(pv))}</property>')
                lines.append('      </filter>')

            lines.append('    </entry>')
            clip_dur = clip_entry.get("out", 0) - clip_entry.get("in", 0)
            prev_end = pos + clip_dur

        lines.append('  </playlist>')

    # Tractor (main timeline)
    lines.append('  <tractor id="maintractor">')
    for track in tracks:
        track_id = f"playlist{track['id']}"
        lines.append(f'    <track producer="{xml_escape(track_id)}"/>')

    # Transitions
    for trans in project.get("transitions", []):
        mlt_svc = xml_escape(trans.get("mlt_service", ""))
        pos_frames = seconds_to_frames(trans.get("position", 0), fps_num, fps_den)
        dur_frames = seconds_to_frames(trans.get("duration", 1), fps_num, fps_den)
        # Find track indices
        a_idx = _track_index(tracks, trans["track_a"])
        b_idx = _track_index(tracks, trans["track_b"])
        lines.append(f'    <transition mlt_service="{mlt_svc}" '
                     f'in="{pos_frames}" out="{pos_frames + dur_frames}" '
                     f'a_track="{a_idx}" b_track="{b_idx}">')
        for pk, pv in trans.get("params", {}).items():
            if pk in ("duration",):
                continue  # duration already encoded in in/out
            lines.append(f'      <property name="{xml_escape(pk)}">{xml_escape(str(pv))}</property>')
        lines.append('    </transition>')

    lines.append('  </tractor>')

    # Guides as Kdenlive metadata
    guides = project.get("guides", [])
    if guides:
        lines.append('  <kdenlivedoc>')
        for g in guides:
            pos_frames = seconds_to_frames(g["position"], fps_num, fps_den)
            lines.append(f'    <guide pos="{pos_frames}" '
                         f'comment="{xml_escape(g.get("label", ""))}" '
                         f'type="{xml_escape(g.get("type", "default"))}"/>')
        lines.append('  </kdenlivedoc>')

    lines.append('</mlt>')
    return '\n'.join(lines)


def _clip_type_num(clip_type: str) -> int:
    """Convert clip type string to Kdenlive type number."""
    mapping = {
        "video": 0,
        "audio": 1,
        "image": 2,
        "color": 3,
        "title": 4,
    }
    return mapping.get(clip_type, 0)


def _track_index(tracks: list, track_id: int) -> int:
    """Find 0-based index of track by ID."""
    for i, t in enumerate(tracks):
        if t["id"] == track_id:
            return i
    return 0
