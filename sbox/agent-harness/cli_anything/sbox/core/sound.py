"""Manages s&box .sound event files - creation and parsing."""

import json
import os
from typing import Any, Dict, List, Optional


def create_sound_event(
    name: str,
    sounds: Optional[List[str]] = None,
    volume: str = "1",
    pitch: str = "1",
    decibels: int = 70,
    selection_mode: str = "Random",
    is_ui: bool = False,
    occlusion: bool = True,
    distance_attenuation: bool = True,
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a .sound event file.

    Args:
        name: Sound event name.
        sounds: List of .vsnd file paths.
        volume: Volume as string float (0-1).
        pitch: Pitch as string float.
        decibels: Loudness in dB.
        selection_mode: How to pick from multiple sounds - "Random", "Sequential".
        is_ui: Whether this is a UI sound (no spatialization).
        occlusion: Enable sound occlusion.
        distance_attenuation: Enable distance-based volume falloff.
        output_path: Output file path. If None, returns data only.

    Returns:
        Dict with name, path, data.
    """
    if sounds is None:
        sounds = []

    data = {
        "UI": is_ui,
        "Volume": volume,
        "Pitch": pitch,
        "Decibels": decibels,
        "SelectionMode": selection_mode,
        "Sounds": sounds,
        "Occlusion": occlusion,
        "AirAbsorption": occlusion,
        "Transmission": occlusion,
        "OcclusionRadius": 64,
        "DistanceAttenuation": distance_attenuation,
        "__references": [],
        "__version": 1,
    }

    result = {
        "name": name,
        "data": data,
    }

    if output_path:
        if not output_path.endswith(".sound"):
            output_path += ".sound"
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        result["path"] = os.path.abspath(output_path)

    return result


def parse_sound_event(sound_path: str) -> Dict[str, Any]:
    """Parse a .sound event file.

    Returns dict with name, path, sounds list, volume, pitch, decibels.
    """
    with open(sound_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    name = os.path.splitext(os.path.basename(sound_path))[0]

    return {
        "name": name,
        "path": os.path.abspath(sound_path),
        "sounds": data.get("Sounds", []),
        "volume": data.get("Volume", "1"),
        "pitch": data.get("Pitch", "1"),
        "decibels": data.get("Decibels", 70),
        "is_ui": data.get("UI", False),
        "selection_mode": data.get("SelectionMode", "Random"),
        "occlusion": data.get("Occlusion", True),
    }


def update_sound_event(
    sound_path: str,
    sounds: Optional[List[str]] = None,
    volume: Optional[str] = None,
    pitch: Optional[str] = None,
    decibels: Optional[int] = None,
    is_ui: Optional[bool] = None,
    occlusion: Optional[bool] = None,
) -> Dict[str, Any]:
    """Update properties of an existing .sound event file.

    Only modifies properties that are explicitly provided (non-None).
    Returns the updated sound info dict.
    """
    with open( sound_path, "r", encoding="utf-8" ) as f:
        data = json.load( f )

    if sounds is not None:
        data["Sounds"] = sounds
    if volume is not None:
        data["Volume"] = volume
    if pitch is not None:
        data["Pitch"] = pitch
    if decibels is not None:
        data["Decibels"] = decibels
    if is_ui is not None:
        data["UI"] = is_ui
    if occlusion is not None:
        data["Occlusion"] = occlusion
        data["AirAbsorption"] = occlusion
        data["Transmission"] = occlusion

    with open( sound_path, "w", encoding="utf-8" ) as f:
        json.dump( data, f, indent=2 )

    return parse_sound_event( sound_path )
