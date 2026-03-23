"""DOMShell MCP client wrapper — communicates with DOMShell MCP server via stdio.

DOMShell is a browser automation tool that maps Chrome's Accessibility Tree
to a virtual filesystem. This module provides a Python interface to DOMShell's
MCP server.

Installation:
1. Install DOMShell Chrome extension from Chrome Web Store
2. Ensure npx is available: npm install -g npx

DOMShell GitHub: https://github.com/apireno/DOMShell
Chrome Web Store: https://chromewebstore.google.com/detail/domshell-%E2%80%94-browser-filesy/okcliheamhmijccjknkkplploacoidnp
"""

import asyncio
import subprocess
import shutil
from typing import Any, Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# DOMShell MCP server command
DEFAULT_SERVER_CMD = "npx"
DEFAULT_SERVER_ARGS = ["@apireno/domshell"]

# Daemon mode: persistent MCP connection
_daemon_session: Optional[ClientSession] = None
_daemon_read: Optional[Any] = None
_daemon_write: Optional[Any] = None
_daemon_client_context: Optional[Any] = None  # Store stdio_client context manager


def _check_npx() -> bool:
    """Check if npx is available."""
    return shutil.which("npx") is not None


def _check_npx_has_domshell() -> bool:
    """Check if DOMShell package is available to npx."""
    try:
        result = subprocess.run(
            ["npx", "@apireno/domshell", "--version"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def is_available() -> tuple[bool, str]:
    """Check if DOMShell MCP server is available.

    Returns:
        (available, message): Tuple of availability status and descriptive message.

    Examples:
        >>> is_available()
        (True, "DOMShell v1.0.0 is available")
        >>> is_available()
        (False, "npx not found. Install Node.js from https://nodejs.org/")
    """
    if not _check_npx():
        return (
            False,
            "npx not found. Install Node.js from https://nodejs.org/ "
            "Then run: npm install -g npx"
        )

    if not _check_npx_has_domshell():
        return (
            False,
            "DOMShell not found. Run `npx @apireno/domshell --version` once\n"
            "Note: The first run may download the package (10-50 MB)."
        )

    # Try to get version
    try:
        result = subprocess.run(
            ["npx", "@apireno/domshell", "--version"],
            capture_output=True,
            timeout=10,
            text=True,
        )
        version = result.stdout.strip() or "unknown"
        return True, f"DOMShell {version} is available"
    except Exception as e:
        return False, f"DOMShell check failed: {e}"


async def _call_tool(
    tool_name: str,
    arguments: dict,
    use_daemon: bool = False
) -> Any:
    """Call a DOMShell MCP tool.

    Args:
        tool_name: Name of the MCP tool (e.g., "domshell_ls", "domshell_cd")
        arguments: Arguments to pass to the tool
        use_daemon: If True, use persistent daemon connection (if available)

    Returns:
        Tool result as returned by MCP server

    Raises:
        RuntimeError: If MCP server is not available or tool call fails
    """
    global _daemon_session, _daemon_read, _daemon_write

    if use_daemon and _daemon_session is not None:
        # Use persistent daemon connection
        try:
            result = await _daemon_session.call_tool(tool_name, arguments)
            return result
        except Exception as e:
            # Daemon died, fall back to spawning new server
            await _stop_daemon()

    # Spawn new MCP server process
    server_params = StdioServerParameters(
        command=DEFAULT_SERVER_CMD,
        args=DEFAULT_SERVER_ARGS
    )

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                return result
    except Exception as e:
        raise RuntimeError(
            f"DOMShell MCP call failed: {e}\n"
            f"Ensure Chrome is running with DOMShell extension installed.\n"
            f"Chrome Web Store: https://chromewebstore.google.com/detail/domshell"
        ) from e

# NOTE: Known limitation - Daemon mode uses asyncio.run() per tool call (in sync wrappers).
# Each asyncio.run() creates a new event loop. Async IO objects created in one loop
# (like the daemon session) may have issues when accessed from subsequent calls that
# create new loops. This is a documented limitation for v1; future work should use
# a single long-lived event loop (e.g., background thread + run_coroutine_threadsafe).
async def _start_daemon() -> bool:
    """Start persistent daemon mode.

    Returns:
        True if daemon started successfully

    Raises:
        RuntimeError: If daemon fails to start
    """
    global _daemon_session, _daemon_read, _daemon_write, _daemon_client_context

    if _daemon_session is not None:
        return True  # Already running

    server_params = StdioServerParameters(
        command=DEFAULT_SERVER_CMD,
        args=DEFAULT_SERVER_ARGS
    )

    try:
        # Store the context manager so we can properly clean it up later
        _daemon_client_context = stdio_client(server_params)
        _daemon_read, _daemon_write = await _daemon_client_context.__aenter__()
        _daemon_session = ClientSession(_daemon_read, _daemon_write)
        await _daemon_session.__aenter__()
        await _daemon_session.initialize()
        return True
    except Exception as e:
        _daemon_session = None
        _daemon_read = None
        _daemon_write = None
        _daemon_client_context = None
        raise RuntimeError(f"Failed to start DOMShell daemon: {e}") from e


async def _stop_daemon() -> None:
    """Stop persistent daemon mode."""
    global _daemon_session, _daemon_read, _daemon_write, _daemon_client_context

    if _daemon_session is None:
        return

    try:
        await _daemon_session.__aexit__(None, None, None)
        if _daemon_client_context:
            await _daemon_client_context.__aexit__(None, None, None)
    except Exception:
        pass  # Ignore cleanup errors
    finally:
        _daemon_session = None
        _daemon_read = None
        _daemon_write = None
        _daemon_client_context = None


def daemon_started() -> bool:
    """Check if daemon mode is active."""
    return _daemon_session is not None


# ── Sync wrappers for each DOMShell tool ─────────────────────────────

def ls(path: str = "/", use_daemon: bool = False) -> dict:
    """List directory contents in the accessibility tree.

    Args:
        path: Path in accessibility tree (e.g., "/", "/main", "/main/div[0]")
        use_daemon: Use persistent daemon connection if available

    Returns:
        Dict with 'entries' key containing list of accessible elements

    Example:
        >>> ls("/")
        {"path": "/", "entries": [{"name": "main", "role": "landmark", ...}]}
    """
    result = asyncio.run(_call_tool("domshell_ls", {"path": path}, use_daemon))
    return result


def cd(path: str, use_daemon: bool = False) -> dict:
    """Change directory in the accessibility tree.

    Args:
        path: Target path
        use_daemon: Use persistent daemon connection if available

    Returns:
        Dict with 'path' key confirming current location

    Example:
        >>> cd("/main/div[0]")
        {"path": "/main/div[0]", "element": {...}}
    """
    result = asyncio.run(_call_tool("domshell_cd", {"path": path}, use_daemon))
    return result


def cat(path: str, use_daemon: bool = False) -> dict:
    """Read element content from the accessibility tree.

    Args:
        path: Path to element
        use_daemon: Use persistent daemon connection if available

    Returns:
        Dict with element details including text, role, attributes

    Example:
        >>> cat("/main/button[0]")
        {"name": "Submit", "role": "button", "text": "Submit", ...}
    """
    result = asyncio.run(_call_tool("domshell_cat", {"path": path}, use_daemon))
    return result


def grep(pattern: str, path: str = "/", use_daemon: bool = False) -> dict:
    """Search for pattern in accessibility tree.

    Args:
        pattern: Text pattern to search for
        path: Root path for search (default: "/")
        use_daemon: Use persistent daemon connection if available

    Returns:
        Dict with 'matches' key containing list of matching elements

    Example:
        >>> grep("Login")
        {"matches": ["/main/button[0]", "/main/link[1]"]}
    """
    result = asyncio.run(_call_tool(
        "domshell_grep",
        {"pattern": pattern, "path": path},
        use_daemon
    ))
    return result


def click(path: str, use_daemon: bool = False) -> dict:
    """Click an element in the accessibility tree.

    Args:
        path: Path to element to click
        use_daemon: Use persistent daemon connection if available

    Returns:
        Dict with action result

    Example:
        >>> click("/main/button[0]")
        {"action": "click", "path": "/main/button[0]", "status": "success"}
    """
    result = asyncio.run(_call_tool("domshell_click", {"path": path}, use_daemon))
    return result


def open_url(url: str, use_daemon: bool = False) -> dict:
    """Navigate to a URL in Chrome.

    Args:
        url: URL to navigate to
        use_daemon: Use persistent daemon connection if available

    Returns:
        Dict with navigation result

    Example:
        >>> open_url("https://example.com")
        {"url": "https://example.com", "status": "loaded"}
    """
    result = asyncio.run(_call_tool("domshell_open", {"url": url}, use_daemon))
    return result


def reload(use_daemon: bool = False) -> dict:
    """Reload the current page.

    Args:
        use_daemon: Use persistent daemon connection if available

    Returns:
        Dict with reload result
    """
    result = asyncio.run(_call_tool("domshell_reload", {}, use_daemon))
    return result


def back(use_daemon: bool = False) -> dict:
    """Navigate back in history.

    Args:
        use_daemon: Use persistent daemon connection if available

    Returns:
        Dict with navigation result
    """
    result = asyncio.run(_call_tool("domshell_back", {}, use_daemon))
    return result


def forward(use_daemon: bool = False) -> dict:
    """Navigate forward in history.

    Args:
        use_daemon: Use persistent daemon connection if available

    Returns:
        Dict with navigation result
    """
    result = asyncio.run(_call_tool("domshell_forward", {}, use_daemon))
    return result


def type_text(path: str, text: str, use_daemon: bool = False) -> dict:
    """Type text into an input element.

    Args:
        path: Path to input element
        text: Text to type
        use_daemon: Use persistent daemon connection if available

    Returns:
        Dict with action result
    """
    result = asyncio.run(_call_tool(
        "domshell_type",
        {"path": path, "text": text},
        use_daemon
    ))
    return result


# ── Daemon control functions ───────────────────────────────────────────

def start_daemon() -> bool:
    """Start persistent daemon mode (sync wrapper).

    Returns:
        True if daemon started successfully

    Raises:
        RuntimeError: If daemon fails to start
    """
    return asyncio.run(_start_daemon())


def stop_daemon() -> None:
    """Stop persistent daemon mode (sync wrapper)."""
    asyncio.run(_stop_daemon())
