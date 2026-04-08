"""Tab-level operations for iTerm2.

All functions are async coroutines intended to be called via
cli_anything.iterm2_ctl.utils.iterm2_backend.run_iterm2().
"""
from typing import Any, Dict, List, Optional


async def list_tabs(connection, window_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """List all tabs, optionally filtered to a specific window."""
    import iterm2
    app = await iterm2.async_get_app(connection)
    result = []
    for window in app.windows:
        if window_id and window.window_id != window_id:
            continue
        current_tab = window.current_tab
        for tab in window.tabs:
            result.append({
                "tab_id": tab.tab_id,
                "window_id": window.window_id,
                "session_count": len(tab.sessions),
                "is_current": (current_tab is not None and tab.tab_id == current_tab.tab_id),
            })
    return result


async def create_tab(
    connection,
    window_id: Optional[str] = None,
    profile: Optional[str] = None,
    command: Optional[str] = None,
    index: Optional[int] = None,
) -> Dict[str, Any]:
    """Create a new tab in a window.

    Args:
        window_id: Target window (None = current window).
        profile: Profile name (None = default).
        command: Command to run (None = shell).
        index: Tab position (None = end).

    Returns:
        Dict with tab_id, window_id, session_id.
    """
    import iterm2
    app = await iterm2.async_get_app(connection)

    if window_id:
        from cli_anything.iterm2_ctl.utils.iterm2_backend import async_find_window
        window = await async_find_window(connection, window_id)
    else:
        window = app.current_terminal_window
        if window is None:
            raise RuntimeError("No open windows. Create a window first with: window create")

    tab = await window.async_create_tab(
        profile=profile,
        command=command,
        index=index,
    )
    if tab is None:
        raise RuntimeError("Failed to create tab")

    session = tab.current_session
    return {
        "tab_id": tab.tab_id,
        "window_id": window.window_id,
        "session_id": session.session_id if session else None,
    }


async def close_tab(connection, tab_id: str, force: bool = False) -> Dict[str, Any]:
    """Close a tab by ID."""
    from cli_anything.iterm2_ctl.utils.iterm2_backend import async_find_tab
    tab = await async_find_tab(connection, tab_id)
    # Close all sessions in the tab
    for session in tab.sessions:
        await session.async_close(force=force)
    return {"tab_id": tab_id, "closed": True}


async def activate_tab(connection, tab_id: str) -> Dict[str, Any]:
    """Bring a tab to focus."""
    import iterm2
    from cli_anything.iterm2_ctl.utils.iterm2_backend import async_find_tab
    tab = await async_find_tab(connection, tab_id)
    session = tab.current_session
    if session:
        await session.async_activate()
    return {"tab_id": tab_id, "activated": True}


async def select_pane_in_direction(
    connection,
    tab_id: str,
    direction: str,
) -> Dict[str, Any]:
    """Move focus to the adjacent split pane in a given direction.

    Args:
        tab_id: The tab containing the split panes.
        direction: One of 'left', 'right', 'above', 'below'.

    Returns:
        Dict with 'new_session_id' (may be None if no pane in that direction).
    """
    import iterm2
    from cli_anything.iterm2_ctl.utils.iterm2_backend import async_find_tab
    dir_map = {
        "left": iterm2.NavigationDirection.LEFT,
        "right": iterm2.NavigationDirection.RIGHT,
        "above": iterm2.NavigationDirection.ABOVE,
        "below": iterm2.NavigationDirection.BELOW,
    }
    nav_dir = dir_map.get(direction.lower())
    if nav_dir is None:
        raise ValueError(f"Invalid direction '{direction}'. Use: left, right, above, below")
    tab = await async_find_tab(connection, tab_id)
    new_session_id = await tab.async_select_pane_in_direction(nav_dir)
    return {
        "tab_id": tab_id,
        "direction": direction,
        "new_session_id": new_session_id,
        "moved": new_session_id is not None,
    }


async def get_tab_info(connection, tab_id: str) -> Dict[str, Any]:
    """Get detailed info about a specific tab."""
    from cli_anything.iterm2_ctl.utils.iterm2_backend import async_find_tab
    tab = await async_find_tab(connection, tab_id)
    sessions = []
    for s in tab.sessions:
        sessions.append({
            "session_id": s.session_id,
            "name": s.name,
        })
    return {
        "tab_id": tab.tab_id,
        "session_count": len(sessions),
        "sessions": sessions,
    }
