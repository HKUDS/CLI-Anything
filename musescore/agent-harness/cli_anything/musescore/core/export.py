"""Export/render pipeline via mscore backend."""

import os
from pathlib import Path

from cli_anything.musescore.utils import musescore_backend as backend


# ── Supported export formats ──────────────────────────────────────────

EXPORT_FORMATS = {
    "pdf":      {"ext": ".pdf",      "magic": b"%PDF-",       "desc": "PDF document"},
    "png":      {"ext": ".png",      "magic": b"\x89PNG",     "desc": "PNG image (per page)"},
    "svg":      {"ext": ".svg",      "magic": None,           "desc": "SVG vector (per page)"},
    "mp3":      {"ext": ".mp3",      "magic": None,           "desc": "MP3 audio"},
    "flac":     {"ext": ".flac",     "magic": b"fLaC",        "desc": "FLAC audio"},
    "wav":      {"ext": ".wav",      "magic": b"RIFF",        "desc": "WAV audio"},
    "midi":     {"ext": ".mid",      "magic": b"MThd",        "desc": "MIDI file"},
    "musicxml": {"ext": ".musicxml", "magic": None,           "desc": "MusicXML"},
    "mscz":     {"ext": ".mscz",     "magic": b"PK",          "desc": "MuseScore file"},
    "braille":  {"ext": ".brf",      "magic": None,           "desc": "Braille music notation"},
}


def export_score(input_path: str, output_path: str, *,
                 fmt: str | None = None,
                 dpi: int | None = None,
                 bitrate: int | None = None,
                 trim: int | None = None,
                 style: str | None = None,
                 sound_profile: str | None = None,
                 export_parts: bool = False) -> dict:
    """Export a score to the specified format.

    Format is auto-detected from output_path extension, or can be
    specified explicitly via fmt.

    Returns:
        Dict with export result info.
    """
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"Score file not found: {input_path}")

    # Determine format
    if fmt is None:
        ext = Path(output_path).suffix.lower()
        fmt = _ext_to_format(ext)
    if fmt not in EXPORT_FORMATS:
        raise ValueError(f"Unsupported format: {fmt}. Supported: {list(EXPORT_FORMATS.keys())}")

    # Ensure output directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Run export
    result_path = backend.export_score(
        input_path, output_path,
        dpi=dpi, bitrate=bitrate, trim=trim,
        style=style, sound_profile=sound_profile,
        export_parts=export_parts,
    )

    return {
        "input": input_path,
        "output": str(result_path),
        "format": fmt,
    }


def batch_export(input_path: str, outputs: list[str]) -> list[dict]:
    """Export a score to multiple formats at once via batch job.

    Args:
        input_path: Path to input score.
        outputs: List of output file paths.

    Returns:
        List of dicts with per-output results.
    """
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"Score file not found: {input_path}")

    job_list = [{"in": str(input_path), "out": str(o)} for o in outputs]
    result_paths = backend.batch_convert(job_list)

    return [
        {
            "input": input_path,
            "output": str(p),
            "format": _ext_to_format(p.suffix),
        }
        for p in result_paths
    ]


def verify_output(path: str, expected_format: str | None = None) -> dict:
    """Verify an exported file using magic bytes.

    Args:
        path: Path to the output file.
        expected_format: Expected format name (e.g., "pdf", "midi").

    Returns:
        Dict with verification results.
    """
    if not os.path.isfile(path):
        return {"path": path, "exists": False, "valid": False}

    size = os.path.getsize(path)
    if size == 0:
        return {"path": path, "exists": True, "size": 0, "valid": False}

    result = {
        "path": path,
        "exists": True,
        "size": size,
    }

    # Determine expected format from extension if not specified
    if expected_format is None:
        expected_format = _ext_to_format(Path(path).suffix)

    fmt_info = EXPORT_FORMATS.get(expected_format)
    if fmt_info and fmt_info["magic"]:
        with open(path, "rb") as f:
            header = f.read(max(len(fmt_info["magic"]), 5))

        magic = fmt_info["magic"]
        # Special handling for MP3 (can start with ID3 tag or sync bytes)
        if expected_format == "mp3":
            result["valid"] = (
                header[:2] == b"\xff\xfb"
                or header[:3] == b"ID3"
            )
        else:
            result["valid"] = header[:len(magic)] == magic
    else:
        # No magic bytes to check; just verify non-empty
        result["valid"] = size > 0

    result["format"] = expected_format
    return result


def _ext_to_format(ext: str) -> str:
    """Map file extension to format name."""
    ext = ext.lower().lstrip(".")
    mapping = {
        "pdf": "pdf",
        "png": "png",
        "svg": "svg",
        "mp3": "mp3",
        "flac": "flac",
        "wav": "wav",
        "mid": "midi",
        "midi": "midi",
        "musicxml": "musicxml",
        "xml": "musicxml",
        "mscz": "mscz",
        "brf": "braille",
    }
    return mapping.get(ext, ext)
