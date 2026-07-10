"""Timeline operations: tracks, clips, trimming, splitting, moving."""

import os
import uuid
from typing import Optional
import xml.etree.ElementTree as ET

from ..utils import mlt_xml
from ..utils.time import parse_time_input, frames_to_timecode
from .session import Session


def is_transition_entry(entry: ET.Element, root: ET.Element) -> bool:
    """Check if a playlist entry element references a transition sub-tractor."""
    if entry.tag != "entry":
        return False
    prod_id = entry.get("producer", "")
    prod = mlt_xml.find_element_by_id(root, prod_id)
    return (prod is not None
            and prod.tag == "tractor"
            and mlt_xml.get_property(prod, "shotcut:transition") is not None)


def is_transition_entry_by_dict(entry_dict: dict, root: ET.Element) -> bool:
    """Check if a playlist entry dict (from get_playlist_entries) references a transition."""
    if entry_dict.get("type") != "entry":
        return False
    prod_id = entry_dict.get("producer", "")
    prod = mlt_xml.find_element_by_id(root, prod_id)
    return (prod is not None
            and prod.tag == "tractor"
            and mlt_xml.get_property(prod, "shotcut:transition") is not None)


def _remove_adjacent_transitions(root: ET.Element, playlist: ET.Element,
                                 target_entry: ET.Element,
                                 fps_num: int, fps_den: int) -> None:
    """Remove transitions directly adjacent to a specific playlist entry."""
    from . import transitions as trans_mod

    children = list(playlist)
    idx = None
    for i, child in enumerate(children):
        if child is target_entry:
            idx = i
            break
    if idx is None:
        return

    # Check entry before target
    if idx > 0:
        prev = children[idx - 1]
        if prev.tag == "entry" and is_transition_entry(prev, root):
            trans_id = prev.get("producer", "")
            trans_elem = mlt_xml.find_element_by_id(root, trans_id)
            if trans_elem is not None:
                trans_mod._remove_transition_and_restore(root, trans_elem, fps_num, fps_den,
                                                          skip_producer=target_entry.get("producer", ""))
                if prev in list(playlist):
                    playlist.remove(prev)

    # Re-read children after potential removal above
    children = list(playlist)
    idx = None
    for i, child in enumerate(children):
        if child is target_entry:
            idx = i
            break
    if idx is None:
        return

    # Check entry after target
    if idx + 1 < len(children):
        nxt = children[idx + 1]
        if nxt.tag == "entry" and is_transition_entry(nxt, root):
            trans_id = nxt.get("producer", "")
            trans_elem = mlt_xml.find_element_by_id(root, trans_id)
            if trans_elem is not None:
                trans_mod._remove_transition_and_restore(root, trans_elem, fps_num, fps_den,
                                                          skip_producer=target_entry.get("producer", ""))
                if nxt in list(playlist):
                    playlist.remove(nxt)


def real_clip_entries(entries: list[dict], root: ET.Element) -> list[dict]:
    """Filter playlist entry dicts to real clips, excluding transitions."""
    trans_ids = _get_transition_ids(root)
    return [e for e in entries
            if e["type"] == "entry"
            and e.get("producer", "") not in trans_ids]


def _get_transition_ids(root: ET.Element) -> set[str]:
    return {c.get("id", "") for c in root
            if c.tag == "tractor"
            and not mlt_xml.get_property(c, "shotcut")
            and mlt_xml.get_property(c, "shotcut:transition")}


def _get_track_playlist(session: Session, track_index: int) -> ET.Element:
    """Get the playlist element for a track by its index."""
    if track_index < 0 or track_index >= len(session._track_playlists):
        raise IndexError(f"Track index {track_index} out of range (0-{len(session._track_playlists)-1})")
    playlist = session._track_playlists[track_index]
    if playlist is None:
        raise RuntimeError(f"No playlist for track {track_index}")
    return playlist


