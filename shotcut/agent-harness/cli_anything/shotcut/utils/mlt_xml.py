"""MLT XML parsing and generation utilities.

This module handles all low-level MLT XML manipulation. It understands the MLT
XML schema and provides helper functions for common operations.
"""

import copy
import uuid
from lxml import etree
from typing import Optional


def new_id(prefix: str = "producer") -> str:
    """Generate a unique MLT element ID."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def parse_mlt(filepath: str) -> etree._Element:
    """Parse an MLT XML file and return the root element."""
    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(filepath, parser)
    return tree.getroot()


def write_mlt(root: etree._Element, filepath: str) -> None:
    """Write an MLT XML tree to a file."""
    tree = etree.ElementTree(root)
    tree.write(filepath, xml_declaration=True, encoding="utf-8",
               pretty_print=True)


def mlt_to_string(root: etree._Element) -> str:
    """Serialize an MLT XML tree to a string."""
    return etree.tostring(root, xml_declaration=True, encoding="utf-8",
                          pretty_print=True).decode("utf-8")


def get_property(element: etree._Element, name: str,
                 default: Optional[str] = None) -> Optional[str]:
    """Get a property value from an MLT element."""
    prop = element.find(f"property[@name='{name}']")
    if prop is not None and prop.text is not None:
        return prop.text
    return default


def set_property(element: etree._Element, name: str, value: str) -> None:
    """Set a property on an MLT element, creating it if needed."""
    prop = element.find(f"property[@name='{name}']")
    if prop is None:
        prop = etree.SubElement(element, "property")
        prop.set("name", name)
    prop.text = str(value)


def remove_property(element: etree._Element, name: str) -> bool:
    """Remove a property from an MLT element. Returns True if found."""
    prop = element.find(f"property[@name='{name}']")
    if prop is not None:
        element.remove(prop)
        return True
    return False


def find_element_by_id(root: etree._Element, element_id: str) -> Optional[etree._Element]:
    """Find any element by its id attribute."""
    result = root.xpath(f"//*[@id='{element_id}']")
    return result[0] if result else None


def get_all_producers(root: etree._Element) -> list[etree._Element]:
    """Get all producer elements from the MLT document."""
    return root.findall(".//producer")


def get_all_playlists(root: etree._Element) -> list[etree._Element]:
    """Get all playlist elements."""
    return root.findall(".//playlist")


def get_all_tractors(root: etree._Element) -> list[etree._Element]:
    """Get all tractor elements."""
    return root.findall(".//tractor")


def get_all_filters(root: etree._Element) -> list[etree._Element]:
    """Get all filter elements."""
    return root.findall(".//filter")


def get_main_tractor(root: etree._Element) -> Optional[etree._Element]:
    """Find the main timeline tractor.

    In Shotcut projects, this is typically the last tractor or the one
    referenced by the root's 'producer' attribute.
    """
    main_id = root.get("producer")
    if main_id:
        elem = find_element_by_id(root, main_id)
        if elem is not None and elem.tag == "tractor":
            return elem
    # Fallback: last tractor in the document
    tractors = get_all_tractors(root)
    return tractors[-1] if tractors else None


def get_tractor_tracks(tractor: etree._Element) -> list[etree._Element]:
    """Get the track elements from a tractor's multitrack."""
    multitrack = tractor.find("multitrack")
    if multitrack is None:
        return []
    return multitrack.findall("track")


