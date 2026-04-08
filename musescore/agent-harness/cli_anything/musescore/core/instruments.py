"""Instrument management — list, add, remove, reorder.

For listing, uses mscore --score-meta. For add/remove/reorder,
manipulates the MSCX XML directly.
"""

import logging
import os
from pathlib import Path

from cli_anything.musescore.utils import musescore_backend as backend

logger = logging.getLogger(__name__)
from cli_anything.musescore.utils import mscx_xml as xml_utils


def list_instruments(path: str) -> list[dict]:
    """List instruments in a score.

    Tries mscore --score-meta first, falls back to XML parsing.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Score file not found: {path}")

    # Try mscore metadata
    try:
        meta = backend.get_score_meta(path)
        parts = meta.get("parts", [])
        return [
            {
                "index": i,
                "name": p.get("name", f"Instrument {i+1}"),
                "instrumentId": p.get("instrumentId", ""),
                "program": p.get("program", 0),
            }
            for i, p in enumerate(parts)
        ]
    except Exception as e:
        logger.debug("mscore metadata failed for instruments, falling back to XML: %s", e)

    # Fallback: XML parsing
    try:
        tree = xml_utils.read_score_tree(path)
        instruments = xml_utils.get_instruments(tree)
        return [
            {
                "index": i,
                "name": inst.get("name") or inst.get("part_name", f"Instrument {i+1}"),
                "instrumentId": inst.get("id", ""),
            }
            for i, inst in enumerate(instruments)
        ]
    except Exception as e:
        raise RuntimeError(f"Could not list instruments: {e}")


def add_instrument(path: str, output_path: str, instrument_id: str,
                   name: str) -> dict:
    """Add an instrument to a .mscz score via MSCX XML manipulation.

    Args:
        path: Path to input .mscz file.
        output_path: Path to output .mscz file.
        instrument_id: MuseScore instrument ID (e.g., "keyboard.piano").
        name: Display name for the instrument.

    Returns:
        Dict with result info.
    """
    fmt = xml_utils.detect_format(path)
    if fmt != "mscz":
        raise ValueError("Instrument manipulation requires .mscz format")

    data = xml_utils.read_mscz(path)
    root = data["mscx"].getroot()

    # Find or create the Score element
    score = root.find(".//Score")
    if score is None:
        raise RuntimeError("No <Score> element found in MSCX")

    # Count existing parts BEFORE adding the new one
    import xml.etree.ElementTree as ET
    staff_id = str(len(score.findall("Part")) + 1)

    part = ET.SubElement(score, "Part")
    staff = ET.SubElement(part, "Staff")
    staff.set("id", staff_id)

    instrument = ET.SubElement(part, "Instrument")
    instrument.set("id", instrument_id)
    long_name = ET.SubElement(instrument, "longName")
    long_name.text = name
    short_name = ET.SubElement(instrument, "shortName")
    short_name.text = name[:3]

    # Also add a Staff element at the score level
    score_staff = ET.SubElement(score, "Staff")
    score_staff.set("id", staff_id)

    xml_utils.write_mscz(output_path, data)

    return {
        "action": "add",
        "instrument_id": instrument_id,
        "name": name,
        "output": str(Path(output_path).resolve()),
    }


def remove_instrument(path: str, output_path: str,
                      instrument_name: str) -> dict:
    """Remove an instrument from a .mscz score.

    Args:
        path: Path to input .mscz file.
        output_path: Path to output .mscz file.
        instrument_name: Name of the instrument to remove (case-insensitive).

    Returns:
        Dict with result info.
    """
    fmt = xml_utils.detect_format(path)
    if fmt != "mscz":
        raise ValueError("Instrument manipulation requires .mscz format")

    data = xml_utils.read_mscz(path)
    root = data["mscx"].getroot()

    score = root.find(".//Score")
    if score is None:
        raise RuntimeError("No <Score> element found in MSCX")

    # Find the part to remove
    removed = False
    for part in score.findall("Part"):
        inst = part.find("Instrument")
        if inst is not None:
            ln = inst.find("longName")
            name = ln.text if ln is not None else ""
            if name.lower() == instrument_name.lower():
                # Get staff ID before removing
                staff_elem = part.find("Staff")
                staff_id = staff_elem.get("id") if staff_elem is not None else None

                score.remove(part)

                # Also remove corresponding score-level Staff
                if staff_id:
                    for s in score.findall("Staff"):
                        if s.get("id") == staff_id:
                            score.remove(s)
                            break

                removed = True
                break

    if not removed:
        raise ValueError(f"Instrument '{instrument_name}' not found")

    xml_utils.write_mscz(output_path, data)

    return {
        "action": "remove",
        "instrument_name": instrument_name,
        "output": str(Path(output_path).resolve()),
    }


def reorder_instruments(path: str, output_path: str,
                        new_order: list[str]) -> dict:
    """Reorder instruments in a .mscz score.

    Args:
        path: Path to input .mscz file.
        output_path: Path to output .mscz file.
        new_order: List of instrument names in desired order.

    Returns:
        Dict with result info.
    """
    fmt = xml_utils.detect_format(path)
    if fmt != "mscz":
        raise ValueError("Instrument manipulation requires .mscz format")

    data = xml_utils.read_mscz(path)
    root = data["mscx"].getroot()

    score = root.find(".//Score")
    if score is None:
        raise RuntimeError("No <Score> element found in MSCX")

    # Collect parts by name
    parts_by_name = {}
    for part in score.findall("Part"):
        inst = part.find("Instrument")
        if inst is not None:
            ln = inst.find("longName")
            name = ln.text if ln is not None else ""
            parts_by_name[name.lower()] = part

    # Validate: new_order must contain all instruments
    provided = {n.lower() for n in new_order}
    existing = set(parts_by_name.keys())
    missing = existing - provided
    if missing:
        missing_names = [n for n in parts_by_name if n in missing]
        raise ValueError(
            f"new_order is missing instruments: {missing_names}. "
            f"All instruments must be included to prevent data loss."
        )
    unknown = provided - existing
    if unknown:
        raise ValueError(f"Instruments not found in score: {list(unknown)}")

    # Remove all parts
    for part in score.findall("Part"):
        score.remove(part)

    # Re-add in new order
    for name in new_order:
        score.append(parts_by_name[name.lower()])

    xml_utils.write_mscz(output_path, data)

    return {
        "action": "reorder",
        "new_order": new_order,
        "output": str(Path(output_path).resolve()),
    }
