"""Kdenlive CLI - MLT XML generation helpers and timecode conversions."""

import json
import re
import uuid
import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional

from cli_anything.kdenlive.core.filters import FILTER_REGISTRY



def xml_escape(s: str) -> str:
    s = s.replace("&", "&amp;")
    s = s.replace("<", "&lt;")
    s = s.replace(">", "&gt;")
    s = s.replace('"', "&quot;")
    s = s.replace("'", "&apos;")
    return s


def _add_disabled_filter(parent, service, counter):
    f = ET.SubElement(parent, "filter", {"id": f"filter{counter}"})
    _add_prop(f, "mlt_service", service)
    _add_prop(f, "internal_added", "237")
    _add_prop(f, "disable", "1")
    return counter + 1


def seconds_to_timecode(seconds: float) -> str:
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
    millis_str = m.group(4) if m.group(4) else "0"
    millis = int(millis_str.ljust(3, '0'))
    return hours * 3600 + minutes * 60 + secs + millis / 1000.0


def seconds_to_frames(seconds: float, fps_num: int = 30, fps_den: int = 1) -> int:
    fps = fps_num / max(fps_den, 1)
    return int(round(seconds * fps))


def frames_to_seconds(frames: int, fps_num: int = 30, fps_den: int = 1) -> float:
    fps = fps_num / max(fps_den, 1)
    return frames / fps


def _add_prop(parent: ET.Element, name: str, value) -> ET.Element:
    prop = ET.SubElement(parent, "property")
    prop.set("name", name)
    prop.text = str(value)
    return prop


def _compute_track_duration(track: dict, fps_num: int, fps_den: int,
                            valid_ids: Optional[set] = None) -> int:
    """Track duration in frames, as the inclusive final frame index.

    ``valid_ids`` restricts the calculation to entries whose clip is still in
    the bin. `bin remove` leaves the track entry behind and the playlist build
    below skips it, so counting it here would stretch the tractor past
    anything that actually gets written — melt then encodes the gap as black.
    """
    max_end = 0.0
    for clip_entry in track.get("clips", []):
        if valid_ids is not None and clip_entry.get("clip_id") not in valid_ids:
            continue
        clip_end = clip_entry.get("position", 0.0) + (
            clip_entry.get("out", 0) - clip_entry.get("in", 0)
        )
        max_end = max(max_end, clip_end)
    if max_end <= 0:
        return 0
    return max(seconds_to_frames(max_end, fps_num, fps_den) - 1, 0)


def _clip_type_num(clip_type: str) -> int:
    mapping = {
        "video": 0,
        "audio": 1,
        "image": 2,
        "color": 3,
        "title": 4,
    }
    return mapping.get(clip_type, 0)


def _avformat_indexes(parent: ET.Element, clip_type: str):
    if clip_type == "audio":
        _add_prop(parent, "audio_index", "0")
        _add_prop(parent, "video_index", "-1")
    elif clip_type == "image":
        _add_prop(parent, "audio_index", "-1")
        _add_prop(parent, "video_index", "0")
    else:
        _add_prop(parent, "audio_index", "1")
        _add_prop(parent, "video_index", "0")


def _set_producer_props(parent: ET.Element, clip_type: str):
    if clip_type == "color":
        _add_prop(parent, "mlt_service", "color")
    else:
        _add_prop(parent, "mlt_service", "avformat-novalidate")
        _add_prop(parent, "seekable", "1")
        _avformat_indexes(parent, clip_type)


def _track_index(tracks: list, track_id: int) -> int:
    for i, t in enumerate(tracks):
        if t["id"] == track_id:
            return i
    return 0


_SEQUENCE_FOLDER_ID = "2"
_SEQUENCE_KDENLIVE_ID = "3"
_CLIP_KDENLIVE_ID_START = 4