def _resolve_insert_index(playlist: ET.Element, position: int,
                          root: ET.Element) -> int:
    """Map a logical clip position to a physical playlist child index.

    Counts real clips (skips transition entries). When the target position
    falls between a transition entry and its following clip, backs up to
    insert before the transition entry so the transition pair stays intact.
    """
    all_children = list(playlist)
    children = [c for c in all_children if c.tag != "property"]
    real_count = 0
    for i, child in enumerate(children):
        if child.tag == "entry" and is_transition_entry(child, root):
            continue
        if child.tag == "blank":
            continue
        if real_count == position:
            idx = i
            while idx > 0:
                prev = children[idx - 1]
                if prev.tag == "entry" and is_transition_entry(prev, root):
                    idx -= 1
                else:
                    break
            return all_children.index(children[idx])
        real_count += 1
    return len(all_children)


def _get_fps(session: Session) -> tuple[int, int]:
    """Get fps_num, fps_den from the project profile."""
    profile = session.get_profile()
    fps_num = int(profile.get("frame_rate_num", 30000))
    fps_den = int(profile.get("frame_rate_den", 1001))
    return fps_num, fps_den


def _entry_duration_frames(session: Session, entry: dict) -> int:
    fps_num, fps_den = _get_fps(session)
    if entry["type"] == "blank":
        return parse_time_input(entry["length"], fps_num, fps_den)
    in_point = entry.get("in") or "00:00:00.000"
    out_point = entry.get("out")
    if not out_point:
        raise RuntimeError("Absolute timeline placement requires clips with finite out points")
    return (
        parse_time_input(out_point, fps_num, fps_den)
        - parse_time_input(in_point, fps_num, fps_den)
        + 1
    )


def _absolute_insertion_point(
    session: Session, playlist: ET.Element, at_time: str
) -> tuple[int, int, int]:
    fps_num, fps_den = _get_fps(session)
    target = parse_time_input(at_time, fps_num, fps_den)
    if target < 0:
        raise ValueError(f"Timeline position must be non-negative, got {at_time!r}")

    children = list(playlist)
    timeline_cursor = 0

    for phys_idx, child in enumerate(children):
        if child.tag == "property":
            continue

        if child.tag == "blank":
            duration = parse_time_input(child.get("length", "00:00:00.000"), fps_num, fps_den)
            start = timeline_cursor
            end = start + duration
            if target == start:
                return phys_idx, 0, 0
            if start < target < end:
                return phys_idx, target - start, end - target
            timeline_cursor = end
            continue

        if child.tag == "entry":
            in_tc = child.get("in", "00:00:00.000")
            out_tc = child.get("out")
            if out_tc is None:
                prod = mlt_xml.find_element_by_id(session.root, child.get("producer", ""))
                out_tc = prod.get("out", "00:00:00.000") if prod is not None else "00:00:00.000"
            duration = (
                parse_time_input(out_tc, fps_num, fps_den)
                - parse_time_input(in_tc, fps_num, fps_den)
                + 1
            )
            start = timeline_cursor
            end = start + duration
            if target == start:
                return phys_idx, 0, 0
            if start < target < end:
                raise RuntimeError(
                    f"Timeline position {at_time} overlaps an existing clip on track; "
                    "split or move clips before placing another clip there"
                )
            timeline_cursor = end
            continue

    return len(children), max(0, target - timeline_cursor), 0


def _prepare_insert_index(playlist: ET.Element, position: int,
                                session: Session) -> int:
    from .transitions import _remove_transition_and_restore
    insert_idx = _resolve_insert_index(playlist, position, session.root)
    children = list(playlist)
    if insert_idx < len(children):
        child_at = children[insert_idx]
        if child_at.tag == "entry" and is_transition_entry(child_at, session.root):
            trans_id = child_at.get("producer")
            trans_tractor = mlt_xml.find_element_by_id(session.root, trans_id)
            if trans_tractor is not None:
                fps_num, fps_den = _get_fps(session)
                _remove_transition_and_restore(
                    session.root, trans_tractor, fps_num, fps_den)
                insert_idx = _resolve_insert_index(playlist, position, session.root)
    return insert_idx


