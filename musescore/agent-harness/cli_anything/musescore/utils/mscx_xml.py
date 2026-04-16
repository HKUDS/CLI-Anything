"""MSCX/MusicXML parsing utilities.

Handles reading and writing .mscz (ZIP containing .mscx XML) and
.mxl (ZIP containing MusicXML) files, plus XML inspection helpers.
"""

import os
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path


# ── Key Signature Mapping ─────────────────────────────────────────────

# Integer key signatures: -7 (Cb) to +7 (C#)
# Negative = flats, positive = sharps, 0 = C major / A minor
KEY_INT_TO_MAJOR = {
    -7: "Cb", -6: "Gb", -5: "Db", -4: "Ab", -3: "Eb", -2: "Bb", -1: "F",
    0: "C", 1: "G", 2: "D", 3: "A", 4: "E", 5: "B", 6: "F#", 7: "C#",
}

KEY_INT_TO_MINOR = {
    -7: "Ab", -6: "Eb", -5: "Bb", -4: "F", -3: "C", -2: "G", -1: "D",
    0: "A", 1: "E", 2: "B", 3: "F#", 4: "C#", 5: "G#", 6: "D#", 7: "A#",
}

# Reverse: name → integer (case-insensitive, supports "C major", "C", "Cm", "C minor")
_KEY_NAME_TO_INT: dict[str, int] = {}
for _i, _name in KEY_INT_TO_MAJOR.items():
    _KEY_NAME_TO_INT[_name.lower()] = _i
    _KEY_NAME_TO_INT[f"{_name.lower()} major"] = _i
    _KEY_NAME_TO_INT[f"{_name.lower()}maj"] = _i
for _i, _name in KEY_INT_TO_MINOR.items():
    _KEY_NAME_TO_INT[f"{_name.lower()} minor"] = _i
    _KEY_NAME_TO_INT[f"{_name.lower()}m"] = _i
    _KEY_NAME_TO_INT[f"{_name.lower()}min"] = _i


def key_name_to_int(name: str) -> int:
    """Convert a key name to its integer representation.

    Accepts: "C", "C major", "Db", "Db major", "A minor", "Am", etc.

    Raises:
        ValueError: If the key name is not recognized.
    """
    normalized = name.strip().lower()
    if normalized in _KEY_NAME_TO_INT:
        return _KEY_NAME_TO_INT[normalized]

    raise ValueError(
        f"Unrecognized key name: '{name}'. "
        f"Examples: C, Db major, F# minor, Bb, Am"
    )


def key_int_to_name(key_int: int, minor: bool = False) -> str:
    """Convert a key integer to its name."""
    table = KEY_INT_TO_MINOR if minor else KEY_INT_TO_MAJOR
    if key_int not in table:
        raise ValueError(f"Invalid key integer: {key_int}. Must be -7 to 7.")
    suffix = " minor" if minor else " major"
    return table[key_int] + suffix


# ── MSCZ (MuseScore ZIP) I/O ─────────────────────────────────────────

def read_mscz(path: str) -> dict:
    """Read a .mscz file (ZIP archive).

    Returns:
        Dict with keys:
        - "mscx": ElementTree of the .mscx XML
        - "mscx_filename": name of the .mscx file inside the ZIP
        - "style": content of score_style.mss (str or None)
        - "audio_settings": content of audiosettings.json (str or None)
        - "view_settings": content of viewsettings.json (str or None)
        - "other_files": dict of other filename → bytes
    """
    result = {
        "mscx": None,
        "mscx_filename": None,
        "style": None,
        "audio_settings": None,
        "view_settings": None,
        "other_files": {},
    }

    with zipfile.ZipFile(path, "r") as zf:
        for name in zf.namelist():
            if name.endswith(".mscx"):
                result["mscx_filename"] = name
                xml_bytes = zf.read(name)
                result["mscx"] = ET.ElementTree(ET.fromstring(xml_bytes))
            elif name == "score_style.mss" or name.endswith("/score_style.mss"):
                result["style"] = zf.read(name).decode("utf-8")
            elif name == "audiosettings.json" or name.endswith("/audiosettings.json"):
                result["audio_settings"] = zf.read(name).decode("utf-8")
            elif name == "viewsettings.json" or name.endswith("/viewsettings.json"):
                result["view_settings"] = zf.read(name).decode("utf-8")
            else:
                result["other_files"][name] = zf.read(name)

    if result["mscx"] is None:
        raise ValueError(f"No .mscx file found inside {path}")

    return result


