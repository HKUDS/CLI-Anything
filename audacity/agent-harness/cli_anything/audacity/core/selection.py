"""Audacity CLI - Selection management module.

Manages the current selection range (start and end time) within the project.
The selection determines which portion of the timeline is affected by
operations like effects, cut, copy, paste.
"""

from typing import Dict, Any


def set_selection(
    project: Dict[str, Any],
    start: float,
    end: float,
) -> Dict[str, Any]:
    """Set the selection range."""
    if start < 0:
        raise ValueError(f"Selection start must be >= 0, got {start}")
    if end < start:
        raise ValueError(f"Selection end ({end}) must be >= start ({start})")

    sel = {"start": start, "end": end}
    project["selection"] = sel
    return sel


def select_all(project: Dict[str, Any]) -> Dict[str, Any]:
    """Select the entire project duration (from 0 to max track end)."""
    max_end = 0.0
    for t in project.get("tracks", []):
        for c in t.get("clips", []):
            end = c.get("end_time", 0.0)
            if end > max_end:
                max_end = end

    # If no clips, select 0-0
    sel = {"start": 0.0, "end": max_end}
    project["selection"] = sel
    return sel


def select_none(project: Dict[str, Any]) -> Dict[str, Any]:
    """Clear the selection."""
    sel = {"start": 0.0, "end": 0.0}
    project["selection"] = sel
    return sel


def get_selection(project: Dict[str, Any]) -> Dict[str, Any]:
    """Get the current selection range."""
    sel = project.get("selection", {"start": 0.0, "end": 0.0})
    duration = sel.get("end", 0.0) - sel.get("start", 0.0)
    return {
        "start": sel.get("start", 0.0),
        "end": sel.get("end", 0.0),
        "duration": round(duration, 3),
        "has_selection": duration > 0,
    }
