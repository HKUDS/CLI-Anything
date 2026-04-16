"""LibreOffice CLI - Impress (presentations) module."""

from typing import Dict, Any, List, Optional


def _ensure_impress(project: Dict[str, Any]) -> None:
    """Ensure the project is an Impress document."""
    if project.get("type") != "impress":
        raise ValueError(
            f"Document type is '{project.get('type')}', expected 'impress'."
        )
    if "slides" not in project:
        project["slides"] = []


def add_slide(
    project: Dict[str, Any],
    title: str = "",
    content: str = "",
    position: Optional[int] = None,
) -> Dict[str, Any]:
    """Add a slide to the presentation."""
    _ensure_impress(project)
    slide = {
        "title": title,
        "content": content,
        "elements": [],
    }
    slides = project["slides"]
    if position is not None:
        if position < 0 or position > len(slides):
            raise IndexError(
                f"Position {position} out of range (0-{len(slides)})"
            )
        slides.insert(position, slide)
    else:
        slides.append(slide)
    return slide


def remove_slide(
    project: Dict[str, Any],
    index: int,
) -> Dict[str, Any]:
    """Remove a slide by index."""
    _ensure_impress(project)
    slides = project["slides"]
    if not slides:
        raise ValueError("No slides to remove.")
    if index < 0 or index >= len(slides):
        raise IndexError(
            f"Slide index {index} out of range (0-{len(slides) - 1})"
        )
    return slides.pop(index)


def set_slide_content(
    project: Dict[str, Any],
    index: int,
    title: Optional[str] = None,
    content: Optional[str] = None,
) -> Dict[str, Any]:
    """Update a slide's title and/or content."""
    _ensure_impress(project)
    slides = project["slides"]
    if index < 0 or index >= len(slides):
        raise IndexError(
            f"Slide index {index} out of range (0-{len(slides) - 1})"
        )
    slide = slides[index]
    if title is not None:
        slide["title"] = title
    if content is not None:
        slide["content"] = content
    return slide


def add_slide_element(
    project: Dict[str, Any],
    slide_index: int,
    element_type: str = "text_box",
    text: str = "",
    x: str = "2cm",
    y: str = "2cm",
    width: str = "10cm",
    height: str = "5cm",
) -> Dict[str, Any]:
    """Add an element to a slide."""
    _ensure_impress(project)
    slides = project["slides"]
    if slide_index < 0 or slide_index >= len(slides):
        raise IndexError(
            f"Slide index {slide_index} out of range (0-{len(slides) - 1})"
        )
    if element_type not in ("text_box", "image", "shape"):
        raise ValueError(
            f"Invalid element type: {element_type}. "
            f"Use 'text_box', 'image', or 'shape'."
        )
    element = {
        "type": element_type,
        "text": text,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
    }
    slides[slide_index].setdefault("elements", []).append(element)
    return element


def remove_slide_element(
    project: Dict[str, Any],
    slide_index: int,
    element_index: int,
) -> Dict[str, Any]:
    """Remove an element from a slide."""
    _ensure_impress(project)
    slides = project["slides"]
    if slide_index < 0 or slide_index >= len(slides):
        raise IndexError(
            f"Slide index {slide_index} out of range (0-{len(slides) - 1})"
        )
    elements = slides[slide_index].get("elements", [])
    if element_index < 0 or element_index >= len(elements):
        raise IndexError(
            f"Element index {element_index} out of range "
            f"(0-{len(elements) - 1})"
        )
    return elements.pop(element_index)


def move_slide(
    project: Dict[str, Any],
    from_index: int,
    to_index: int,
) -> Dict[str, Any]:
    """Move a slide to a new position."""
    _ensure_impress(project)
    slides = project["slides"]
    if from_index < 0 or from_index >= len(slides):
        raise IndexError(
            f"From index {from_index} out of range (0-{len(slides) - 1})"
        )
    if to_index < 0 or to_index >= len(slides):
        raise IndexError(
            f"To index {to_index} out of range (0-{len(slides) - 1})"
        )
    slide = slides.pop(from_index)
    slides.insert(to_index, slide)
    return slide


def duplicate_slide(
    project: Dict[str, Any],
    index: int,
) -> Dict[str, Any]:
    """Duplicate a slide."""
    _ensure_impress(project)
    import copy
    slides = project["slides"]
    if index < 0 or index >= len(slides):
        raise IndexError(
            f"Slide index {index} out of range (0-{len(slides) - 1})"
        )
    dup = copy.deepcopy(slides[index])
    dup["title"] = dup.get("title", "") + " (copy)"
    slides.insert(index + 1, dup)
    return dup


def list_slides(project: Dict[str, Any]) -> List[Dict[str, Any]]:
    """List all slides with their indices and titles."""
    _ensure_impress(project)
    result = []
    for i, slide in enumerate(project.get("slides", [])):
        result.append({
            "index": i,
            "title": slide.get("title", ""),
            "content_preview": (slide.get("content", "") or "")[:80],
            "element_count": len(slide.get("elements", [])),
        })
    return result


def get_slide(
    project: Dict[str, Any],
    index: int,
) -> Dict[str, Any]:
    """Get a slide by index."""
    _ensure_impress(project)
    slides = project.get("slides", [])
    if index < 0 or index >= len(slides):
        raise IndexError(
            f"Slide index {index} out of range (0-{len(slides) - 1})"
        )
    return slides[index]
