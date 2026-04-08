"""iTerm2 backend — wraps the iterm2 Python API.

This module provides the bridge between the synchronous Click CLI and
the async iterm2 Python API. All iTerm2 operations are async; this module
wraps them for use in synchronous Click commands.

iTerm2 must be running for any operation to work. Enable the Python API
at iTerm2 → Preferences → General → Magic → Enable Python API.
"""
import asyncio
import os
import sys
from typing import Any, Callable, Coroutine


def find_iterm2_app() -> str:
    """Return the path to iTerm2.app, or raise RuntimeError with install instructions."""
    candidates = [
        "/Applications/iTerm.app",
        os.path.expanduser("~/Applications/iTerm.app"),
    ]
    for path in candidates:
        if os.path.isdir(path):
            return path
    raise RuntimeError(
        "iTerm2 is not installed or not in the expected location.\n"
        "Install it from: https://iterm2.com/\n"
        "Then ensure it is running before using this CLI.\n"
        "Also enable the Python API:\n"
        "  iTerm2 → Preferences → General → Magic → Enable Python API"
    )


def require_iterm2_running():
    """Raise a clear error if iTerm2 is not reachable."""
    try:
        import iterm2  # noqa: F401
    except ImportError:
        raise RuntimeError(
            "The 'iterm2' Python package is not installed.\n"
            "Install it with: pip install iterm2"
        )


def run_iterm2(coro_fn: Callable, *args, **kwargs) -> Any:
    """Run an async iTerm2 operation synchronously.

    Args:
        coro_fn: async function with signature (connection, *args, **kwargs) -> result
        *args: positional args to pass to coro_fn
        **kwargs: keyword args to pass to coro_fn

    Returns:
        The return value of coro_fn.

    Raises:
        RuntimeError: If iTerm2 is not running or the API is not enabled.
        ConnectionRefusedError: If the WebSocket connection fails.
    """
    require_iterm2_running()
    import iterm2

    result_holder: dict = {}
    error_holder: dict = {}

    async def _wrapper(connection):
        try:
            result_holder["value"] = await coro_fn(connection, *args, **kwargs)
        except Exception as exc:
            error_holder["exc"] = exc

    try:
        iterm2.run_until_complete(_wrapper)
    except Exception as exc:
        # run_until_complete raises on connection failure
        err_msg = str(exc)
        if "connect" in err_msg.lower() or "refused" in err_msg.lower() or "websocket" in err_msg.lower():
            raise RuntimeError(
                "Cannot connect to iTerm2.\n"
                "Make sure:\n"
                "  1. iTerm2 is running\n"
                "  2. Python API is enabled: iTerm2 → Preferences → General → Magic → Enable Python API\n"
                f"  (Original error: {exc})"
            ) from exc
        raise

    if "exc" in error_holder:
        raise error_holder["exc"]

    return result_holder.get("value")


async def async_get_app(connection):
    """Get the iTerm2 App singleton."""
    import iterm2
    return await iterm2.async_get_app(connection)


async def async_find_window(connection, window_id: str):
    """Find a window by ID or raise ValueError."""
    import iterm2
    app = await iterm2.async_get_app(connection)
    for window in app.windows:
        if window.window_id == window_id:
            return window
    available = [w.window_id for w in app.windows]
    raise ValueError(f"Window '{window_id}' not found. Available: {available}")


async def async_find_tab(connection, tab_id: str):
    """Find a tab by ID across all windows, or raise ValueError."""
    import iterm2
    app = await iterm2.async_get_app(connection)
    for window in app.windows:
        for tab in window.tabs:
            if tab.tab_id == tab_id:
                return tab
    raise ValueError(f"Tab '{tab_id}' not found.")


async def async_find_session(connection, session_id: str):
    """Find a session by ID across all windows/tabs, or raise ValueError."""
    import iterm2
    app = await iterm2.async_get_app(connection)
    for window in app.windows:
        for tab in window.tabs:
            for session in tab.sessions:
                if session.session_id == session_id:
                    return session
    raise ValueError(f"Session '{session_id}' not found.")


def connection_error_help() -> str:
    """Return helpful text for connection errors."""
    return (
        "iTerm2 connection failed.\n"
        "Steps to fix:\n"
        "  1. Open iTerm2\n"
        "  2. Go to: Preferences → General → Magic\n"
        "  3. Check 'Enable Python API'\n"
        "  4. Restart iTerm2 if you just enabled it"
    )
