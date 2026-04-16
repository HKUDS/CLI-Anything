"""Session-level operations for iTerm2.

A session is a single terminal pane. Tabs can contain multiple sessions
(split panes). All functions are async coroutines.
"""
from typing import Any, Dict, List, Optional


async def list_sessions(
    connection,
    window_id: Optional[str] = None,
    tab_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List all sessions, optionally filtered by window or tab."""
    import iterm2
    app = await iterm2.async_get_app(connection)
    result = []

    for window in app.windows:
        if window_id and window.window_id != window_id:
            continue
        for tab in window.tabs:
            if tab_id and tab.tab_id != tab_id:
                continue
            current_session = tab.current_session
            for session in tab.sessions:
                result.append({
                    "session_id": session.session_id,
                    "name": session.name,
                    "tab_id": tab.tab_id,
                    "window_id": window.window_id,
                    "is_current": (
                        current_session is not None
                        and session.session_id == current_session.session_id
                    ),
                })
    return result


async def get_session_info(connection, session_id: str) -> Dict[str, Any]:
    """Get info about a specific session."""
    from cli_anything.iterm2_ctl.utils.iterm2_backend import async_find_session
    session = await async_find_session(connection, session_id)
    return {
        "session_id": session.session_id,
        "name": session.name,
    }


async def send_text(
    connection,
    session_id: str,
    text: str,
    suppress_broadcast: bool = False,
) -> Dict[str, Any]:
    """Send text/keystrokes to a session.

    Args:
        session_id: Target session ID.
        text: Text to send (use \\n for Enter).
        suppress_broadcast: If True, suppress sending to broadcast domains.

    Returns:
        Dict confirming the send.
    """
    from cli_anything.iterm2_ctl.utils.iterm2_backend import async_find_session
    session = await async_find_session(connection, session_id)
    await session.async_send_text(text, suppress_broadcast=suppress_broadcast)
    return {
        "session_id": session_id,
        "text_length": len(text),
        "sent": True,
    }


async def split_pane(
    connection,
    session_id: str,
    vertical: bool = False,
    before: bool = False,
    profile: Optional[str] = None,
    command: Optional[str] = None,
) -> Dict[str, Any]:
    """Split a session into two panes.

    Args:
        session_id: Session to split.
        vertical: If True, split vertically (side by side). Default: horizontal (top/bottom).
        before: If True, new pane appears before the split point.
        profile: Profile name for new pane (None = same profile).
        command: Command to run in new pane (None = shell).

    Returns:
        Dict with new session_id.
    """
    import iterm2
    from cli_anything.iterm2_ctl.utils.iterm2_backend import async_find_session
    session = await async_find_session(connection, session_id)

    profile_customizations = None
    if command:
        customizations = iterm2.LocalWriteOnlyProfile()
        customizations.set_use_custom_command("Yes")
        customizations.set_command(command)
        profile_customizations = customizations

    new_session = await session.async_split_pane(
        vertical=vertical,
        before=before,
        profile=profile,
        profile_customizations=profile_customizations,
    )
    if new_session is None:
        raise RuntimeError("Failed to split pane")
    return {
        "original_session_id": session_id,
        "new_session_id": new_session.session_id,
        "vertical": vertical,
    }


async def close_session(
    connection, session_id: str, force: bool = False
) -> Dict[str, Any]:
    """Close a session."""
    from cli_anything.iterm2_ctl.utils.iterm2_backend import async_find_session
    session = await async_find_session(connection, session_id)
    await session.async_close(force=force)
    return {"session_id": session_id, "closed": True}


async def activate_session(connection, session_id: str) -> Dict[str, Any]:
    """Bring a session to focus."""
    from cli_anything.iterm2_ctl.utils.iterm2_backend import async_find_session
    session = await async_find_session(connection, session_id)
    await session.async_activate()
    return {"session_id": session_id, "activated": True}


async def get_screen_contents(
    connection, session_id: str, lines: Optional[int] = None
) -> Dict[str, Any]:
    """Get the visible screen contents of a session.

    Args:
        session_id: Target session.
        lines: Number of lines to return (None = all visible lines).

    Returns:
        Dict with 'lines' list and metadata.
    """
    from cli_anything.iterm2_ctl.utils.iterm2_backend import async_find_session
    session = await async_find_session(connection, session_id)
    contents = await session.async_get_screen_contents()
    total = contents.number_of_lines
    limit = lines if lines is not None else total
    screen_lines = []
    for i in range(min(limit, total)):
        line = contents.line(i)
        screen_lines.append(line.string)
    return {
        "session_id": session_id,
        "total_lines": total,
        "returned_lines": len(screen_lines),
        "lines": screen_lines,
    }


async def get_scrollback(
    connection,
    session_id: str,
    lines: Optional[int] = None,
    tail: Optional[int] = None,
) -> Dict[str, Any]:
    """Get the full scrollback buffer including history beyond the visible screen.

    Uses async_get_line_info() + async_get_contents() inside a Transaction for
    consistency. This reads ALL available lines — scrollback history + visible
    screen — not just what's currently visible.

    Args:
        session_id: Target session.
        lines: Max total lines to return (None = all available). Applied from
            the oldest line forward.
        tail: If set, return only the last N lines (most recent). Takes
            precedence over `lines`.

    Returns:
        Dict with:
          - lines: list of line strings (oldest → newest)
          - total_available: scrollback_buffer_height + mutable_area_height
          - scrollback_lines: lines in the history buffer
          - screen_lines: lines in the visible mutable area
          - overflow: lines lost due to buffer overflow
          - returned_lines: count actually returned
    """
    import iterm2
    from cli_anything.iterm2_ctl.utils.iterm2_backend import async_find_session

    session = await async_find_session(connection, session_id)

    async with iterm2.Transaction(connection):
        li = await session.async_get_line_info()
        total_available = li.scrollback_buffer_height + li.mutable_area_height

        if tail is not None:
            # Read only the last `tail` lines
            want = min(tail, total_available)
            first_line = li.overflow + (total_available - want)
            count = want
        elif lines is not None:
            first_line = li.overflow
            count = min(lines, total_available)
        else:
            first_line = li.overflow
            count = total_available

        raw = await session.async_get_contents(first_line, count)

    result_lines = [lc.string for lc in raw]
    return {
        "session_id": session_id,
        "total_available": total_available,
        "scrollback_lines": li.scrollback_buffer_height,
        "screen_lines": li.mutable_area_height,
        "overflow": li.overflow,
        "returned_lines": len(result_lines),
        "lines": result_lines,
    }


async def get_selection(connection, session_id: str) -> Dict[str, Any]:
    """Get the currently selected text in a session."""
    from cli_anything.iterm2_ctl.utils.iterm2_backend import async_find_session
    session = await async_find_session(connection, session_id)
    selection_text = await session.async_get_selection_text(
        await session.async_get_selection()
    )
    return {
        "session_id": session_id,
        "selected_text": selection_text,
        "has_selection": bool(selection_text),
    }


async def set_session_name(connection, session_id: str, name: str) -> Dict[str, Any]:
    """Set the name of a session (shown in the tab bar)."""
    from cli_anything.iterm2_ctl.utils.iterm2_backend import async_find_session
    session = await async_find_session(connection, session_id)
    await session.async_set_name(name)
    return {"session_id": session_id, "name": name}


async def restart_session(
    connection, session_id: str, only_if_exited: bool = False
) -> Dict[str, Any]:
    """Restart a session."""
    from cli_anything.iterm2_ctl.utils.iterm2_backend import async_find_session
    session = await async_find_session(connection, session_id)
    await session.async_restart(only_if_exited=only_if_exited)
    return {"session_id": session_id, "restarted": True}


async def get_session_variable(
    connection, session_id: str, variable_name: str
) -> Dict[str, Any]:
    """Get a session variable value."""
    from cli_anything.iterm2_ctl.utils.iterm2_backend import async_find_session
    session = await async_find_session(connection, session_id)
    value = await session.async_get_variable(variable_name)
    return {
        "session_id": session_id,
        "variable": variable_name,
        "value": value,
    }


async def set_session_variable(
    connection, session_id: str, variable_name: str, value: Any
) -> Dict[str, Any]:
    """Set a session variable."""
    from cli_anything.iterm2_ctl.utils.iterm2_backend import async_find_session
    session = await async_find_session(connection, session_id)
    await session.async_set_variable(variable_name, value)
    return {
        "session_id": session_id,
        "variable": variable_name,
        "value": value,
        "set": True,
    }


async def inject_bytes(connection, session_id: str, data: bytes) -> Dict[str, Any]:
    """Inject raw bytes into a session's input stream (as if received from the shell)."""
    from cli_anything.iterm2_ctl.utils.iterm2_backend import async_find_session
    session = await async_find_session(connection, session_id)
    await session.async_inject(data)
    return {"session_id": session_id, "injected_bytes": len(data)}


def _get_process_name(pid) -> Optional[str]:
    """Return the process name for a given PID using ps, or None on failure."""
    import subprocess
    if pid is None:
        return None
    try:
        result = subprocess.run(
            ["ps", "-p", str(int(pid)), "-o", "comm="],
            capture_output=True, text=True, timeout=2,
        )
        name = result.stdout.strip()
        return name.split("/")[-1] if name else None
    except Exception:
        return None


async def workspace_snapshot(connection) -> Dict[str, Any]:
    """Rich snapshot of every session: name, path, pid, process, role, last screen line.

    For each session across all windows and tabs, returns:
      - session_id, name, window_id, tab_id
      - path:    current working directory (from iTerm2 session variable)
      - pid:     shell PID (from iTerm2 session variable)
      - process: foreground process name derived from pid via ps
      - role:    value of user.role session variable, or null if not set
      - last_line: last non-empty line currently visible on screen

    Use this instead of app status when you need to understand *what is
    happening* in each pane, not just that it exists.
    """
    import iterm2
    app = await iterm2.async_get_app(connection)
    sessions = []

    for window in app.windows:
        for tab in window.tabs:
            for session in tab.sessions:
                path = await session.async_get_variable("path")
                pid = await session.async_get_variable("pid")
                role = await session.async_get_variable("user.role")
                process = _get_process_name(pid)

                last_line = None
                contents = await session.async_get_screen_contents()
                for i in range(contents.number_of_lines - 1, -1, -1):
                    line = contents.line(i).string.strip()
                    if line:
                        last_line = line
                        break

                sessions.append({
                    "session_id": session.session_id,
                    "name": session.name,
                    "window_id": window.window_id,
                    "tab_id": tab.tab_id,
                    "path": path,
                    "pid": pid,
                    "process": process,
                    "role": role,
                    "last_line": last_line,
                })

    return {"session_count": len(sessions), "sessions": sessions}


async def set_grid_size(
    connection, session_id: str, columns: int, rows: int
) -> Dict[str, Any]:
    """Set the terminal grid size (columns x rows) for a session."""
    import iterm2
    from cli_anything.iterm2_ctl.utils.iterm2_backend import async_find_session
    session = await async_find_session(connection, session_id)
    size = iterm2.util.Size(width=columns, height=rows)
    await session.async_set_grid_size(size)
    return {"session_id": session_id, "columns": columns, "rows": rows}