def _update_tractor_out(session: Session) -> None:
    """Update main tractor out to match the longest track duration."""
    fps_num, fps_den = _get_fps(session)
    tractor = session.get_main_tractor()
    max_frames = 0

    for track_elem in mlt_xml.get_tractor_tracks(tractor):
        playlist_id = track_elem.get("producer")
        if not playlist_id or playlist_id == "background":
            continue
        playlist = mlt_xml.find_element_by_id(session.root, playlist_id)
        if playlist is None:
            continue

        track_frames = 0
        for child in playlist:
            if child.tag == "entry":
                in_tc = child.get("in", "00:00:00.000")
                out_tc = child.get("out")
                if out_tc is None:
                    producer_id = child.get("producer", "")
                    producer = mlt_xml.find_element_by_id(session.root, producer_id)
                    if producer is not None:
                        out_tc = producer.get("out", "00:00:00.000")
                    else:
                        out_tc = "00:00:00.000"
                track_frames += parse_time_input(out_tc, fps_num, fps_den)
                track_frames -= parse_time_input(in_tc, fps_num, fps_den)
                track_frames += 1
            elif child.tag == "blank":
                track_frames += parse_time_input(child.get("length", "00:00:00.000"), fps_num, fps_den)

        max_frames = max(max_frames, track_frames)

    out_tc = frames_to_timecode(max_frames - 1, fps_num, fps_den) if max_frames > 0 else "00:00:00.000"
    mlt_xml.set_tractor_out(session.root, out_tc)

    # Sync background producer and playlist entry to match — melt ignores
    # tractor out and renders until the longest track playlist entry ends.
    bg_producer = mlt_xml.find_element_by_id(session.root, "black")
    if bg_producer is not None:
        bg_producer.set("out", out_tc)
        mlt_xml.set_property(bg_producer, "length",
                             frames_to_timecode(max_frames, fps_num, fps_den)
                             if max_frames > 0 else "00:00:00.040")
    bg_playlist = mlt_xml.find_element_by_id(session.root, "background")
    if bg_playlist is not None:
        for entry in bg_playlist.findall("entry"):
            entry.set("out", out_tc)


def add_track(session: Session, track_type: str = "video",
              name: str = "") -> dict:
    """Add a new track to the timeline.

    Args:
        session: Active session
        track_type: "video" or "audio"
        name: Optional track name

    Returns:
        Dict with track info
    """
    if track_type not in ("video", "audio"):
        raise ValueError(f"Track type must be 'video' or 'audio', got {track_type!r}")

    session.checkpoint()
    tractor = session.get_main_tractor()
    playlist_id, track_index = mlt_xml.add_track_to_tractor(
        session.root, tractor, track_type, name
    )
    playlist = mlt_xml.find_element_by_id(session.root, playlist_id)
    while len(session._track_playlists) < track_index:
        session._track_playlists.append(None)
    if len(session._track_playlists) == track_index:
        session._track_playlists.append(playlist)
    else:
        session._track_playlists[track_index] = playlist

    return {
        "action": "add_track",
        "track_index": track_index,
        "playlist_id": playlist_id,
        "type": track_type,
        "name": name,
    }


