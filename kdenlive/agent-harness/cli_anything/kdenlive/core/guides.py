"""Kdenlive CLI - Guide/marker management module."""

from typing import Dict, Any, List, Optional


GUIDE_TYPES = ("default", "chapter", "segment")


def _next_guide_id(project: Dict[str, Any]) -> int:
    """Generate next unique guide ID."""
    existing = {g.get("id", -1) for g in project.get("guides", [])}
    idx = 0
    while idx in existing:
        idx += 1
    return idx


def add_guide(
    project: Dict[str, Any],
    position: float,
    label: str = "",
    guide_type: str = "default",
    comment: str = "",
) -> Dict[str, Any]:
    """Add a guide/marker at a position (in seconds)."""
    if position < 0:
        raise ValueError(f"Position must be non-negative: {position}")
    if guide_type not in GUIDE_TYPES:
        raise ValueError(
            f"Invalid guide type: {guide_type}. Must be one of: {', '.join(GUIDE_TYPES)}"
        )

    gid = _next_guide_id(project)
    guide = {
        "id": gid,
        "position": position,
        "label": label,
        "type": guide_type,
        "comment": comment,
    }
    project.setdefault("guides", []).append(guide)
    # Sort guides by position
    project["guides"].sort(key=lambda g: g["position"])
    return guide


def remove_guide(project: Dict[str, Any], guide_id: int) -> Dict[str, Any]:
    """Remove a guide by ID."""
    guides = project.get("guides", [])
    for i, g in enumerate(guides):
        if g["id"] == guide_id:
            return guides.pop(i)
    raise ValueError(f"Guide not found: {guide_id}")


def list_guides(project: Dict[str, Any]) -> List[Dict[str, Any]]:
    """List all guides."""
    return [
        {
            "id": g["id"],
            "position": g["position"],
            "label": g.get("label", ""),
            "type": g.get("type", "default"),
            "comment": g.get("comment", ""),
        }
        for g in project.get("guides", [])
    ]
