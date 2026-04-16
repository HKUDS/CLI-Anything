"""Connector (edge) operations: add, remove, modify, list."""

from ..utils import drawio_xml
from .session import Session


def list_connectors(session: Session, diagram_index: int = 0) -> list[dict]:
    """List all connectors (edges) on a page."""
    if not session.is_open:
        raise RuntimeError("No project is open")
    cells = drawio_xml.get_edges(session.root, diagram_index)
    return [drawio_xml.get_cell_info(c) for c in cells]


def add_connector(session: Session, source_id: str, target_id: str,
                  edge_style: str = "orthogonal", label: str = "",
                  diagram_index: int = 0, edge_id: str = None) -> dict:
    """Add a connector between two shapes.

    Args:
        session: Active session.
        source_id: Source shape cell ID.
        target_id: Target shape cell ID.
        edge_style: Edge style preset (straight, orthogonal, curved,
                    entity-relation) or raw style string.
        label: Optional label on the edge.
        edge_id: Optional custom ID. Auto-generated if not provided.

    Returns:
        Dict with action and new edge info.
    """
    if not session.is_open:
        raise RuntimeError("No project is open")

    # Validate source and target exist
    if drawio_xml.find_cell_by_id(session.root, source_id, diagram_index) is None:
        raise ValueError(f"Source cell not found: {source_id}")
    if drawio_xml.find_cell_by_id(session.root, target_id, diagram_index) is None:
        raise ValueError(f"Target cell not found: {target_id}")

    if edge_id is not None and drawio_xml.find_cell_by_id(session.root, edge_id, diagram_index) is not None:
        raise ValueError(f"Cell ID already exists: {edge_id}")

    session.checkpoint()
    edge_id = drawio_xml.add_edge(
        session.root, source_id, target_id, edge_style, label,
        diagram_index=diagram_index, edge_id=edge_id,
    )

    return {
        "action": "add_connector",
        "id": edge_id,
        "source": source_id,
        "target": target_id,
        "style": edge_style,
        "label": label,
    }


def remove_connector(session: Session, edge_id: str,
                     diagram_index: int = 0) -> dict:
    """Remove a connector by ID."""
    if not session.is_open:
        raise RuntimeError("No project is open")

    session.checkpoint()
    found = drawio_xml.remove_cell(session.root, edge_id, diagram_index)
    if not found:
        raise ValueError(f"Connector not found: {edge_id}")

    return {
        "action": "remove_connector",
        "id": edge_id,
    }


def update_connector_label(session: Session, edge_id: str, label: str,
                           diagram_index: int = 0) -> dict:
    """Update a connector's label."""
    if not session.is_open:
        raise RuntimeError("No project is open")

    session.checkpoint()
    found = drawio_xml.update_cell_label(session.root, edge_id, label, diagram_index)
    if not found:
        raise ValueError(f"Connector not found: {edge_id}")

    return {
        "action": "update_connector_label",
        "id": edge_id,
        "label": label,
    }


def set_connector_style(session: Session, edge_id: str,
                        key: str, value: str,
                        diagram_index: int = 0) -> dict:
    """Set a style property on a connector.

    Common style keys:
        strokeColor, strokeWidth, dashed, endArrow, startArrow,
        edgeStyle, curved, rounded, opacity
    """
    if not session.is_open:
        raise RuntimeError("No project is open")

    cell = drawio_xml.find_cell_by_id(session.root, edge_id, diagram_index)
    if cell is None:
        raise ValueError(f"Connector not found: {edge_id}")

    session.checkpoint()
    drawio_xml.set_style_property(cell, key, value)

    return {
        "action": "set_connector_style",
        "id": edge_id,
        "key": key,
        "value": value,
    }


def list_edge_styles() -> dict:
    """List all available edge style presets."""
    return {name: style for name, style in sorted(drawio_xml.EDGE_STYLES.items())}
