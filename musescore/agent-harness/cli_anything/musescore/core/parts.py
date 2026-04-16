"""Part extraction and management."""

import base64
import logging
import os
from pathlib import Path

from cli_anything.musescore.utils import musescore_backend as backend

logger = logging.getLogger(__name__)


def list_parts(path: str) -> list[dict]:
    """List all parts in a score.

    Returns:
        List of dicts with part name, instrumentId, etc.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Score file not found: {path}")

    # Try score-meta first (lighter)
    try:
        meta = backend.get_score_meta(path)
        parts = meta.get("parts", [])
        return [
            {
                "index": i,
                "name": p.get("name", f"Part {i+1}"),
                "instrumentId": p.get("instrumentId", ""),
                "program": p.get("program", 0),
                "lyricCount": p.get("lyricCount", 0),
                "harmonyCount": p.get("harmonyCount", 0),
            }
            for i, p in enumerate(parts)
        ]
    except Exception as e:
        logger.debug("mscore metadata failed for parts, falling back to score-parts: %s", e)

    # Fallback: score-parts (parts = list of names, partsMeta = list of dicts)
    try:
        parts_data = backend.get_score_parts(path)
        part_names = parts_data.get("parts", [])
        part_meta = parts_data.get("partsMeta", [])
        return [
            {
                "index": i,
                "name": part_names[i] if i < len(part_names) else f"Part {i+1}",
                "id": part_meta[i].get("id", "") if i < len(part_meta) else "",
            }
            for i in range(max(len(part_names), len(part_meta)))
        ]
    except Exception as e:
        raise RuntimeError(f"Could not list parts: {e}")


def extract_part(path: str, part_name: str, output_path: str) -> dict:
    """Extract a single part from a score.

    Uses --score-parts to get base64-encoded .mscz data for each part,
    then writes the matching part to the output file.

    Args:
        path: Path to the input score.
        part_name: Name of the part to extract.
        output_path: Path to write the extracted part.

    Returns:
        Dict with extraction result info.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Score file not found: {path}")

    parts_data = backend.get_score_parts(path)
    part_names = parts_data.get("parts", [])
    part_bins = parts_data.get("partsBin", [])

    # Find matching part index (case-insensitive)
    match_idx = None
    for i, name in enumerate(part_names):
        if name.lower() == part_name.lower():
            match_idx = i
            break

    if match_idx is None:
        raise ValueError(
            f"Part '{part_name}' not found. Available parts: {part_names}"
        )

    if match_idx >= len(part_bins):
        raise RuntimeError(f"No binary data for part '{part_name}'")

    part_data = part_bins[match_idx]
    if not part_data:
        raise RuntimeError(f"No data for part '{part_name}'")

    decoded = base64.b64decode(part_data)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(decoded)

    return {
        "part_name": part_names[match_idx],
        "output": str(Path(output_path).resolve()),
        "size_bytes": len(decoded),
    }


def generate_all_parts(path: str, output_dir: str) -> list[dict]:
    """Extract all parts from a score into separate files.

    Args:
        path: Path to the input score.
        output_dir: Directory to write part files into.

    Returns:
        List of dicts with extraction results.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Score file not found: {path}")

    parts_data = backend.get_score_parts(path)
    part_names = parts_data.get("parts", [])
    part_bins = parts_data.get("partsBin", [])
    results = []

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    for i, name in enumerate(part_names):
        if i >= len(part_bins) or not part_bins[i]:
            continue

        safe_name = name.replace("/", "_").replace("\\", "_").replace(" ", "_")
        output_path = os.path.join(output_dir, f"{safe_name}.mscz")

        decoded = base64.b64decode(part_bins[i])
        with open(output_path, "wb") as f:
            f.write(decoded)

        results.append({
            "part_name": name,
            "output": output_path,
            "size_bytes": len(decoded),
        })

    return results
