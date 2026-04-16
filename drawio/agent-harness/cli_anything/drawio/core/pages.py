"""Multi-page operations: add, remove, rename, list pages."""

from ..utils import drawio_xml
from .session import Session


def list_pages(session: Session) -> list[dict]:
    """List all pages in the diagram."""
    if not session.is_open:
        raise RuntimeError("No project is open")
    return drawio_xml.list_pages(session.root)


def add_page(session: Session, name: str = "",
             page_width: int = 850, page_height: int = 1100) -> dict:
    """Add a new page to the diagram."""
    if not session.is_open:
        raise RuntimeError("No project is open")

    session.checkpoint()
    diagram_id = drawio_xml.add_page(session.root, name, page_width, page_height)

    pages = drawio_xml.list_pages(session.root)
    return {
        "action": "add_page",
        "diagram_id": diagram_id,
        "page_count": len(pages),
        "name": pages[-1]["name"],
    }


def remove_page(session: Session, page_index: int) -> dict:
    """Remove a page by index. Cannot remove the last page."""
    if not session.is_open:
        raise RuntimeError("No project is open")

    session.checkpoint()
    drawio_xml.remove_page(session.root, page_index)

    return {
        "action": "remove_page",
        "removed_index": page_index,
        "page_count": len(session.root.findall("diagram")),
    }


def rename_page(session: Session, page_index: int, name: str) -> dict:
    """Rename a page."""
    if not session.is_open:
        raise RuntimeError("No project is open")

    session.checkpoint()
    drawio_xml.rename_page(session.root, page_index, name)

    return {
        "action": "rename_page",
        "page_index": page_index,
        "name": name,
    }
