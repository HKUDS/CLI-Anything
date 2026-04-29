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
import os
import subprocess
import shutil
from typing import Any, Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# DOMShell MCP server command
# The harness connects to a running DOMShell server via domshell-proxy (stdio bridge).
# Configure via environment variables:
#   DOMSHELL_TOKEN  — auth token (required, must match the running server)
#   DOMSHELL_PORT   — MCP HTTP port of the running server (default: 3001)
DEFAULT_SERVER_CMD = "npx"
MCP_CALL_TIMEOUT_SECONDS = float(os.environ.get("DOMSHELL_MCP_CALL_TIMEOUT", "15"))
MCP_CLOSE_TIMEOUT_SECONDS = float(os.environ.get("DOMSHELL_MCP_CLOSE_TIMEOUT", "2"))


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


def _should_ignore_loop_error(context: dict[str, Any]) -> bool:
    """判断是否忽略已知的 anyio 关闭阶段噪声异常。"""
    exc = context.get("exception")
    if not exc:
        return False
    text = str(exc)
    return "Attempted to exit cancel scope in a different task" in text


def _run_sync(coro):
    """以可控事件循环执行协程，避免 asyncio.run 关闭阶段噪声。"""
    loop = asyncio.new_event_loop()
    old_loop = None
    try:
        old_loop = asyncio.get_event_loop_policy().get_event_loop()
    except RuntimeError:
        old_loop = None
    try:
        asyncio.set_event_loop(loop)
        default_handler = loop.get_exception_handler()

        def _exception_handler(current_loop, context):
            if _should_ignore_loop_error(context):
                return
            if default_handler is not None:
                default_handler(current_loop, context)
            else:
                current_loop.default_exception_handler(context)

        loop.set_exception_handler(_exception_handler)
        return loop.run_until_complete(coro)
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception:
            # 关闭阶段异常不应影响工具结果
            pass
        loop.close()
        asyncio.set_event_loop(old_loop)

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
            return _normalize_tool_result(tool_name, result, arguments)
        except Exception as e:
            # Daemon died, fall back to spawning new server
            await _stop_daemon()

    # Spawn new MCP server process
    server_params = StdioServerParameters(
        command=DEFAULT_SERVER_CMD,
        args=_build_server_args()
    )
    try:
        # 说明：DOMShell 在某些环境下会在 __aexit__ 阶段阻塞，导致命令无输出卡住。
        # 这里改为一次性连接后直接执行并返回，避免被退出清理阻塞。
        client_ctx = stdio_client(server_params)
        read, write = await client_ctx.__aenter__()
        session_ctx = ClientSession(read, write)
        session = await session_ctx.__aenter__()
        await session.initialize()
        result = await asyncio.wait_for(
            session.call_tool(tool_name, arguments),
            timeout=MCP_CALL_TIMEOUT_SECONDS
        )
        return _normalize_tool_result(tool_name, result, arguments)
    except Exception as e:
        raise RuntimeError(
            f"DOMShell MCP call failed: {e}\n"
            f"Ensure Chrome is running with DOMShell extension installed.\n"
            f"Chrome Web Store: https://chromewebstore.google.com/detail/domshell"
        ) from e
async def _safe_aexit(ctx: Any) -> None:
    """带超时保护地关闭异步上下文，避免退出阶段卡死。"""
    if ctx is None:
        return
    try:
        await asyncio.wait_for(
            ctx.__aexit__(None, None, None),
            timeout=MCP_CLOSE_TIMEOUT_SECONDS
        )
    except Exception:
        # 退出阶段失败不应影响主流程
        pass


def _extract_text_content(result: Any) -> str:
    """从 MCP 结果中提取 text 内容。"""
    content_items = getattr(result, "content", None)
    if not content_items:
        return ""
    texts: list[str] = []
    for item in content_items:
        text = getattr(item, "text", None)
        if text:
            texts.append(str(text))
    return "\n".join(texts).strip()


