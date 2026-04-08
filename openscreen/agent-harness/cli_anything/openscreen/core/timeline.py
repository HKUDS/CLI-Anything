"""Timeline operations — zoom, speed, trim, crop, and annotation regions.

Each region type maps directly to Openscreen's data model:
- ZoomRegion: startMs, endMs, depth (1-6), focus (cx, cy), focusMode
- SpeedRegion: startMs, endMs, speed (0.25-2.0)
- TrimRegion: startMs, endMs
- AnnotationRegion: startMs, endMs, type, content, position, size, style
- CropRegion: x, y, width, height (all normalized 0-1)
"""

import uuid
from typing import Optional

from .session import Session


# ── Constants ────────────────────────────────────────────────────────────

ZOOM_DEPTHS = {1: 1.25, 2: 1.5, 3: 1.8, 4: 2.2, 5: 3.5, 6: 5.0}
VALID_SPEEDS = [0.25, 0.5, 0.75, 1.25, 1.5, 1.75, 2.0]
ANNOTATION_TYPES = ["text", "image", "figure"]
ARROW_DIRECTIONS = [
    "up", "down", "left", "right",
    "up-right", "up-left", "down-right", "down-left",
]


def _gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _validate_time_range(start_ms: int, end_ms: int) -> None:
    """Validate that start_ms >= 0 and end_ms > start_ms."""
    if start_ms < 0:
        raise ValueError(f"start_ms must be >= 0, got {start_ms}")
    if end_ms <= start_ms:
        raise ValueError(f"end_ms ({end_ms}) must be > start_ms ({start_ms})")


# ── Zoom regions ─────────────────────────────────────────────────────────

def list_zoom_regions(session: Session) -> list[dict]:
    """List all zoom regions."""
    if not session.is_open:
        raise RuntimeError("No project is open")
    regions = session.editor.get("zoomRegions", [])
    return sorted(regions, key=lambda r: r["startMs"])


def add_zoom_region(
    session: Session,
    start_ms: int,
    end_ms: int,
    depth: int = 3,
    focus_x: float = 0.5,
    focus_y: float = 0.5,
    focus_mode: str = "manual",
) -> dict:
    """Add a zoom region to the timeline."""
    if not session.is_open:
        raise RuntimeError("No project is open")
    if depth not in ZOOM_DEPTHS:
        raise ValueError(f"Invalid depth {depth}. Valid: {list(ZOOM_DEPTHS.keys())}")
    if not 0 <= focus_x <= 1 or not 0 <= focus_y <= 1:
        raise ValueError("Focus coordinates must be 0.0-1.0")
    _validate_time_range(start_ms, end_ms)

    session.checkpoint()
    region = {
        "id": _gen_id("zoom"),
        "startMs": start_ms,
        "endMs": end_ms,
        "depth": depth,
        "focus": {"cx": focus_x, "cy": focus_y},
        "focusMode": focus_mode,
    }
    session.editor.setdefault("zoomRegions", []).append(region)
    return region


def remove_zoom_region(session: Session, region_id: str) -> dict:
    """Remove a zoom region by ID."""
    if not session.is_open:
        raise RuntimeError("No project is open")
    session.checkpoint()
    regions = session.editor.get("zoomRegions", [])
    before = len(regions)
    session.editor["zoomRegions"] = [r for r in regions if r["id"] != region_id]
    removed = before - len(session.editor["zoomRegions"])
    if removed == 0:
        raise ValueError(f"Zoom region not found: {region_id}")
    return {"status": "removed", "id": region_id}


# ── Speed regions ────────────────────────────────────────────────────────

def list_speed_regions(session: Session) -> list[dict]:
    """List all speed regions."""
    if not session.is_open:
        raise RuntimeError("No project is open")
    regions = session.editor.get("speedRegions", [])
    return sorted(regions, key=lambda r: r["startMs"])


def add_speed_region(
    session: Session,
    start_ms: int,
    end_ms: int,
    speed: float = 1.5,
) -> dict:
    """Add a speed region to the timeline."""
    if not session.is_open:
        raise RuntimeError("No project is open")
    if speed not in VALID_SPEEDS:
        raise ValueError(f"Invalid speed {speed}. Valid: {VALID_SPEEDS}")
    _validate_time_range(start_ms, end_ms)

    session.checkpoint()
    region = {
        "id": _gen_id("speed"),
        "startMs": start_ms,
        "endMs": end_ms,
        "speed": speed,
    }
    session.editor.setdefault("speedRegions", []).append(region)
    return region


def remove_speed_region(session: Session, region_id: str) -> dict:
    """Remove a speed region by ID."""
    if not session.is_open:
        raise RuntimeError("No project is open")
    session.checkpoint()
    regions = session.editor.get("speedRegions", [])
    before = len(regions)
    session.editor["speedRegions"] = [r for r in regions if r["id"] != region_id]
    if before - len(session.editor["speedRegions"]) == 0:
        raise ValueError(f"Speed region not found: {region_id}")
    return {"status": "removed", "id": region_id}


