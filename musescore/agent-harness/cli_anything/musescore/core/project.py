"""Project management — create, open, save, info."""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

from cli_anything.musescore.utils import musescore_backend as backend
from cli_anything.musescore.utils import mscx_xml as xml_utils


def open_project(path: str) -> dict:
    """Open a score file and return project data.

    Supports .mscz, .mxl, .musicxml, .mid formats.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Score file not found: {path}")

    fmt = xml_utils.detect_format(path)
    project = {
        "name": Path(path).stem,
        "path": str(Path(path).resolve()),
        "format": fmt,
    }

    # Try to get metadata from mscore
    try:
        meta = backend.get_score_meta(path)
        project["metadata"] = meta
        if meta.get("title"):
            project["name"] = meta["title"]
    except Exception as e:
        logger.debug("mscore metadata failed, falling back to XML: %s", e)
        # Fall back to XML parsing for metadata
        try:
            tree = xml_utils.read_score_tree(path)
            title = xml_utils.get_score_title(tree)
            if title:
                project["name"] = title
            project["metadata"] = {
                "key_signature": xml_utils.get_key_signature(tree),
                "time_signature": xml_utils.get_time_signature(tree),
                "instruments": xml_utils.get_instruments(tree),
                "measures": xml_utils.count_measures(tree),
                "notes": xml_utils.count_notes(tree),
            }
        except Exception as e:
            logger.debug("XML parsing also failed: %s", e)

    return project


def save_project(input_path: str, output_path: str) -> dict:
    """Save/convert a score to .mscz format via mscore export.

    This delegates to mscore -o which handles all format conversion.
    """
    from cli_anything.musescore.core import export
    return export.export_score(input_path, output_path, fmt="mscz")


def project_info(path: str) -> dict:
    """Get comprehensive info about a score file."""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Score file not found: {path}")

    info = {
        "path": str(Path(path).resolve()),
        "format": xml_utils.detect_format(path),
        "size_bytes": os.path.getsize(path),
    }

    # Try mscore --score-meta first (most complete)
    try:
        meta = backend.get_score_meta(path)
        info["metadata"] = meta
        return info
    except Exception as e:
        logger.debug("mscore metadata failed for info, falling back to XML: %s", e)

    # Fall back to XML parsing
    try:
        tree = xml_utils.read_score_tree(path)
        info["metadata"] = {
            "title": xml_utils.get_score_title(tree),
            "key_signature": xml_utils.get_key_signature(tree),
            "key_name": _key_sig_name(xml_utils.get_key_signature(tree)),
            "time_signature": xml_utils.get_time_signature(tree),
            "instruments": xml_utils.get_instruments(tree),
            "measures": xml_utils.count_measures(tree),
            "notes": xml_utils.count_notes(tree),
        }
    except Exception as e:
        info["error"] = f"Could not parse score: {e}"

    return info


def _key_sig_name(key_int: int | None) -> str | None:
    if key_int is None:
        return None
    try:
        return xml_utils.key_int_to_name(key_int)
    except ValueError:
        return f"keysig={key_int}"
