"""LibreOffice CLI - Document styles module."""

from typing import Dict, Any, List, Optional


VALID_FAMILIES = ("paragraph", "text")

VALID_PROPERTIES = {
    "font_size", "font_name", "bold", "italic", "underline",
    "color", "alignment", "line_height", "margin_top", "margin_bottom",
}


def create_style(
    project: Dict[str, Any],
    name: str,
    family: str = "paragraph",
    parent: Optional[str] = None,
    properties: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Create a new named style."""
    if "styles" not in project:
        project["styles"] = {}
    if name in project["styles"]:
        raise ValueError(f"Style '{name}' already exists.")
    if family not in VALID_FAMILIES:
        raise ValueError(
            f"Invalid style family: {family}. "
            f"Must be one of: {', '.join(VALID_FAMILIES)}"
        )
    props = properties or {}
    _validate_properties(props)

    style_def = {
        "family": family,
        "properties": props,
    }
    if parent:
        style_def["parent"] = parent

    project["styles"][name] = style_def
    return {"name": name, **style_def}


def modify_style(
    project: Dict[str, Any],
    name: str,
    properties: Optional[Dict] = None,
    family: Optional[str] = None,
    parent: Optional[str] = None,
) -> Dict[str, Any]:
    """Modify an existing style."""
    if "styles" not in project or name not in project["styles"]:
        raise ValueError(f"Style '{name}' not found.")

    style_def = project["styles"][name]

    if family is not None:
        if family not in VALID_FAMILIES:
            raise ValueError(
                f"Invalid style family: {family}. "
                f"Must be one of: {', '.join(VALID_FAMILIES)}"
            )
        style_def["family"] = family

    if parent is not None:
        style_def["parent"] = parent

    if properties is not None:
        _validate_properties(properties)
        style_def["properties"].update(properties)

    return {"name": name, **style_def}


def remove_style(
    project: Dict[str, Any],
    name: str,
) -> Dict[str, Any]:
    """Remove a named style."""
    if "styles" not in project or name not in project["styles"]:
        raise ValueError(f"Style '{name}' not found.")
    removed = project["styles"].pop(name)
    return {"name": name, **removed}


def list_styles(project: Dict[str, Any]) -> List[Dict[str, Any]]:
    """List all defined styles."""
    result = []
    for name, style_def in project.get("styles", {}).items():
        result.append({
            "name": name,
            "family": style_def.get("family", "paragraph"),
            "parent": style_def.get("parent"),
            "properties": style_def.get("properties", {}),
        })
    return result


def get_style(
    project: Dict[str, Any],
    name: str,
) -> Dict[str, Any]:
    """Get a style by name."""
    if "styles" not in project or name not in project["styles"]:
        raise ValueError(f"Style '{name}' not found.")
    style_def = project["styles"][name]
    return {"name": name, **style_def}


def apply_style(
    project: Dict[str, Any],
    style_name: str,
    content_index: int,
) -> Dict[str, Any]:
    """Apply a named style to a content item (Writer only)."""
    if project.get("type") != "writer":
        raise ValueError("apply_style is only supported for Writer documents.")
    if "styles" not in project or style_name not in project["styles"]:
        raise ValueError(f"Style '{style_name}' not found.")

    content = project.get("content", [])
    if content_index < 0 or content_index >= len(content):
        raise IndexError(
            f"Content index {content_index} out of range "
            f"(0-{len(content) - 1})"
        )

    item = content[content_index]
    style_def = project["styles"][style_name]
    # Merge style properties into item's style
    item_style = item.get("style", {})
    item_style.update(style_def.get("properties", {}))
    item["style"] = item_style

    return {
        "content_index": content_index,
        "style_applied": style_name,
        "content_type": item.get("type"),
    }


def _validate_properties(props: Dict) -> None:
    """Validate style properties."""
    unknown = set(props.keys()) - VALID_PROPERTIES
    if unknown:
        raise ValueError(
            f"Unknown style properties: {', '.join(unknown)}. "
            f"Valid: {', '.join(sorted(VALID_PROPERTIES))}"
        )