# ── Trim regions ─────────────────────────────────────────────────────────

def list_trim_regions(session: Session) -> list[dict]:
    """List all trim regions."""
    if not session.is_open:
        raise RuntimeError("No project is open")
    regions = session.editor.get("trimRegions", [])
    return sorted(regions, key=lambda r: r["startMs"])


def add_trim_region(session: Session, start_ms: int, end_ms: int) -> dict:
    """Add a trim (cut) region to the timeline."""
    if not session.is_open:
        raise RuntimeError("No project is open")
    _validate_time_range(start_ms, end_ms)

    session.checkpoint()
    region = {
        "id": _gen_id("trim"),
        "startMs": start_ms,
        "endMs": end_ms,
    }
    session.editor.setdefault("trimRegions", []).append(region)
    return region


def remove_trim_region(session: Session, region_id: str) -> dict:
    """Remove a trim region by ID."""
    if not session.is_open:
        raise RuntimeError("No project is open")
    session.checkpoint()
    regions = session.editor.get("trimRegions", [])
    before = len(regions)
    session.editor["trimRegions"] = [r for r in regions if r["id"] != region_id]
    if before - len(session.editor["trimRegions"]) == 0:
        raise ValueError(f"Trim region not found: {region_id}")
    return {"status": "removed", "id": region_id}


# ── Crop ─────────────────────────────────────────────────────────────────

def get_crop(session: Session) -> dict:
    """Get current crop region."""
    if not session.is_open:
        raise RuntimeError("No project is open")
    return session.editor.get("cropRegion", {"x": 0, "y": 0, "width": 1, "height": 1})


def set_crop(session: Session, x: float, y: float, w: float, h: float) -> dict:
    """Set crop region (all values normalized 0-1)."""
    if not session.is_open:
        raise RuntimeError("No project is open")
    for val, name in [(x, "x"), (y, "y"), (w, "width"), (h, "height")]:
        if not 0 <= val <= 1:
            raise ValueError(f"{name} must be 0.0-1.0, got {val}")
    if x + w > 1.001 or y + h > 1.001:
        raise ValueError("Crop region extends beyond frame boundaries")

    session.checkpoint()
    session.editor["cropRegion"] = {"x": x, "y": y, "width": w, "height": h}
    return session.editor["cropRegion"]


# ── Annotations ──────────────────────────────────────────────────────────

def list_annotations(session: Session) -> list[dict]:
    """List all annotation regions."""
    if not session.is_open:
        raise RuntimeError("No project is open")
    regions = session.editor.get("annotationRegions", [])
    return sorted(regions, key=lambda r: r["startMs"])


def add_text_annotation(
    session: Session,
    start_ms: int,
    end_ms: int,
    text: str,
    x: float = 0.5,
    y: float = 0.5,
    font_size: int = 32,
    color: str = "#ffffff",
    bg_color: str = "#000000",
) -> dict:
    """Add a text annotation to the timeline."""
    if not session.is_open:
        raise RuntimeError("No project is open")
    _validate_time_range(start_ms, end_ms)

    session.checkpoint()
    region = {
        "id": _gen_id("ann"),
        "startMs": start_ms,
        "endMs": end_ms,
        "type": "text",
        "textContent": text,
        "content": text,
        "position": {"x": x, "y": y},
        "size": {"width": 0.3, "height": 0.1},
        "style": {
            "color": color,
            "backgroundColor": bg_color,
            "fontSize": font_size,
            "fontFamily": "Inter",
            "fontWeight": "normal",
            "fontStyle": "normal",
            "textDecoration": "none",
            "textAlign": "center",
        },
        "zIndex": 1,
    }
    session.editor.setdefault("annotationRegions", []).append(region)
    return region


def remove_annotation(session: Session, region_id: str) -> dict:
    """Remove an annotation by ID."""
    if not session.is_open:
        raise RuntimeError("No project is open")
    session.checkpoint()
    regions = session.editor.get("annotationRegions", [])
    before = len(regions)
    session.editor["annotationRegions"] = [r for r in regions if r["id"] != region_id]
    if before - len(session.editor["annotationRegions"]) == 0:
        raise ValueError(f"Annotation not found: {region_id}")
    return {"status": "removed", "id": region_id}


# ── Update / query helpers (added from auto version) ─────────────────────