def build_mlt_xml(project: Dict[str, Any]) -> str:
    """Build a Kdenlive Gen 5 (doc version 1.1) compatible MLT XML document."""
    profile = project.get("profile", {})
    width = profile.get("width", 1920)
    height = profile.get("height", 1080)
    fps_num = profile.get("fps_num", 30)
    fps_den = profile.get("fps_den", 1)
    progressive = profile.get("progressive", True)
    dar_num = profile.get("dar_num", 16)
    dar_den = profile.get("dar_den", 9)

    sar_num = dar_num * height
    sar_den = dar_den * width

    bin_clips = project.get("bin", [])
    tracks = project.get("tracks", [])
    guides = project.get("guides", [])

    # Map clip IDs to numeric kdenlive IDs (4, 5, 6, ...)
    clip_kid = {}
    clip_data_by_id = {}
    for i, clip in enumerate(bin_clips):
        clip_kid[clip["id"]] = str(_CLIP_KDENLIVE_ID_START + i)
        clip_data_by_id[clip["id"]] = clip

    max_dur = 0
    track_durs = {}
    for track in tracks:
        td = _compute_track_duration(track, fps_num, fps_den, set(clip_data_by_id))
        track_durs[track["id"]] = td
        max_dur = max(max_dur, td)
    if max_dur == 0:
        max_dur = seconds_to_frames(300, fps_num, fps_den)

    root = ET.Element("mlt")
    root.set("LC_NUMERIC", "C")
    root.set("version", "7.0.0")
    root.set("title", project.get("name", "untitled"))
    root.set("producer", "main_bin")

    ET.SubElement(root, "profile", {
        "description": profile.get("name", "custom"),
        "width": str(width),
        "height": str(height),
        "progressive": str(1 if progressive else 0),
        "sample_aspect_num": str(sar_num),
        "sample_aspect_den": str(sar_den),
        "display_aspect_num": str(dar_num),
        "display_aspect_den": str(dar_den),
        "frame_rate_num": str(fps_num),
        "frame_rate_den": str(fps_den),
        "colorspace": "709",
    })

    # Black track producer
    black = ET.SubElement(root, "producer", {"id": "producer0", "in": "0", "out": str(max_dur)})
    _add_prop(black, "resource", "black")
    _add_prop(black, "mlt_service", "color")
    _add_prop(black, "kdenlive:playlistid", "black_track")
    _add_prop(black, "set.test_audio", "0")

    # Sort tracks: audio first, video last so video appears on top in kdenlive
    audio_tracks = [t for t in tracks if t.get("type") == "audio"]
    video_tracks = [t for t in tracks if t.get("type") != "audio"]
    sorted_tracks = audio_tracks + video_tracks

    # Mapping: original track index in project["tracks"] -> sequence position
    orig_to_seq = {}
    for seq_idx, t in enumerate(sorted_tracks):
        orig_idx = tracks.index(t)
        orig_to_seq[orig_idx] = seq_idx

    # Per-track: chains, dual playlists, wrapping tractor
    chain_counter = 0
    filter_counter = 0
    transition_counter = 0
    track_tractor_ids = []

    for track in sorted_tracks:
        track_type = track.get("type", "video")
        is_audio = track_type == "audio"
        tractor_id = f"tractor{track['id']}"

        # Chain per unique clip in this track
        track_clip_chains = {}
        for clip_entry in track.get("clips", []):
            clip_id = clip_entry.get("clip_id", "")
            if clip_id in track_clip_chains:
                continue
            chain_id = f"chain{chain_counter}"
            chain_counter += 1
            clip_data = clip_data_by_id.get(clip_id)
            if not clip_data:
                track_clip_chains[clip_id] = clip_id
                continue
            dur = seconds_to_frames(clip_data.get("duration", 0), fps_num, fps_den)
            chain = ET.SubElement(root, "chain", {"id": chain_id, "in": "0", "out": str(max(dur - 1, 0))})
            _add_prop(chain, "length", str(dur))
            _add_prop(chain, "eof", "pause")
            _add_prop(chain, "resource", clip_data.get("source", ""))
            _set_producer_props(chain, clip_data.get("type", "video"))
            _add_prop(chain, "kdenlive:folderid", "-1")
            _add_prop(chain, "kdenlive:id", clip_kid.get(clip_id, clip_id))
            _add_prop(chain, "mute_on_pause", "0")
            _add_prop(chain, "kdenlive:clip_type", str(_clip_type_num(clip_data.get("type", "video"))))
            if is_audio:
                _add_prop(chain, "set.test_audio", "0")
                _add_prop(chain, "set.test_image", "1")
            else:
                _add_prop(chain, "set.test_audio", "1")
                _add_prop(chain, "set.test_image", "0")
            track_clip_chains[clip_id] = chain_id

        # Playlist 1: clip entries
        pl1 = ET.SubElement(root, "playlist", {"id": f"playlist{track['id'] * 2}"})
        if is_audio:
            _add_prop(pl1, "kdenlive:audio_track", "1")

        prev_end = 0.0
        for clip_entry in track.get("clips", []):
            cid = clip_entry.get("clip_id", "")
            if cid not in clip_data_by_id:
                continue
            pos = clip_entry.get("position", 0.0)
            gap = pos - prev_end
            if gap > 0.001:
                ET.SubElement(pl1, "blank", {"length": str(seconds_to_frames(gap, fps_num, fps_den))})

            in_f = seconds_to_frames(clip_entry.get("in", 0), fps_num, fps_den)
            out_f = seconds_to_frames(clip_entry.get("out", 0), fps_num, fps_den)
            ref = track_clip_chains.get(cid, cid)
            entry = ET.SubElement(pl1, "entry", {"producer": ref, "in": str(in_f), "out": str(max(out_f - 1, 0))})

            for filt in clip_entry.get("filters", []):
                f_el = ET.SubElement(entry, "filter", {"id": f"filter{filter_counter}"})
                filter_counter += 1
                _add_prop(f_el, "mlt_service", filt.get("mlt_service", ""))
                kdenlive_id = FILTER_REGISTRY.get(filt.get("name", ""), {}).get("kdenlive_name", filt.get("mlt_service", ""))
                _add_prop(f_el, "kdenlive_id", kdenlive_id)
                for pk, pv in filt.get("params", {}).items():
                    _add_prop(f_el, pk, str(pv))

            _add_prop(entry, "kdenlive:id", clip_kid.get(cid, cid))
            prev_end = pos + clip_entry.get("out", 0) - clip_entry.get("in", 0)

        # Playlist 2: empty (dual playlist for mixes)
        pl2 = ET.SubElement(root, "playlist", {"id": f"playlist{track['id'] * 2 + 1}"})
        if is_audio:
            _add_prop(pl2, "kdenlive:audio_track", "1")

        # Wrapping tractor
        track_dur = track_durs[track["id"]]
        tractor = ET.SubElement(root, "tractor", {"id": tractor_id, "in": "0", "out": str(track_dur)})
        if is_audio:
            _add_prop(tractor, "kdenlive:audio_track", "1")
        if track.get("name"):
            _add_prop(tractor, "kdenlive:track_name", track["name"])

        if track.get("hide"):
            hide = "both"
        elif is_audio and track.get("mute"):
            hide = "both"
        elif is_audio:
            hide = "video"
        else:
            hide = "audio"
        ET.SubElement(tractor, "track", {"hide": hide, "producer": pl1.get("id")})
        ET.SubElement(tractor, "track", {"hide": hide, "producer": pl2.get("id")})

        if is_audio:
            filter_counter = _add_disabled_filter(tractor, "volume", filter_counter)
            filter_counter = _add_disabled_filter(tractor, "panner", filter_counter)
            filter_counter = _add_disabled_filter(tractor, "audiolevel", filter_counter)

        track_tractor_ids.append(tractor_id)

    # Sequence tractor (UUID id)
    doc_uuid = f"{{{uuid.uuid4()}}}"
    sequence_uuid = doc_uuid
    video_count = len(video_tracks)
    audio_count = len(audio_tracks)

    seq = ET.SubElement(root, "tractor", {"id": sequence_uuid, "in": "0", "out": str(max_dur)})
    _add_prop(seq, "kdenlive:uuid", sequence_uuid)
    _add_prop(seq, "kdenlive:clipname", "Sequence 1")
    _add_prop(seq, "kdenlive:sequenceproperties.hasAudio", "1" if audio_count > 0 else "0")
    _add_prop(seq, "kdenlive:sequenceproperties.hasVideo", "1" if video_count > 0 else "0")
    _add_prop(seq, "kdenlive:sequenceproperties.activeTrack", str(len(tracks) - 1 if tracks else 0))
    _add_prop(seq, "kdenlive:sequenceproperties.tracksCount", str(len(tracks)))
    _add_prop(seq, "kdenlive:sequenceproperties.documentuuid", sequence_uuid)
    dur_tc = seconds_to_timecode(frames_to_seconds(max_dur + 1, fps_num, fps_den)) if max_dur > 0 else "00:00:00.000"
    _add_prop(seq, "kdenlive:duration", dur_tc)
    _add_prop(seq, "kdenlive:maxduration", str(max_dur + 1))
    _add_prop(seq, "kdenlive:producer_type", "17")
    _add_prop(seq, "kdenlive:id", _SEQUENCE_KDENLIVE_ID)
    _add_prop(seq, "kdenlive:clip_type", "0")
    _add_prop(seq, "kdenlive:file_size", "0")
    _add_prop(seq, "kdenlive:folderid", _SEQUENCE_FOLDER_ID)
    _add_prop(seq, "kdenlive:sequenceproperties.videoTarget", str(len(sorted_tracks) - 1 if video_tracks else -1))
    _add_prop(seq, "kdenlive:sequenceproperties.audioTarget", str(audio_count - 1 if audio_count > 0 else -1))
    _add_prop(seq, "kdenlive:sequenceproperties.tracks", str(len(tracks)))
    _add_prop(seq, "kdenlive:sequenceproperties.zoom", "8")
    _add_prop(seq, "kdenlive:sequenceproperties.zonein", "0")
    _add_prop(seq, "kdenlive:sequenceproperties.zoneout", str(max_dur))
    _add_prop(seq, "kdenlive:sequenceproperties.groups", "[]")

    guides_data = [
        {"pos": seconds_to_frames(g["position"], fps_num, fps_den),
         "comment": g.get("label", ""),
         "type": g.get("type", "default")}
        for g in guides
    ]
    _add_prop(seq, "kdenlive:sequenceproperties.guides", json.dumps(guides_data))

    # Tracks: black track first, then per-track tractors
    ET.SubElement(seq, "track", {"producer": "producer0"})
    for tid in track_tractor_ids:
        ET.SubElement(seq, "track", {"producer": tid})

    # Internal mix transitions for audio tracks
    for i, track in enumerate(sorted_tracks):
        if track.get("type") == "audio":
            t = ET.SubElement(seq, "transition", {"id": f"transition{transition_counter}"})
            transition_counter += 1
            _add_prop(t, "a_track", "0")
            _add_prop(t, "b_track", str(i + 1))
            _add_prop(t, "mlt_service", "mix")
            _add_prop(t, "kdenlive_id", "mix")
            _add_prop(t, "internal_added", "237")
            _add_prop(t, "always_active", "1")
            _add_prop(t, "accepts_blanks", "1")
            _add_prop(t, "sum", "1")

    # Internal qtblend transitions for video tracks
    for i, track in enumerate(sorted_tracks):
        if track.get("type") != "audio":
            t = ET.SubElement(seq, "transition", {"id": f"transition{transition_counter}"})
            transition_counter += 1
            _add_prop(t, "a_track", "0")
            _add_prop(t, "b_track", str(i + 1))
            _add_prop(t, "mlt_service", "qtblend")
            _add_prop(t, "kdenlive_id", "qtblend")
            _add_prop(t, "internal_added", "237")
            _add_prop(t, "always_active", "1")
            _add_prop(t, "compositing", "0")
            _add_prop(t, "distort", "0")
            _add_prop(t, "rotate_center", "0")

    # User transitions
    for td in project.get("transitions", []):
        pos_f = seconds_to_frames(td.get("position", 0), fps_num, fps_den)
        dur_f = seconds_to_frames(td.get("duration", 1), fps_num, fps_den)
        a_orig = _track_index(tracks, td["track_a"])
        b_orig = _track_index(tracks, td["track_b"])
        a_idx = orig_to_seq.get(a_orig, a_orig) + 1
        b_idx = orig_to_seq.get(b_orig, b_orig) + 1
        trans = ET.SubElement(seq, "transition", {
            "id": f"transition{transition_counter}",
            "mlt_service": td.get("mlt_service", ""),
            "in": str(pos_f),
            "out": str(pos_f + dur_f),
            "a_track": str(a_idx),
            "b_track": str(b_idx),
        })
        transition_counter += 1
        _add_prop(trans, "kdenlive_id", td.get("type", ""))
        for pk, pv in td.get("params", {}).items():
            if pk == "duration":
                continue
            _add_prop(trans, pk, str(pv))

    # Sequence-level volume and panner filters
    filter_counter = _add_disabled_filter(seq, "volume", filter_counter)
    filter_counter = _add_disabled_filter(seq, "panner", filter_counter)

    # Bin clip chains (sequential numbering continues)
    bin_chain_ids = {}
    for clip in bin_clips:
        bin_chain_id = f"chain{chain_counter}"
        chain_counter += 1
        bin_chain_ids[clip["id"]] = bin_chain_id
        dur = seconds_to_frames(clip.get("duration", 0), fps_num, fps_den)
        chain = ET.SubElement(root, "chain", {"id": bin_chain_id, "in": "0", "out": str(max(dur - 1, 0))})
        _add_prop(chain, "length", str(dur))
        _add_prop(chain, "eof", "pause")
        _add_prop(chain, "resource", clip.get("source", ""))
        _set_producer_props(chain, clip.get("type", "video"))
        _add_prop(chain, "kdenlive:folderid", "-1")
        _add_prop(chain, "kdenlive:id", clip_kid[clip["id"]])
        _add_prop(chain, "mute_on_pause", "0")
        _add_prop(chain, "kdenlive:clip_type", str(_clip_type_num(clip.get("type", "video"))))
        if clip.get("name"):
            _add_prop(chain, "kdenlive:clipname", clip["name"])

    # Main bin playlist
    main_bin = ET.SubElement(root, "playlist", {"id": "main_bin"})
    _add_prop(main_bin, "kdenlive:folder.-1.2", "Sequences")
    _add_prop(main_bin, "kdenlive:sequenceFolder", _SEQUENCE_FOLDER_ID)
    _add_prop(main_bin, "kdenlive:docproperties.version", "1.1")
    _add_prop(main_bin, "kdenlive:docproperties.uuid", doc_uuid)
    _add_prop(main_bin, "kdenlive:docproperties.opensequences", sequence_uuid)
    _add_prop(main_bin, "kdenlive:docproperties.activetimeline", sequence_uuid)
    _add_prop(main_bin, "xml_retain", "1")

    ET.SubElement(main_bin, "entry", {"in": "0", "out": "0", "producer": sequence_uuid})
    for clip in bin_clips:
        dur = seconds_to_frames(clip.get("duration", 0), fps_num, fps_den)
        ET.SubElement(main_bin, "entry", {"in": "0", "out": str(max(dur - 1, 0)), "producer": bin_chain_ids[clip["id"]]})

    # Project tractor (last element — what melt plays)
    proj_tr = ET.SubElement(root, "tractor", {"id": "tractor_project", "in": "0", "out": str(max_dur)})
    _add_prop(proj_tr, "kdenlive:projectTractor", "1")
    ET.SubElement(proj_tr, "track", {"producer": sequence_uuid, "in": "0", "out": str(max_dur)})

    ET.indent(root, space="  ")
    return '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(root, encoding="unicode")