def remove_track(session: Session, track_index: int) -> dict:
    """Remove a track from the timeline.

    Args:
        track_index: Index of the track to remove (0 is usually background)
    """
    session.checkpoint()
    tractor = session.get_main_tractor()
    tracks = mlt_xml.get_tractor_tracks(tractor)

    if track_index < 1 or track_index >= len(tracks):
        raise IndexError(
            f"Track index {track_index} out of range. "
            f"Valid range: 1-{len(tracks)-1} (track 0 is background)"
        )

    track_elem = tracks[track_index]
    producer_id = track_elem.get("producer")

    # Remove the track from tractor (directly or from multitrack)
    multitrack = tractor.find("multitrack")
    if multitrack is not None:
        multitrack.remove(track_elem)
    else:
        tractor.remove(track_elem)

    # Remove sub-tractor transitions whose entries were in this playlist
    from . import transitions as trans_mod
    trans_mod.remove_transitions_for_playlist(session.root, producer_id)

    # Remove the associated playlist
    playlist = mlt_xml.find_element_by_id(session.root, producer_id)
    if playlist is not None:
        mlt_xml.remove_element(playlist)

    # Remove transitions referencing this track index
    for trans in list(tractor.findall("transition")):
        b_track = mlt_xml.get_property(trans, "b_track")
        if b_track == str(track_index):
            tractor.remove(trans)

    # Fix a_track referencing the deleted track, then decrement higher indices
    remaining_tracks = mlt_xml.get_tractor_tracks(tractor)
    for trans in tractor.findall("transition"):
        a_track_val = mlt_xml.get_property(trans, "a_track")
        b_track_val = mlt_xml.get_property(trans, "b_track")
        if a_track_val is not None and int(a_track_val) == track_index:
            new_a = 0
            for i in range(track_index - 1, -1, -1):
                if i < len(remaining_tracks):
                    pl = mlt_xml.find_element_by_id(
                        session.root, remaining_tracks[i].get("producer", ""))
                    if pl is not None and mlt_xml.get_property(pl, "shotcut:video"):
                        new_a = i
                        break
            mlt_xml.set_property(trans, "a_track", str(new_a))
            if mlt_xml.get_property(trans, "mlt_service") == "qtblend":
                mlt_xml.set_property(trans, "disable", "1" if new_a == 0 else "0")
        if a_track_val is not None and int(a_track_val) > track_index:
            mlt_xml.set_property(trans, "a_track", str(int(a_track_val) - 1))
        if b_track_val is not None and int(b_track_val) > track_index:
            mlt_xml.set_property(trans, "b_track", str(int(b_track_val) - 1))

    _update_tractor_out(session)

    if track_index < len(session._track_playlists):
        session._track_playlists.pop(track_index)

    return {
        "action": "remove_track",
        "track_index": track_index,
        "playlist_id": producer_id,
    }


def list_tracks(session: Session) -> list[dict]:
    """List all tracks in the timeline."""
    if not session.is_open:
        raise RuntimeError("No project is open")

    tractor = session.get_main_tractor()
    tracks = mlt_xml.get_tractor_tracks(tractor)
    result = []

    for i, te in enumerate(tracks):
        producer_id = te.get("producer", "")
        playlist = mlt_xml.find_element_by_id(session.root, producer_id)

        info = {
            "index": i,
            "playlist_id": producer_id,
            "hide": te.get("hide", ""),
        }

        if playlist is not None:
            info["name"] = mlt_xml.get_property(playlist, "shotcut:name", "")
            is_video = mlt_xml.get_property(playlist, "shotcut:video")
            is_audio = mlt_xml.get_property(playlist, "shotcut:audio")
            if is_video:
                info["type"] = "video"
            elif is_audio or te.get("hide") == "video":
                info["type"] = "audio"
            elif producer_id == "background":
                info["type"] = "background"
            else:
                info["type"] = "video"

            entries = mlt_xml.get_playlist_entries(playlist)
            info["clip_count"] = len(real_clip_entries(entries, session.root))
        else:
            info["type"] = "unknown"
            info["clip_count"] = 0

        result.append(info)

    return result


