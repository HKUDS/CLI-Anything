"""Audacity CLI - Label/marker management module.

Labels mark timestamps or time ranges in an audio project.
They are commonly used for marking sections, timestamps for
transcription, and chapter markers.
"""

from typing import Dict, Any, List, Optional


def add_label(
    project: Dict[str, Any],
    start: float,
    end: Optional[float] = None,
    text: str = "",
) -> Dict[str, Any]:
    """Add a label to the project."""
    labels = project.setdefault("labels", [])

    if start < 0:
        raise ValueError(f"Label start must be >= 0, got {start}")
    if end is not None and end < start:
        raise ValueError(f"Label end ({end}) must be >= start ({start})")

    if end is None:
        end = start

    # Generate unique ID
    existing_ids = {l.get("id", i) for i, l in enumerate(labels)}
    new_id = 0
    while new_id in existing_ids:
        new_id += 1

    label = {
        "id": new_id,
        "start": start,
        "end": end,
        "text": text,
    }
    labels.append(label)
    return label


def remove_label(
    project: Dict[str, Any],
    label_index: int,
) -> Dict[str, Any]:
    """Remove a label by index."""
    labels = project.get("labels", [])
    if label_index < 0 or label_index >= len(labels):
        raise IndexError(
            f"Label index {label_index} out of range (0-{len(labels) - 1})"
        )
    return labels.pop(label_index)


def list_labels(project: Dict[str, Any]) -> List[Dict[str, Any]]:
    """List all labels in the project."""
    labels = project.get("labels", [])
    result = []
    for i, l in enumerate(labels):
        is_range = l.get("start", 0) != l.get("end", 0)
        result.append({
            "index": i,
            "id": l.get("id", i),
            "start": l.get("start", 0.0),
            "end": l.get("end", 0.0),
            "text": l.get("text", ""),
            "type": "range" if is_range else "point",
            "duration": round(l.get("end", 0.0) - l.get("start", 0.0), 3),
        })
    return result
