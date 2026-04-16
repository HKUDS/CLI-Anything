"""Audacity CLI - Effect registry and management module.

Provides a registry of audio effects with parameter specifications,
and functions to add/remove/modify effects on tracks. Effects are
stored in the project JSON and applied during export/render.
"""

from typing import Dict, Any, List, Optional


# Effect registry: maps effect name -> parameter specifications
EFFECT_REGISTRY = {
    "amplify": {
        "category": "volume",
        "description": "Amplify or attenuate audio by a dB amount",
        "params": {
            "gain_db": {"type": "float", "default": 0.0, "min": -60, "max": 60,
                        "description": "Gain in decibels"},
        },
    },
    "normalize": {
        "category": "volume",
        "description": "Normalize audio to a target peak level",
        "params": {
            "target_db": {"type": "float", "default": -1.0, "min": -60, "max": 0,
                          "description": "Target peak level in dB"},
        },
    },
    "fade_in": {
        "category": "fade",
        "description": "Apply a fade-in at the start",
        "params": {
            "duration": {"type": "float", "default": 1.0, "min": 0.01, "max": 300,
                         "description": "Fade duration in seconds"},
        },
    },
    "fade_out": {
        "category": "fade",
        "description": "Apply a fade-out at the end",
        "params": {
            "duration": {"type": "float", "default": 1.0, "min": 0.01, "max": 300,
                         "description": "Fade duration in seconds"},
        },
    },
    "reverse": {
        "category": "transform",
        "description": "Reverse the audio",
        "params": {},
    },
    "silence": {
        "category": "generate",
        "description": "Generate silence",
        "params": {
            "duration": {"type": "float", "default": 1.0, "min": 0.01, "max": 3600,
                         "description": "Silence duration in seconds"},
        },
    },
    "tone": {
        "category": "generate",
        "description": "Generate a sine wave tone",
        "params": {
            "frequency": {"type": "float", "default": 440.0, "min": 20, "max": 20000,
                          "description": "Frequency in Hz"},
            "duration": {"type": "float", "default": 1.0, "min": 0.01, "max": 3600,
                         "description": "Duration in seconds"},
            "amplitude": {"type": "float", "default": 0.5, "min": 0.0, "max": 1.0,
                          "description": "Amplitude (0.0-1.0)"},
        },
    },
    "change_speed": {
        "category": "transform",
        "description": "Change playback speed (also changes pitch)",
        "params": {
            "factor": {"type": "float", "default": 1.0, "min": 0.1, "max": 10.0,
                       "description": "Speed factor (2.0 = double speed)"},
        },
    },
    "change_pitch": {
        "category": "transform",
        "description": "Change pitch by semitones",
        "params": {
            "semitones": {"type": "float", "default": 0.0, "min": -24, "max": 24,
                          "description": "Pitch shift in semitones"},
        },
    },
    "echo": {
        "category": "delay",
        "description": "Add echo/delay effect",
        "params": {
            "delay_ms": {"type": "float", "default": 500.0, "min": 1, "max": 5000,
                         "description": "Delay time in milliseconds"},
            "decay": {"type": "float", "default": 0.5, "min": 0.0, "max": 1.0,
                      "description": "Echo decay factor"},
        },
    },
    "low_pass": {
        "category": "eq",
        "description": "Low-pass filter (cut high frequencies)",
        "params": {
            "cutoff": {"type": "float", "default": 1000.0, "min": 20, "max": 20000,
                       "description": "Cutoff frequency in Hz"},
        },
    },
    "high_pass": {
        "category": "eq",
        "description": "High-pass filter (cut low frequencies)",
        "params": {
            "cutoff": {"type": "float", "default": 100.0, "min": 20, "max": 20000,
                       "description": "Cutoff frequency in Hz"},
        },
    },
    "compress": {
        "category": "dynamics",
        "description": "Dynamic range compression",
        "params": {
            "threshold": {"type": "float", "default": -20.0, "min": -60, "max": 0,
                          "description": "Threshold in dB"},
            "ratio": {"type": "float", "default": 4.0, "min": 1.0, "max": 20.0,
                      "description": "Compression ratio"},
            "attack": {"type": "float", "default": 5.0, "min": 0.1, "max": 1000,
                       "description": "Attack time in ms"},
            "release": {"type": "float", "default": 50.0, "min": 1, "max": 5000,
                        "description": "Release time in ms"},
        },
    },
    "limit": {
        "category": "dynamics",
        "description": "Hard limiter",
        "params": {
            "threshold_db": {"type": "float", "default": -1.0, "min": -60, "max": 0,
                             "description": "Limiter threshold in dB"},
        },
    },
    "change_tempo": {
        "category": "transform",
        "description": "Change tempo without changing pitch",
        "params": {
            "factor": {"type": "float", "default": 1.0, "min": 0.1, "max": 10.0,
                       "description": "Tempo factor (2.0 = double tempo)"},
        },
    },
    "noise_reduction": {
        "category": "restoration",
        "description": "Reduce background noise",
        "params": {
            "reduction_db": {"type": "float", "default": 12.0, "min": 0, "max": 48,
                             "description": "Noise reduction amount in dB"},
        },
    },
}