def add_clip(session: Session, clip_id: str, track_index: int,
             in_point: Optional[str] = None,
             out_point: Optional[str] = None,
             position: Optional[int] = None,
             at_time: Optional[str] = None,
             caption: Optional[str] = None) -> dict:
    """Add a clip to a track by referencing an imported media clip_id.

    The timeline chain is shared — same clip_id always maps to the same chain.
    Each call creates a new playlist entry with its own in/out range.
    """
    if position is not None and at_time is not None:
        raise ValueError("Cannot specify both position and at_time")

    bin_chain = session._bin_chains.get(clip_id)
    if bin_chain is None:
        available = ", ".join(sorted(session._bin_chains.keys()))
        raise ValueError(
            f"Clip {clip_id!r} not imported. Available: {available}. "
            f"Use 'media import' first."
        )

    resource = mlt_xml.get_property(bin_chain, "resource", "")
    session.checkpoint()

    # Reuse timeline chain for same clip_id
    timeline_chain_id = f"tl_{clip_id}"
    timeline_chain = mlt_xml.find_element_by_id(session.root, timeline_chain_id)

    if timeline_chain is None or mlt_xml.get_parent(timeline_chain) is None:
        length_tc = mlt_xml.get_property(bin_chain, "length")
        source_out = bin_chain.get("out") or length_tc
        video_index = mlt_xml.get_property(bin_chain, "video_index") or "0"
        audio_index = mlt_xml.get_property(bin_chain, "audio_index") or "1"

        timeline_chain = mlt_xml.create_chain(
            session.root, resource,
            in_point="00:00:00.000",
            out_point=source_out,
            caption=caption or os.path.basename(resource),
            extra_props={"video_index": video_index, "audio_index": audio_index},
            insert_idx=session._timeline_insert_idx,
            length=length_tc,
            id_override=timeline_chain_id,
        )
        session._timeline_insert_idx += 1

    playlist = _get_track_playlist(session, track_index)
    final_in = in_point or timeline_chain.get("in", "00:00:00.000")
    final_out = out_point or timeline_chain.get("out")

    if at_time is not None:
        fps_num, fps_den = _get_fps(session)
        insert_idx, leading_blank, trailing_blank = _absolute_insertion_point(
            session, playlist, at_time)
        if leading_blank > 0:
            blank = ET.SubElement(playlist, "blank")
            blank.set("length", frames_to_timecode(leading_blank, fps_num, fps_den))
            mlt_xml._set_parent(blank, playlist)
            playlist.remove(blank)
            playlist.insert(insert_idx, blank)
            insert_idx += 1
        mlt_xml.add_entry_to_playlist(
            playlist, timeline_chain.get("id"),
            in_point=final_in, out_point=final_out,
            insert_before=insert_idx)
        if trailing_blank > 0:
            blank = ET.SubElement(playlist, "blank")
            blank.set("length", frames_to_timecode(trailing_blank, fps_num, fps_den))
            mlt_xml._set_parent(blank, playlist)
            playlist.remove(blank)
            playlist.insert(insert_idx + 1, blank)
    elif position is not None:
        insert_idx = _prepare_insert_index(playlist, position, session)
        mlt_xml.add_entry_to_playlist(
            playlist, timeline_chain.get("id"),
            in_point=final_in, out_point=final_out,
            insert_before=insert_idx,
        )
    else:
        mlt_xml.add_entry_to_playlist(
            playlist, timeline_chain.get("id"),
            in_point=final_in, out_point=final_out,
        )

    _update_tractor_out(session)

    return {
        "action": "add_clip",
        "clip_id": clip_id,
        "chain_id": timeline_chain.get("id"),
        "track_index": track_index,
        "resource": resource,
        "in": final_in,
        "out": final_out,
        "position": position,
        "at_time": at_time,
        "caption": caption or os.path.basename(resource),
    }


