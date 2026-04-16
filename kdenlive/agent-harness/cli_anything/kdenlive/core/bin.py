"""Kdenlive CLI - Media bin management module."""

from typing import Dict, Any, List, Optional


CLIP_TYPES = ("video", "audio", "image", "color", "title")


def _next_clip_id(project: Dict[str, Any]) -> str:
    """Generate next unique clip ID."""
    existing = {c["id"] for c in project.get("bin", [])}
    idx = 0
    while f"clip{idx}" in existing:
        idx += 1
    return f"clip{idx}"


def _unique_clip_name(project: Dict[str, Any], name: str) -> str:
    """Ensure unique clip name in bin."""
    existing = {c.get("name", "") for c in project.get("bin", [])}
    if name not in existing:
        return name
    i = 1
    while f"{name}.{i:03d}" in existing:
        i += 1
    return f"{name}.{i:03d}"


def import_clip(
    project: Dict[str, Any],
    source: str,
    name: Optional[str] = None,
    duration: float = 0.0,
    clip_type: str = "video",
) -> Dict[str, Any]:
    """Import a clip into the project bin."""
    if clip_type not in CLIP_TYPES:
        raise ValueError(
            f"Invalid clip type: {clip_type}. Must be one of: {', '.join(CLIP_TYPES)}"
        )
    if duration < 0:
        raise ValueError(f"Duration must be non-negative: {duration}")

    if name is None:
        # Derive name from source path
        import os
        name = os.path.splitext(os.path.basename(source))[0]

    name = _unique_clip_name(project, name)
    clip_id = _next_clip_id(project)

    clip = {
        "id": clip_id,
        "name": name,
        "source": source,
        "duration": duration,
        "type": clip_type,
    }
    project.setdefault("bin", []).append(clip)
    return clip


def remove_clip(project: Dict[str, Any], clip_id: str) -> Dict[str, Any]:
    """Remove a clip from the bin by ID."""
    bin_clips = project.get("bin", [])
    for i, clip in enumerate(bin_clips):
        if clip["id"] == clip_id:
            return bin_clips.pop(i)
    raise ValueError(f"Clip not found: {clip_id}")


def list_clips(project: Dict[str, Any]) -> List[Dict[str, Any]]:
    """List all clips in the bin."""
    return [
        {
            "id": c["id"],
            "name": c.get("name", ""),
            "source": c.get("source", ""),
            "duration": c.get("duration", 0),
            "type": c.get("type", "video"),
        }
        for c in project.get("bin", [])
    ]


def get_clip(project: Dict[str, Any], clip_id: str) -> Dict[str, Any]:
    """Get a clip by ID."""
    for clip in project.get("bin", []):
        if clip["id"] == clip_id:
            return dict(clip)
    raise ValueError(f"Clip not found: {clip_id}")
