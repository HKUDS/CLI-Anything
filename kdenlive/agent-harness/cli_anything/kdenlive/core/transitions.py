"""Kdenlive CLI - Transition management module."""

from typing import Dict, Any, List, Optional


TRANSITION_TYPES = {
    "dissolve": {
        "mlt_service": "luma",
        "params": {
            "duration": {"type": "float", "default": 1.0, "min": 0.01, "max": 60.0},
            "softness": {"type": "float", "default": 0.0, "min": 0.0, "max": 1.0},
        },
    },
    "wipe": {
        "mlt_service": "luma",
        "params": {
            "duration": {"type": "float", "default": 1.0, "min": 0.01, "max": 60.0},
            "resource": {"type": "str", "default": ""},
            "softness": {"type": "float", "default": 0.0, "min": 0.0, "max": 1.0},
        },
    },
    "slide": {
        "mlt_service": "affine",
        "params": {
            "duration": {"type": "float", "default": 1.0, "min": 0.01, "max": 60.0},
            "direction": {"type": "str", "default": "left"},
        },
    },
    "composite": {
        "mlt_service": "composite",
        "params": {
            "fill": {"type": "int", "default": 1, "min": 0, "max": 1},
            "aligned": {"type": "int", "default": 1, "min": 0, "max": 1},
        },
    },
    "affine": {
        "mlt_service": "affine",
        "params": {
            "distort": {"type": "int", "default": 0, "min": 0, "max": 1},
        },
    },
}


def _next_transition_id(project: Dict[str, Any]) -> int:
    """Generate next unique transition ID."""
    existing = {t.get("id", -1) for t in project.get("transitions", [])}
    idx = 0
    while idx in existing:
        idx += 1
    return idx


def add_transition(
    project: Dict[str, Any],
    transition_type: str,
    track_a: int,
    track_b: int,
    position: float = 0.0,
    duration: float = 1.0,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Add a transition between two tracks."""
    if transition_type not in TRANSITION_TYPES:
        raise ValueError(
            f"Unknown transition type: {transition_type}. "
            f"Available: {', '.join(TRANSITION_TYPES.keys())}"
        )

    # Validate tracks exist
    track_ids = {t["id"] for t in project.get("tracks", [])}
    if track_a not in track_ids:
        raise ValueError(f"Track not found: {track_a}")
    if track_b not in track_ids:
        raise ValueError(f"Track not found: {track_b}")
    if track_a == track_b:
        raise ValueError("Transition must be between two different tracks.")

    if position < 0:
        raise ValueError(f"Position must be non-negative: {position}")
    if duration <= 0:
        raise ValueError(f"Duration must be positive: {duration}")

    spec = TRANSITION_TYPES[transition_type]

    # Validate params
    validated = {}
    param_specs = spec["params"]
    user_params = params or {}

    unknown = set(user_params.keys()) - set(param_specs.keys())
    if unknown:
        raise ValueError(
            f"Unknown parameters for '{transition_type}': {', '.join(unknown)}."
        )

    for pname, pspec in param_specs.items():
        value = user_params.get(pname, pspec["default"])
        ptype = pspec["type"]
        if ptype == "float":
            value = float(value)
            if "min" in pspec and value < pspec["min"]:
                raise ValueError(f"Parameter '{pname}' below minimum {pspec['min']}.")
            if "max" in pspec and value > pspec["max"]:
                raise ValueError(f"Parameter '{pname}' above maximum {pspec['max']}.")
        elif ptype == "int":
            value = int(value)
            if "min" in pspec and value < pspec["min"]:
                raise ValueError(f"Parameter '{pname}' below minimum {pspec['min']}.")
            if "max" in pspec and value > pspec["max"]:
                raise ValueError(f"Parameter '{pname}' above maximum {pspec['max']}.")
        elif ptype == "str":
            value = str(value)
        validated[pname] = value

    # Override duration if in params
    if "duration" in validated:
        duration = validated["duration"]

    tid = _next_transition_id(project)
    transition = {
        "id": tid,
        "type": transition_type,
        "mlt_service": spec["mlt_service"],
        "track_a": track_a,
        "track_b": track_b,
        "position": position,
        "duration": duration,
        "params": validated,
    }

    project.setdefault("transitions", []).append(transition)
    return transition


def remove_transition(project: Dict[str, Any], transition_id: int) -> Dict[str, Any]:
    """Remove a transition by ID."""
    transitions = project.get("transitions", [])
    for i, t in enumerate(transitions):
        if t["id"] == transition_id:
            return transitions.pop(i)
    raise ValueError(f"Transition not found: {transition_id}")


def set_transition(
    project: Dict[str, Any],
    transition_id: int,
    param_name: str,
    value: Any,
) -> Dict[str, Any]:
    """Set a parameter on a transition."""
    transitions = project.get("transitions", [])
    transition = None
    for t in transitions:
        if t["id"] == transition_id:
            transition = t
            break
    if transition is None:
        raise ValueError(f"Transition not found: {transition_id}")

    ttype = transition["type"]
    spec = TRANSITION_TYPES.get(ttype, {})
    param_specs = spec.get("params", {})

    # Allow setting position and duration directly
    if param_name == "position":
        transition["position"] = float(value)
        return dict(transition)
    elif param_name == "duration":
        transition["duration"] = float(value)
        if "duration" in transition.get("params", {}):
            transition["params"]["duration"] = float(value)
        return dict(transition)

    if param_name not in param_specs:
        raise ValueError(
            f"Unknown parameter '{param_name}' for transition '{ttype}'. "
            f"Valid: position, duration, {', '.join(param_specs.keys())}"
        )

    pspec = param_specs[param_name]
    ptype = pspec["type"]
    if ptype == "float":
        value = float(value)
    elif ptype == "int":
        value = int(value)

    transition.setdefault("params", {})[param_name] = value
    return dict(transition)


def list_transitions(project: Dict[str, Any]) -> List[Dict[str, Any]]:
    """List all transitions."""
    return [
        {
            "id": t["id"],
            "type": t["type"],
            "mlt_service": t.get("mlt_service", ""),
            "track_a": t["track_a"],
            "track_b": t["track_b"],
            "position": t.get("position", 0),
            "duration": t.get("duration", 1),
            "params": t.get("params", {}),
        }
        for t in project.get("transitions", [])
    ]