def remove_clip(session: Session, track_index: int, clip_index: int,
                ripple: bool = True) -> dict:
    """Remove a clip from a track.

    Args:
        track_index: Track containing the clip
        clip_index: Index of the clip on the track
        ripple: If True, close the gap; if False, leave a blank
    """
    session.checkpoint()
    playlist = _get_track_playlist(session, track_index)
    entries = mlt_xml.get_playlist_entries(playlist)

    # Find the entry at clip_index (skip transition entries)
    clip_entries = real_clip_entries(entries, session.root)
    if clip_index < 0 or clip_index >= len(clip_entries):
        raise IndexError(
            f"Clip index {clip_index} out of range (0-{len(clip_entries)-1})"
        )

    target_entry = clip_entries[clip_index]

    fps_num, fps_den = _get_fps(session)

    # Find the actual XML element by walking the playlist and matching clip_index
    real_idx = 0
    target_child = None
    for child in list(playlist):
        if child.tag != "entry":
            continue
        if is_transition_entry(child, session.root):
            continue
        if real_idx == clip_index:
            target_child = child
            break
        real_idx += 1

    if target_child is None:
        raise RuntimeError("Failed to find clip element")

    # Remove transitions adjacent to the specific entry (not global producer search)
    _remove_adjacent_transitions(session.root, playlist, target_child, fps_num, fps_den)

    producer_id = target_child.get("producer", "")
    if ripple:
        playlist.remove(target_child)
    else:
        in_tc = target_child.get("in", "00:00:00.000")
        out_tc = target_child.get("out", "00:00:00.000")
        playlist.remove(target_child)
        in_frames = parse_time_input(in_tc, fps_num, fps_den)
        out_frames = parse_time_input(out_tc, fps_num, fps_den)
        duration_frames = out_frames - in_frames + 1
        if duration_frames > 0:
            duration_tc = frames_to_timecode(duration_frames, fps_num, fps_den)
            blank = ET.Element("blank")
            blank.set("length", duration_tc)
            entries_seen = 0
            insert_pos = 0
            for j, ch in enumerate(list(playlist)):
                if ch.tag in ("entry", "blank"):
                    if ch.tag == "entry" and is_transition_entry(ch, session.root):
                        continue
                    if entries_seen == clip_index:
                        insert_pos = j
                        break
                    entries_seen += 1
            else:
                insert_pos = len(list(playlist))
            playlist.insert(insert_pos, blank)

    _update_tractor_out(session)
    return {
        "action": "remove_clip",
        "track_index": track_index,
        "clip_index": clip_index,
        "producer_id": producer_id,
        "ripple": ripple,
    }


def move_clip(session: Session, from_track: int, clip_index: int,
              to_track: int, to_position: Optional[int] = None) -> dict:
    """Move a clip from one position to another.

    Args:
        from_track: Source track index
        clip_index: Clip index on source track
        to_track: Destination track index
        to_position: Position on destination track (None = append)
    """
    session.checkpoint()

    # Get the clip entry from source track
    src_playlist = _get_track_playlist(session, from_track)

    entry_count = 0
    clip_element = None
    for child in list(src_playlist):
        if child.tag == "entry" and not is_transition_entry(child, session.root):
            if entry_count == clip_index:
                clip_element = child
                break
            entry_count += 1

    if clip_element is None:
        raise IndexError(f"Clip index {clip_index} not found on track {from_track}")

    producer_id = clip_element.get("producer")

    from . import transitions as trans_mod
    fps_num, fps_den = _get_fps(session)
    trans_mod.remove_transitions_for_clip(session.root, producer_id, fps_num, fps_den)

    # Read in/out AFTER transition restoration
    in_point = clip_element.get("in")
    out_point = clip_element.get("out")

    # Remove from source
    src_playlist.remove(clip_element)

    # Add to destination
    dst_playlist = _get_track_playlist(session, to_track)
    if to_position is not None:
        insert_idx = _prepare_insert_index(dst_playlist, to_position, session)
        mlt_xml.add_entry_to_playlist(
            dst_playlist, producer_id,
            in_point=in_point, out_point=out_point,
            insert_before=insert_idx,
        )
    else:
        mlt_xml.add_entry_to_playlist(
            dst_playlist, producer_id,
            in_point=in_point, out_point=out_point,
        )

    _update_tractor_out(session)
    return {
        "action": "move_clip",
        "from_track": from_track,
        "clip_index": clip_index,
        "to_track": to_track,
        "to_position": to_position,
        "chain_id": producer_id,
    }


def trim_clip(session: Session, track_index: int, clip_index: int,
              in_point: Optional[str] = None,
              out_point: Optional[str] = None) -> dict:
    """Trim a clip's in/out points.

    Args:
        track_index: Track containing the clip
        clip_index: Index of the clip
        in_point: New in point (None = keep current)
        out_point: New out point (None = keep current)
    """
    session.checkpoint()
    playlist = _get_track_playlist(session, track_index)

    entry_count = 0
    for child in list(playlist):
        if child.tag == "entry" and not is_transition_entry(child, session.root):
            if entry_count == clip_index:
                old_in = child.get("in")
                old_out = child.get("out")
                if in_point is not None:
                    child.set("in", in_point)
                if out_point is not None:
                    child.set("out", out_point)

                from . import transitions as trans_mod
                fps_num, fps_den = _get_fps(session)
                trans_mod.retime_transitions_for_clip(
                    session.root, child.get("producer"),
                    out_point, in_point, fps_num, fps_den)

                _update_tractor_out(session)
                return {
                    "action": "trim_clip",
                    "track_index": track_index,
                    "clip_index": clip_index,
                    "old_in": old_in,
                    "old_out": old_out,
                    "new_in": child.get("in"),
                    "new_out": child.get("out"),
                }
            entry_count += 1

    raise IndexError(f"Clip index {clip_index} not found on track {track_index}")


