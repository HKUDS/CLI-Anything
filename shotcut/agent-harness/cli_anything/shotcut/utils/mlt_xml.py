"""MLT XML parsing and generation utilities.

This module handles all low-level MLT XML manipulation using
xml.etree.ElementTree from the Python standard library.
"""

import copy
import uuid
import xml.etree.ElementTree as ET
from typing import Optional

# Global parent mapping because ET.Element has no getparent().
# Safe for single-session architecture: only one Session/MLT tree exists per
# process. See Session class docstring in session.py for details.
_parent_map: dict[int, Optional[ET.Element]] = {}


def _clear_parent_map() -> None:
    _parent_map.clear()


def _set_parent(child: ET.Element, parent: Optional[ET.Element]) -> None:
    _parent_map[id(child)] = parent


def _remove_parent(child: ET.Element) -> None:
    _parent_map.pop(id(child), None)


def _register_tree(root: ET.Element, parent: Optional[ET.Element] = None) -> None:
    _set_parent(root, parent)
    for child in root:
        _register_tree(child, root)


def _unregister_tree(root: ET.Element) -> None:
    _parent_map.pop(id(root), None)
    for child in root:
        _unregister_tree(child)


def get_parent(element: ET.Element) -> Optional[ET.Element]:
    return _parent_map.get(id(element))


