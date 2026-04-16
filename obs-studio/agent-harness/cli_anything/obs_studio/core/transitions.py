"""OBS Studio CLI - Transition management."""

import copy
from typing import Dict, Any, List, Optional
from cli_anything.obs_studio.utils.obs_utils import unique_name, get_item


TRANSITION_TYPES = {
    "cut": {"label": "Cut", "default_duration": 0},
    "fade": {"label": "Fade", "default_duration": 300},
    "swipe": {"label": "Swipe", "default_duration": 500},
    "slide": {"label": "Slide", "default_duration": 500},
    "stinger": {"label": "Stinger", "default_duration": 1000},
    "fade_to_color": {"label": "Fade to Color", "default_duration": 300},
    "luma_wipe": {"label": "Luma Wipe", "default_duration": 500},
}


def _get_transitions(project: Dict[str, Any]) -> List[Dict[str, Any]]:
    return project.setdefault("transitions", [])


def add_transition(
    project: Dict[str, Any],
    transition_type: str,
    name: Optional[str] = None,
    duration: Optional[int] = None,
) -> Dict[str, Any]:
    """Add a transition."""
    if transition_type not in TRANSITION_TYPES:
        raise ValueError(
            f"Unknown transition type: {transition_type}. Valid: {', '.join(sorted(TRANSITION_TYPES.keys()))}"
        )

    spec = TRANSITION_TYPES[transition_type]
    transitions = _get_transitions(project)

    if name is None:
        name = spec["label"]
    name = unique_name(name, transitions)

    if duration is None:
        duration = spec["default_duration"]
    if duration < 0:
        raise ValueError(f"Duration must be non-negative: {duration}")

    trans = {
        "name": name,
        "type": transition_type,
        "duration": duration,
    }
    transitions.append(trans)
    return trans


def remove_transition(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Remove a transition by index."""
    transitions = _get_transitions(project)
    trans = get_item(transitions, index, "transition")
    if len(transitions) <= 1:
        raise ValueError("Cannot remove the last transition. At least one must exist.")
    return transitions.pop(index)


def set_duration(project: Dict[str, Any], index: int, duration: int) -> Dict[str, Any]:
    """Set the duration of a transition in milliseconds."""
    transitions = _get_transitions(project)
    trans = get_item(transitions, index, "transition")
    if duration < 0:
        raise ValueError(f"Duration must be non-negative: {duration}")
    trans["duration"] = duration
    return trans


def set_active_transition(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Set the active transition by index."""
    transitions = _get_transitions(project)
    trans = get_item(transitions, index, "transition")
    project["active_transition"] = index
    return {"active_transition": trans["name"], "index": index}


def list_transitions(project: Dict[str, Any]) -> List[Dict[str, Any]]:
    """List all transitions."""
    transitions = _get_transitions(project)
    active = project.get("active_transition", 0)
    return [
        {
            "index": i,
            "name": t.get("name", f"Transition {i}"),
            "type": t.get("type", "cut"),
            "duration": t.get("duration", 0),
            "active": i == active,
        }
        for i, t in enumerate(transitions)
    ]