def split_clip(session: Session, track_index: int, clip_index: int,
               at: str) -> dict:
    """Split a clip at a given timecode, creating two clips.

    Args:
        track_index: Track containing the clip
        clip_index: Index of the clip
        at: Timecode within the clip's source where to split
    """
    session.checkpoint()
    playlist = _get_track_playlist(session, track_index)

    entry_count = 0
    for child in list(playlist):
        if child.tag == "entry" and not is_transition_entry(child, session.root):
            if entry_count == clip_index:
                producer_id = child.get("producer")
                old_in = child.get("in", "00:00:00.000")

                from . import transitions as trans_mod
                fps_num, fps_den = _get_fps(session)
                trans_mod.remove_transitions_for_clip(session.root, producer_id, fps_num, fps_den)

                # Read out AFTER transition restoration
                old_out = child.get("out")
                if old_out is None:
                    raise RuntimeError("Cannot split clip without out point")

                old_in_frames = parse_time_input(old_in, fps_num, fps_den)
                old_out_frames = parse_time_input(old_out, fps_num, fps_den)
                split_frames = parse_time_input(at, fps_num, fps_den)
                if split_frames <= old_in_frames:
                    raise ValueError("Split point must be after the clip in point")
                if split_frames > old_out_frames:
                    raise ValueError("Split point must not exceed the clip out point")

                first_out = frames_to_timecode(split_frames - 1, fps_num, fps_den)

                # MLT out-points are inclusive, so the first half must end on
                # the frame immediately before the split point.
                child.set("out", first_out)

                # Second part: split point → original out
                # Create a copy of the timeline chain
                original_chain = mlt_xml.find_element_by_id(session.root, producer_id)
                if original_chain is None:
                    raise RuntimeError(f"Chain {producer_id!r} not found")

                new_chain = mlt_xml.deep_copy_element(original_chain)
                new_chain_id = mlt_xml.new_id("chain")
                new_chain.set("id", new_chain_id)
                mlt_xml.set_property(new_chain, "shotcut:uuid",
                                     uuid.uuid4().hex)

                # Insert chain before track playlists
                insert_idx = mlt_xml.find_insert_index_for_timeline_chain(session.root)
                session.root.insert(insert_idx, new_chain)
                mlt_xml._register_tree(new_chain, session.root)
                new_entry = ET.Element("entry")
                new_entry.set("producer", new_chain_id)
                new_entry.set("in", at)
                new_entry.set("out", old_out)

                playlist_children = list(playlist)
                current_idx = playlist_children.index(child)
                playlist.insert(current_idx + 1, new_entry)

                _update_tractor_out(session)
                return {
                    "action": "split_clip",
                    "track_index": track_index,
                    "clip_index": clip_index,
                    "at": at,
                    "first_clip": {"chain_id": producer_id, "in": old_in, "out": first_out},
                    "second_clip": {"chain_id": new_chain_id, "in": at, "out": old_out},
                }
            entry_count += 1

    raise IndexError(f"Clip index {clip_index} not found on track {track_index}")


