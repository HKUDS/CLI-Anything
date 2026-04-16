"""Audacity CLI - Clip management module.

Handles importing audio files, adding clips to tracks, trimming,
splitting, moving, and removing clips. Each clip references a source
audio file and has start/end times on the track timeline plus
trim offsets within the source.
"""

import os
import wave
from typing import Dict, Any, List, Optional


def import_audio(path: str) -> Dict[str, Any]:
    """Probe an audio file and return clip-ready metadata."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Audio file not found: {path}")

    abs_path = os.path.abspath(path)
    info = {
        "source": abs_path,
        "filename": os.path.basename(path),
        "file_size": os.path.getsize(abs_path),
    }

    # Try to read WAV info
    try:
        with wave.open(abs_path, "r") as wf:
            info["sample_rate"] = wf.getframerate()
            info["channels"] = wf.getnchannels()
            info["bit_depth"] = wf.getsampwidth() * 8
            info["frames"] = wf.getnframes()
            info["duration"] = wf.getnframes() / wf.getframerate()
            info["format"] = "WAV"
    except (wave.Error, EOFError, struct_error()):
        # Not a WAV or unreadable — store basic info
        info["duration"] = 0.0
        info["format"] = _guess_format(abs_path)

    return info


def struct_error():
    """Return struct.error for exception handling."""
    import struct
    return struct.error


def _guess_format(path: str) -> str:
    """Guess audio format from extension."""
    ext = os.path.splitext(path)[1].lower()
    fmt_map = {
        ".wav": "WAV", ".mp3": "MP3", ".flac": "FLAC",
        ".ogg": "OGG", ".aiff": "AIFF", ".aif": "AIFF",
        ".m4a": "M4A", ".wma": "WMA",
    }
    return fmt_map.get(ext, "unknown")


def add_clip(
    project: Dict[str, Any],
    track_index: int,
    source: str,
    name: Optional[str] = None,
    start_time: float = 0.0,
    end_time: Optional[float] = None,
    trim_start: float = 0.0,
    trim_end: Optional[float] = None,
    volume: float = 1.0,
) -> Dict[str, Any]:
    """Add a clip to a track."""
    tracks = project.get("tracks", [])
    if track_index < 0 or track_index >= len(tracks):
        raise IndexError(f"Track index {track_index} out of range (0-{len(tracks) - 1})")

    track = tracks[track_index]
    clips = track.setdefault("clips", [])

    abs_source = os.path.abspath(source) if source else ""

    # Determine duration from source if available
    duration = 0.0
    if abs_source and os.path.exists(abs_source):
        try:
            with wave.open(abs_source, "r") as wf:
                duration = wf.getnframes() / wf.getframerate()
        except (wave.Error, EOFError):
            pass

    if end_time is None:
        end_time = start_time + (duration - trim_start if duration > 0 else 10.0)
    if trim_end is None:
        trim_end = duration if duration > 0 else (end_time - start_time + trim_start)

    if start_time < 0:
        raise ValueError(f"start_time must be >= 0, got {start_time}")
    if end_time < start_time:
        raise ValueError(f"end_time ({end_time}) must be >= start_time ({start_time})")

    # Generate unique clip ID
    existing_ids = {c.get("id", i) for i, c in enumerate(clips)}
    new_id = 0
    while new_id in existing_ids:
        new_id += 1

    if name is None:
        name = os.path.splitext(os.path.basename(source))[0] if source else f"clip_{new_id}"

    clip = {
        "id": new_id,
        "name": name,
        "source": abs_source,
        "start_time": start_time,
        "end_time": end_time,
        "trim_start": trim_start,
        "trim_end": trim_end,
        "volume": volume,
    }
    clips.append(clip)
    return clip


def remove_clip(
    project: Dict[str, Any],
    track_index: int,
    clip_index: int,
) -> Dict[str, Any]:
    """Remove a clip from a track by index."""
    tracks = project.get("tracks", [])
    if track_index < 0 or track_index >= len(tracks):
        raise IndexError(f"Track index {track_index} out of range (0-{len(tracks) - 1})")

    track = tracks[track_index]
    clips = track.get("clips", [])
    if clip_index < 0 or clip_index >= len(clips):
        raise IndexError(f"Clip index {clip_index} out of range (0-{len(clips) - 1})")

    return clips.pop(clip_index)


def trim_clip(
    project: Dict[str, Any],
    track_index: int,
    clip_index: int,
    trim_start: Optional[float] = None,
    trim_end: Optional[float] = None,
) -> Dict[str, Any]:
    """Trim a clip's start and/or end within its source."""
    tracks = project.get("tracks", [])
    if track_index < 0 or track_index >= len(tracks):
        raise IndexError(f"Track index {track_index} out of range")
    clips = tracks[track_index].get("clips", [])
    if clip_index < 0 or clip_index >= len(clips):
        raise IndexError(f"Clip index {clip_index} out of range")

    clip = clips[clip_index]

    if trim_start is not None:
        if trim_start < 0:
            raise ValueError("trim_start must be >= 0")
        old_trim_start = clip["trim_start"]
        delta = trim_start - old_trim_start
        clip["trim_start"] = trim_start
        clip["start_time"] = clip["start_time"] + delta

    if trim_end is not None:
        if trim_end < clip["trim_start"]:
            raise ValueError("trim_end must be >= trim_start")
        old_duration = clip["end_time"] - clip["start_time"]
        new_duration = trim_end - clip["trim_start"]
        clip["trim_end"] = trim_end
        clip["end_time"] = clip["start_time"] + new_duration

    return clip