def write_mscz(path: str, data: dict) -> Path:
    """Write a .mscz file from component data.

    Args:
        path: Output .mscz path.
        data: Dict as returned by read_mscz().

    Returns:
        Path to the written file.
    """
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Write the .mscx XML
        mscx_filename = data.get("mscx_filename", "score.mscx")
        xml_str = ET.tostring(data["mscx"].getroot(), encoding="unicode",
                              xml_declaration=True)
        zf.writestr(mscx_filename, xml_str)

        # Write style
        if data.get("style"):
            zf.writestr("score_style.mss", data["style"])

        # Write settings
        if data.get("audio_settings"):
            zf.writestr("audiosettings.json", data["audio_settings"])
        if data.get("view_settings"):
            zf.writestr("viewsettings.json", data["view_settings"])

        # Write other files
        for name, content in data.get("other_files", {}).items():
            zf.writestr(name, content)

    return Path(path)


# ── MXL (MusicXML ZIP) I/O ───────────────────────────────────────────

def read_mxl(path: str) -> ET.ElementTree:
    """Read a .mxl file (compressed MusicXML).

    Returns:
        ElementTree of the MusicXML content.
    """
    with zipfile.ZipFile(path, "r") as zf:
        # Look for the MusicXML file
        for name in zf.namelist():
            if name.endswith(".xml") and not name.startswith("META-INF"):
                xml_bytes = zf.read(name)
                return ET.ElementTree(ET.fromstring(xml_bytes))

    raise ValueError(f"No MusicXML file found inside {path}")


# ── XML Inspection Helpers ────────────────────────────────────────────

def get_key_signature(tree: ET.ElementTree) -> int | None:
    """Extract the first key signature from a MusicXML or MSCX tree.

    Returns:
        Integer key signature (-7 to 7), or None if not found.
    """
    root = tree.getroot()

    # MusicXML: <key><fifths>-5</fifths></key>
    fifths = root.find(".//{*}fifths")
    if fifths is not None and fifths.text:
        return int(fifths.text)

    # MSCX: <KeySig><accidental>-5</accidental></KeySig>
    # or <KeySig><concertKey>-5</concertKey></KeySig>
    for tag in ["accidental", "concertKey"]:
        elem = root.find(f".//KeySig/{tag}")
        if elem is not None and elem.text:
            return int(elem.text)

    return None


def get_time_signature(tree: ET.ElementTree) -> str | None:
    """Extract the first time signature.

    Returns:
        String like "4/4", "3/4", etc., or None.
    """
    root = tree.getroot()

    # MusicXML: <time><beats>4</beats><beat-type>4</beat-type></time>
    beats = root.find(".//{*}beats")
    beat_type = root.find(".//{*}beat-type")
    if beats is not None and beat_type is not None:
        return f"{beats.text}/{beat_type.text}"

    # MSCX: <TimeSig><sigN>4</sigN><sigD>4</sigD></TimeSig>
    sig_n = root.find(".//TimeSig/sigN")
    sig_d = root.find(".//TimeSig/sigD")
    if sig_n is not None and sig_d is not None:
        return f"{sig_n.text}/{sig_d.text}"

    return None