def new_id(prefix: str = "producer") -> str:
    """Generate a unique MLT element ID."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def parse_mlt(filepath: str) -> ET.Element:
    """Parse an MLT XML file and return the root element."""
    _clear_parent_map()
    tree = ET.parse(filepath)
    root = tree.getroot()
    _register_tree(root)
    return root


def write_mlt(root: ET.Element, filepath: str) -> None:
    """Write an MLT XML tree to a file.

    Normalize top-level media ordering first so playlists never
    forward-reference chain/producer nodes declared later in the XML.
    """
    pretty = copy.deepcopy(root)
    normalize_top_level_order(pretty)
    ET.indent(pretty, space="  ")
    tree = ET.ElementTree(pretty)
    tree.write(filepath, xml_declaration=True, encoding="utf-8")


def mlt_to_string(root: ET.Element) -> str:
    """Serialize an MLT XML tree to a string."""
    pretty = copy.deepcopy(root)
    ET.indent(pretty, space="  ")
    return ET.tostring(pretty, xml_declaration=True, encoding="utf-8").decode("utf-8")


def get_property(element: ET.Element, name: str,
                 default: Optional[str] = None) -> Optional[str]:
    """Get a property value from an MLT element."""
    prop = element.find(f"property[@name='{name}']")
    if prop is not None and prop.text is not None:
        return prop.text
    return default


def set_property(element: ET.Element, name: str, value: str) -> None:
    """Set a property on an MLT element, creating it if needed."""
    prop = element.find(f"property[@name='{name}']")
    if prop is not None:
        prop.text = str(value)
        return
    prop = ET.SubElement(element, "property")
    prop.set("name", name)
    prop.text = str(value)
    _set_parent(prop, element)


def remove_property(element: ET.Element, name: str) -> bool:
    """Remove a property from an MLT element. Returns True if found."""
    prop = element.find(f"property[@name='{name}']")
    if prop is not None:
        element.remove(prop)
        _remove_parent(prop)
        return True
    return False


def find_element_by_id(root: ET.Element, element_id: str) -> Optional[ET.Element]:
    return root.find(f".//*[@id='{element_id}']")


def get_all_producers(root: ET.Element) -> list[ET.Element]:
    """Get all producer and chain elements from the MLT document."""
    return root.findall(".//producer") + root.findall(".//chain")


def get_all_playlists(root: ET.Element) -> list[ET.Element]:
    """Get all playlist elements."""
    return root.findall(".//playlist")


def get_all_tractors(root: ET.Element) -> list[ET.Element]:
    """Get all tractor elements."""
    return root.findall(".//tractor")


def get_all_filters(root: ET.Element) -> list[ET.Element]:
    """Get all filter elements."""
    return root.findall(".//filter")


def get_main_tractor(root: ET.Element) -> Optional[ET.Element]:
    """Find the main timeline tractor."""
    main_id = root.get("producer")
    if main_id:
        elem = find_element_by_id(root, main_id)
        if elem is not None and elem.tag == "tractor":
            return elem
    # Fallback: last tractor in the document
    tractors = get_all_tractors(root)
    return tractors[-1] if tractors else None


def get_tractor_tracks(tractor: ET.Element) -> list[ET.Element]:
    """Get the track elements from a tractor."""
    tracks = tractor.findall("track")
    if tracks:
        return tracks
    multitrack = tractor.find("multitrack")
    if multitrack is None:
        return []
    return multitrack.findall("track")


def _find_insert_index_for_bin_chain(root: ET.Element) -> int:
    """Find insertion index for a bin chain (before main_bin)."""
    for i, child in enumerate(root):
        if child.tag == "playlist" and child.get("id") == "main_bin":
            return i
    return 1  # After profile


def find_insert_index_for_timeline_chain(root: ET.Element) -> int:
    """Find insertion index for a timeline chain (after background, before tracks)."""
    found_bg = False
    for i, child in enumerate(root):
        if child.tag == "playlist" and child.get("id") == "background":
            found_bg = True
            continue
        if found_bg and child.tag == "playlist":
            return i
    # Fallback: before first tractor
    for i, child in enumerate(root):
        if child.tag == "tractor":
            return i
    return len(root)


def _find_insert_index_for_playlist(root: ET.Element) -> int:
    """Find the insertion index for a new track playlist.

    Playlists should be inserted before the main tractor (last tractor),
    skipping any sub-tractor transitions that precede existing playlists.
    """
    # Find the main tractor: the one with the "shotcut" property
    for i, child in enumerate(root):
        if child.tag == "tractor" and get_property(child, "shotcut"):
            return i
    return len(root)


def create_blank_project(profile: dict) -> ET.Element:
    """Create a minimal blank MLT project."""
    _clear_parent_map()
    root = ET.Element("mlt")
    root.set("LC_NUMERIC", "C")
    root.set("version", "7.36.1")
    root.set("title", "Shotcut version 26.2.26")
    root.set("producer", "main_bin")

    # Profile
    prof = ET.SubElement(root, "profile")
    prof.set("description", f"{profile.get('width', 1920)}x{profile.get('height', 1080)} "
             f"{profile.get('frame_rate_num', 30000)}/{profile.get('frame_rate_den', 1001)}fps")
    for key in ["width", "height", "frame_rate_num", "frame_rate_den",
                "sample_aspect_num", "sample_aspect_den",
                "display_aspect_num", "display_aspect_den",
                "progressive", "colorspace"]:
        if key in profile:
            prof.set(key, str(profile[key]))

    # Main bin playlist (holds source clips for reference)
    main_bin = ET.SubElement(root, "playlist")
    main_bin.set("id", "main_bin")
    set_property(main_bin, "xml_retain", "1")
    _set_parent(main_bin, root)

    # Background producer (black)
    bg = ET.SubElement(root, "producer")
    bg.set("id", "black")
    bg.set("in", "00:00:00.000")
    bg.set("out", "04:00:00.000")
    set_property(bg, "length", "04:00:00.040")
    set_property(bg, "eof", "pause")
    set_property(bg, "resource", "0")
    set_property(bg, "aspect_ratio", "1")
    set_property(bg, "mlt_service", "color")
    set_property(bg, "mlt_image_format", "rgba")
    set_property(bg, "set.test_audio", "0")
    _set_parent(bg, root)

    # Background playlist
    bg_playlist = ET.SubElement(root, "playlist")
    bg_playlist.set("id", "background")
    entry = ET.SubElement(bg_playlist, "entry")
    entry.set("producer", "black")
    entry.set("in", "00:00:00.000")
    entry.set("out", "04:00:00.000")
    _set_parent(entry, bg_playlist)
    _set_parent(bg_playlist, root)

    # Main tractor (timeline)
    tractor = ET.SubElement(root, "tractor")
    tractor.set("id", "tractor0")
    tractor.set("title", "Shotcut version 26.2.26")
    tractor.set("in", "00:00:00.000")
    tractor.set("out", "00:00:00.000")
    set_property(tractor, "shotcut", "1")
    set_property(tractor, "shotcut:projectAudioChannels", "2")
    set_property(tractor, "shotcut:projectFolder", "0")
    set_property(tractor, "shotcut:processingMode", "Native8Cpu")
    set_property(tractor, "shotcut:skipConvert", "0")
    _set_parent(tractor, root)

    bg_track = ET.SubElement(tractor, "track")
    bg_track.set("producer", "background")
    _set_parent(bg_track, tractor)

    return root


def _first_playlist_or_tractor_index(root: ET.Element) -> int:
    """Return the first top-level playlist/tractor index, or len(root)."""
    for idx, child in enumerate(list(root)):
        if child.tag in ("playlist", "tractor"):
            return idx
    return len(root)


def insert_before_playlists_and_tractors(root: ET.Element, element: ET.Element) -> None:
    """Insert a top-level declaration before any playlists or tractors."""
    root.insert(_first_playlist_or_tractor_index(root), element)
    _set_parent(element, root)


def normalize_top_level_order(root: ET.Element) -> None:
    """Move late top-level chains/producers ahead of playlists and tractors."""
    late_media: list[ET.Element] = []
    seen_playlist_or_tractor = False
    for child in list(root):
        if child.tag in ("playlist", "tractor"):
            seen_playlist_or_tractor = True
        elif child.tag in ("producer", "chain") and seen_playlist_or_tractor:
            late_media.append(child)

    for element in late_media:
        root.remove(element)

    insert_idx = _first_playlist_or_tractor_index(root)
    for offset, element in enumerate(late_media):
        root.insert(insert_idx + offset, element)


def _add_system_transitions(tractor: ET.Element, track_index: int,
                            root: ET.Element = None,
                            track_type: str = "video") -> None:
    """Add standard mix and qtblend transitions for a track.

    Audio tracks only get a mix transition. Video tracks get both mix
    and qtblend, matching Shotcut's actual output.
    """
    # Audio mix transition (always added)
    mix_trans = ET.SubElement(tractor, "transition")
    mix_trans.set("id", new_id("transition"))
    set_property(mix_trans, "a_track", "0")
    set_property(mix_trans, "b_track", str(track_index))
    set_property(mix_trans, "mlt_service", "mix")
    set_property(mix_trans, "always_active", "1")
    set_property(mix_trans, "sum", "1")
    _set_parent(mix_trans, tractor)

    if track_type == "audio":
        return

    # Video composite transition
    prev_video_track = 0
    is_first_video = True
    if root is not None:
        all_tracks = get_tractor_tracks(tractor)
        for i in range(1, track_index):
            if i < len(all_tracks):
                pl = find_element_by_id(root, all_tracks[i].get("producer", ""))
                if pl is not None and get_property(pl, "shotcut:video"):
                    prev_video_track = i
                    is_first_video = False

    comp_trans = ET.SubElement(tractor, "transition")
    comp_trans.set("id", new_id("transition"))
    set_property(comp_trans, "a_track", str(prev_video_track))
    set_property(comp_trans, "b_track", str(track_index))
    set_property(comp_trans, "compositing", "0")
    set_property(comp_trans, "distort", "0")
    set_property(comp_trans, "rotate_center", "0")
    set_property(comp_trans, "mlt_service", "qtblend")
    set_property(comp_trans, "threads", "0")
    set_property(comp_trans, "disable", "1" if is_first_video else "0")
    _set_parent(comp_trans, tractor)


def add_track_to_tractor(root: ET.Element, tractor: ET.Element,
                         track_type: str = "video",
                         name: str = "") -> tuple[str, int]:
    """Add a new track (playlist) to a tractor.

    Returns:
        Tuple of (playlist_id, track_index)
    """
    playlist_id = new_id("playlist")

    # Create the playlist element
    playlist = ET.Element("playlist")
    playlist.set("id", playlist_id)
    if name:
        set_property(playlist, "shotcut:name", name)
    if track_type == "video":
        set_property(playlist, "shotcut:video", "1")
    else:
        set_property(playlist, "shotcut:audio", "1")
    _set_parent(playlist, None)  # Will be set when inserted

    # Insert playlist before the first tractor in the document
    insert_idx = _find_insert_index_for_playlist(root)
    root.insert(insert_idx, playlist)
    _set_parent(playlist, root)

    # Add track reference — preserve multitrack if already present
    multitrack = tractor.find("multitrack")
    if multitrack is not None:
        existing_tracks = multitrack.findall("track")
        track_elem = ET.SubElement(multitrack, "track")
        _set_parent(track_elem, multitrack)
    else:
        existing_tracks = tractor.findall("track")
        track_elem = ET.SubElement(tractor, "track")
        _set_parent(track_elem, tractor)

    track_elem.set("producer", playlist_id)
    if track_type == "audio":
        track_elem.set("hide", "video")

    track_index = len(existing_tracks)

    # Add standard transitions for compositing
    if track_index > 0:
        _add_system_transitions(tractor, track_index, root, track_type)

    return playlist_id, track_index


def _create_media_element(tag: str, elem_id: str, resource: str,
                          in_point: str, out_point: Optional[str],
                          caption: Optional[str], service: str,
                          extra_props: Optional[dict] = None,
                          length: Optional[str] = None) -> ET.Element:
    """Create a chain or producer element for media."""
    elem = ET.Element(tag)
    elem.set("id", elem_id)
    elem.set("in", in_point)
    if out_point:
        elem.set("out", out_point)

    set_property(elem, "length", length or out_point or "")
    set_property(elem, "eof", "pause")
    set_property(elem, "resource", resource)
    set_property(elem, "mlt_service", service)
    set_property(elem, "seekable", "1")
    set_property(elem, "shotcut:skipConvert", "0")
    set_property(elem, "ignore_points", "0")

    if caption:
        set_property(elem, "shotcut:caption", caption)
    else:
        import os
        set_property(elem, "shotcut:caption", os.path.basename(resource))

    if extra_props:
        for key, val in extra_props.items():
            set_property(elem, key, str(val))

    return elem


def create_chain(root: ET.Element, resource: str,
                 in_point: str = "00:00:00.000",
                 out_point: Optional[str] = None,
                 caption: Optional[str] = None,
                 service: str = "avformat-novalidate",
                 extra_props: Optional[dict] = None,
                 insert_idx: Optional[int] = None,
                 length: Optional[str] = None,
                 id_override: Optional[str] = None) -> ET.Element:
    chain_id = id_override or new_id("chain")
    chain = _create_media_element(
        "chain", chain_id, resource, in_point, out_point, caption, service, extra_props,
        length=length,
    )

    if insert_idx is not None:
        root.insert(insert_idx, chain)
        _set_parent(chain, root)
    else:
        insert_before_playlists_and_tractors(root, chain)

    return chain


def create_producer(root: ET.Element, resource: str,
                    in_point: str = "00:00:00.000",
                    out_point: Optional[str] = None,
                    caption: Optional[str] = None,
                    service: str = "avformat") -> ET.Element:
    """Create a new <producer> element (for internal services like color)."""
    prod_id = new_id("producer")
    producer = _create_media_element(
        "producer", prod_id, resource, in_point, out_point, caption, service
    )

    insert_before_playlists_and_tractors(root, producer)

    return producer


def add_chain_to_bin(root: ET.Element, chain: ET.Element) -> ET.Element:
    """Add an entry for a chain to the main_bin playlist.

    Args:
        root: The MLT document root
        chain: The chain element to reference

    Returns:
        The new entry element
    """
    main_bin = find_element_by_id(root, "main_bin")
    if main_bin is None:
        raise RuntimeError("main_bin playlist not found")

    entry = ET.SubElement(main_bin, "entry")
    entry.set("producer", chain.get("id"))
    entry.set("in", chain.get("in", "00:00:00.000"))
    entry.set("out", chain.get("out", "00:00:00.000"))
    _set_parent(entry, main_bin)

    return entry


def add_entry_to_playlist(playlist: ET.Element, producer_id: str,
                          in_point: Optional[str] = None,
                          out_point: Optional[str] = None,
                          position: Optional[int] = None,
                          insert_before: Optional[int] = None) -> ET.Element:
    """Add a clip entry to a playlist (track).

    Args:
        insert_before: If provided, insert before the playlist child at this
                       raw index. Overrides position.
    """
    entry = ET.Element("entry")
    entry.set("producer", producer_id)
    if in_point:
        entry.set("in", in_point)
    if out_point:
        entry.set("out", out_point)

    if insert_before is not None:
        playlist.insert(insert_before, entry)
    elif position is not None:
        children = list(playlist)
        non_prop = [c for c in children if c.tag != "property"]
        if position < len(non_prop):
            playlist.insert(list(playlist).index(non_prop[position]), entry)
        else:
            playlist.append(entry)
    else:
        playlist.append(entry)

    _set_parent(entry, playlist)
    return entry


def add_blank_to_playlist(playlist: ET.Element, length: str) -> ET.Element:
    """Add a blank (gap) to a playlist."""
    blank = ET.SubElement(playlist, "blank")
    blank.set("length", length)
    _set_parent(blank, playlist)
    return blank


def add_filter_to_element(element: ET.Element, service: str,
                          shotcut_filter: Optional[str] = None,
                          properties: Optional[dict] = None) -> ET.Element:
    """Add a filter to any MLT element (producer, chain, playlist, tractor).

    Args:
        element: The element to attach the filter to
        service: MLT service name (e.g., "brightness", "volume")
        shotcut_filter: Shotcut UI identifier (e.g., "brightness", "volume")
        properties: Dict of property name → value

    Returns:
        The new filter element
    """
    filt = ET.SubElement(element, "filter")
    filt.set("id", new_id("filter"))
    set_property(filt, "mlt_service", service)

    if shotcut_filter:
        set_property(filt, "shotcut:filter", shotcut_filter)

    if properties:
        for key, val in properties.items():
            set_property(filt, key, str(val))

    _set_parent(filt, element)
    return filt


def remove_element(element: ET.Element) -> bool:
    """Remove an element from its parent. Returns True if successful."""
    parent = get_parent(element)
    if parent is not None:
        parent.remove(element)
        _remove_parent(element)
        return True
    return False


def get_playlist_entries(playlist: ET.Element) -> list[dict]:
    """Get all entries and blanks from a playlist as structured data."""
    results = []
    idx = 0
    for child in playlist:
        if child.tag == "entry":
            results.append({
                "type": "entry",
                "producer": child.get("producer"),
                "in": child.get("in"),
                "out": child.get("out"),
                "index": idx,
            })
            idx += 1
        elif child.tag == "blank":
            results.append({
                "type": "blank",
                "length": child.get("length"),
                "index": idx,
            })
            idx += 1
    return results


def deep_copy_element(element: ET.Element) -> ET.Element:
    """Create a deep copy of an XML element."""
    return copy.deepcopy(element)


def set_tractor_out(root: ET.Element, out_timecode: str) -> None:
    """Set the main tractor's out point."""
    tractor = get_main_tractor(root)
    if tractor is not None:
        tractor.set("out", out_timecode)
