"""Obsidian vault operations — list, read, create, update, delete, append."""

from urllib.parse import quote

from cli_anything.obsidian.utils.obsidian_backend import (
    api_get, api_put, api_delete,
)


def list_files(base_url: str, api_key: str, path: str = "/") -> dict:
    """List files and folders in the vault."""
    endpoint = f"/vault/{quote(path.strip('/'), safe='/')}/" if path != "/" else "/vault/"
    return api_get(base_url, endpoint, api_key)


def read_note(base_url: str, api_key: str, path: str) -> dict:
    """Read a note's content."""
    endpoint = f"/vault/{quote(path.lstrip('/'), safe='/')}"
    return api_get(base_url, endpoint, api_key)


def create_note(base_url: str, api_key: str, path: str, content: str) -> dict:
    """Create a new note in the vault."""
    endpoint = f"/vault/{quote(path.lstrip('/'), safe='/')}"
    return api_put(base_url, endpoint, api_key, content=content)


def update_note(base_url: str, api_key: str, path: str, content: str) -> dict:
    """Update an existing note's content (overwrites)."""
    endpoint = f"/vault/{quote(path.lstrip('/'), safe='/')}"
    return api_put(base_url, endpoint, api_key, content=content)


def delete_note(base_url: str, api_key: str, path: str) -> dict:
    """Delete a note from the vault."""
    endpoint = f"/vault/{quote(path.lstrip('/'), safe='/')}"
    return api_delete(base_url, endpoint, api_key)


def append_note(base_url: str, api_key: str, path: str, content: str,
                position: str = "end") -> dict:
    """Append or prepend content to an existing note.

    Reads the current content, inserts new content at the specified position,
    and writes back. This approach works with Obsidian REST API v3.x which
    changed PATCH to target-based operations.

    Args:
        base_url: API base URL.
        api_key: Bearer token.
        path: Path to the note.
        content: Content to insert.
        position: 'end' to append, 'beginning' to prepend.

    Returns:
        Status dict.
    """
    existing = read_note(base_url, api_key, path)
    current = existing.get("content", "")
    if position == "beginning":
        new_content = content + current
    else:
        new_content = current + content
    return update_note(base_url, api_key, path, new_content)