def _parse_ls_text(path: str, text: str) -> dict:
    """将 DOMShell ls 的文本输出解析为结构化 entries。"""
    entries: list[dict[str, str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # 兼容: windows/       (1 windows)
        name_part = stripped.split("(")[0].strip()
        if not name_part:
            continue
        clean_name = name_part.rstrip("/")
        if path in ("", "/"):
            entry_path = f"/{clean_name}"
        else:
            entry_path = f"{path.rstrip('/')}/{clean_name}"
        entries.append(
            {
                "name": clean_name,
                "role": "container",
                "path": entry_path,
            }
        )
    return {"path": path or "/", "entries": entries, "raw_text": text}


def _parse_grep_text(text: str) -> dict:
    """将 DOMShell grep 的文本输出解析为 matches 列表。"""
    matches = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            matches.append(stripped)
    return {"matches": matches, "raw_text": text}


def _normalize_tool_result(tool_name: str, result: Any, arguments: dict) -> dict:
    """将 mcp.types.CallToolResult 统一转换为 CLI 可消费字典。"""
    if isinstance(result, dict):
        return result

    is_error = getattr(result, "isError", False)
    text = _extract_text_content(result)

    if tool_name == "domshell_ls":
        parsed = _parse_ls_text(arguments.get("options", "/"), text)
    elif tool_name == "domshell_grep":
        parsed = _parse_grep_text(text)
    elif tool_name == "domshell_cd":
        parsed = {
            "path": arguments.get("path", "/"),
            "raw_text": text,
        }
    else:
        parsed = {"raw_text": text}

    if is_error:
        parsed["error"] = text or f"{tool_name} failed"
    return parsed

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
        args=_build_server_args()
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
        await _safe_aexit(_daemon_session)
        await _safe_aexit(_daemon_client_context)
    except Exception:
        pass
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
    result = _run_sync(_call_tool("domshell_ls", {"options": path}, use_daemon))
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
    result = _run_sync(_call_tool("domshell_cd", {"path": path}, use_daemon))
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
    result = _run_sync(_call_tool("domshell_cat", {"name": path}, use_daemon))
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
    result = _run_sync(_call_tool(
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
    result = _run_sync(_call_tool("domshell_click", {"name": path}, use_daemon))
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
    result = _run_sync(_call_tool("domshell_open", {"url": url}, use_daemon))
    return result


def reload(use_daemon: bool = False) -> dict:
    """Reload the current page.

    Args:
        use_daemon: Use persistent daemon connection if available

    Returns:
        Dict with reload result
    """
    result = _run_sync(_call_tool("domshell_reload", {}, use_daemon))
    return result


def back(use_daemon: bool = False) -> dict:
    """Navigate back in history.

    Args:
        use_daemon: Use persistent daemon connection if available

    Returns:
        Dict with navigation result
    """
    result = _run_sync(_call_tool("domshell_back", {}, use_daemon))
    return result


def forward(use_daemon: bool = False) -> dict:
    """Navigate forward in history.

    Args:
        use_daemon: Use persistent daemon connection if available

    Returns:
        Dict with navigation result
    """
    result = _run_sync(_call_tool("domshell_forward", {}, use_daemon))
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
    async def _focus_and_type():
        global _daemon_session
        if use_daemon and _daemon_session is not None:
            await _daemon_session.call_tool("domshell_focus", {"name": path})
            return await _daemon_session.call_tool("domshell_type", {"text": text})

        server_params = StdioServerParameters(
            command=DEFAULT_SERVER_CMD,
            args=_build_server_args()
        )
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                await session.call_tool("domshell_focus", {"name": path})
                return await session.call_tool("domshell_type", {"text": text})

    return _run_sync(_focus_and_type())


# ── Daemon control functions ───────────────────────────────────────────

def start_daemon() -> bool:
    """Start persistent daemon mode (sync wrapper).

    Returns:
        True if daemon started successfully

    Raises:
        RuntimeError: If daemon fails to start
    """
    return _run_sync(_start_daemon())


def stop_daemon() -> None:
    """Stop persistent daemon mode (sync wrapper)."""
    _run_sync(_stop_daemon())
