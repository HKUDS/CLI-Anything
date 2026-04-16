"""Transition management: add, remove, configure transitions between clips."""

from typing import Optional
from lxml import etree

from ..utils import mlt_xml
from .session import Session


# Registry of available transition types
TRANSITION_REGISTRY = {
    "dissolve": {
        "service": "luma",
        "category": "video",
        "description": "Cross-dissolve between two clips",
        "params": {
            "softness": {"type": "float", "default": "0", "range": "0.0-1.0",
                         "description": "Edge softness of the transition"},
            "invert": {"type": "int", "default": "0",
                       "description": "Invert the transition (0 or 1)"},
        },
    },
    "wipe-left": {
        "service": "luma",
        "category": "video",
        "description": "Wipe from right to left",
        "params": {
            "resource": {"type": "string", "default": "%luma01.pgm",
                         "description": "Luma pattern file"},
            "softness": {"type": "float", "default": "0.1", "range": "0.0-1.0",
                         "description": "Edge softness"},
        },
    },
    "wipe-right": {
        "service": "luma",
        "category": "video",
        "description": "Wipe from left to right",
        "params": {
            "resource": {"type": "string", "default": "%luma01.pgm",
                         "description": "Luma pattern file"},
            "softness": {"type": "float", "default": "0.1", "range": "0.0-1.0",
                         "description": "Edge softness"},
            "invert": {"type": "int", "default": "1",
                       "description": "Invert direction"},
        },
    },
    "wipe-down": {
        "service": "luma",
        "category": "video",
        "description": "Wipe from top to bottom",
        "params": {
            "resource": {"type": "string", "default": "%luma04.pgm",
                         "description": "Luma pattern file (vertical)"},
            "softness": {"type": "float", "default": "0.1", "range": "0.0-1.0",
                         "description": "Edge softness"},
        },
    },
    "wipe-up": {
        "service": "luma",
        "category": "video",
        "description": "Wipe from bottom to top",
        "params": {
            "resource": {"type": "string", "default": "%luma04.pgm",
                         "description": "Luma pattern file (vertical)"},
            "softness": {"type": "float", "default": "0.1", "range": "0.0-1.0",
                         "description": "Edge softness"},
            "invert": {"type": "int", "default": "1",
                       "description": "Invert direction"},
        },
    },
    "bar-horizontal": {
        "service": "luma",
        "category": "video",
        "description": "Horizontal bars wipe",
        "params": {
            "resource": {"type": "string", "default": "%luma05.pgm",
                         "description": "Luma pattern file"},
            "softness": {"type": "float", "default": "0.1", "range": "0.0-1.0",
                         "description": "Edge softness"},
        },
    },
    "bar-vertical": {
        "service": "luma",
        "category": "video",
        "description": "Vertical bars wipe",
        "params": {
            "resource": {"type": "string", "default": "%luma06.pgm",
                         "description": "Luma pattern file"},
            "softness": {"type": "float", "default": "0.1", "range": "0.0-1.0",
                         "description": "Edge softness"},
        },
    },
    "diagonal": {
        "service": "luma",
        "category": "video",
        "description": "Diagonal wipe",
        "params": {
            "resource": {"type": "string", "default": "%luma07.pgm",
                         "description": "Luma pattern file (diagonal)"},
            "softness": {"type": "float", "default": "0.1", "range": "0.0-1.0",
                         "description": "Edge softness"},
        },
    },
    "clock": {
        "service": "luma",
        "category": "video",
        "description": "Clock wipe (radial sweep)",
        "params": {
            "resource": {"type": "string", "default": "%luma16.pgm",
                         "description": "Luma pattern file (clock)"},
            "softness": {"type": "float", "default": "0.1", "range": "0.0-1.0",
                         "description": "Edge softness"},
        },
    },
    "iris-circle": {
        "service": "luma",
        "category": "video",
        "description": "Circular iris wipe",
        "params": {
            "resource": {"type": "string", "default": "%luma22.pgm",
                         "description": "Luma pattern file (iris)"},
            "softness": {"type": "float", "default": "0.2", "range": "0.0-1.0",
                         "description": "Edge softness"},
        },
    },
    "crossfade": {
        "service": "mix",
        "category": "audio",
        "description": "Audio crossfade between clips",
        "params": {
            "start": {"type": "float", "default": "0.0", "range": "0.0-1.0",
                      "description": "Start mix level"},
            "end": {"type": "float", "default": "1.0", "range": "0.0-1.0",
                    "description": "End mix level"},
        },
    },
}


def list_available_transitions(category: Optional[str] = None) -> list[dict]:
    """List all available transition types."""
    result = []
    for name, info in sorted(TRANSITION_REGISTRY.items()):
        if category and info["category"] != category:
            continue
        result.append({
            "name": name,
            "service": info["service"],
            "category": info["category"],
            "description": info["description"],
            "params": list(info["params"].keys()),
        })
    return result


def get_transition_info(transition_name: str) -> dict:
    """Get detailed info about a transition type."""
    if transition_name not in TRANSITION_REGISTRY:
        available = ", ".join(sorted(TRANSITION_REGISTRY.keys()))
        raise ValueError(f"Unknown transition: {transition_name!r}. Available: {available}")
    info = dict(TRANSITION_REGISTRY[transition_name])
    info["name"] = transition_name
    return info


