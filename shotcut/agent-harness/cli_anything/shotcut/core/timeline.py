"""Timeline operations: tracks, clips, trimming, splitting, moving."""

import os
from typing import Optional
from lxml import etree

from ..utils import mlt_xml
from ..utils.time import parse_time_input, frames_to_timecode
from .session import Session


def _get_track_playlist(session: Session, track_index: int) -> etree._Element:
    """Get the playlist element for a track by its index."""
    tractor = session.get_main_tractor()
    tracks = mlt_xml.get_tractor_tracks(tractor)
    if track_index < 0 or track_index >= len(tracks):
        raise IndexError(f"Track index {track_index} out of range (0-{len(tracks)-1})")
    producer_id = tracks[track_index].get("producer")
    playlist = mlt_xml.find_element_by_id(session.root, producer_id)
    if playlist is None:
        raise RuntimeError(f"Playlist {producer_id!r} not found for track {track_index}")
    return playlist


def _get_fps(session: Session) -> tuple[int, int]:
    """Get fps_num, fps_den from the project profile."""
    profile = session.get_profile()
    fps_num = int(profile.get("frame_rate_num", 30000))
    fps_den = int(profile.get("frame_rate_den", 1001))
    return fps_num, fps_den


def _entry_duration_frames(session: Session, entry: dict) -> int:
    """Return duration in frames for a playlist entry or blank."""
    fps_num, fps_den = _get_fps(session)
    if entry["type"] == "blank":
        return parse_time_input(entry["length"], fps_num, fps_den)

    in_point = entry.get("in") or "00:00:00.000"
    out_point = entry.get("out")
    if not out_point:
        raise RuntimeError("Absolute timeline placement requires clips with finite out points")
    return parse_time_input(out_point, fps_num, fps_den) - parse_time_input(in_point, fps_num, fps_den)


def _absolute_insertion_point(
    session: Session, playlist: etree._Element, at_time: str
) -> tuple[int, int, int]:
    """Resolve where a new clip can start on a track timeline.

    Returns:
        (insert_child_index, leading_blank_frames, trailing_blank_frames)
    """
    fps_num, fps_den = _get_fps(session)
    target = parse_time_input(at_time, fps_num, fps_den)
    if target < 0:
        raise ValueError(f"Timeline position must be non-negative, got {at_time!r}")

    children = list(playlist)
    entries = mlt_xml.get_playlist_entries(playlist)
    timeline_cursor = 0

    for idx, entry in enumerate(entries):
        duration = _entry_duration_frames(session, entry)
        start = timeline_cursor
        end = start + duration
        if target == start:
            return idx + len([c for c in children[: idx] if c.tag == "property"]), 0, 0
        if entry["type"] == "blank" and start < target < end:
            leading = target - start
            trailing = end - target
            return idx + len([c for c in children[: idx] if c.tag == "property"]), leading, trailing
        if entry["type"] == "entry" and start < target < end:
            raise RuntimeError(
                f"Timeline position {at_time} overlaps an existing clip on track; "
                "split or move clips before placing another clip there"
            )
        timeline_cursor = end

    return len(children), max(0, target - timeline_cursor), 0


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

    # Remove the track from multitrack
    multitrack = tractor.find("multitrack")
    multitrack.remove(track_elem)

    # Remove the associated playlist
    playlist = mlt_xml.find_element_by_id(session.root, producer_id)
    if playlist is not None:
        mlt_xml.remove_element(playlist)

    # Remove transitions referencing this track index
    for trans in list(tractor.findall("transition")):
        b_track = mlt_xml.get_property(trans, "b_track")
        if b_track == str(track_index):
            tractor.remove(trans)

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
            clip_entries = [e for e in entries if e["type"] == "entry"]
            info["clip_count"] = len(clip_entries)
        else:
            info["type"] = "unknown"
            info["clip_count"] = 0

        result.append(info)

    return result


