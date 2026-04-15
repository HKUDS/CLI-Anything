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
import json
import os
import signal
import socket
import subprocess
import shutil
import sys
from pathlib import Path
from typing import Any, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from cli_anything.browser.utils.tool_result import (
    normalize_tool_result as _normalize_tool_result,
    tool_result_has_error as _tool_result_has_error,
)


# DOMShell MCP server command
# The harness connects to a running DOMShell server via domshell-proxy (stdio bridge).
# Configure via environment variables:
#   DOMSHELL_TOKEN  — auth token (required, must match the running server)
#   DOMSHELL_PORT   — MCP HTTP port of the running server (default: 3001)
DEFAULT_SERVER_CMD = "npx"


def _build_server_args() -> list[str]:
    """Build server args at call time so env var changes are honored."""
    token = os.environ.get("DOMSHELL_TOKEN", "")
    if not token:
        raise RuntimeError(
            "DOMSHELL_TOKEN environment variable is required.\n"
            "Set it to the auth token of your running DOMShell server.\n"
            "Example: export DOMSHELL_TOKEN=<token from DOMShell startup>"
        )
    port = os.environ.get("DOMSHELL_PORT", "3001")
    return [
        "-p", "@apireno/domshell",
        "domshell-proxy",
        "--port", port,
        "--token", token,
    ]

# Daemon mode: persistent MCP connection
#
# v1 used an in-process ClientSession only, which meant `session daemon-start`
# appeared to work but did not survive across CLI invocations. The upgraded
# design below runs a small background Unix-socket daemon so any later process
# can reuse the same browser session.
_daemon_session: Optional[ClientSession] = None
_daemon_read: Optional[Any] = None
_daemon_write: Optional[Any] = None
_daemon_client_context: Optional[Any] = None  # Store stdio_client context manager
_daemon_process: Optional[subprocess.Popen] = None


def _daemon_runtime_dir() -> Path:
    return Path.home() / ".cli-anything-browser"


def _daemon_socket_path() -> Path:
    return _daemon_runtime_dir() / "daemon.sock"


def _daemon_pid_path() -> Path:
    return _daemon_runtime_dir() / "daemon.pid"


def _ensure_daemon_runtime_dir() -> Path:
    path = _daemon_runtime_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _daemon_is_socket_alive() -> bool:
    """Return True when the Unix-socket daemon is reachable."""
    sock = _daemon_socket_path()
    if not sock.exists():
        return False
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(0.5)
            client.connect(str(sock))
            client.sendall(b'{"cmd":"ping"}\n')
            data = b""
            while not data.endswith(b"\n"):
                chunk = client.recv(4096)
                if not chunk:
                    break
                data += chunk
            if not data:
                return False
            payload = json.loads(data.decode("utf-8", errors="replace"))
            return payload.get("ok") is True
    except OSError:
        return False
    except json.JSONDecodeError:
        return False


def daemon_started() -> bool:
    """Check if any daemon process is currently active."""
    return _daemon_is_socket_alive() or _daemon_session is not None


async def _daemon_request(payload: dict, timeout: float = 30.0) -> dict:
    """Send one JSON request to the background daemon."""
    sock = _daemon_socket_path()
    if not sock.exists():
        raise RuntimeError("Daemon socket not found")

    reader, writer = await asyncio.open_unix_connection(str(sock))
    try:
        writer.write((json.dumps(payload) + "\n").encode("utf-8"))
        await writer.drain()

        raw = await asyncio.wait_for(reader.readline(), timeout=timeout)
        if not raw:
            raise RuntimeError("Daemon disconnected before returning a result")
        response = json.loads(raw.decode("utf-8", errors="replace"))
        return response
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