def list_clips(session: Session, track_index: int) -> list[dict]:
    """List all clips on a track.

    Returns:
        List of clip info dicts
    """
    playlist = _get_track_playlist(session, track_index)
    entries = mlt_xml.get_playlist_entries(playlist)
    result = []

    trans_ids = _get_transition_ids(session.root)
    clip_idx = 0
    for entry in entries:
        if entry["type"] == "entry" and entry.get("producer", "") not in trans_ids:
            # Look up producer info
            producer = mlt_xml.find_element_by_id(session.root, entry["producer"])
            caption = ""
            resource = ""
            if producer is not None:
                caption = mlt_xml.get_property(producer, "shotcut:caption", "")
                resource = mlt_xml.get_property(producer, "resource", "")

            result.append({
                "clip_index": clip_idx,
                "chain_id": entry["producer"],
                "in": entry["in"],
                "out": entry["out"],
                "caption": caption,
                "resource": resource,
            })
            clip_idx += 1
        elif entry["type"] == "blank":
            result.append({
                "type": "blank",
                "length": entry["length"],
            })

    return result


def add_blank(session: Session, track_index: int, length: str) -> dict:
    """Add a blank gap to a track.

    Args:
        track_index: Track to add the blank to
        length: Duration of the blank (timecode)
    """
    session.checkpoint()
    playlist = _get_track_playlist(session, track_index)
    mlt_xml.add_blank_to_playlist(playlist, length)

    return {
        "action": "add_blank",
        "track_index": track_index,
        "length": length,
    }


def set_track_name(session: Session, track_index: int, name: str) -> dict:
    """Set a track's display name."""
    session.checkpoint()
    playlist = _get_track_playlist(session, track_index)
    mlt_xml.set_property(playlist, "shotcut:name", name)

    return {
        "action": "set_track_name",
        "track_index": track_index,
        "name": name,
    }


def set_track_mute(session: Session, track_index: int, mute: bool) -> dict:
    """Mute or unmute a track."""
    session.checkpoint()
    tractor = session.get_main_tractor()
    tracks = mlt_xml.get_tractor_tracks(tractor)

    if track_index < 0 or track_index >= len(tracks):
        raise IndexError(f"Track index {track_index} out of range")

    track_elem = tracks[track_index]
    current_hide = track_elem.get("hide", "")

    if mute:
        if current_hide == "video":
            track_elem.set("hide", "both")
        elif current_hide not in ("audio", "both"):
            track_elem.set("hide", "audio")
    else:
        if current_hide == "both":
            track_elem.set("hide", "video")
        elif current_hide == "audio":
            track_elem.attrib.pop("hide", None)

    return {
        "action": "set_track_mute",
        "track_index": track_index,
        "mute": mute,
        "hide": track_elem.get("hide", ""),
    }


def set_track_hidden(session: Session, track_index: int, hidden: bool) -> dict:
    """Hide or show a video track."""
    session.checkpoint()
    tractor = session.get_main_tractor()
    tracks = mlt_xml.get_tractor_tracks(tractor)

    if track_index < 0 or track_index >= len(tracks):
        raise IndexError(f"Track index {track_index} out of range")

    track_elem = tracks[track_index]
    current_hide = track_elem.get("hide", "")

    if hidden:
        if current_hide == "audio":
            track_elem.set("hide", "both")
        elif current_hide not in ("video", "both"):
            track_elem.set("hide", "video")
    else:
        if current_hide == "both":
            track_elem.set("hide", "audio")
        elif current_hide == "video":
            track_elem.attrib.pop("hide", None)

    return {
        "action": "set_track_hidden",
        "track_index": track_index,
        "hidden": hidden,
        "hide": track_elem.get("hide", ""),
    }


def show_timeline(session: Session) -> dict:
    """Get a complete timeline overview.

    Returns a structured dict with all tracks and their clips.
    """
    if not session.is_open:
        raise RuntimeError("No project is open")

    tracks = list_tracks(session)
    timeline = []

    for track in tracks:
        track_data = dict(track)
        if track["type"] != "background" and track["type"] != "unknown":
            try:
                track_data["clips"] = list_clips(session, track["index"])
            except (IndexError, RuntimeError):
                track_data["clips"] = []
        timeline.append(track_data)

    fps_num, fps_den = _get_fps(session)
    return {
        "fps_num": fps_num,
        "fps_den": fps_den,
        "tracks": timeline,
    }