def update_zoom_region(
    session: Session,
    region_id: str,
    start_ms: Optional[int] = None,
    end_ms: Optional[int] = None,
    depth: Optional[int] = None,
    focus_x: Optional[float] = None,
    focus_y: Optional[float] = None,
) -> dict:
    """Update an existing zoom region.

    Only the keyword arguments that are provided are changed; omitted arguments
    leave the corresponding field unchanged.

    Args:
        session: Active Session instance.
        region_id: ID of the zoom region to update.
        start_ms: New start time in milliseconds.
        end_ms: New end time in milliseconds.
        depth: New zoom depth (1-6).
        focus_x: New horizontal focus center (0.0-1.0).
        focus_y: New vertical focus center (0.0-1.0).

    Returns:
        The updated region dict.

    Raises:
        RuntimeError: If no project is open.
        ValueError: If region_id is not found or parameters are invalid.
    """
    if not session.is_open:
        raise RuntimeError("No project is open")
    regions = session.editor.get("zoomRegions", [])
    region = next((r for r in regions if r.get("id") == region_id), None)
    if region is None:
        raise ValueError(f"Zoom region not found: {region_id}")

    new_start = start_ms if start_ms is not None else region["startMs"]
    new_end = end_ms if end_ms is not None else region["endMs"]
    _validate_time_range(new_start, new_end)

    new_depth = depth if depth is not None else region["depth"]
    if new_depth not in ZOOM_DEPTHS:
        raise ValueError(f"Invalid depth {new_depth}. Valid: {list(ZOOM_DEPTHS.keys())}")

    new_fx = focus_x if focus_x is not None else region["focus"]["cx"]
    new_fy = focus_y if focus_y is not None else region["focus"]["cy"]
    if not 0 <= new_fx <= 1 or not 0 <= new_fy <= 1:
        raise ValueError("Focus coordinates must be 0.0-1.0")

    session.checkpoint()
    region["startMs"] = new_start
    region["endMs"] = new_end
    region["depth"] = new_depth
    region["focus"]["cx"] = new_fx
    region["focus"]["cy"] = new_fy
    return region


def update_annotation(session: Session, region_id: str, **kwargs) -> dict:
    """Update fields on an existing annotation region.

    Supported kwargs: start_ms, end_ms, text_content, position_x, position_y,
    size, color, background_color, font_size, font_family.

    Args:
        session: Active Session instance.
        region_id: ID of the annotation to update.
        **kwargs: Fields to update (see above).

    Returns:
        The updated region dict.

    Raises:
        RuntimeError: If no project is open.
        ValueError: If region_id is not found.
    """
    if not session.is_open:
        raise RuntimeError("No project is open")
    regions = session.editor.get("annotationRegions", [])
    region = next((r for r in regions if r.get("id") == region_id), None)
    if region is None:
        raise ValueError(f"Annotation not found: {region_id}")

    session.checkpoint()

    if "start_ms" in kwargs:
        region["startMs"] = int(kwargs["start_ms"])
    if "end_ms" in kwargs:
        region["endMs"] = int(kwargs["end_ms"])
    if "text_content" in kwargs:
        region["textContent"] = str(kwargs["text_content"])
        region["content"] = str(kwargs["text_content"])
    if "position_x" in kwargs:
        region["position"]["x"] = float(kwargs["position_x"])
    if "position_y" in kwargs:
        region["position"]["y"] = float(kwargs["position_y"])
    if "size" in kwargs:
        region["size"] = kwargs["size"]
    if "color" in kwargs:
        region["style"]["color"] = str(kwargs["color"])
    if "background_color" in kwargs:
        region["style"]["backgroundColor"] = str(kwargs["background_color"])
    if "font_size" in kwargs:
        region["style"]["fontSize"] = int(kwargs["font_size"])
    if "font_family" in kwargs:
        region["style"]["fontFamily"] = str(kwargs["font_family"])

    return region


def get_timeline_boundaries(session: Session) -> list[int]:
    """Return a sorted list of all unique time boundary points (in ms).

    Includes 0 and all startMs/endMs values from zoom, speed, trim, and
    annotation regions. Useful for computing rendering segments.

    Args:
        session: Active Session instance.

    Returns:
        Sorted list of unique boundary millisecond values.

    Raises:
        RuntimeError: If no project is open.
    """
    if not session.is_open:
        raise RuntimeError("No project is open")
    ed = session.editor
    boundaries = {0}
    for region_key in ("zoomRegions", "speedRegions", "trimRegions", "annotationRegions"):
        for region in ed.get(region_key, []):
            boundaries.add(region.get("startMs", 0))
            boundaries.add(region.get("endMs", 0))
    return sorted(boundaries)


def get_active_regions_at(session: Session, time_ms: int) -> dict:
    """Return all regions active at a specific time (startMs <= time_ms < endMs).

    Args:
        session: Active Session instance.
        time_ms: Query time in milliseconds.

    Returns:
        Dict with keys "zoom", "speed", "trim", "annotation", each mapping to
        a list of region dicts active at that time.

    Raises:
        RuntimeError: If no project is open.
    """
    if not session.is_open:
        raise RuntimeError("No project is open")
    ed = session.editor

    def active(regions: list) -> list:
        return [r for r in regions if r.get("startMs", 0) <= time_ms < r.get("endMs", 0)]

    return {
        "zoom": active(ed.get("zoomRegions", [])),
        "speed": active(ed.get("speedRegions", [])),
        "trim": active(ed.get("trimRegions", [])),
        "annotation": active(ed.get("annotationRegions", [])),
    }