def create_blank_project(profile: dict) -> etree._Element:
    """Create a minimal blank MLT project.

    Args:
        profile: dict with keys like width, height, frame_rate_num,
                 frame_rate_den, sample_aspect_num, sample_aspect_den,
                 display_aspect_num, display_aspect_den, colorspace
    """
    root = etree.Element("mlt")
    root.set("LC_NUMERIC", "C")
    root.set("version", "7.0.0")
    root.set("title", "Shotcut")
    root.set("producer", "main_bin")

    # Profile
    prof = etree.SubElement(root, "profile")
    prof.set("description", f"{profile.get('width', 1920)}x{profile.get('height', 1080)} "
             f"{profile.get('frame_rate_num', 30000)}/{profile.get('frame_rate_den', 1001)}fps")
    for key in ["width", "height", "frame_rate_num", "frame_rate_den",
                "sample_aspect_num", "sample_aspect_den",
                "display_aspect_num", "display_aspect_den",
                "progressive", "colorspace"]:
        if key in profile:
            prof.set(key, str(profile[key]))

    # Main bin playlist (holds source clips for reference)
    main_bin = etree.SubElement(root, "playlist")
    main_bin.set("id", "main_bin")
    set_property(main_bin, "xml_retain", "1")

    # Background producer (black)
    bg = etree.SubElement(root, "producer")
    bg.set("id", "black")
    bg.set("in", "00:00:00.000")
    bg.set("out", "04:00:00.000")
    set_property(bg, "resource", "0")
    set_property(bg, "mlt_service", "color")
    set_property(bg, "mlt_image_format", "rgba")

    # Background playlist
    bg_playlist = etree.SubElement(root, "playlist")
    bg_playlist.set("id", "background")
    entry = etree.SubElement(bg_playlist, "entry")
    entry.set("producer", "black")
    entry.set("in", "00:00:00.000")
    entry.set("out", "04:00:00.000")

    # Main tractor (timeline)
    tractor = etree.SubElement(root, "tractor")
    tractor.set("id", "tractor0")
    tractor.set("in", "00:00:00.000")
    tractor.set("out", "00:00:00.000")
    set_property(tractor, "shotcut", "1")
    set_property(tractor, "shotcut:projectAudioChannels", "2")

    multitrack = etree.SubElement(tractor, "multitrack")
    bg_track = etree.SubElement(multitrack, "track")
    bg_track.set("producer", "background")

    return root


def add_track_to_tractor(root: etree._Element, tractor: etree._Element,
                         track_type: str = "video",
                         name: str = "") -> tuple[str, str]:
    """Add a new track (playlist) to a tractor.

    Args:
        root: The MLT document root
        tractor: The tractor element to add the track to
        track_type: "video" or "audio"
        name: Optional track name

    Returns:
        Tuple of (playlist_id, track_index_in_multitrack)
    """
    playlist_id = new_id("playlist")

    # Create the playlist element before the tractor
    playlist = etree.Element("playlist")
    playlist.set("id", playlist_id)
    if name:
        set_property(playlist, "shotcut:name", name)
    if track_type == "video":
        set_property(playlist, "shotcut:video", "1")
    else:
        set_property(playlist, "shotcut:audio", "1")

    # Insert playlist before the tractor in the document
    tractor_parent = tractor.getparent()
    if tractor_parent is None:
        tractor_parent = root
    tractor_idx = list(tractor_parent).index(tractor)
    tractor_parent.insert(tractor_idx, playlist)

    # Add track reference in multitrack
    multitrack = tractor.find("multitrack")
    if multitrack is None:
        multitrack = etree.SubElement(tractor, "multitrack")

    track_elem = etree.SubElement(multitrack, "track")
    track_elem.set("producer", playlist_id)
    if track_type == "audio":
        track_elem.set("hide", "video")
    elif track_type == "video":
        track_elem.set("hide", "")

    track_index = len(multitrack.findall("track")) - 1

    # Add standard transitions for compositing
    if track_type == "video" and track_index > 0:
        # Audio mix transition
        mix_trans = etree.SubElement(tractor, "transition")
        mix_trans.set("id", new_id("transition"))
        set_property(mix_trans, "a_track", "0")
        set_property(mix_trans, "b_track", str(track_index))
        set_property(mix_trans, "mlt_service", "mix")
        set_property(mix_trans, "always_active", "1")
        set_property(mix_trans, "sum", "1")

        # Video composite transition
        comp_trans = etree.SubElement(tractor, "transition")
        comp_trans.set("id", new_id("transition"))
        set_property(comp_trans, "a_track", "0")
        set_property(comp_trans, "b_track", str(track_index))
        set_property(comp_trans, "mlt_service", "frei0r.cairoblend")
        set_property(comp_trans, "disable", "0")

    if track_type == "audio" and track_index > 0:
        mix_trans = etree.SubElement(tractor, "transition")
        mix_trans.set("id", new_id("transition"))
        set_property(mix_trans, "a_track", "0")
        set_property(mix_trans, "b_track", str(track_index))
        set_property(mix_trans, "mlt_service", "mix")
        set_property(mix_trans, "always_active", "1")
        set_property(mix_trans, "sum", "1")

    return playlist_id, track_index


