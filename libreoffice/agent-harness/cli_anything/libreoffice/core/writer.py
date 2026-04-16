"""LibreOffice CLI - Writer (word processor) module."""

from typing import Dict, Any, List, Optional


def _ensure_writer(project: Dict[str, Any]) -> None:
    """Ensure the project is a Writer document."""
    if project.get("type") != "writer":
        raise ValueError(
            f"Document type is '{project.get('type')}', expected 'writer'."
        )
    if "content" not in project:
        project["content"] = []


def add_paragraph(
    project: Dict[str, Any],
    text: str = "",
    style: Optional[Dict] = None,
    position: Optional[int] = None,
) -> Dict[str, Any]:
    """Add a paragraph to the document."""
    _ensure_writer(project)
    item = {
        "type": "paragraph",
        "text": text,
        "style": style or {},
    }
    if position is not None:
        if position < 0 or position > len(project["content"]):
            raise IndexError(
                f"Position {position} out of range "
                f"(0-{len(project['content'])})"
            )
        project["content"].insert(position, item)
    else:
        project["content"].append(item)
    return item


def add_heading(
    project: Dict[str, Any],
    text: str = "",
    level: int = 1,
    style: Optional[Dict] = None,
    position: Optional[int] = None,
) -> Dict[str, Any]:
    """Add a heading to the document."""
    _ensure_writer(project)
    if level < 1 or level > 6:
        raise ValueError(f"Heading level must be 1-6, got {level}")
    item = {
        "type": "heading",
        "level": level,
        "text": text,
        "style": style or {},
    }
    if position is not None:
        if position < 0 or position > len(project["content"]):
            raise IndexError(
                f"Position {position} out of range "
                f"(0-{len(project['content'])})"
            )
        project["content"].insert(position, item)
    else:
        project["content"].append(item)
    return item


def add_list(
    project: Dict[str, Any],
    items: Optional[List[str]] = None,
    list_style: str = "bullet",
    position: Optional[int] = None,
) -> Dict[str, Any]:
    """Add a list to the document."""
    _ensure_writer(project)
    if list_style not in ("bullet", "number"):
        raise ValueError(
            f"Invalid list style: {list_style}. Use 'bullet' or 'number'."
        )
    item = {
        "type": "list",
        "list_style": list_style,
        "items": items or [],
    }
    if position is not None:
        if position < 0 or position > len(project["content"]):
            raise IndexError(
                f"Position {position} out of range "
                f"(0-{len(project['content'])})"
            )
        project["content"].insert(position, item)
    else:
        project["content"].append(item)
    return item


def add_table(
    project: Dict[str, Any],
    rows: int = 2,
    cols: int = 2,
    data: Optional[List[List[str]]] = None,
    position: Optional[int] = None,
) -> Dict[str, Any]:
    """Add a table to the document."""
    _ensure_writer(project)
    if rows < 1 or cols < 1:
        raise ValueError(f"Table must have at least 1 row and 1 column")
    if data is None:
        data = [["" for _ in range(cols)] for _ in range(rows)]
    item = {
        "type": "table",
        "rows": rows,
        "cols": cols,
        "data": data,
    }
    if position is not None:
        if position < 0 or position > len(project["content"]):
            raise IndexError(
                f"Position {position} out of range "
                f"(0-{len(project['content'])})"
            )
        project["content"].insert(position, item)
    else:
        project["content"].append(item)
    return item


def add_page_break(
    project: Dict[str, Any],
    position: Optional[int] = None,
) -> Dict[str, Any]:
    """Add a page break to the document."""
    _ensure_writer(project)
    item = {"type": "page_break"}
    if position is not None:
        if position < 0 or position > len(project["content"]):
            raise IndexError(
                f"Position {position} out of range "
                f"(0-{len(project['content'])})"
            )
        project["content"].insert(position, item)
    else:
        project["content"].append(item)
    return item


def remove_content(
    project: Dict[str, Any],
    index: int,
) -> Dict[str, Any]:
    """Remove a content item by index."""
    _ensure_writer(project)
    content = project["content"]
    if not content:
        raise ValueError("No content to remove.")
    if index < 0 or index >= len(content):
        raise IndexError(
            f"Index {index} out of range (0-{len(content) - 1})"
        )
    return content.pop(index)


def list_content(project: Dict[str, Any]) -> List[Dict[str, Any]]:
    """List all content items with their indices."""
    _ensure_writer(project)
    result = []
    for i, item in enumerate(project.get("content", [])):
        entry = {
            "index": i,
            "type": item.get("type", "unknown"),
        }
        if item.get("type") == "heading":
            entry["level"] = item.get("level", 1)
            entry["text"] = item.get("text", "")[:80]
        elif item.get("type") == "paragraph":
            entry["text"] = item.get("text", "")[:80]
        elif item.get("type") == "list":
            entry["list_style"] = item.get("list_style", "bullet")
            entry["item_count"] = len(item.get("items", []))
        elif item.get("type") == "table":
            entry["rows"] = item.get("rows", 0)
            entry["cols"] = item.get("cols", 0)
        result.append(entry)
    return result


def get_content(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Get a content item by index."""
    _ensure_writer(project)
    content = project.get("content", [])
    if index < 0 or index >= len(content):
        raise IndexError(
            f"Index {index} out of range (0-{len(content) - 1})"
        )
    return content[index]


def set_content_text(
    project: Dict[str, Any],
    index: int,
    text: str,
) -> Dict[str, Any]:
    """Set the text of a content item."""
    _ensure_writer(project)
    content = project.get("content", [])
    if index < 0 or index >= len(content):
        raise IndexError(
            f"Index {index} out of range (0-{len(content) - 1})"
        )
    item = content[index]
    if item["type"] not in ("paragraph", "heading"):
        raise ValueError(
            f"Cannot set text on content type '{item['type']}'"
        )
    item["text"] = text
    return item
