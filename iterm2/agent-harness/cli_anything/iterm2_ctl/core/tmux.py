"""Tmux integration operations for iTerm2.

Exposes iTerm2's tmux -CC integration: list active connections, send tmux
commands, create tmux windows (shown as iTerm2 tabs), and show/hide them.

All functions are async coroutines intended to be called via
cli_anything.iterm2_ctl.utils.iterm2_backend.run_iterm2().

Prerequisites: a tmux session must be attached via `tmux -CC` inside iTerm2
for any connection to appear. The list commands work even with zero connections.
"""
from typing import Any, Dict, List, Optional


async def _ensure_app_and_connections(connection):
    """Initialize App (sets up DELEGATE_FACTORY) then return tmux connections."""
    import iterm2
    # App must be instantiated first — it registers the delegate factory that
    # async_get_tmux_connections() requires.
    await iterm2.async_get_app(connection)
    return await iterm2.async_get_tmux_connections(connection)


async def _resolve_connection(connection, connection_id: Optional[str]):
    """Return a TmuxConnection by ID, or the first one if ID is None."""
    connections = await _ensure_app_and_connections(connection)
    if not connections:
        raise RuntimeError(
            "No active tmux connections. Start one with:\n"
            "  tmux -CC        # in an iTerm2 terminal\n"
            "  tmux -CC attach # to attach to an existing session"
        )
    if connection_id is None:
        return connections[0]
    for c in connections:
        if c.connection_id == connection_id:
            return c
    available = [c.connection_id for c in connections]
    raise ValueError(
        f"Tmux connection '{connection_id}' not found. Available: {available}"
    )


async def list_connections(connection) -> List[Dict[str, Any]]:
    """List all active iTerm2 tmux integration connections.

    Each connection corresponds to a running `tmux -CC` session. Returns
    an empty list if no tmux integration is active.
    """
    connections = await _ensure_app_and_connections(connection)
    result = []
    for c in connections:
        owning = c.owning_session
        result.append({
            "connection_id": c.connection_id,
            "owning_session_id": owning.session_id if owning else None,
            "owning_session_name": owning.name if owning else None,
        })
    return result


async def send_command(
    connection,
    command: str,
    connection_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Send a tmux command to an active tmux integration connection.

    Args:
        command: Any valid tmux command, e.g. "list-sessions", "new-window -n work".
        connection_id: Which connection to use (None = first available).

    Returns:
        Dict with the tmux command output.
    """
    tc = await _resolve_connection(connection, connection_id)
    output = await tc.async_send_command(command)
    return {
        "connection_id": tc.connection_id,
        "command": command,
        "output": output,
    }


async def create_window(
    connection,
    connection_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new tmux window via iTerm2's integration.

    The new tmux window surfaces as a new iTerm2 tab. Returns window and
    tab info.

    Args:
        connection_id: Which tmux connection to use (None = first available).
    """
    tc = await _resolve_connection(connection, connection_id)
    window = await tc.async_create_window()
    if window is None:
        raise RuntimeError("Failed to create tmux window — got None from iTerm2")
    tab = window.current_tab
    session = tab.current_session if tab else None
    return {
        "connection_id": tc.connection_id,
        "window_id": window.window_id,
        "tab_id": tab.tab_id if tab else None,
        "session_id": session.session_id if session else None,
    }


async def set_window_visible(
    connection,
    tmux_window_id: str,
    visible: bool,
    connection_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Show or hide a tmux window (represented as an iTerm2 tab).

    Args:
        tmux_window_id: The tmux window ID (from tab.tmux_window_id, e.g. "@1").
        visible: True to show, False to hide.
        connection_id: Which tmux connection (None = first available).
    """
    tc = await _resolve_connection(connection, connection_id)
    await tc.async_set_tmux_window_visible(tmux_window_id, visible)
    return {
        "connection_id": tc.connection_id,
        "tmux_window_id": tmux_window_id,
        "visible": visible,
    }


async def list_tmux_tabs(connection) -> List[Dict[str, Any]]:
    """List all iTerm2 tabs that are backed by a tmux integration window.

    Returns only tabs that have a non-None tmux_window_id.
    """
    import iterm2
    app = await iterm2.async_get_app(connection)
    result = []
    for window in app.windows:
        for tab in window.tabs:
            if tab.tmux_window_id is not None:
                result.append({
                    "tab_id": tab.tab_id,
                    "window_id": window.window_id,
                    "tmux_window_id": tab.tmux_window_id,
                    "tmux_connection_id": tab.tmux_connection_id,
                    "session_count": len(tab.sessions),
                })
    return result


async def bootstrap(
    connection,
    attach: bool = False,
    session_id: Optional[str] = None,
    timeout: float = 15.0,
) -> Dict[str, Any]:
    """Start a tmux -CC session in iTerm2 and wait for the connection to appear.

    Sends `tmux -CC` (or `tmux -CC attach`) to a session, then polls
    async_get_tmux_connections() until the connection materialises or the
    timeout expires.

    Args:
        attach: If True, send `tmux -CC attach` instead of `tmux -CC`.
        session_id: Which iTerm2 session to start tmux in. If None, uses the
            current window's first session.
        timeout: Seconds to wait for the connection to appear. Default 15.

    Returns:
        Dict with 'connection_id', 'owning_session_id', 'command', and
        'elapsed_seconds'.
    """
    import asyncio
    import iterm2
    from cli_anything.iterm2_ctl.utils.iterm2_backend import async_find_session

    app = await iterm2.async_get_app(connection)

    # Resolve session
    if session_id is not None:
        target = await async_find_session(connection, session_id)
    else:
        # Fall back to first session in current window
        if not app.windows:
            raise RuntimeError("No iTerm2 windows open. Create one first.")
        target = app.windows[0].current_tab.current_session

    # Snapshot existing connections so we detect the new one
    existing_ids = {
        c.connection_id
        for c in await iterm2.async_get_tmux_connections(connection)
    }

    cmd = "tmux -CC attach" if attach else "tmux -CC"
    await target.async_send_text(cmd + "\n")

    # Poll until a new connection appears
    start = asyncio.get_event_loop().time()
    while True:
        await asyncio.sleep(0.5)
        current = await iterm2.async_get_tmux_connections(connection)
        new_conns = [c for c in current if c.connection_id not in existing_ids]
        if new_conns:
            nc = new_conns[0]
            owning = nc.owning_session
            elapsed = asyncio.get_event_loop().time() - start
            return {
                "connection_id": nc.connection_id,
                "owning_session_id": owning.session_id if owning else None,
                "command": cmd,
                "elapsed_seconds": round(elapsed, 2),
            }
        if asyncio.get_event_loop().time() - start > timeout:
            raise RuntimeError(
                f"Timed out after {timeout}s waiting for tmux -CC connection. "
                "Make sure tmux is installed and no existing session conflicts."
            )


async def run_session_tmux_command(
    connection,
    session_id: str,
    command: str,
) -> Dict[str, Any]:
    """Run a tmux command from within a specific session.

    The session must be a tmux integration session (i.e. the shell running
    inside it is connected to tmux -CC). Raises if the session is not tmux.

    Args:
        session_id: The iTerm2 session ID.
        command: A tmux command to run (e.g. "rename-window foo").
    """
    from cli_anything.iterm2_ctl.utils.iterm2_backend import async_find_session
    session = await async_find_session(connection, session_id)
    output = await session.async_run_tmux_command(command)
    return {
        "session_id": session_id,
        "command": command,
        "output": output,
    }
