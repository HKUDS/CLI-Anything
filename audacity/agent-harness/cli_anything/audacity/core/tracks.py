"""Audacity CLI - Track management module.

Handles adding, removing, renaming, and configuring audio tracks.
Each track has properties: name, type, mute, solo, volume, pan,
plus lists of clips and effects.
"""

from typing import Dict, Any, List, Optional


def add_track(
    project: Dict[str, Any],
    name: Optional[str] = None,
    track_type: str = "audio",
    volume: float = 1.0,
    pan: float = 0.0,
) -> Dict[str, Any]:
    """Add a new track to the project."""
    tracks = project.setdefault("tracks", [])

    if track_type not in ("audio", "label"):
        raise ValueError(f"Invalid track type: {track_type}. Use 'audio' or 'label'.")

    if volume < 0.0 or volume > 2.0:
        raise ValueError(f"Volume must be between 0.0 and 2.0, got {volume}")
    if pan < -1.0 or pan > 1.0:
        raise ValueError(f"Pan must be between -1.0 and 1.0, got {pan}")

    # Generate unique ID
    existing_ids = {t.get("id", i) for i, t in enumerate(tracks)}
    new_id = 0
    while new_id in existing_ids:
        new_id += 1

    if name is None:
        name = f"Track {new_id}"

    track = {
        "id": new_id,
        "name": name,
        "type": track_type,
        "mute": False,
        "solo": False,
        "volume": volume,
        "pan": pan,
        "clips": [],
        "effects": [],
    }
    tracks.append(track)
    return track


def remove_track(project: Dict[str, Any], track_index: int) -> Dict[str, Any]:
    """Remove a track by index."""
    tracks = project.get("tracks", [])
    if track_index < 0 or track_index >= len(tracks):
        raise IndexError(f"Track index {track_index} out of range (0-{len(tracks) - 1})")
    return tracks.pop(track_index)


def get_track(project: Dict[str, Any], track_index: int) -> Dict[str, Any]:
    """Get a track by index."""
    tracks = project.get("tracks", [])
    if track_index < 0 or track_index >= len(tracks):
        raise IndexError(f"Track index {track_index} out of range (0-{len(tracks) - 1})")
    return tracks[track_index]


def set_track_property(
    project: Dict[str, Any],
    track_index: int,
    prop: str,
    value: Any,
) -> Dict[str, Any]:
    """Set a track property."""
    track = get_track(project, track_index)

    if prop == "name":
        track["name"] = str(value)
    elif prop == "mute":
        track["mute"] = str(value).lower() in ("true", "1", "yes")
    elif prop == "solo":
        track["solo"] = str(value).lower() in ("true", "1", "yes")
    elif prop == "volume":
        v = float(value)
        if v < 0.0 or v > 2.0:
            raise ValueError(f"Volume must be between 0.0 and 2.0, got {v}")
        track["volume"] = v
    elif prop == "pan":
        p = float(value)
        if p < -1.0 or p > 1.0:
            raise ValueError(f"Pan must be between -1.0 and 1.0, got {p}")
        track["pan"] = p
    else:
        raise ValueError(
            f"Unknown track property: {prop}. "
            "Valid: name, mute, solo, volume, pan"
        )

    return track


def list_tracks(project: Dict[str, Any]) -> List[Dict[str, Any]]:
    """List all tracks with summary info."""
    result = []
    tracks = project.get("tracks", [])
    for i, t in enumerate(tracks):
        clips = t.get("clips", [])
        # Calculate track duration
        max_end = 0.0
        for c in clips:
            end = c.get("end_time", 0.0)
            if end > max_end:
                max_end = end

        result.append({
            "index": i,
            "id": t.get("id", i),
            "name": t.get("name", f"Track {i}"),
            "type": t.get("type", "audio"),
            "mute": t.get("mute", False),
            "solo": t.get("solo", False),
            "volume": t.get("volume", 1.0),
            "pan": t.get("pan", 0.0),
            "clip_count": len(clips),
            "effect_count": len(t.get("effects", [])),
            "duration": round(max_end, 3),
        })
    return result
