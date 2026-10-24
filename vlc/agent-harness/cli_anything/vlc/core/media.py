"""Best-effort parser for VLC ``--stats`` / verbose dummy-mode output.

VLC does not emit a stable structured metadata format, so this parser is tolerant: it
extracts whatever it can recognise (duration, bitrate, codec hints, stream counts) and
leaves unrecognised fields as ``None``. Good enough for agent triage.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Match


def _first(pattern: str, text: str, group: int = 1) -> Any:
    m: Match | None = re.search(pattern, text, re.IGNORECASE)
    return m.group(group) if m else None


def parse_vlc_stats(text: str) -> Dict[str, Any]:
    """Parse VLC dummy-mode output into a dict of best-effort media metadata."""
    info: Dict[str, Any] = {
        "duration_seconds": None,
        "bitrate_kbps": None,
        "video_codec": None,
        "audio_codec": None,
        "width": None,
        "height": None,
        "streams": 0,
        "raw_excerpt": text[:2000],
    }

    dur = _first(r"duration\s*[:=]\s*([\d.]+)", text)
    if dur is None:
        dur = _first(r"(\d+(?:\.\d+)?)\s*(?:sec|s)\b", text)
    if dur is not None:
        try:
            info["duration_seconds"] = round(float(dur), 3)
        except ValueError:
            pass

    br = _first(r"bitrate\s*[:=]\s*(\d+)", text)
    if br is not None:
        info["bitrate_kbps"] = int(br)

    # Elementary stream / decoder module lines often name a codec.
    vc = _first(r"(?:vcodec|video codec|decoder)\D{0,20}(h26[45]|vp0?[89]|av1|mpeg[24]|theora|avc)", text)
    if vc:
        info["video_codec"] = vc.upper()
    ac = _first(r"(?:acodec|audio codec|decoder)\D{0,20}(aac|mp3|opus|vorbis|flac|mp2|ac3)", text)
    if ac:
        info["audio_codec"] = ac.lower()

    wh = re.search(r"(\d{2,5})x(\d{2,5})", text, re.IGNORECASE)
    if wh:
        info["width"] = int(wh.group(1))
        info["height"] = int(wh.group(2))

    info["streams"] = len(re.findall(r"es_out.*(?:adding|creating).*stream|elementary stream", text, re.IGNORECASE))

    return info
