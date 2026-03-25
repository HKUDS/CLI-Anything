"""Window-level operations for iTerm2.

All functions are async coroutines intended to be called via
cli_anything.iterm2_ctl.utils.iterm2_backend.run_iterm2().
"""
from typing import Any, Dict, List, Optional


async def list_windows(connection) -> List[Dict[str, Any]]:
    """Return a list of all open windows with metadata."""
    import iterm2
    app = await iterm2.async_get_app(connection)
    result = []
    for window in app.windows:
        tabs = window.tabs
        tab_count = len(tabs)
        session_count = sum(len(t.sessions) for t in tabs)
        result.append({
            "window_id": window.window_id,
            "tab_count": tab_count,
            "session_count": session_count,
            "is_current": (app.current_terminal_window is not None
                           and window.window_id == app.current_terminal_window.window_id),
        })
    return result


async def create_window(
    connection,
    profile: Optional[str] = None,
    command: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new iTerm2 window.

    Args:
        profile: Profile name to use (None = default).
        command: Command to run in the new window (None = shell).

    Returns:
        Dict with window_id, tab_id, session_id.
    """
    import iterm2
    app = await iterm2.async_get_app(connection)
    window = await iterm2.Window.async_create(
        connection, profile=profile, command=command
    )
    if window is None:
        raise RuntimeError("Failed to create window")
    tab = window.current_tab
    session = tab.current_session if tab else None
    return {
        "window_id": window.window_id,
        "tab_id": tab.tab_id if tab else None,
        "session_id": session.session_id if session else None,
    }


async def close_window(connection, window_id: str, force: bool = False) -> Dict[str, Any]:
    """Close a window by ID."""
    from cli_anything.iterm2_ctl.utils.iterm2_backend import async_find_window
    window = await async_find_window(connection, window_id)
    await window.async_close(force=force)
    return {"window_id": window_id, "closed": True}


async def activate_window(connection, window_id: str) -> Dict[str, Any]:
    """Bring a window to focus."""
    from cli_anything.iterm2_ctl.utils.iterm2_backend import async_find_window
    window = await async_find_window(connection, window_id)
    await window.async_activate()
    return {"window_id": window_id, "activated": True}


async def set_window_title(connection, window_id: str, title: str) -> Dict[str, Any]:
    """Set the title of a window."""
    from cli_anything.iterm2_ctl.utils.iterm2_backend import async_find_window
    window = await async_find_window(connection, window_id)
    await window.async_set_title(title)
    return {"window_id": window_id, "title": title}


async def get_window_frame(connection, window_id: str) -> Dict[str, Any]:
    """Get the position and size of a window."""
    from cli_anything.iterm2_ctl.utils.iterm2_backend import async_find_window
    window = await async_find_window(connection, window_id)
    frame = await window.async_get_frame()
    return {
        "window_id": window_id,
        "x": frame.origin.x,
        "y": frame.origin.y,
        "width": frame.size.width,
        "height": frame.size.height,
    }


async def set_window_frame(
    connection, window_id: str, x: float, y: float, width: float, height: float
) -> Dict[str, Any]:
    """Set the position and size of a window."""
    import iterm2
    from cli_anything.iterm2_ctl.utils.iterm2_backend import async_find_window
    window = await async_find_window(connection, window_id)
    frame = iterm2.util.Frame(
        origin=iterm2.util.Point(x=x, y=y),
        size=iterm2.util.Size(width=width, height=height),
    )
    await window.async_set_frame(frame)
    return {"window_id": window_id, "x": x, "y": y, "width": width, "height": height}


async def get_window_fullscreen(connection, window_id: str) -> Dict[str, Any]:
    """Check if a window is in fullscreen mode."""
    from cli_anything.iterm2_ctl.utils.iterm2_backend import async_find_window
    window = await async_find_window(connection, window_id)
    fullscreen = await window.async_get_fullscreen()
    return {"window_id": window_id, "fullscreen": fullscreen}


async def set_window_fullscreen(
    connection, window_id: str, fullscreen: bool
) -> Dict[str, Any]:
    """Set fullscreen mode for a window."""
    from cli_anything.iterm2_ctl.utils.iterm2_backend import async_find_window
    window = await async_find_window(connection, window_id)
    await window.async_set_fullscreen(fullscreen)
    return {"window_id": window_id, "fullscreen": fullscreen}


async def get_current_window(connection) -> Optional[Dict[str, Any]]:
    """Return info about the currently focused window."""
    import iterm2
    app = await iterm2.async_get_app(connection)
    window = app.current_terminal_window
    if window is None:
        return None
    tab = window.current_tab
    session = tab.current_session if tab else None
    return {
        "window_id": window.window_id,
        "tab_id": tab.tab_id if tab else None,
        "session_id": session.session_id if session else None,
    }
