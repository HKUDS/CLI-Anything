"""Obsidian active note operations — get and open."""

from urllib.parse import quote

from cli_anything.obsidian.utils.obsidian_backend import api_get, api_post


def get_active(base_url: str, api_key: str) -> dict:
    """Get the currently active (open) note in Obsidian."""
    return api_get(base_url, "/active/", api_key)


def open_note(base_url: str, api_key: str, path: str, new_leaf: bool = False) -> dict:
    """Open a note in Obsidian (POST /open/{filename})."""
    params = {"newLeaf": "true"} if new_leaf else None
    return api_post(base_url, f"/open/{quote(path.lstrip('/'))}", api_key, params=params)