def add_transition(session: Session, transition_name: str,
                   track_a: int, track_b: int,
                   in_point: Optional[str] = None,
                   out_point: Optional[str] = None,
                   params: Optional[dict] = None) -> dict:
    """Add a transition between two tracks.

    In MLT, transitions blend between two tracks over a time range.
    The clips must overlap on the timeline for the transition to be visible.

    Args:
        session: Active session
        transition_name: Name from TRANSITION_REGISTRY or raw MLT service
        track_a: Source track index (bottom/background)
        track_b: Destination track index (top/foreground)
        in_point: Start timecode of the transition
        out_point: End timecode of the transition
        params: Parameter overrides
    """
    session.checkpoint()

    tractor = session.get_main_tractor()
    tracks = mlt_xml.get_tractor_tracks(tractor)

    if track_a < 0 or track_a >= len(tracks):
        raise IndexError(f"Track A index {track_a} out of range")
    if track_b < 0 or track_b >= len(tracks):
        raise IndexError(f"Track B index {track_b} out of range")

    # Resolve transition from registry or use as raw service
    if transition_name in TRANSITION_REGISTRY:
        reg = TRANSITION_REGISTRY[transition_name]
        service = reg["service"]
        props = {}
        for pname, pinfo in reg["params"].items():
            props[pname] = pinfo["default"]
        if params:
            props.update(params)
    else:
        service = transition_name
        props = params or {}

    # Create the transition element
    trans = etree.SubElement(tractor, "transition")
    trans_id = mlt_xml.new_id("transition")
    trans.set("id", trans_id)
    if in_point:
        trans.set("in", in_point)
    if out_point:
        trans.set("out", out_point)

    mlt_xml.set_property(trans, "a_track", str(track_a))
    mlt_xml.set_property(trans, "b_track", str(track_b))
    mlt_xml.set_property(trans, "mlt_service", service)

    for key, val in props.items():
        mlt_xml.set_property(trans, key, str(val))

    return {
        "action": "add_transition",
        "transition_name": transition_name,
        "service": service,
        "transition_id": trans_id,
        "track_a": track_a,
        "track_b": track_b,
        "in_point": in_point,
        "out_point": out_point,
        "params": props,
    }


def remove_transition(session: Session, transition_index: int) -> dict:
    """Remove a transition by index.

    Only removes user-added transitions, not the system compositing
    transitions (always_active mix/blend).
    """
    session.checkpoint()
    tractor = session.get_main_tractor()
    transitions = _get_user_transitions(tractor)

    if transition_index < 0 or transition_index >= len(transitions):
        raise IndexError(f"Transition index {transition_index} out of range "
                         f"(0-{len(transitions)-1})")

    trans = transitions[transition_index]
    trans_id = trans.get("id")
    service = mlt_xml.get_property(trans, "mlt_service", "")
    tractor.remove(trans)

    return {
        "action": "remove_transition",
        "transition_index": transition_index,
        "transition_id": trans_id,
        "service": service,
    }


def set_transition_param(session: Session, transition_index: int,
                         param_name: str, param_value: str) -> dict:
    """Set a parameter on a transition."""
    session.checkpoint()
    tractor = session.get_main_tractor()
    transitions = _get_user_transitions(tractor)

    if transition_index < 0 or transition_index >= len(transitions):
        raise IndexError(f"Transition index {transition_index} out of range")

    trans = transitions[transition_index]
    old_value = mlt_xml.get_property(trans, param_name)
    mlt_xml.set_property(trans, param_name, param_value)

    return {
        "action": "set_transition_param",
        "transition_index": transition_index,
        "param": param_name,
        "old_value": old_value,
        "new_value": param_value,
    }


def list_transitions(session: Session) -> list[dict]:
    """List all user-added transitions on the timeline."""
    tractor = session.get_main_tractor()
    transitions = _get_user_transitions(tractor)

    result = []
    for i, trans in enumerate(transitions):
        service = mlt_xml.get_property(trans, "mlt_service", "")
        a_track = mlt_xml.get_property(trans, "a_track", "")
        b_track = mlt_xml.get_property(trans, "b_track", "")

        props = {}
        for prop in trans.findall("property"):
            name = prop.get("name", "")
            if name and name not in ("mlt_service", "a_track", "b_track",
                                      "always_active", "sum"):
                props[name] = prop.text or ""

        result.append({
            "index": i,
            "id": trans.get("id"),
            "service": service,
            "track_a": a_track,
            "track_b": b_track,
            "in": trans.get("in"),
            "out": trans.get("out"),
            "params": props,
        })

    return result


def _get_user_transitions(tractor: etree._Element) -> list[etree._Element]:
    """Get transitions that are user-added (not system compositing ones).

    System transitions have always_active=1 and are auto-created
    when tracks are added. User transitions have explicit in/out points
    or don't have always_active.
    """
    all_transitions = tractor.findall("transition")
    user_transitions = []
    for t in all_transitions:
        always_active = mlt_xml.get_property(t, "always_active", "0")
        if always_active != "1":
            user_transitions.append(t)
    return user_transitions
