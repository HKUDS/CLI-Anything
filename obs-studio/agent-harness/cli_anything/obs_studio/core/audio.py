"""OBS Studio CLI - Audio management."""

import copy
from typing import Dict, Any, List, Optional
from cli_anything.obs_studio.utils.obs_utils import generate_id, unique_name, get_item, validate_range


MONITOR_TYPES = ("none", "monitor_only", "monitor_and_output")


def _get_audio_sources(project: Dict[str, Any]) -> List[Dict[str, Any]]:
    return project.setdefault("audio_sources", [])


def add_audio_source(
    project: Dict[str, Any],
    name: str = "Audio",
    audio_type: str = "input",
    device: str = "",
    volume: float = 1.0,
    muted: bool = False,
    monitor: str = "none",
) -> Dict[str, Any]:
    """Add a global audio source."""
    if audio_type not in ("input", "output"):
        raise ValueError(f"Invalid audio type: {audio_type}. Use 'input' or 'output'.")
    if monitor not in MONITOR_TYPES:
        raise ValueError(f"Invalid monitor type: {monitor}. Valid: {', '.join(MONITOR_TYPES)}")
    volume = validate_range(volume, 0.0, 3.0, "Volume")

    audio_sources = _get_audio_sources(project)
    name = unique_name(name, audio_sources)

    source = {
        "id": generate_id(audio_sources),
        "name": name,
        "type": audio_type,
        "device": device,
        "volume": volume,
        "muted": muted,
        "monitor": monitor,
        "balance": 0.0,
        "sync_offset": 0,
        "filters": [],
    }
    audio_sources.append(source)
    return source


def remove_audio_source(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Remove a global audio source."""
    audio_sources = _get_audio_sources(project)
    source = get_item(audio_sources, index, "audio source")
    return audio_sources.pop(index)


def set_volume(project: Dict[str, Any], index: int, volume: float) -> Dict[str, Any]:
    """Set volume for an audio source (0.0 to 3.0, where 1.0 is 100%)."""
    audio_sources = _get_audio_sources(project)
    source = get_item(audio_sources, index, "audio source")
    source["volume"] = validate_range(volume, 0.0, 3.0, "Volume")
    return source


def mute(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Mute an audio source."""
    audio_sources = _get_audio_sources(project)
    source = get_item(audio_sources, index, "audio source")
    source["muted"] = True
    return source


def unmute(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Unmute an audio source."""
    audio_sources = _get_audio_sources(project)
    source = get_item(audio_sources, index, "audio source")
    source["muted"] = False
    return source


def set_monitor(project: Dict[str, Any], index: int, monitor_type: str) -> Dict[str, Any]:
    """Set audio monitoring type."""
    if monitor_type not in MONITOR_TYPES:
        raise ValueError(f"Invalid monitor type: {monitor_type}. Valid: {', '.join(MONITOR_TYPES)}")
    audio_sources = _get_audio_sources(project)
    source = get_item(audio_sources, index, "audio source")
    source["monitor"] = monitor_type
    return source


def set_balance(project: Dict[str, Any], index: int, balance: float) -> Dict[str, Any]:
    """Set stereo balance (-1.0 to 1.0)."""
    audio_sources = _get_audio_sources(project)
    source = get_item(audio_sources, index, "audio source")
    source["balance"] = validate_range(balance, -1.0, 1.0, "Balance")
    return source


def set_sync_offset(project: Dict[str, Any], index: int, offset_ms: int) -> Dict[str, Any]:
    """Set audio sync offset in milliseconds."""
    audio_sources = _get_audio_sources(project)
    source = get_item(audio_sources, index, "audio source")
    source["sync_offset"] = int(offset_ms)
    return source


def list_audio(project: Dict[str, Any]) -> List[Dict[str, Any]]:
    """List all audio sources."""
    audio_sources = _get_audio_sources(project)
    return [
        {
            "index": i,
            "id": s.get("id", i),
            "name": s.get("name", f"Audio {i}"),
            "type": s.get("type", "input"),
            "volume": s.get("volume", 1.0),
            "muted": s.get("muted", False),
            "monitor": s.get("monitor", "none"),
        }
        for i, s in enumerate(audio_sources)
    ]


def get_audio_source(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Get detailed info about an audio source."""
    audio_sources = _get_audio_sources(project)
    return get_item(audio_sources, index, "audio source")