def add_clip(session: Session, resource: str, track_index: int,
             in_point: Optional[str] = None,
             out_point: Optional[str] = None,
             position: Optional[int] = None,
             at_time: Optional[str] = None,
             caption: Optional[str] = None) -> dict:
    """Add a media clip to a track.

    Args:
        session: Active session
        resource: Path to the media file
        track_index: Track to add the clip to
        in_point: Trim in point (timecode or frames)
        out_point: Trim out point (timecode or frames)
        position: Insert position (clip index on track), None = append
        at_time: Absolute timeline start time for the clip
        caption: Display name for the clip
    """
    resource = os.path.abspath(resource)
    if not os.path.isfile(resource):
        raise FileNotFoundError(f"Media file not found: {resource}")
    if position is not None and at_time is not None:
        raise ValueError("Use either position or at_time, not both")

    session.checkpoint()

    # Create a producer for this clip
    producer = mlt_xml.create_producer(
        session.root, resource,
        in_point=in_point or "00:00:00.000",
        out_point=out_point,
        caption=caption,
    )

    # Add entry to the track's playlist
    playlist = _get_track_playlist(session, track_index)
    if at_time is not None:
        insert_child_index, leading_blank_frames, trailing_blank_frames = _absolute_insertion_point(
            session, playlist, at_time
        )
        fps_num, fps_den = _get_fps(session)
        if leading_blank_frames:
            blank = etree.Element("blank")
            blank.set("length", frames_to_timecode(leading_blank_frames, fps_num, fps_den))
            playlist.insert(insert_child_index, blank)
            insert_child_index += 1

        entry = etree.Element("entry")
        entry.set("producer", producer.get("id"))
        if in_point:
            entry.set("in", in_point)
        if out_point:
            entry.set("out", out_point)
        playlist.insert(insert_child_index, entry)

        if trailing_blank_frames:
            blank = etree.Element("blank")
            blank.set("length", frames_to_timecode(trailing_blank_frames, fps_num, fps_den))
            playlist.insert(insert_child_index + 1, blank)
    else:
        entry = mlt_xml.add_entry_to_playlist(
            playlist, producer.get("id"),
            in_point=in_point,
            out_point=out_point,
            position=position,
        )

    return {
        "action": "add_clip",
        "producer_id": producer.get("id"),
        "track_index": track_index,
        "resource": resource,
        "in": in_point,
        "out": out_point,
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

    # Find the entry at clip_index
    clip_entries = [e for e in entries if e["type"] == "entry"]
    if clip_index < 0 or clip_index >= len(clip_entries):
        raise IndexError(
            f"Clip index {clip_index} out of range (0-{len(clip_entries)-1})"
        )

    # Find the actual XML element
    entry_count = 0
    for child in list(playlist):
        if child.tag == "entry":
            if entry_count == clip_index:
                producer_id = child.get("producer", "")
                if ripple:
                    playlist.remove(child)
                else:
                    # Replace with a blank of similar duration
                    in_tc = child.get("in", "00:00:00.000")
                    out_tc = child.get("out", "00:00:00.000")
                    playlist.remove(child)
                    # Calculate duration
                    fps_num, fps_den = _get_fps(session)
                    in_frames = parse_time_input(in_tc, fps_num, fps_den)
                    out_frames = parse_time_input(out_tc, fps_num, fps_den)
                    duration_frames = out_frames - in_frames
                    if duration_frames > 0:
                        duration_tc = frames_to_timecode(duration_frames, fps_num, fps_den)
                        blank = etree.Element("blank")
                        blank.set("length", duration_tc)
                        # Insert at same position
                        entries_seen = 0
                        insert_pos = 0
                        for j, ch in enumerate(list(playlist)):
                            if ch.tag in ("entry", "blank"):
                                if entries_seen == clip_index:
                                    insert_pos = j
                                    break
                                entries_seen += 1
                        else:
                            insert_pos = len(list(playlist))
                        playlist.insert(insert_pos, blank)

                return {
                    "action": "remove_clip",
                    "track_index": track_index,
                    "clip_index": clip_index,
                    "producer_id": producer_id,
                    "ripple": ripple,
                }
            entry_count += 1

    raise RuntimeError("Failed to find clip element")


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
        if child.tag == "entry":
            if entry_count == clip_index:
                clip_element = child
                break
            entry_count += 1

    if clip_element is None:
        raise IndexError(f"Clip index {clip_index} not found on track {from_track}")

    # Copy the entry data
    producer_id = clip_element.get("producer")
    in_point = clip_element.get("in")
    out_point = clip_element.get("out")

    # Remove from source
    src_playlist.remove(clip_element)

    # Add to destination
    dst_playlist = _get_track_playlist(session, to_track)
    mlt_xml.add_entry_to_playlist(
        dst_playlist, producer_id,
        in_point=in_point, out_point=out_point,
        position=to_position,
    )

    return {
        "action": "move_clip",
        "from_track": from_track,
        "clip_index": clip_index,
        "to_track": to_track,
        "to_position": to_position,
        "producer_id": producer_id,
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
        if child.tag == "entry":
            if entry_count == clip_index:
                old_in = child.get("in")
                old_out = child.get("out")
                if in_point is not None:
                    child.set("in", in_point)
                if out_point is not None:
                    child.set("out", out_point)
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
    for i, child in enumerate(list(playlist)):
        if child.tag == "entry":
            if entry_count == clip_index:
                producer_id = child.get("producer")
                old_in = child.get("in", "00:00:00.000")
                old_out = child.get("out")
                if old_out is None:
                    raise RuntimeError("Cannot split clip without out point")

                # First part: original in → split point
                child.set("out", at)

                # Second part: split point → original out
                # Create a copy of the producer
                original_producer = mlt_xml.find_element_by_id(session.root, producer_id)
                if original_producer is None:
                    raise RuntimeError(f"Producer {producer_id!r} not found")

                new_producer = mlt_xml.deep_copy_element(original_producer)
                new_prod_id = mlt_xml.new_id("producer")
                new_producer.set("id", new_prod_id)
                mlt_xml.set_property(new_producer, "shotcut:uuid",
                                     __import__("uuid").uuid4().hex)

                # Insert producer in document
                tractor = session.get_main_tractor()
                tractor_idx = list(session.root).index(tractor)
                session.root.insert(tractor_idx, new_producer)

                # Insert new entry after current one
                new_entry = etree.Element("entry")
                new_entry.set("producer", new_prod_id)
                new_entry.set("in", at)
                new_entry.set("out", old_out)

                # Find the position of current child and insert after
                playlist_children = list(playlist)
                current_idx = playlist_children.index(child)
                playlist.insert(current_idx + 1, new_entry)

                return {
                    "action": "split_clip",
                    "track_index": track_index,
                    "clip_index": clip_index,
                    "at": at,
                    "first_clip": {"producer": producer_id, "in": old_in, "out": at},
                    "second_clip": {"producer": new_prod_id, "in": at, "out": old_out},
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

    clip_idx = 0
    for entry in entries:
        if entry["type"] == "entry":
            # Look up producer info
            producer = mlt_xml.find_element_by_id(session.root, entry["producer"])
            caption = ""
            resource = ""
            if producer is not None:
                caption = mlt_xml.get_property(producer, "shotcut:caption", "")
                resource = mlt_xml.get_property(producer, "resource", "")

            result.append({
                "clip_index": clip_idx,
                "producer_id": entry["producer"],
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
