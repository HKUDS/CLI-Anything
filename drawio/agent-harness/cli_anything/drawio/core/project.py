"""Project management operations."""

import os
from typing import Optional

from ..utils import drawio_xml
from .session import Session


# Standard page presets
PAGE_PRESETS = {
    "letter": {"width": 850, "height": 1100},
    "a4": {"width": 827, "height": 1169},
    "a3": {"width": 1169, "height": 1654},
    "16:9": {"width": 1280, "height": 720},
    "4:3": {"width": 1024, "height": 768},
    "square": {"width": 800, "height": 800},
    "custom": {"width": 850, "height": 1100},
}


def new_project(session: Session, preset: str = "letter",
                width: Optional[int] = None, height: Optional[int] = None) -> dict:
    """Create a new blank diagram project.

    Args:
        session: The active session.
        preset: Page preset name (see PAGE_PRESETS).
        width: Override page width.
        height: Override page height.

    Returns:
        Dict with project info.
    """
    if preset not in PAGE_PRESETS:
        available = ", ".join(sorted(PAGE_PRESETS.keys()))
        raise ValueError(f"Unknown preset: {preset!r}. Available: {available}")

    page = PAGE_PRESETS[preset]
    w = width or page["width"]
    h = height or page["height"]

    session.new_project(page_width=w, page_height=h)

    return {
        "action": "new_project",
        "preset": preset,
        "page_size": f"{w}x{h}",
    }


def open_project(session: Session, path: str) -> dict:
    """Open an existing .drawio project file."""
    session.open_project(path)

    shape_count = len(drawio_xml.get_vertices(session.root))
    edge_count = len(drawio_xml.get_edges(session.root))
    page_count = len(session.root.findall("diagram"))

    return {
        "action": "open_project",
        "path": session.project_path,
        "page_count": page_count,
        "shape_count": shape_count,
        "edge_count": edge_count,
    }


def save_project(session: Session, path: Optional[str] = None) -> dict:
    """Save the current project."""
    saved_path = session.save_project(path)
    return {
        "action": "save_project",
        "path": saved_path,
    }


def project_info(session: Session) -> dict:
    """Get detailed info about the current project."""
    if not session.is_open:
        raise RuntimeError("No project is open")

    root = session.root

    # Page info
    pages = drawio_xml.list_pages(root)

    # Shapes on first page
    shapes = []
    for cell in drawio_xml.get_vertices(root):
        shapes.append(drawio_xml.get_cell_info(cell))

    # Edges on first page
    edges = []
    for cell in drawio_xml.get_edges(root):
        edges.append(drawio_xml.get_cell_info(cell))

    # Canvas settings
    try:
        model = drawio_xml.get_model(root)
        canvas = {
            "pageWidth": model.get("pageWidth", "850"),
            "pageHeight": model.get("pageHeight", "1100"),
            "gridSize": model.get("gridSize", "10"),
            "grid": model.get("grid", "1") == "1",
        }
    except RuntimeError:
        canvas = {}

    return {
        "project_path": session.project_path,
        "modified": session.is_modified,
        "pages": pages,
        "canvas": canvas,
        "shapes": shapes,
        "edges": edges,
    }


def list_presets() -> dict:
    """List all available page presets."""
    return {name: f"{p['width']}x{p['height']}" for name, p in sorted(PAGE_PRESETS.items())}