def list_available(category: Optional[str] = None) -> List[Dict[str, Any]]:
    """List available effects, optionally filtered by category."""
    result = []
    for name, info in EFFECT_REGISTRY.items():
        if category and info["category"] != category:
            continue
        result.append({
            "name": name,
            "category": info["category"],
            "description": info["description"],
            "param_count": len(info["params"]),
        })
    return result


def get_effect_info(name: str) -> Dict[str, Any]:
    """Get detailed info about an effect."""
    if name not in EFFECT_REGISTRY:
        raise ValueError(
            f"Unknown effect: {name}. Use 'effect list-available' to see options."
        )
    info = EFFECT_REGISTRY[name]
    return {
        "name": name,
        "category": info["category"],
        "description": info["description"],
        "params": info["params"],
    }


def validate_params(name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and fill defaults for effect parameters."""
    if name not in EFFECT_REGISTRY:
        raise ValueError(f"Unknown effect: {name}")

    spec = EFFECT_REGISTRY[name]["params"]
    result = {}

    for pname, pspec in spec.items():
        if pname in params:
            val = params[pname]
            ptype = pspec["type"]
            if ptype == "float":
                val = float(val)
                if "min" in pspec and val < pspec["min"]:
                    raise ValueError(
                        f"Parameter '{pname}' minimum is {pspec['min']}, got {val}"
                    )
                if "max" in pspec and val > pspec["max"]:
                    raise ValueError(
                        f"Parameter '{pname}' maximum is {pspec['max']}, got {val}"
                    )
            elif ptype == "int":
                val = int(val)
                if "min" in pspec and val < pspec["min"]:
                    raise ValueError(
                        f"Parameter '{pname}' minimum is {pspec['min']}, got {val}"
                    )
                if "max" in pspec and val > pspec["max"]:
                    raise ValueError(
                        f"Parameter '{pname}' maximum is {pspec['max']}, got {val}"
                    )
            elif ptype == "bool":
                val = str(val).lower() in ("true", "1", "yes")
            elif ptype == "str":
                val = str(val)
            result[pname] = val
        else:
            result[pname] = pspec.get("default")

    # Check for unknown params
    unknown = set(params.keys()) - set(spec.keys())
    if unknown:
        raise ValueError(f"Unknown parameters for effect '{name}': {unknown}")

    return result


def add_effect(
    project: Dict[str, Any],
    name: str,
    track_index: int = 0,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Add an effect to a track."""
    tracks = project.get("tracks", [])
    if track_index < 0 or track_index >= len(tracks):
        raise IndexError(
            f"Track index {track_index} out of range (0-{len(tracks) - 1})"
        )

    if name not in EFFECT_REGISTRY:
        raise ValueError(f"Unknown effect: {name}")

    validated = validate_params(name, params or {})

    effect_entry = {
        "name": name,
        "params": validated,
    }

    track = tracks[track_index]
    track.setdefault("effects", []).append(effect_entry)
    return effect_entry


def remove_effect(
    project: Dict[str, Any],
    effect_index: int,
    track_index: int = 0,
) -> Dict[str, Any]:
    """Remove an effect from a track by index."""
    tracks = project.get("tracks", [])
    if track_index < 0 or track_index >= len(tracks):
        raise IndexError(f"Track index {track_index} out of range")

    effects = tracks[track_index].get("effects", [])
    if effect_index < 0 or effect_index >= len(effects):
        raise IndexError(
            f"Effect index {effect_index} out of range (0-{len(effects) - 1})"
        )

    return effects.pop(effect_index)


def set_effect_param(
    project: Dict[str, Any],
    effect_index: int,
    param: str,
    value: Any,
    track_index: int = 0,
) -> None:
    """Set an effect parameter value."""
    tracks = project.get("tracks", [])
    if track_index < 0 or track_index >= len(tracks):
        raise IndexError(f"Track index {track_index} out of range")

    effects = tracks[track_index].get("effects", [])
    if effect_index < 0 or effect_index >= len(effects):
        raise IndexError(f"Effect index {effect_index} out of range")

    effect = effects[effect_index]
    name = effect["name"]
    spec = EFFECT_REGISTRY[name]["params"]

    if param not in spec:
        raise ValueError(
            f"Unknown parameter '{param}' for effect '{name}'. "
            f"Valid: {list(spec.keys())}"
        )

    # Validate
    test_params = dict(effect["params"])
    test_params[param] = value
    validated = validate_params(name, test_params)
    effect["params"] = validated


def list_effects(
    project: Dict[str, Any],
    track_index: int = 0,
) -> List[Dict[str, Any]]:
    """List effects on a track."""
    tracks = project.get("tracks", [])
    if track_index < 0 or track_index >= len(tracks):
        raise IndexError(f"Track index {track_index} out of range")

    effects = tracks[track_index].get("effects", [])
    result = []
    for i, e in enumerate(effects):
        result.append({
            "index": i,
            "name": e["name"],
            "params": e["params"],
            "category": EFFECT_REGISTRY.get(e["name"], {}).get("category", "unknown"),
        })
    return result
