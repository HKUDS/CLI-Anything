"""Transition management: add, remove, configure transitions between clips."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Optional

from ..utils import mlt_xml
from ..utils.time import frames_to_timecode, parse_time_input
from .session import Session
from .timeline import _get_track_playlist, _get_fps, is_transition_entry


# Registry of available transition types
TRANSITION_REGISTRY = {
    "dissolve": {
        "service": "luma",
        "category": "video",
        "description": "Cross-dissolve between two clips",
        "params": {
            "softness": {"type": "float", "default": "0", "range": "0.0-1.0",
                         "description": "Edge softness of the transition"},
            "invert": {"type": "int", "default": "0",
                       "description": "Invert the transition (0 or 1)"},
        },
    },
    "wipe-left": {
        "service": "luma",
        "category": "video",
        "description": "Wipe from right to left",
        "params": {
            "resource": {"type": "string", "default": "%luma01.pgm",
                         "description": "Luma pattern file"},
            "softness": {"type": "float", "default": "0.1", "range": "0.0-1.0",
                         "description": "Edge softness"},
        },
    },
    "wipe-right": {
        "service": "luma",
        "category": "video",
        "description": "Wipe from left to right",
        "params": {
            "resource": {"type": "string", "default": "%luma01.pgm",
                         "description": "Luma pattern file"},
            "softness": {"type": "float", "default": "0.1", "range": "0.0-1.0",
                         "description": "Edge softness"},
            "invert": {"type": "int", "default": "1",
                       "description": "Invert direction"},
        },
    },
    "wipe-down": {
        "service": "luma",
        "category": "video",
        "description": "Wipe from top to bottom",
        "params": {
            "resource": {"type": "string", "default": "%luma04.pgm",
                         "description": "Luma pattern file (vertical)"},
            "softness": {"type": "float", "default": "0.1", "range": "0.0-1.0",
                         "description": "Edge softness"},
        },
    },
    "wipe-up": {
        "service": "luma",
        "category": "video",
        "description": "Wipe from bottom to top",
        "params": {
            "resource": {"type": "string", "default": "%luma04.pgm",
                         "description": "Luma pattern file (vertical)"},
            "softness": {"type": "float", "default": "0.1", "range": "0.0-1.0",
                         "description": "Edge softness"},
            "invert": {"type": "int", "default": "1",
                       "description": "Invert direction"},
        },
    },
    "bar-horizontal": {
        "service": "luma",
        "category": "video",
        "description": "Horizontal bars wipe",
        "params": {
            "resource": {"type": "string", "default": "%luma05.pgm",
                         "description": "Luma pattern file"},
            "softness": {"type": "float", "default": "0.1", "range": "0.0-1.0",
                         "description": "Edge softness"},
        },
    },
    "bar-vertical": {
        "service": "luma",
        "category": "video",
        "description": "Vertical bars wipe",
        "params": {
            "resource": {"type": "string", "default": "%luma06.pgm",
                         "description": "Luma pattern file"},
            "softness": {"type": "float", "default": "0.1", "range": "0.0-1.0",
                         "description": "Edge softness"},
        },
    },
    "diagonal": {
        "service": "luma",
        "category": "video",
        "description": "Diagonal wipe",
        "params": {
            "resource": {"type": "string", "default": "%luma07.pgm",
                         "description": "Luma pattern file (diagonal)"},
            "softness": {"type": "float", "default": "0.1", "range": "0.0-1.0",
                         "description": "Edge softness"},
        },
    },
    "clock": {
        "service": "luma",
        "category": "video",
        "description": "Clock wipe (radial sweep)",
        "params": {
            "resource": {"type": "string", "default": "%luma16.pgm",
                         "description": "Luma pattern file (clock)"},
            "softness": {"type": "float", "default": "0.1", "range": "0.0-1.0",
                         "description": "Edge softness"},
        },
    },
    "iris-circle": {
        "service": "luma",
        "category": "video",
        "description": "Circular iris wipe",
        "params": {
            "resource": {"type": "string", "default": "%luma22.pgm",
                         "description": "Luma pattern file (iris)"},
            "softness": {"type": "float", "default": "0.2", "range": "0.0-1.0",
                         "description": "Edge softness"},
        },
    },
    "crossfade": {
        "service": "mix",
        "category": "audio",
        "description": "Audio crossfade between clips",
        "params": {
            "start": {"type": "float", "default": "0.0", "range": "0.0-1.0",
                      "description": "Start mix level"},
            "end": {"type": "float", "default": "1.0", "range": "0.0-1.0",
                    "description": "End mix level"},
        },
    },
}


def list_available_transitions(category: Optional[str] = None) -> list[dict]:
    """List all available transition types."""
    result = []
    for name, info in sorted(TRANSITION_REGISTRY.items()):
        if category and info["category"] != category:
            continue
        result.append({
            "name": name,
            "service": info["service"],
            "category": info["category"],
            "description": info["description"],
            "params": list(info["params"].keys()),
        })
    return result


def get_transition_info(transition_name: str) -> dict:
    """Get detailed info about a transition type."""
    if transition_name not in TRANSITION_REGISTRY:
        available = ", ".join(sorted(TRANSITION_REGISTRY.keys()))
        raise ValueError(f"Unknown transition: {transition_name!r}. Available: {available}")
    info = dict(TRANSITION_REGISTRY[transition_name])
    info["name"] = transition_name
    return info


def add_transition(session: Session, transition_name: str,
                   track_index: int, clip_a_index: int,
                   duration_frames: int = 14,
                   params: Optional[dict] = None) -> dict:
    """Add a transition between two adjacent clips on a track.

    Uses Shotcut's sub-tractor format so the transition is visible
    and editable in Shotcut's timeline UI.
    """
    session.checkpoint()
    fps_num, fps_den = _get_fps(session)
    playlist = _get_track_playlist(session, track_index)

    # Collect entry elements in playlist order, excluding existing transitions
    entries = [c for c in playlist if c.tag in ("entry", "blank")]
    clip_entries = [e for e in entries if e.tag == "entry" and not is_transition_entry(e, session.root)]
    if clip_a_index < 0 or clip_a_index >= len(clip_entries) - 1:
        raise IndexError(
            f"Need two adjacent clips for transition; "
            f"clip_a_index {clip_a_index} out of range (0-{len(clip_entries)-2})"
        )

    entry_a = clip_entries[clip_a_index]
    entry_b = clip_entries[clip_a_index + 1]

    # Verify no blanks or existing transitions between the two clips
    found_a = False
    for child in playlist:
        if child is entry_a:
            found_a = True
            continue
        if found_a:
            if child is entry_b:
                break
            if child.tag == "blank":
                raise ValueError(
                    f"Cannot add transition: blank gap between clip {clip_a_index} "
                    f"and {clip_a_index + 1}"
                )
            if child.tag == "entry" and is_transition_entry(child, session.root):
                raise ValueError(
                    f"Cannot add transition: a transition already exists "
                    f"between clip {clip_a_index} and {clip_a_index + 1}"
                )

    chain_a_id = entry_a.get("producer", "")
    chain_b_id = entry_b.get("producer", "")

    # Parse current in/out points
    src_a_in = parse_time_input(entry_a.get("in", "00:00:00.000"), fps_num, fps_den)
    src_a_out = parse_time_input(entry_a.get("out", "00:00:00.000"), fps_num, fps_den)
    src_b_in = parse_time_input(entry_b.get("in", "00:00:00.000"), fps_num, fps_den)
    src_b_out = parse_time_input(entry_b.get("out", "00:00:00.000"), fps_num, fps_den)

    dur_a = src_a_out - src_a_in
    dur_b = src_b_out - src_b_in

    trans_frames = min(duration_frames, dur_a, dur_b)
    if trans_frames <= 0:
        raise RuntimeError("Clips too short for transition")
    half_a = (trans_frames + 1) // 2
    half_b = trans_frames - half_a

    trans_tc = frames_to_timecode(trans_frames, fps_num, fps_den)

    new_src_a_out = src_a_out - half_a
    new_src_b_in = src_b_in + half_b

    new_src_a_out_tc = frames_to_timecode(new_src_a_out, fps_num, fps_den)
    new_src_b_in_tc = frames_to_timecode(new_src_b_in, fps_num, fps_den)

    # Track references inside the transition tractor must span the full
    # transition duration, not just half. Each track pulls from the
    # trimmed-off portion of its source clip.
    track_a_in = max(src_a_in, src_a_out - trans_frames)
    track_a_out = src_a_out
    track_b_in = src_b_in
    track_b_out = min(src_b_out, src_b_in + trans_frames)

    track_a_in_tc = frames_to_timecode(track_a_in, fps_num, fps_den)
    track_a_out_tc = frames_to_timecode(track_a_out, fps_num, fps_den)
    track_b_in_tc = frames_to_timecode(track_b_in, fps_num, fps_den)
    track_b_out_tc = frames_to_timecode(track_b_out, fps_num, fps_den)

    # Resolve transition service and params
    if transition_name in TRANSITION_REGISTRY:
        reg = TRANSITION_REGISTRY[transition_name]
        service = reg["service"]
        props = {}
        for pname, pinfo in reg["params"].items():
            props[pname] = pinfo["default"]
        if params:
            props.update(params)
    else:
        service = transition_name
        props = params or {}

    # Create sub-tractor (Shotcut format: has in/out, shotcut:transition property)
    trans_tractor = ET.Element("tractor")
    trans_id = mlt_xml.new_id("tractor")
    trans_tractor.set("id", trans_id)
    trans_tractor.set("in", "00:00:00.000")
    trans_tractor.set("out", trans_tc)
    mlt_xml.set_property(trans_tractor, "shotcut:transition", "lumaMix")

    tr_a = ET.SubElement(trans_tractor, "track")
    tr_a.set("producer", chain_a_id)
    tr_a.set("in", track_a_in_tc)
    tr_a.set("out", track_a_out_tc)

    tr_b = ET.SubElement(trans_tractor, "track")
    tr_b.set("producer", chain_b_id)
    tr_b.set("in", track_b_in_tc)
    tr_b.set("out", track_b_out_tc)

    # Luma (video) transition
    luma = ET.SubElement(trans_tractor, "transition")
    luma.set("id", mlt_xml.new_id("transition"))
    luma.set("out", trans_tc)
    mlt_xml.set_property(luma, "a_track", "0")
    mlt_xml.set_property(luma, "b_track", "1")
    mlt_xml.set_property(luma, "mlt_service", service)
    mlt_xml.set_property(luma, "factory", "loader")
    mlt_xml.set_property(luma, "progressive", "1")
    mlt_xml.set_property(luma, "alpha_over", "1")
    mlt_xml.set_property(luma, "fix_background_alpha", "1")
    mlt_xml.set_property(luma, "invert", "0")
    for k, v in props.items():
        mlt_xml.set_property(luma, k, str(v))

    # Mix (audio) transition — skip if the main service is already mix
    if service != "mix":
        mix = ET.SubElement(trans_tractor, "transition")
        mix.set("id", mlt_xml.new_id("transition"))
        mix.set("out", trans_tc)
        mlt_xml.set_property(mix, "a_track", "0")
        mlt_xml.set_property(mix, "b_track", "1")
        mlt_xml.set_property(mix, "start", "-1")
        mlt_xml.set_property(mix, "accepts_blanks", "1")
        mlt_xml.set_property(mix, "mlt_service", "mix")

    # Insert sub-tractor BEFORE the playlist that references it
    root = session.root
    for idx, child in enumerate(root):
        if child is playlist:
            root.insert(idx, trans_tractor)
            mlt_xml._register_tree(trans_tractor, root)
            break

    # Trim original entries so their trimmed-off portions feed the transition
    entry_a.set("out", new_src_a_out_tc)
    entry_b.set("in", new_src_b_in_tc)

    # Insert transition entry between the two clips in the playlist
    trans_entry = ET.Element("entry")
    trans_entry.set("producer", trans_id)
    trans_entry.set("in", "00:00:00.000")
    trans_entry.set("out", trans_tc)

    for i, child in enumerate(list(playlist)):
        if child is entry_a:
            playlist.insert(i + 1, trans_entry)
            break

    return {
        "action": "add_transition",
        "transition_name": transition_name,
        "service": service,
        "tractor_id": trans_id,
        "track_index": track_index,
        "clip_a_index": clip_a_index,
        "duration_frames": trans_frames,
        "params": props,
    }


def remove_transition(session: Session, transition_index: int) -> dict:
    """Remove a transition by index and restore trimmed clip lengths."""
    session.checkpoint()
    fps_num, fps_den = _get_fps(session)
    transitions = _get_user_transitions(session.root)

    if transition_index < 0 or transition_index >= len(transitions):
        raise IndexError(f"Transition index {transition_index} out of range "
                         f"(0-{len(transitions)-1})")

    trans = transitions[transition_index]
    trans_id = trans.get("id")

    _remove_transition_and_restore(session.root, trans, fps_num, fps_den)

    return {
        "action": "remove_transition",
        "transition_index": transition_index,
        "transition_id": trans_id,
    }


def set_transition_param(session: Session, transition_index: int,
                         param_name: str, param_value: str) -> dict:
    """Set a parameter on a transition."""
    session.checkpoint()
    transitions = _get_user_transitions(session.root)

    if transition_index < 0 or transition_index >= len(transitions):
        raise IndexError(f"Transition index {transition_index} out of range")

    trans = transitions[transition_index]
    target = None
    for t in trans.findall("transition"):
        svc = mlt_xml.get_property(t, "mlt_service", "")
        if svc != "mix":
            target = t
            break
    if target is None:
        children = trans.findall("transition")
        if not children:
            raise RuntimeError("No editable transition found")
        target = children[0]

    old_value = mlt_xml.get_property(target, param_name)
    mlt_xml.set_property(target, param_name, param_value)

    return {
        "action": "set_transition_param",
        "transition_index": transition_index,
        "param": param_name,
        "old_value": old_value,
        "new_value": param_value,
    }


def list_transitions(session: Session) -> list[dict]:
    """List all transitions on the timeline."""
    transitions = _get_user_transitions(session.root)
    result = []
    for i, trans in enumerate(transitions):
        service = ""
        mix_service = ""
        props = {}
        for t in trans.findall("transition"):
            svc = mlt_xml.get_property(t, "mlt_service", "")
            if svc == "mix":
                if not mix_service:
                    mix_service = svc
            else:
                if not service:
                    service = svc
            for prop in t.findall("property"):
                name = prop.get("name", "")
                if name and name not in ("mlt_service", "a_track", "b_track"):
                    props[name] = prop.text or ""
        if not service:
            service = mix_service

        track_ids = [tr.get("producer", "") for tr in trans.findall("track")]

        result.append({
            "index": i,
            "id": trans.get("id"),
            "service": service,
            "track_producers": track_ids,
            "in": trans.get("in"),
            "out": trans.get("out"),
            "params": props,
        })
    return result


def _get_user_transitions(root: ET.Element) -> list[ET.Element]:
    """Get all sub-tractor transitions (Shotcut editable format).

    Excludes the main timeline tractor (identified by the ``shotcut`` property)
    rather than hard-coding an id, because real Shotcut projects may assign
    any id to the main tractor (e.g. tractor1) while using tractor0 for a
    transition sub-tractor.
    """
    result = []
    for child in root:
        if child.tag == "tractor" and not mlt_xml.get_property(child, "shotcut"):
            if mlt_xml.get_property(child, "shotcut:transition"):
                result.append(child)
    return result


def _find_transitions_for_producer(root: ET.Element, producer_id: str) -> list[ET.Element]:
    """Find all sub-tractor transitions that reference a producer."""
    result = []
    for trans in _get_user_transitions(root):
        for track in trans.findall("track"):
            if track.get("producer") == producer_id:
                result.append(trans)
                break
    return result


def _compute_restoration_gains(trans: ET.Element, entry_a: ET.Element | None,
                               entry_b: ET.Element | None,
                               fps_num: int, fps_den: int) -> tuple[int, int]:
    tracks = trans.findall("track")
    if len(tracks) >= 2 and entry_a is not None and entry_b is not None:
        track_a = tracks[0]
        track_b = tracks[1]
        gain_a = parse_time_input(track_a.get("out", "00:00:00.000"), fps_num, fps_den) \
            - parse_time_input(entry_a.get("out", "00:00:00.000"), fps_num, fps_den)
        gain_b = parse_time_input(entry_b.get("in", "00:00:00.000"), fps_num, fps_den) \
            - parse_time_input(track_b.get("in", "00:00:00.000"), fps_num, fps_den)
        if gain_a > 0 or gain_b > 0:
            return gain_a, gain_b
    trans_frames = parse_time_input(trans.get("out", "00:00:00.000"), fps_num, fps_den)
    half_a = (trans_frames + 1) // 2
    half_b = trans_frames - half_a
    return half_a, half_b


def _remove_transition_and_restore(root: ET.Element, trans: ET.Element,
                                   fps_num: int, fps_den: int,
                                   skip_producer: str = "") -> None:
    """Remove a transition tractor and restore trimmed clip lengths.

    skip_producer: if set, don't restore frames to this producer's clip entry
                   (the user has already trimmed it).
    """
    trans_id = trans.get("id")

    track_producers = [t.get("producer", "") for t in trans.findall("track")]

    for child in list(root):
        if child.tag != "playlist":
            continue
        children = list(child)
        for i, entry in enumerate(children):
            if entry.tag == "entry" and entry.get("producer") == trans_id:
                entry_a = None
                for j in range(i - 1, -1, -1):
                    if children[j].tag == "entry" and children[j].get("producer", "") in track_producers:
                        entry_a = children[j]
                        break
                entry_b = None
                for j in range(i + 1, len(children)):
                    if children[j].tag == "entry" and children[j].get("producer", "") in track_producers:
                        entry_b = children[j]
                        break

                gain_a, gain_b = _compute_restoration_gains(
                    trans, entry_a, entry_b, fps_num, fps_den)

                child.remove(entry)

                if entry_a is not None and gain_a > 0 and entry_a.get("producer", "") != skip_producer:
                    a_out = parse_time_input(entry_a.get("out", "00:00:00.000"),
                                             fps_num, fps_den)
                    entry_a.set("out", frames_to_timecode(a_out + gain_a,
                                                          fps_num, fps_den))
                if entry_b is not None and gain_b > 0 and entry_b.get("producer", "") != skip_producer:
                    b_in = parse_time_input(entry_b.get("in", "00:00:00.000"),
                                            fps_num, fps_den)
                    new_b_in = max(0, b_in - gain_b)
                    entry_b.set("in", frames_to_timecode(new_b_in,
                                                          fps_num, fps_den))
                break

    root.remove(trans)


def _return_frames_to_other_clip(root: ET.Element, trans: ET.Element,
                                 producer_id: str, freed_frames: int,
                                 fps_num: int, fps_den: int) -> None:
    """Return freed frames to the other clip participating in a transition."""
    if freed_frames <= 0:
        return
    tracks = trans.findall("track")
    for t in tracks:
        other_id = t.get("producer", "")
        if other_id != producer_id:
            for child in root:
                if child.tag != "playlist":
                    continue
                for entry in child.findall("entry"):
                    if entry.get("producer") == other_id:
                        if t is tracks[1]:
                            cur_in = parse_time_input(entry.get("in", "00:00:00.000"),
                                                      fps_num, fps_den)
                            entry.set("in", frames_to_timecode(max(0, cur_in - freed_frames),
                                                               fps_num, fps_den))
                        else:
                            cur_out = parse_time_input(entry.get("out", "00:00:00.000"),
                                                       fps_num, fps_den)
                            entry.set("out", frames_to_timecode(cur_out + freed_frames,
                                                                fps_num, fps_den))
                        return


def _update_playlist_entry_out(root: ET.Element, trans_id: str, new_out: str) -> None:
    """Update the playlist entry referencing a transition to match new out."""
    if not trans_id:
        return
    for child in root:
        if child.tag != "playlist":
            continue
        for entry in child.findall("entry"):
            if entry.get("producer") == trans_id:
                entry.set("out", new_out)
                return


def remove_transitions_for_clip(root: ET.Element, producer_id: str,
                                fps_num: int, fps_den: int) -> None:
    """Remove all transitions that reference a clip producer."""
    for trans in _find_transitions_for_producer(root, producer_id):
        _remove_transition_and_restore(root, trans, fps_num, fps_den)


def remove_transitions_for_playlist(root: ET.Element, playlist_id: str) -> None:
    """Remove all transitions whose entries appear in a given playlist."""
    playlist = mlt_xml.find_element_by_id(root, playlist_id)
    if playlist is None:
        return

    transition_ids = set()
    for entry in playlist.findall("entry"):
        prod_id = entry.get("producer", "")
        prod = mlt_xml.find_element_by_id(root, prod_id)
        if prod is not None and prod.tag == "tractor" and mlt_xml.get_property(prod, "shotcut:transition"):
            transition_ids.add(prod_id)

    for trans_id in transition_ids:
        trans = mlt_xml.find_element_by_id(root, trans_id)
        if trans is not None:
            root.remove(trans)


def retime_transitions_for_clip(root: ET.Element, producer_id: str,
                                new_out: Optional[str],
                                new_in: Optional[str],
                                fps_num: int, fps_den: int) -> None:
    """Update transition track in/out when a clip is trimmed."""
    for trans in _find_transitions_for_producer(root, producer_id):
        tracks = trans.findall("track")
        for track in tracks:
            if track.get("producer") == producer_id:
                if new_out is not None:
                    track_out = parse_time_input(track.get("out", "00:00:00.000"),
                                                 fps_num, fps_den)
                    clip_out = parse_time_input(new_out, fps_num, fps_den)
                    if track_out > clip_out:
                        track_in_frames = parse_time_input(track.get("in", "0"),
                                                           fps_num, fps_den)
                        old_dur = track_out - track_in_frames
                        track.set("out", new_out)
                        trans_dur = clip_out - track_in_frames
                        if trans_dur <= 0:
                            _remove_transition_and_restore(root, trans, fps_num, fps_den,
                                                           skip_producer=producer_id)
                            break
                        elif trans_dur < old_dur:
                            new_out_tc = frames_to_timecode(trans_dur, fps_num, fps_den)
                            trans.set("out", new_out_tc)
                            for inner_t in trans.findall("transition"):
                                inner_t.set("out", new_out_tc)
                            _update_playlist_entry_out(root, trans.get("id"), new_out_tc)
                            freed = old_dur - trans_dur
                            _return_frames_to_other_clip(root, trans, producer_id,
                                                        freed, fps_num, fps_den)
                if new_in is not None:
                    track_in = parse_time_input(track.get("in", "00:00:00.000"),
                                                fps_num, fps_den)
                    clip_in = parse_time_input(new_in, fps_num, fps_den)
                    if track_in < clip_in:
                        track_out_frames = parse_time_input(track.get("out", "0"),
                                                            fps_num, fps_den)
                        old_dur = track_out_frames - track_in
                        track.set("in", new_in)
                        new_dur = track_out_frames - clip_in
                        if new_dur <= 0:
                            _remove_transition_and_restore(root, trans, fps_num, fps_den,
                                                           skip_producer=producer_id)
                            break
                        elif new_dur < old_dur:
                            new_out_tc = frames_to_timecode(new_dur, fps_num, fps_den)
                            trans.set("out", new_out_tc)
                            for inner_t in trans.findall("transition"):
                                inner_t.set("out", new_out_tc)
                            _update_playlist_entry_out(root, trans.get("id"), new_out_tc)
                            freed = old_dur - new_dur
                            _return_frames_to_other_clip(root, trans, producer_id,
                                                        freed, fps_num, fps_den)
                            # Re-anchor the other track's in to keep it at the cut point
                            other = tracks[0] if track is tracks[1] else tracks[1]
                            other_in = parse_time_input(
                                other.get("in", "00:00:00.000"), fps_num, fps_den)
                            other.set("in", frames_to_timecode(
                                other_in + freed, fps_num, fps_den))
                break