def get_instruments(tree: ET.ElementTree) -> list[dict]:
    """Extract instrument info from a MusicXML or MSCX tree.

    Returns:
        List of dicts with 'id', 'name', 'part_name' keys.
    """
    root = tree.getroot()
    instruments = []

    # MusicXML: <score-part id="P1"><part-name>Piano</part-name>
    #            <score-instrument id="P1-I1"><instrument-name>Piano</instrument-name>
    for sp in root.findall(".//{*}score-part"):
        inst = {"id": sp.get("id", ""), "name": "", "part_name": ""}
        pn = sp.find("{*}part-name")
        if pn is None:
            pn = sp.find("part-name")
        if pn is not None:
            inst["part_name"] = pn.text or ""
        sin = sp.find(".//{*}instrument-name")
        if sin is not None:
            inst["name"] = sin.text or ""
        else:
            inst["name"] = inst["part_name"]
        instruments.append(inst)

    if instruments:
        return instruments

    # MSCX: <Part><Instrument id="keyboard.piano"><longName>Piano</longName>
    for part in root.findall(".//Part"):
        inst_elem = part.find("Instrument")
        if inst_elem is not None:
            inst = {
                "id": inst_elem.get("id", ""),
                "name": "",
                "part_name": "",
            }
            ln = inst_elem.find("longName")
            if ln is not None:
                inst["name"] = ln.text or ""
            sn = inst_elem.find("shortName")
            if sn is not None:
                inst["part_name"] = sn.text or inst["name"]
            else:
                inst["part_name"] = inst["name"]
            instruments.append(inst)

    return instruments


def get_score_title(tree: ET.ElementTree) -> str:
    """Extract score title from XML."""
    root = tree.getroot()

    # MusicXML: <work><work-title>...</work-title></work>
    # or <movement-title>...</movement-title>
    wt = root.find(".//{*}work-title")
    if wt is not None and wt.text:
        return wt.text
    mt = root.find(".//{*}movement-title")
    if mt is not None and mt.text:
        return mt.text

    # MSCX: <metaTag name="workTitle">...</metaTag>
    for meta in root.findall(".//metaTag"):
        if meta.get("name") == "workTitle" and meta.text:
            return meta.text

    return ""


def count_measures(tree: ET.ElementTree) -> int:
    """Count the number of measures in a score."""
    root = tree.getroot()

    # MusicXML: count <measure> elements in the first part
    measures = root.findall(".//{*}measure")
    if measures:
        # Each part has its own measures; count the first part's
        first_part = root.find(".//{*}part")
        if first_part is not None:
            return len(first_part.findall("{*}measure"))
        return len(measures)

    # MSCX: count <Measure> elements in the first staff
    mscx_measures = root.findall(".//Measure")
    if mscx_measures:
        first_staff = root.find(".//Staff")
        if first_staff is not None:
            return len(first_staff.findall("Measure"))
        return len(mscx_measures)

    return 0


def count_notes(tree: ET.ElementTree) -> int:
    """Count the number of notes in a score."""
    root = tree.getroot()

    # MusicXML
    notes = root.findall(".//{*}note")
    if notes:
        return len(notes)

    # MSCX
    return len(root.findall(".//Note"))


def detect_format(path: str) -> str:
    """Detect score file format from extension.

    Returns:
        One of: "mscz", "mxl", "musicxml", "mid", "unknown"
    """
    ext = Path(path).suffix.lower()
    return {
        ".mscz": "mscz",
        ".mxl": "mxl",
        ".musicxml": "musicxml",
        ".xml": "musicxml",
        ".mid": "mid",
        ".midi": "mid",
    }.get(ext, "unknown")


def read_score_tree(path: str) -> ET.ElementTree:
    """Read a score file and return its XML tree.

    Supports .mscz, .mxl, .musicxml, .xml formats.
    """
    fmt = detect_format(path)
    if fmt == "mscz":
        data = read_mscz(path)
        return data["mscx"]
    elif fmt == "mxl":
        return read_mxl(path)
    elif fmt == "musicxml":
        return ET.parse(path)
    else:
        raise ValueError(f"Cannot read XML tree from format: {fmt} ({path})")
