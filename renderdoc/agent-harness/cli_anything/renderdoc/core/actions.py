"""
Action (draw call) inspection: list, search, navigate the action tree.

Works with a CaptureHandle's ReplayController to enumerate draw calls,
clears, dispatches, and other GPU actions recorded in a frame capture.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    import renderdoc as rd

    HAS_RD = True
except ImportError:
    rd = None  # type: ignore[assignment]
    HAS_RD = False


# ---------------------------------------------------------------------------
# Action helpers
# ---------------------------------------------------------------------------

def _action_to_dict(action, structured_file=None) -> Dict[str, Any]:
    """Serialise one ActionDescription to a plain dict."""
    name = action.customName
    if not name and structured_file is not None:
        name = action.GetName(structured_file)
    flags_list = _decode_flags(action.flags)
    return {
        "eventId": action.eventId,
        "actionId": action.actionId,
        "name": name or "",
        "flags": flags_list,
        "numIndices": action.numIndices,
        "numInstances": action.numInstances,
        "indexOffset": action.indexOffset,
        "baseVertex": action.baseVertex,
        "vertexOffset": action.vertexOffset,
        "instanceOffset": action.instanceOffset,
        "outputs": [str(o) for o in action.outputs],
        "depthOut": str(action.depthOut),
        "children_count": len(action.children),
    }


def _decode_flags(flags) -> List[str]:
    """Decode ActionFlags bitmask into list of human-readable names."""
    if rd is None:
        return []
    names = []
    flag_map = {
        rd.ActionFlags.Clear: "Clear",
        rd.ActionFlags.Drawcall: "Drawcall",
        rd.ActionFlags.Dispatch: "Dispatch",
        rd.ActionFlags.CmdList: "CmdList",
        rd.ActionFlags.SetMarker: "SetMarker",
        rd.ActionFlags.PushMarker: "PushMarker",
        rd.ActionFlags.PopMarker: "PopMarker",
        rd.ActionFlags.Present: "Present",
        rd.ActionFlags.MultiAction: "MultiAction",
        rd.ActionFlags.Copy: "Copy",
        rd.ActionFlags.Resolve: "Resolve",
        rd.ActionFlags.GenMips: "GenMips",
        rd.ActionFlags.PassBoundary: "PassBoundary",
        rd.ActionFlags.Indexed: "Indexed",
        rd.ActionFlags.Instanced: "Instanced",
        rd.ActionFlags.Auto: "Auto",
        rd.ActionFlags.Indirect: "Indirect",
        rd.ActionFlags.ClearColor: "ClearColor",
        rd.ActionFlags.ClearDepthStencil: "ClearDepthStencil",
        rd.ActionFlags.BeginPass: "BeginPass",
        rd.ActionFlags.EndPass: "EndPass",
    }
    for flag_val, flag_name in flag_map.items():
        if flags & flag_val:
            names.append(flag_name)
    return names


# ---------------------------------------------------------------------------
# Flat enumeration
# ---------------------------------------------------------------------------

def _flatten_actions(actions, out: list, structured_file=None, depth: int = 0):
    """Recursively flatten action tree."""
    for a in actions:
        d = _action_to_dict(a, structured_file)
        d["depth"] = depth
        out.append(d)
        if len(a.children) > 0:
            _flatten_actions(a.children, out, structured_file, depth + 1)


def list_actions(controller, flat: bool = True) -> List[Dict[str, Any]]:
    """Return all actions in the capture.

    Parameters
    ----------
    controller : rd.ReplayController
    flat : bool
        If True (default), return a flat list with a ``depth`` key.
        If False, return only root-level actions.
    """
    sf = controller.GetStructuredFile()
    root_actions = controller.GetRootActions()
    if flat:
        result: List[Dict[str, Any]] = []
        _flatten_actions(root_actions, result, sf)
        return result
    return [_action_to_dict(a, sf) for a in root_actions]


def find_action_by_event(controller, event_id: int) -> Optional[Dict[str, Any]]:
    """Find a single action by its eventId."""
    sf = controller.GetStructuredFile()
    # Use the flat list and filter
    all_actions: List[Dict[str, Any]] = []
    _flatten_actions(controller.GetRootActions(), all_actions, sf)
    for a in all_actions:
        if a["eventId"] == event_id:
            return a
    return None


def find_actions_by_name(controller, pattern: str) -> List[Dict[str, Any]]:
    """Find actions whose name contains *pattern* (case-insensitive)."""
    sf = controller.GetStructuredFile()
    all_actions: List[Dict[str, Any]] = []
    _flatten_actions(controller.GetRootActions(), all_actions, sf)
    pat = pattern.lower()
    return [a for a in all_actions if pat in a["name"].lower()]


def get_drawcalls_only(controller) -> List[Dict[str, Any]]:
    """Return only actual draw calls (not markers, clears, etc.)."""
    all_actions = list_actions(controller, flat=True)
    return [a for a in all_actions if "Drawcall" in a["flags"]]


def action_summary(controller) -> Dict[str, Any]:
    """High-level summary: counts of different action types."""
    all_actions = list_actions(controller, flat=True)
    summary = {
        "total_actions": len(all_actions),
        "drawcalls": 0,
        "clears": 0,
        "dispatches": 0,
        "copies": 0,
        "markers": 0,
        "presents": 0,
    }
    for a in all_actions:
        flags = a["flags"]
        if "Drawcall" in flags:
            summary["drawcalls"] += 1
        if "Clear" in flags:
            summary["clears"] += 1
        if "Dispatch" in flags:
            summary["dispatches"] += 1
        if "Copy" in flags:
            summary["copies"] += 1
        if "PushMarker" in flags or "SetMarker" in flags:
            summary["markers"] += 1
        if "Present" in flags:
            summary["presents"] += 1
    return summary