async def _daemon_server_main() -> None:
    """Background daemon process that keeps one DOMShell MCP session alive."""
    socket_path = _daemon_socket_path()
    runtime_dir = _ensure_daemon_runtime_dir()
    pid_path = _daemon_pid_path()

    # Remove stale socket from a prior crash.
    try:
        socket_path.unlink()
    except FileNotFoundError:
        pass

    server_params = StdioServerParameters(
        command=DEFAULT_SERVER_CMD,
        args=_build_server_args(),
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
                try:
                    raw = await reader.readline()
                    if not raw:
                        return
                    request = json.loads(raw.decode("utf-8", errors="replace"))
                    cmd = request.get("cmd")

                    if cmd == "ping":
                        response = {"ok": True}
                    elif cmd == "tool":
                        tool_name = request["tool_name"]
                        arguments = request.get("arguments", {})
                        result = await session.call_tool(tool_name, arguments)
                        response = {"ok": True, "result": _normalize_tool_result(result)}
                    elif cmd == "shutdown":
                        response = {"ok": True, "result": "shutdown"}
                        writer.write((json.dumps(response) + "\n").encode("utf-8"))
                        await writer.drain()
                        return
                    else:
                        response = {"ok": False, "error": f"Unknown command: {cmd}"}
                except Exception as e:
                    response = {"ok": False, "error": str(e)}

                writer.write((json.dumps(response) + "\n").encode("utf-8"))
                await writer.drain()
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass

            server = await asyncio.start_unix_server(handle_client, path=str(socket_path))
            pid_path.write_text(str(os.getpid()), encoding="utf-8")
            try:
                async with server:
                    await server.serve_forever()
            finally:
                try:
                    socket_path.unlink()
                except FileNotFoundError:
                    pass
                try:
                    pid_path.unlink()
                except FileNotFoundError:
                    pass


def _spawn_daemon_process() -> subprocess.Popen:
    """Spawn the background daemon process detached from this CLI."""
    _ensure_daemon_runtime_dir()
    cmd = [
        sys.executable,
        "-c",
        "import asyncio; from cli_anything.browser.utils.domshell_backend import _daemon_server_main; asyncio.run(_daemon_server_main())",
    ]
    return subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        env=os.environ.copy(),
    )