def create_producer(root: etree._Element, resource: str,
                    in_point: str = "00:00:00.000",
                    out_point: Optional[str] = None,
                    caption: Optional[str] = None,
                    service: str = "avformat") -> etree._Element:
    """Create a new producer element for a media file.

    Args:
        root: The MLT document root (producer is appended here)
        resource: Path to the media file
        in_point: In timecode
        out_point: Out timecode (None = full duration)
        caption: Display name
        service: MLT service type (avformat, color, etc.)

    Returns:
        The new producer element
    """
    prod_id = new_id("producer")
    producer = etree.Element("producer")
    producer.set("id", prod_id)
    producer.set("in", in_point)
    if out_point:
        producer.set("out", out_point)

    set_property(producer, "resource", resource)
    set_property(producer, "mlt_service", service)

    if caption:
        set_property(producer, "shotcut:caption", caption)
    else:
        # Use filename as caption
        import os
        set_property(producer, "shotcut:caption", os.path.basename(resource))

    # Generate a UUID for clip tracking
    set_property(producer, "shotcut:uuid", str(uuid.uuid4()))

    # Insert before the first tractor
    tractors = root.findall("tractor")
    if tractors:
        tractor_idx = list(root).index(tractors[0])
        root.insert(tractor_idx, producer)
    else:
        root.append(producer)

    return producer


def add_entry_to_playlist(playlist: etree._Element, producer_id: str,
                          in_point: Optional[str] = None,
                          out_point: Optional[str] = None,
                          position: Optional[int] = None) -> etree._Element:
    """Add a clip entry to a playlist (track).

    Args:
        playlist: The playlist element
        producer_id: ID of the producer to reference
        in_point: In point (trim start), or None for producer's in
        out_point: Out point (trim end), or None for producer's out
        position: Insert position (index among entries/blanks), or None for append

    Returns:
        The new entry element
    """
    entry = etree.Element("entry")
    entry.set("producer", producer_id)
    if in_point:
        entry.set("in", in_point)
    if out_point:
        entry.set("out", out_point)

    if position is not None:
        children = list(playlist)
        # Skip property elements
        non_prop = [c for c in children if c.tag != "property"]
        if position < len(non_prop):
            playlist.insert(list(playlist).index(non_prop[position]), entry)
        else:
            playlist.append(entry)
    else:
        playlist.append(entry)

    return entry


def add_blank_to_playlist(playlist: etree._Element, length: str) -> etree._Element:
    """Add a blank (gap) to a playlist."""
    blank = etree.SubElement(playlist, "blank")
    blank.set("length", length)
    return blank


def add_filter_to_element(element: etree._Element, service: str,
                          properties: Optional[dict] = None) -> etree._Element:
    """Add a filter to any MLT element (producer, playlist, tractor).

    Args:
        element: The element to attach the filter to
        service: MLT service name (e.g., "brightness", "volume")
        properties: Dict of property name → value

    Returns:
        The new filter element
    """
    filt = etree.SubElement(element, "filter")
    filt.set("id", new_id("filter"))
    set_property(filt, "mlt_service", service)

    if properties:
        for key, val in properties.items():
            set_property(filt, key, str(val))

    return filt


def remove_element(element: etree._Element) -> bool:
    """Remove an element from its parent. Returns True if successful."""
    parent = element.getparent()
    if parent is not None:
        parent.remove(element)
        return True
    return False


def get_playlist_entries(playlist: etree._Element) -> list[dict]:
    """Get all entries and blanks from a playlist as structured data.

    Returns list of dicts with keys:
        - type: "entry" or "blank"
        - producer: producer ID (entries only)
        - in: in point (entries only)
        - out: out point (entries only)
        - length: blank duration (blanks only)
        - index: position in the playlist
    """
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


def deep_copy_element(element: etree._Element) -> etree._Element:
    """Create a deep copy of an XML element."""
    return copy.deepcopy(element)
