"""Compositing: blend modes, picture-in-picture, and layer compositing."""

from typing import Optional
from lxml import etree

from ..utils import mlt_xml
from .session import Session


# Available blend modes for the cairo blend transition
BLEND_MODES = {
    "normal": {"value": "normal", "description": "Normal compositing (default)"},
    "add": {"value": "add", "description": "Additive blending (lighten)"},
    "saturate": {"value": "saturate", "description": "Saturate blend"},
    "multiply": {"value": "multiply", "description": "Multiply (darken)"},
    "screen": {"value": "screen", "description": "Screen (lighten)"},
    "overlay": {"value": "overlay", "description": "Overlay (contrast boost)"},
    "darken": {"value": "darken", "description": "Darken (keep darker pixels)"},
    "lighten": {"value": "lighten", "description": "Lighten (keep lighter pixels)"},
    "colordodge": {"value": "colordodge", "description": "Color dodge"},
    "colorburn": {"value": "colorburn", "description": "Color burn"},
    "hardlight": {"value": "hardlight", "description": "Hard light"},
    "softlight": {"value": "softlight", "description": "Soft light"},
    "difference": {"value": "difference", "description": "Difference"},
    "exclusion": {"value": "exclusion", "description": "Exclusion"},
    "hslhue": {"value": "hslhue", "description": "HSL Hue"},
    "hslsaturation": {"value": "hslsaturation", "description": "HSL Saturation"},
    "hslcolor": {"value": "hslcolor", "description": "HSL Color"},
    "hslluminosity": {"value": "hslluminosity", "description": "HSL Luminosity"},
}


def list_blend_modes() -> list[dict]:
    """List all available blend modes."""
    return [{"name": name, **info} for name, info in sorted(BLEND_MODES.items())]


def set_track_blend_mode(session: Session, track_index: int,
                         blend_mode: str) -> dict:
    """Set the blend mode for a track's compositing transition.

    Args:
        session: Active session
        track_index: Track index (must be > 0, background track has no blend)
        blend_mode: Blend mode name from BLEND_MODES
    """
    if blend_mode not in BLEND_MODES:
        available = ", ".join(sorted(BLEND_MODES.keys()))
        raise ValueError(f"Unknown blend mode: {blend_mode!r}. Available: {available}")

    if track_index <= 0:
        raise ValueError("Cannot set blend mode on background track (index 0)")

    session.checkpoint()
    tractor = session.get_main_tractor()
    tracks = mlt_xml.get_tractor_tracks(tractor)

    if track_index >= len(tracks):
        raise IndexError(f"Track index {track_index} out of range")

    # Find the compositing transition for this track
    comp_trans = _find_compositing_transition(tractor, track_index)
    if comp_trans is None:
        # Create one if it doesn't exist
        comp_trans = etree.SubElement(tractor, "transition")
        comp_trans.set("id", mlt_xml.new_id("transition"))
        mlt_xml.set_property(comp_trans, "a_track", "0")
        mlt_xml.set_property(comp_trans, "b_track", str(track_index))
        mlt_xml.set_property(comp_trans, "mlt_service", "frei0r.cairoblend")
        mlt_xml.set_property(comp_trans, "disable", "0")

    mlt_xml.set_property(comp_trans, "blend_mode", blend_mode)

    return {
        "action": "set_blend_mode",
        "track_index": track_index,
        "blend_mode": blend_mode,
        "description": BLEND_MODES[blend_mode]["description"],
    }


def get_track_blend_mode(session: Session, track_index: int) -> dict:
    """Get the current blend mode for a track."""
    tractor = session.get_main_tractor()
    comp_trans = _find_compositing_transition(tractor, track_index)

    if comp_trans is None:
        return {"track_index": track_index, "blend_mode": "normal",
                "description": "No compositing transition found"}

    mode = mlt_xml.get_property(comp_trans, "blend_mode", "normal")
    desc = BLEND_MODES.get(mode, {}).get("description", "Unknown mode")
    return {"track_index": track_index, "blend_mode": mode,
            "description": desc}