def split_clip(
    project: Dict[str, Any],
    track_index: int,
    clip_index: int,
    split_time: float,
) -> List[Dict[str, Any]]:
    """Split a clip at a given time position. Returns the two resulting clips."""
    tracks = project.get("tracks", [])
    if track_index < 0 or track_index >= len(tracks):
        raise IndexError(f"Track index {track_index} out of range")
    clips = tracks[track_index].get("clips", [])
    if clip_index < 0 or clip_index >= len(clips):
        raise IndexError(f"Clip index {clip_index} out of range")

    clip = clips[clip_index]
    if split_time <= clip["start_time"] or split_time >= clip["end_time"]:
        raise ValueError(
            f"Split time {split_time} must be between clip start "
            f"({clip['start_time']}) and end ({clip['end_time']})"
        )

    # Calculate how far into the source the split occurs
    offset_into_clip = split_time - clip["start_time"]
    split_source_time = clip["trim_start"] + offset_into_clip

    # Create second half
    existing_ids = {c.get("id", i) for i, c in enumerate(clips)}
    new_id = 0
    while new_id in existing_ids:
        new_id += 1

    clip2 = {
        "id": new_id,
        "name": clip["name"] + " (split)",
        "source": clip["source"],
        "start_time": split_time,
        "end_time": clip["end_time"],
        "trim_start": split_source_time,
        "trim_end": clip["trim_end"],
        "volume": clip["volume"],
    }

    # Modify original clip (first half)
    clip["end_time"] = split_time
    clip["trim_end"] = split_source_time

    # Insert second clip after the first
    insert_pos = clip_index + 1
    clips.insert(insert_pos, clip2)

    return [clip, clip2]


def move_clip(
    project: Dict[str, Any],
    track_index: int,
    clip_index: int,
    new_start_time: float,
) -> Dict[str, Any]:
    """Move a clip to a new start time on the timeline."""
    tracks = project.get("tracks", [])
    if track_index < 0 or track_index >= len(tracks):
        raise IndexError(f"Track index {track_index} out of range")
    clips = tracks[track_index].get("clips", [])
    if clip_index < 0 or clip_index >= len(clips):
        raise IndexError(f"Clip index {clip_index} out of range")

    if new_start_time < 0:
        raise ValueError("new_start_time must be >= 0")

    clip = clips[clip_index]
    duration = clip["end_time"] - clip["start_time"]
    clip["start_time"] = new_start_time
    clip["end_time"] = new_start_time + duration
    return clip


def list_clips(
    project: Dict[str, Any],
    track_index: int,
) -> List[Dict[str, Any]]:
    """List all clips on a track."""
    tracks = project.get("tracks", [])
    if track_index < 0 or track_index >= len(tracks):
        raise IndexError(f"Track index {track_index} out of range (0-{len(tracks) - 1})")

    clips = tracks[track_index].get("clips", [])
    result = []
    for i, c in enumerate(clips):
        result.append({
            "index": i,
            "id": c.get("id", i),
            "name": c.get("name", f"Clip {i}"),
            "source": c.get("source", ""),
            "start_time": c.get("start_time", 0.0),
            "end_time": c.get("end_time", 0.0),
            "duration": round(c.get("end_time", 0.0) - c.get("start_time", 0.0), 3),
            "trim_start": c.get("trim_start", 0.0),
            "trim_end": c.get("trim_end", 0.0),
            "volume": c.get("volume", 1.0),
        })
    return result
