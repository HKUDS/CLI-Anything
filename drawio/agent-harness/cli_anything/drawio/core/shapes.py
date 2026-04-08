"""Shape (vertex) operations: add, remove, modify, list."""

from ..utils import drawio_xml
from .session import Session


def list_shapes(session: Session, diagram_index: int = 0) -> list[dict]:
    """List all shapes on a page."""
    if not session.is_open:
        raise RuntimeError("No project is open")
    cells = drawio_xml.get_vertices(session.root, diagram_index)
    return [drawio_xml.get_cell_info(c) for c in cells]


def add_shape(session: Session, shape_type: str = "rectangle",
              x: float = 100, y: float = 100,
              width: float = 120, height: float = 60,
              label: str = "", diagram_index: int = 0,
              cell_id: str = None) -> dict:
    """Add a shape to the diagram.

    Args:
        session: Active session.
        shape_type: Shape preset (rectangle, rounded, ellipse, diamond,
                    triangle, hexagon, cylinder, cloud, parallelogram,
                    process, document, callout, note, actor, text).
        x, y: Position.
        width, height: Dimensions.
        label: Text label.
        cell_id: Optional custom ID. Auto-generated if not provided.

    Returns:
        Dict with action and new shape info.
    """
    if not session.is_open:
        raise RuntimeError("No project is open")

    if cell_id is not None and drawio_xml.find_cell_by_id(session.root, cell_id, diagram_index) is not None:
        raise ValueError(f"Cell ID already exists: {cell_id}")

    session.checkpoint()
    cell_id = drawio_xml.add_vertex(
        session.root, shape_type, x, y, width, height, label,
        diagram_index=diagram_index, cell_id=cell_id,
    )

    return {
        "action": "add_shape",
        "id": cell_id,
        "shape_type": shape_type,
        "label": label,
        "x": x, "y": y,
        "width": width, "height": height,
    }


def remove_shape(session: Session, cell_id: str,
                 diagram_index: int = 0) -> dict:
    """Remove a shape by ID (also removes connected edges)."""
    if not session.is_open:
        raise RuntimeError("No project is open")

    session.checkpoint()
    found = drawio_xml.remove_cell(session.root, cell_id, diagram_index)
    if not found:
        raise ValueError(f"Shape not found: {cell_id}")

    return {
        "action": "remove_shape",
        "id": cell_id,
    }


def update_label(session: Session, cell_id: str, label: str,
                 diagram_index: int = 0) -> dict:
    """Update a shape's label text."""
    if not session.is_open:
        raise RuntimeError("No project is open")

    session.checkpoint()
    found = drawio_xml.update_cell_label(session.root, cell_id, label, diagram_index)
    if not found:
        raise ValueError(f"Cell not found: {cell_id}")

    return {
        "action": "update_label",
        "id": cell_id,
        "label": label,
    }


def move_shape(session: Session, cell_id: str, x: float, y: float,
               diagram_index: int = 0) -> dict:
    """Move a shape to new coordinates."""
    if not session.is_open:
        raise RuntimeError("No project is open")

    session.checkpoint()
    found = drawio_xml.move_cell(session.root, cell_id, x, y, diagram_index)
    if not found:
        raise ValueError(f"Cell not found: {cell_id}")

    return {
        "action": "move_shape",
        "id": cell_id,
        "x": x, "y": y,
    }


def resize_shape(session: Session, cell_id: str,
                 width: float, height: float,
                 diagram_index: int = 0) -> dict:
    """Resize a shape."""
    if not session.is_open:
        raise RuntimeError("No project is open")

    session.checkpoint()
    found = drawio_xml.resize_cell(session.root, cell_id, width, height, diagram_index)
    if not found:
        raise ValueError(f"Cell not found: {cell_id}")

    return {
        "action": "resize_shape",
        "id": cell_id,
        "width": width, "height": height,
    }


def set_style(session: Session, cell_id: str, key: str, value: str,
              diagram_index: int = 0) -> dict:
    """Set a style property on a shape.

    Common style keys:
        fillColor, strokeColor, fontColor, fontSize, fontStyle,
        opacity, rounded, shadow, dashed, strokeWidth
    """
    if not session.is_open:
        raise RuntimeError("No project is open")

    cell = drawio_xml.find_cell_by_id(session.root, cell_id, diagram_index)
    if cell is None:
        raise ValueError(f"Cell not found: {cell_id}")

    session.checkpoint()
    drawio_xml.set_style_property(cell, key, value)

    return {
        "action": "set_style",
        "id": cell_id,
        "key": key,
        "value": value,
    }


def get_shape_info(session: Session, cell_id: str,
                   diagram_index: int = 0) -> dict:
    """Get detailed info about a specific shape."""
    if not session.is_open:
        raise RuntimeError("No project is open")

    cell = drawio_xml.find_cell_by_id(session.root, cell_id, diagram_index)
    if cell is None:
        raise ValueError(f"Cell not found: {cell_id}")

    info = drawio_xml.get_cell_info(cell)
    info["style_parsed"] = drawio_xml.parse_style(cell.get("style", ""))
    return info


def list_shape_types() -> dict:
    """List all available shape type presets."""
    return {name: style for name, style in sorted(drawio_xml.SHAPE_STYLES.items())}