def set_track_opacity(session: Session, track_index: int,
                      opacity: float) -> dict:
    """Set the opacity of an entire track.

    This applies a brightness filter with the alpha value to the track.
    """
    if opacity < 0.0 or opacity > 1.0:
        raise ValueError(f"Opacity must be 0.0-1.0, got {opacity}")

    session.checkpoint()
    tractor = session.get_main_tractor()
    tracks = mlt_xml.get_tractor_tracks(tractor)

    if track_index < 0 or track_index >= len(tracks):
        raise IndexError(f"Track index {track_index} out of range")

    # Find the track's playlist
    producer_id = tracks[track_index].get("producer")
    playlist = mlt_xml.find_element_by_id(session.root, producer_id)
    if playlist is None:
        raise RuntimeError("Track playlist not found")

    # Look for existing opacity filter, or create one
    for filt in playlist.findall("filter"):
        svc = mlt_xml.get_property(filt, "mlt_service", "")
        if svc == "brightness" and mlt_xml.get_property(filt, "shotcut:filter") == "opacity":
            mlt_xml.set_property(filt, "alpha", str(opacity))
            return {"action": "set_track_opacity", "track_index": track_index,
                    "opacity": opacity}

    # Create new opacity filter
    filt = mlt_xml.add_filter_to_element(playlist, "brightness",
                                          {"alpha": str(opacity),
                                           "level": "1",
                                           "shotcut:filter": "opacity"})

    return {"action": "set_track_opacity", "track_index": track_index,
            "opacity": opacity}


def pip_position(session: Session, track_index: int, clip_index: int,
                 x: str = "0", y: str = "0",
                 width: str = "100%", height: str = "100%",
                 opacity: float = 1.0) -> dict:
    """Set picture-in-picture position and size for a clip.

    This applies/updates an affine filter on the clip to position it
    as a picture-in-picture overlay.

    Args:
        session: Active session
        track_index: Track containing the clip
        clip_index: Clip index on the track
        x: X position (pixels or percentage like "10%" or "100")
        y: Y position (pixels or percentage)
        width: Width (pixels or percentage)
        height: Height (pixels or percentage)
        opacity: Opacity (0.0-1.0)
    """
    session.checkpoint()

    tractor = session.get_main_tractor()
    tracks = mlt_xml.get_tractor_tracks(tractor)

    if track_index < 0 or track_index >= len(tracks):
        raise IndexError(f"Track index {track_index} out of range")

    producer_id = tracks[track_index].get("producer")
    playlist = mlt_xml.find_element_by_id(session.root, producer_id)
    if playlist is None:
        raise RuntimeError("Track playlist not found")

    entries = mlt_xml.get_playlist_entries(playlist)
    clip_entries = [e for e in entries if e["type"] == "entry"]
    if clip_index < 0 or clip_index >= len(clip_entries):
        raise IndexError(f"Clip index {clip_index} out of range")

    clip_producer_id = clip_entries[clip_index]["producer"]
    producer = mlt_xml.find_element_by_id(session.root, clip_producer_id)
    if producer is None:
        raise RuntimeError(f"Producer {clip_producer_id!r} not found")

    # Build geometry string: x/y:wxh:opacity
    opacity_int = int(opacity * 100)
    geometry = f"{x}/{y}:{width}x{height}:{opacity_int}"

    # Look for existing affine filter, or create one
    for filt in producer.findall("filter"):
        svc = mlt_xml.get_property(filt, "mlt_service", "")
        if svc == "affine":
            mlt_xml.set_property(filt, "transition.geometry", geometry)
            return {"action": "pip_position", "track_index": track_index,
                    "clip_index": clip_index, "geometry": geometry}

    # Create new affine filter
    mlt_xml.add_filter_to_element(producer, "affine",
                                   {"transition.geometry": geometry,
                                    "background": "color:#00000000"})

    return {"action": "pip_position", "track_index": track_index,
            "clip_index": clip_index, "geometry": geometry}


def _find_compositing_transition(tractor: etree._Element,
                                  track_index: int) -> Optional[etree._Element]:
    """Find the compositing transition for a specific track."""
    for trans in tractor.findall("transition"):
        service = mlt_xml.get_property(trans, "mlt_service", "")
        b_track = mlt_xml.get_property(trans, "b_track", "")
        if service == "frei0r.cairoblend" and b_track == str(track_index):
            return trans
    return None