def _kill_pid(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except PermissionError:
        return

    # Give it a moment to exit, then force-kill if needed.
    for _ in range(20):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        except PermissionError:
            return
        except OSError:
            return
        import time
        time.sleep(0.1)
    try:
        os.kill(pid, signal.SIGKILL)
    except Exception:
        pass


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

    # 1) Preferred path: external daemon socket, if present.
    if use_daemon and _daemon_is_socket_alive():
        response = await _daemon_request({
            "cmd": "tool",
            "tool_name": tool_name,
            "arguments": arguments,
        })
        if not response.get("ok"):
            raise RuntimeError(response.get("error", "Daemon tool call failed"))
        return response.get("result")

    # 2) Legacy in-process daemon (kept for backwards compatibility inside the
    # same Python process / REPL session).
    if use_daemon and _daemon_session is not None:
        try:
            result = await _daemon_session.call_tool(tool_name, arguments)
            return _normalize_tool_result(result)
        except Exception:
            await _stop_daemon()

    # 3) One-shot spawn (default path).
    server_params = StdioServerParameters(
        command=DEFAULT_SERVER_CMD,
        args=_build_server_args()
    )

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                return _normalize_tool_result(result)
    except Exception as e:
        raise RuntimeError(
            f"DOMShell MCP call failed: {e}\n"
            f"Ensure Chrome is running with DOMShell extension installed.\n"
            f"Chrome Web Store: https://chromewebstore.google.com/detail/domshell"
        ) from e

# NOTE: Old v1 daemon mode used in-process state only, which could not survive
# across separate CLI invocations. The new daemon uses a background Unix-socket
# process; the in-process client is kept only as a fallback for the REPL.
async def _start_daemon() -> bool:
    """Start persistent daemon mode.

    Returns:
        True if daemon started successfully

    Raises:
        RuntimeError: If daemon fails to start
    """
    global _daemon_session, _daemon_read, _daemon_write, _daemon_client_context, _daemon_process

    if _daemon_is_socket_alive():
        return True

    # Clean up stale pid/socket from previous runs.
    try:
        stale_pid = _daemon_pid_path().read_text(encoding="utf-8").strip()
        if stale_pid.isdigit():
            _kill_pid(int(stale_pid))
    except Exception:
        pass
    try:
        _daemon_socket_path().unlink()
    except FileNotFoundError:
        pass
    try:
        _daemon_pid_path().unlink()
    except FileNotFoundError:
        pass

    try:
        _daemon_process = _spawn_daemon_process()
    except Exception as e:
        raise RuntimeError(f"Failed to spawn DOMShell daemon process: {e}") from e

    # Wait for the socket to become responsive.
    for _ in range(100):
        if _daemon_is_socket_alive():
            return True
        await asyncio.sleep(0.1)

    raise RuntimeError("Failed to start DOMShell daemon: socket never became ready")


async def _stop_daemon() -> None:
    """Stop persistent daemon mode."""
    global _daemon_session, _daemon_read, _daemon_write, _daemon_client_context, _daemon_process

    # Stop in-process session if present.
    if _daemon_session is not None:
        try:
            await _daemon_session.__aexit__(None, None, None)
            if _daemon_client_context:
                await _daemon_client_context.__aexit__(None, None, None)
        except Exception:
            pass
        finally:
            _daemon_session = None
            _daemon_read = None
            _daemon_write = None
            _daemon_client_context = None

    # Stop external daemon process if present.
    pid = None
    try:
        pid_text = _daemon_pid_path().read_text(encoding="utf-8").strip()
        if pid_text.isdigit():
            pid = int(pid_text)
    except Exception:
        pid = None

    if pid is not None:
        _kill_pid(pid)

    try:
        _daemon_socket_path().unlink()
    except FileNotFoundError:
        pass
    try:
        _daemon_pid_path().unlink()
    except FileNotFoundError:
        pass

    _daemon_process = None


def daemon_started() -> bool:
    """Check if daemon mode is active."""
    return _daemon_is_socket_alive() or _daemon_session is not None



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
    result = asyncio.run(_call_tool("domshell_ls", {"options": path}, use_daemon))
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
    result = asyncio.run(_call_tool("domshell_cat", {"name": path}, use_daemon))
    return result


def grep(pattern: str, use_daemon: bool = False) -> dict:
    """Search for pattern in accessibility tree.

    Searches from the current working directory.

    Args:
        pattern: Text pattern to search for
        use_daemon: Use persistent daemon connection if available

    Returns:
        Dict with 'matches' key containing list of matching elements

    Example:
        >>> grep("Login")
        {"matches": ["/main/button[0]", "/main/link[1]"]}
    """
    result = asyncio.run(_call_tool(
        "domshell_grep",
        {"pattern": pattern},
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
    result = asyncio.run(_call_tool("domshell_click", {"name": path}, use_daemon))
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

    Focuses the element first (via domshell_focus), then types. Both operations
    run in a single MCP session so that focus state is preserved.

    Args:
        path: Path to input element
        text: Text to type
        use_daemon: Use persistent daemon connection if available

    Returns:
        Dict with action result
    """
    # Fast preflight: if the target path doesn't exist, return immediately and
    # do not enter the focus/type flow (which can otherwise hang on bad paths).
    preflight = cat(path, use_daemon=use_daemon)
    preflight = _normalize_tool_result(preflight)
    if _tool_result_has_error(preflight):
        return preflight

    async def _focus_and_type():
        global _daemon_session

        if use_daemon and _daemon_session is not None:
            focus_result = await _daemon_session.call_tool("domshell_focus", {"name": path})
            focus_result = _normalize_tool_result(focus_result)
            if _tool_result_has_error(focus_result):
                return focus_result
            type_result = await _daemon_session.call_tool("domshell_type", {"text": text})
            return _normalize_tool_result(type_result)

        server_params = StdioServerParameters(
            command=DEFAULT_SERVER_CMD,
            args=_build_server_args()
        )
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                focus_result = await session.call_tool("domshell_focus", {"name": path})
                focus_result = _normalize_tool_result(focus_result)
                if _tool_result_has_error(focus_result):
                    return focus_result
                type_result = await session.call_tool("domshell_type", {"text": text})
                return _normalize_tool_result(type_result)

    return asyncio.run(_focus_and_type())


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
