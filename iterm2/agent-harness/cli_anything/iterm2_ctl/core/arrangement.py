"""Arrangement operations for iTerm2.

Arrangements are saved snapshots of window/tab/session layouts.
All functions are async coroutines.
"""
from typing import Any, Dict, List, Optional


async def save_arrangement(connection, name: str) -> Dict[str, Any]:
    """Save all current windows as a named arrangement.

    Replaces any existing arrangement with the same name.

    Args:
        name: Name for the arrangement.

    Returns:
        Dict confirming the save.
    """
    import iterm2
    await iterm2.Arrangement.async_save(connection, name)
    return {"name": name, "saved": True}


async def restore_arrangement(
    connection, name: str, window_id: Optional[str] = None
) -> Dict[str, Any]:
    """Restore a saved arrangement.

    Args:
        name: Name of the arrangement to restore.
        window_id: If provided, restore into an existing window. Otherwise opens new windows.

    Returns:
        Dict confirming the restore.
    """
    import iterm2
    await iterm2.Arrangement.async_restore(connection, name, window_id=window_id)
    return {"name": name, "restored": True, "window_id": window_id}


async def list_arrangements(connection) -> List[str]:
    """List all saved arrangement names."""
    import iterm2
    arrangements = await iterm2.Arrangement.async_list(connection)
    return sorted(arrangements)


async def save_window_arrangement(
    connection, window_id: str, name: str
) -> Dict[str, Any]:
    """Save a single window as a named arrangement.

    Args:
        window_id: The window to save.
        name: Name for the arrangement.
    """
    from cli_anything.iterm2_ctl.utils.iterm2_backend import async_find_window
    window = await async_find_window(connection, window_id)
    await window.async_save_window_as_arrangement(name)
    return {"window_id": window_id, "name": name, "saved": True}


async def restore_arrangement_in_window(
    connection, window_id: str, name: str
) -> Dict[str, Any]:
    """Restore a saved arrangement into an existing window.

    Args:
        window_id: The window to restore into.
        name: Name of the arrangement.
    """
    from cli_anything.iterm2_ctl.utils.iterm2_backend import async_find_window
    window = await async_find_window(connection, window_id)
    await window.async_restore_window_arrangement(name)
    return {"window_id": window_id, "name": name, "restored": True}
