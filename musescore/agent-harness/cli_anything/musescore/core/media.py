"""Media operations — probe, diff, stats."""

import logging
import os
from pathlib import Path

from cli_anything.musescore.utils import musescore_backend as backend
from cli_anything.musescore.utils import mscx_xml as xml_utils

logger = logging.getLogger(__name__)


def probe_score(path: str) -> dict:
    """Get comprehensive metadata about a score.

    Combines mscore --score-meta with XML parsing for a rich result.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Score file not found: {path}")

    result = {
        "path": str(Path(path).resolve()),
        "format": xml_utils.detect_format(path),
        "size_bytes": os.path.getsize(path),
    }

    # mscore metadata
    try:
        meta = backend.get_score_meta(path)
        result["metadata"] = meta
    except Exception as e:
        logger.debug("mscore metadata failed for probe, falling back to XML: %s", e)
        # XML fallback
        try:
            tree = xml_utils.read_score_tree(path)
            result["metadata"] = {
                "title": xml_utils.get_score_title(tree),
                "key_signature": xml_utils.get_key_signature(tree),
                "time_signature": xml_utils.get_time_signature(tree),
                "instruments": xml_utils.get_instruments(tree),
                "measures": xml_utils.count_measures(tree),
                "notes": xml_utils.count_notes(tree),
            }
        except Exception as e:
            result["error"] = str(e)

    return result


def diff_scores(path_a: str, path_b: str, raw: bool = False) -> dict:
    """Diff two scores using mscore --diff.

    Args:
        path_a: Path to first score.
        path_b: Path to second score.
        raw: If True, use --raw-diff.

    Returns:
        Dict with diff results.
    """
    for p in [path_a, path_b]:
        if not os.path.isfile(p):
            raise FileNotFoundError(f"Score file not found: {p}")

    diff_data = backend.diff_scores(path_a, path_b, raw=raw)

    return {
        "file_a": str(Path(path_a).resolve()),
        "file_b": str(Path(path_b).resolve()),
        "raw": raw,
        "diff": diff_data,
    }


def score_stats(path: str) -> dict:
    """Compute statistics about a score from XML analysis.

    Returns note count, measure count, instrument count,
    key signature, time signature, etc.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Score file not found: {path}")

    result = {
        "path": str(Path(path).resolve()),
        "format": xml_utils.detect_format(path),
        "size_bytes": os.path.getsize(path),
    }

    try:
        tree = xml_utils.read_score_tree(path)
        key_int = xml_utils.get_key_signature(tree)
        result["stats"] = {
            "title": xml_utils.get_score_title(tree),
            "measures": xml_utils.count_measures(tree),
            "notes": xml_utils.count_notes(tree),
            "instruments": len(xml_utils.get_instruments(tree)),
            "key_signature": key_int,
            "key_name": xml_utils.key_int_to_name(key_int) if key_int is not None else None,
            "time_signature": xml_utils.get_time_signature(tree),
        }
    except Exception as e:
        result["error"] = str(e)

    return result
