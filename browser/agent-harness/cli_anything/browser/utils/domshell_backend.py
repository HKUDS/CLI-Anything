"""DOMShell MCP client wrapper — communicates with DOMShell MCP server via stdio.

DOMShell is a browser automation tool that maps Chrome's Accessibility Tree
to a virtual filesystem. This module provides a Python interface to DOMShell's
MCP server.

Installation:
1. Install DOMShell Chrome extension from Chrome Web Store
2. Ensure npx is available: npm install -g npx

DOMShell GitHub: https://github.com/apireno/DOMShell
Chrome Web Store: https://chromewebstore.google.com/detail/domshell-%E2%80%94-browser-filesy/okcliheamhmijccjknkkplploacoidnp

DOMShell 2.0.0 (May 2026) changed the default MCP tool surface from 38
per-command tools to a single `domshell_execute` tool that accepts a
shell-style command string (multi-line supported). This wrapper targets
that single tool.
"""

import asyncio
import logging
import os
import re
import shlex
import subprocess
import shutil
import threading
from typing import Any, Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


log = logging.getLogger(__name__)

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
_daemon_session: Optional[ClientSession] = None
_daemon_read: Optional[Any] = None
_daemon_write: Optional[Any] = None
_daemon_client_context: Optional[Any] = None  # Store stdio_client context manager

# Module-level lane id captured from the first daemon-mode-no-session
# call. Reused on every subsequent daemon-no-session call so direct
# wrappers like `open_url(use_daemon=True)` followed by
# `ls(use_daemon=True)` preserve browser state across calls, regardless
# of whether the daemon's persistent stdio connection is currently
# alive or whether we've fallen back to spawning a fresh ClientSession
# per call. The captured id is a numeric Chrome tab-group id, which
# persists at the browser level even across MCP session boundaries —
# so a fresh spawn can swapToAgentLane(id) into the lane the previous
# spawn (or a still-living daemon) created.
#
# Stale-lane failure mode: if the user manually closes the Chrome tab
# group this id points to, subsequent calls will surface DOMShell's
# "Error: no lane 'A'" with its own recovery guidance. We don't
# auto-recover here — same shape as `session.domshell_lane_id`
# pointing to a closed group. Restart the daemon (or reset this attr)
# to clear.
_daemon_lane_id: Optional[str] = None

# Synchronizes the first-call capture of _daemon_lane_id. Concurrent
# callers of _call_execute in daemon mode without a session would
# otherwise race on the `is None` check below. Lock spans only the
# check + assignment (microsecond contention), not the MCP call.
# (Copilot R4 on commit 5790651.)
_daemon_lane_lock = threading.Lock()


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
        (True, "DOMShell vX.Y.Z is available")   # whatever npx resolves to
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


def _q(arg: str) -> str:
    """Quote an argument for the DOMShell command parser (shell-style).

    Rejects newlines: DOMShell's ``domshell_execute`` splits multi-line
    input *before* shell-style quote parsing, so a ``\\n`` or ``\\r``
    inside an otherwise-quoted argument still becomes a command
    separator. Enforcing the check here means every wrapper that flows
    user input through ``_q`` is protected by default, instead of
    relying on per-call ``_assert_single_line`` at each call site.

    Wrappers may still call ``_assert_single_line`` ahead of ``_q`` when a
    field-named error message (e.g. ``"text: ..."``) is more useful than
    the generic one raised here.
    """
    if "\n" in arg or "\r" in arg:
        # Bound the echoed value so an arbitrarily large untrusted payload
        # (e.g. a multi-line paste from the page) doesn't end up verbatim
        # in error messages or downstream logs / telemetry.
        preview = arg[:80] + ("…" if len(arg) > 80 else "")
        raise ValueError(
            "Newline characters are not allowed in command arguments — "
            "DOMShell's domshell_execute treats them as command separators, "
            "so a newline inside any wrapper input would inject additional "
            f"commands. Got ({len(arg)} chars): {preview!r}"
        )
    return shlex.quote(arg)


# DOMShell 2.x appends a "[lane: <id>]" marker as the last line of every
# domshell_execute reply. We parse it out and store it on the harness
# Session so subsequent calls can pass group_id=<id> and stay pinned to
# the same Chrome tab-group (i.e. same browser state).
#
# The marker format is part of the DOMShell 2.x wire contract — see the
# upstream docs (https://github.com/apireno/DOMShell, search the README
# for "Multi-line semantics" / "lane marker"). If DOMShell ever changes
# the marker format (e.g. to JSON, or to [group: …]), this regex needs
# to follow.
_LANE_LINE = re.compile(r"\[lane:\s*([^\]\s]+)\s*\]\s*$")


def _extract_lane_id(result: Any) -> Optional[str]:
    """Parse the trailing ``[lane: <id>]`` marker DOMShell appends to replies.

    Returns the lane id, or ``None`` if no marker is present, the text is
    empty, or the marker reports the default "shared" lane (which is
    DOMShell's no-isolation sentinel and not something we want to pin to).
    """
    text = ""
    content = getattr(result, "content", None)
    if content:
        for c in content:
            piece = getattr(c, "text", None)
            if piece:
                text += piece
    if not text:
        return None
    m = _LANE_LINE.search(text.strip())
    if not m:
        return None
    lane = m.group(1).strip()
    if not lane or lane == "shared":
        return None
    return lane


def _capture_lane(session: Any, result: Any) -> None:
    """Update ``session.domshell_lane_id`` from a ``_call_execute`` result."""
    if session is None:
        return
    lane = _extract_lane_id(result)
    if lane:
        session.domshell_lane_id = lane


def _translate_path(harness_path: str) -> tuple[str, bool]:
    """Translate a harness DOM path into ``(stripped, is_absolute)``.

    The harness models ``/`` as the focused tab's AX root. DOMShell models
    ``/`` and ``~/`` as the BROWSER root (windows/tabs). DOMShell also
    keeps a per-lane cwd that persists between commands — so after
    ``fs cd /main`` the lane cwd is no longer the tab root, and a
    subsequent ``ls main`` (the naive strip-one-slash form) would resolve
    against the drifted cwd as ``/main/main``. Wrong target.

    The fix: distinguish *absolute* from *relative* harness paths so
    callers can wrap the operation in ``cd %here%[/deeper]\\n<op>\\ncd
    <restore>`` for the absolute case (anchoring at the tab root), and
    pass relative paths through unchanged (the lane cwd is the right
    reference for them).

    Uses ``lstrip("/")`` so accidental ``//main`` collapses to ``main``.

    Examples:
        ``""``          → ``("", False)``
        ``"/"``         → ``("", True)``
        ``"/main"``     → ``("main", True)``
        ``"//main"``    → ``("main", True)``
        ``"/main/btn"`` → ``("main/btn", True)``
        ``"main"``      → ``("main", False)``
        ``".."``        → ``("..", False)``
    """
    # Newline guard at the translation boundary: absolute-path branches
    # interpolate `%here%/<translated>` without going through `_q`
    # (DOMShell's path-variable expander runs before quote parsing on
    # `cd`, so quoting would defeat it). Catching newlines here means
    # every wrapper that consumes the translated path is protected
    # against injection, even if the wrapper skips `_q`.
    if "\n" in harness_path or "\r" in harness_path:
        raise ValueError(
            "Newline characters are not allowed in path arguments — "
            "DOMShell's domshell_execute treats them as command separators, "
            f"so a newline in a path would inject additional commands. "
            f"Got ({len(harness_path)} chars): "
            f"{(harness_path[:80] + ('…' if len(harness_path) > 80 else ''))!r}"
        )
    if not harness_path:
        return "", False
    if harness_path.startswith("/"):
        return harness_path.lstrip("/"), True
    return harness_path, False


def _here_path(deeper: str) -> str:
    """Build a ``%here%[/<deeper>]`` token, shell-quoted as a single unit.

    DOMShell's ``cd`` accepts quoted ``%here%`` cleanly
    (``cd '%here%/main'`` was upstream-smoked: ``✓ Entered tab …``), so
    we quote uniformly via ``_q``. Whitespace, brackets, ``$`` etc. in
    the ``<deeper>`` portion survive the wrap correctly.

    For simple cases (no shell metacharacters) ``_q`` returns the input
    unchanged, so ``_here_path("main")`` is still ``%here%/main``.
    """
    return _q(f"%here%/{deeper}") if deeper else _q("%here%")


def _restore_cwd_cmd(session: Any) -> str:
    """Build the trailing ``cd <wd>`` line for an absolute-path wrap.

    Uses the harness's tracked ``working_dir`` (translated to DOMShell
    form) so after the wrapped operation the lane's cwd matches what the
    harness thinks it is. Without this restore, a wrapped operation
    against ``/`` would leave the lane parked at ``%here%`` even though
    the harness's ``working_dir`` is something like ``/main``.

    The harness ``working_dir`` is always absolute in normal use, so the
    common output shape is ``cd %here%/<stripped>``. The relative
    branch is a defensive fallback for an unusual session shape.
    """
    wd = getattr(session, "working_dir", None) or "/"
    stripped, is_abs = _translate_path(wd)
    if is_abs:
        return f"cd {_here_path(stripped)}"
    return f"cd {_q(stripped)}" if stripped else f"cd {_here_path('')}"


def _anchor_path_cmd(deeper: str = "") -> str:
    """Build a single ``cd %here%[/<deeper>]`` command line, shell-quoted.

    The reusable anchor primitive for split-and-check wrapper patterns.
    Every absolute-path wrapper (ls/cat/click/grep) issues this as its
    first ``_call_execute``, then ``_is_error``-checks the result before
    running the operation. Used for the anchor and restore positions in
    the split-and-check pattern.
    """
    return f"cd {_here_path(deeper)}"


def _require_session_for_split_check(
    wrapper: str, session: Any, use_daemon: bool,
) -> None:
    """Raise if a split-and-check wrapper would lose lane consistency.

    Split-and-check patterns (anchor → op → restore as separate
    ``_call_execute`` calls) need all three calls in the same DOMShell
    lane. In daemon mode the persistent connection guarantees that
    naturally; otherwise the wrapper needs ``session.domshell_lane_id``
    to forward via ``group_id`` on each call. Without either, the
    anchor lands in lane A and the operation lands in lane B — same
    lane-isolation regression as round-5's first failure mode.

    The general rule: any wrapper that issues multiple
    ``_call_execute`` calls whose correctness depends on shared lane
    state requires a session in non-daemon mode. Mirrors the round-6.1
    guard in ``type_text``; applied to ``ls`` / ``cat`` / ``click``
    absolute paths and ``grep`` rooted paths (both absolute and
    relative) in round 7.2. Centralizes the contract so future
    multi-call wrappers can call into the same check.
    """
    if session is None and not use_daemon:
        raise ValueError(
            f"{wrapper}: a session argument is required in non-daemon "
            "mode for rooted paths so the anchor cd and the operation "
            "share a DOMShell lane. Either pass a Session, use an "
            "unrooted form, or enable daemon mode."
        )


# CSI (ANSI) escape sequences DOMShell wraps error text in (typically red).
# Strip them before prefix-matching "error" so an ANSI-coloured error line
# isn't misread as success.
_ANSI_CSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _is_error(result: Any) -> bool:
    """Detect whether a ``domshell_execute`` result represents an error.

    DOMShell's actual error shape (verified upstream) is ANSI-red-wrapped
    AND command-prefixed, e.g.:

    * ``\\x1b[31mcd: foo: No such directory\\x1b[0m``
    * ``\\x1b[31mfocus: No such element\\x1b[0m``
    * ``\\x1b[31mls: main: No such directory\\x1b[0m``

    Note none of these start with the literal "error" — the earlier
    detection that ANSI-stripped first then checked ``startswith("error")``
    silently failed every command-prefixed case, which silently regressed
    the safety chain across ``ls`` / ``cat`` / ``click`` / ``grep`` /
    ``type_text`` (Codex PR #308 round 7+). The fix: detect the
    ``\\x1b[31m`` red color marker BEFORE ANSI stripping — DOMShell wraps
    every error in red and uses different codes (e.g. ``\\x1b[32m``
    green) for success.

    Inspects ``isError`` and dict ``error``/``isError`` keys first
    (covers the MCP SDK's explicit error flag and dict test fixtures),
    then the ANSI-red marker, with a final fallback to a stripped
    ``Error:`` prefix for any input that has been pre-stripped (e.g. by
    a transport layer) or that arrives without DOMShell's coloring.
    """
    if hasattr(result, "isError") and result.isError:
        return True
    if isinstance(result, dict):
        if result.get("isError") or result.get("error"):
            return True

    text = _extract_text(result)
    if not text:
        return False

    # DOMShell wraps errors in ANSI red. Detect BEFORE stripping; the
    # color code IS the signal, and the message that follows is
    # typically command-prefixed (cd: …, focus: …, ls: …) rather than
    # "Error:"-prefixed.
    if "\x1b[31m" in text:
        return True

    # Fallback: ANSI-stripped text with explicit "Error:" prefix.
    # Catches rarer non-colored errors and any input that arrives
    # pre-stripped.
    cleaned = _ANSI_CSI_RE.sub("", text).strip().lower()
    if cleaned.startswith("error:"):
        return True

    return False


def _extract_text(result: Any) -> str:
    """Concatenate ``content[*].text`` from a CallToolResult-like object."""
    text = ""
    content = getattr(result, "content", None)
    if content:
        for c in content:
            piece = getattr(c, "text", None)
            if piece:
                text += piece
    return text


def _parse_execute_result(result: Any, command: str) -> dict:
    """Translate a ``domshell_execute`` text response into the dict shape
    ``browser_cli.py`` and friends consume.

    DOMShell 2.x returns text content over MCP (plus a trailing
    ``[lane: <id>]`` marker). The CLI was written for the pre-2.0
    per-command tools, which returned structured dicts — so without
    this translator the harness throws ``AttributeError`` on
    ``result.get("entries")`` / ``result.get("matches")`` etc.

    The shape contract per command (read off the CLI callers):

    * ``ls``  → ``{"entries": [{"name", "role", "path"}, ...], "raw"}``
    * ``grep``→ ``{"matches": [...], "raw"}``
    * error  → ``{"error": text, "output": text}`` (caller checks
      ``"error" in result`` before normal handling)
    * other  → ``{"output": text}`` (CLI's ``output()`` / ``_print_dict``
      handles arbitrary dicts; ``page.go_back/forward`` skip the
      ``set_url`` step if ``"url"`` is absent, matching today's behavior)

    This is a minimum-viable parser that satisfies the dict-key
    contract. Finer-grained parsing of element name / role / path
    columns can land as a follow-up once DOMShell's exact text format
    stabilizes — for now every line is plumbed through as the ``name``
    field (and the ``path`` field) so the CLI's table view still
    renders rather than crashing.
    """
    text = _LANE_LINE.sub("", _extract_text(result)).strip()

    if _is_error(result):
        return {"error": text, "output": text}

    if command == "ls":
        lines = [ln for ln in text.splitlines() if ln.strip()]
        entries = [
            {"name": ln.strip(), "role": "", "path": ln.strip()}
            for ln in lines
        ]
        return {"entries": entries, "raw": text}

    if command == "grep":
        matches = [ln for ln in text.splitlines() if ln.strip()]
        return {"matches": matches, "raw": text}

    if command in ("back", "forward", "navigate", "open"):
        # Navigation commands typically respond with a `URL: <url>`
        # (and often `Title: <title>`) line — extract both so
        # `page.go_back` / `page.go_forward`'s `"url" in result` guards
        # actually fire and `session.set_url` updates correctly. (Round
        # 7's parser made these guards permanently False; this is the
        # Codex P2 #1 fix.) The raw `output` is preserved alongside so
        # CLI display paths still work.
        nav: dict = {"output": text}
        url_match = re.search(r"URL:\s+(\S+)", text)
        if url_match:
            nav["url"] = url_match.group(1)
        title_match = re.search(r"Title:\s+(.+?)(?:\r?\n|$)", text)
        if title_match:
            nav["title"] = title_match.group(1).strip()
        return nav

    # cd / cat / click / focus / type / refresh all funnel through the
    # CLI's generic dict pretty-printer; an ``{"output": text}`` shape
    # is enough.
    return {"output": text}


def _assert_single_line(field: str, value: str) -> None:
    """Reject newline characters in a user-supplied string.

    DOMShell's ``domshell_execute`` splits its ``command`` argument on
    newlines *before* shell-style quote parsing, so a literal ``\\n`` or
    ``\\r`` inside an otherwise-quoted argument escapes the quoting and
    starts a fresh DOMShell command. Guard at the wrapper layer for any
    value that gets interpolated into a multi-line command string.
    """
    if "\n" in value or "\r" in value:
        raise ValueError(
            f"{field}: newline characters are not allowed (would be interpreted "
            f"as DOMShell command separators). Got: {value!r}"
        )


async def _call_execute(
    command: str,
    use_daemon: bool = False,
    *,
    session: Any = None,
) -> Any:
    """Run a DOMShell command via the single `domshell_execute` MCP tool.

    Args:
        command: DOMShell command string. May contain newlines for multi-command
            execution — each line runs in order in the same shell state.
        use_daemon: If True, use persistent daemon connection (if available)
        session: Harness ``Session`` whose ``domshell_lane_id`` should be
            forwarded as ``group_id`` (when set) and updated from the result
            (when DOMShell returns a ``[lane: <id>]`` marker). Pass ``None``
            for one-off direct calls that don't need cross-call state.

    Returns:
        Tool result as returned by MCP server

    Raises:
        RuntimeError: If MCP server is not available or tool call fails
    """
    global _daemon_session, _daemon_read, _daemon_write, _daemon_lane_id

    arguments: dict[str, Any] = {"command": command}
    # Lane handling — three sources, in priority order:
    #   • Session with a captured lane id  → reuse that lane (REPL pattern,
    #     state preserved across non-daemon spawn-per-call sequences).
    #   • Daemon mode + no session + previously captured _daemon_lane_id
    #     → reuse the daemon-level captured id. Works whether the daemon's
    #     stdio is alive (id reused on persistent connection) or dead
    #     (fresh spawn joins the existing Chrome tab-group by id).
    #   • Otherwise → group_id="new". DOMShell creates a fresh isolated
    #     lane and returns the id in the [lane: ...] marker, captured into
    #     either session.domshell_lane_id or _daemon_lane_id for next time.
    #
    # The "shared" branch from the previous version of this code (commit
    # 99d1182) is gone. It claimed the per-connection default lane stayed
    # sticky across calls — true when the persistent daemon connection is
    # alive, but a lie in the fall-back spawn path where each call gets a
    # different per-MCP-session default lane. @yuh-yang's review of
    # b684732 flagged the inconsistency. The module-level capture path
    # below is consistent across both daemon-alive and daemon-dead.
    if session is not None and getattr(session, "domshell_lane_id", None):
        arguments["group_id"] = session.domshell_lane_id
    elif use_daemon and _daemon_lane_id:
        arguments["group_id"] = _daemon_lane_id
    else:
        arguments["group_id"] = "new"

    if use_daemon and _daemon_session is not None:
        # Use persistent daemon connection
        try:
            result = await _daemon_session.call_tool(
                "domshell_execute", arguments
            )
            _capture_lane(session, result)
            # Daemon-level capture on first daemon-no-session call so
            # subsequent calls reuse the same lane regardless of whether
            # the daemon stays alive or we fall back to fresh spawns.
            # `is None` check moved INSIDE the lock to fix the
            # test-and-set race between concurrent callers.
            if use_daemon and session is None:
                with _daemon_lane_lock:
                    if _daemon_lane_id is None:
                        captured = _extract_lane_id(result)
                        if captured:
                            _daemon_lane_id = captured
            return result
        except Exception as e:
            # Daemon died — log diagnosability and fall back to spawning
            # a fresh server below. Silent swallow was making the daemon
            # failure mode invisible in user reports.
            log.warning(
                "DOMShell daemon call failed, respawning per-command: %s", e,
                exc_info=True,
            )
            await _stop_daemon()

    # Spawn new MCP server process
    server_params = StdioServerParameters(
        command=DEFAULT_SERVER_CMD,
        args=_build_server_args()
    )

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as mcp_session:
                await mcp_session.initialize()
                result = await mcp_session.call_tool(
                    "domshell_execute", arguments
                )
                _capture_lane(session, result)
                # See daemon-path capture above for rationale — same
                # logic applies on the fresh-spawn fall-back path,
                # including the lock-guarded test-and-set.
                if use_daemon and session is None:
                    with _daemon_lane_lock:
                        if _daemon_lane_id is None:
                            captured = _extract_lane_id(result)
                            if captured:
                                _daemon_lane_id = captured
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


# ── Sync wrappers for each DOMShell command ──────────────────────────
#
# Each wrapper builds a shell-style command string and dispatches to
# `domshell_execute`. The public Python API is unchanged from the
# pre-2.0.0 per-tool wrappers.

def ls(path: str = "/", use_daemon: bool = False, *, session: Any = None) -> dict:
    """List directory contents in the accessibility tree.

    Args:
        path: Path in accessibility tree (e.g., "/", "/main", "/main/div[0]")
        use_daemon: Use persistent daemon connection if available
        session: Harness session whose DOMShell lane id is reused / updated

    Returns:
        Dict shaped ``{"entries": [{"name": str, "role": "", "path": str}, ...],
        "raw": str}`` (or ``{"error": str, "output": str}`` on failure —
        wrappers reuse ``_parse_execute_result``'s contract).

        ``name`` and ``path`` carry the raw line text from DOMShell's
        ``ls`` output; directory entries currently include a trailing
        ``/`` (cosmetic, see follow-up). ``role`` is always empty in
        this round — structured role extraction will land alongside a
        finer column parser in the follow-up.

    Example:
        >>> ls("/main", session=session)   # session required for absolute paths
        {"entries": [{"name": "heading_1", "role": "", "path": "heading_1"},
                     {"name": "div/",      "role": "", "path": "div/"},
                     ...],
         "raw": "heading_1\\ndiv/\\n..."}
    """
    translated, is_absolute = _translate_path(path)
    if is_absolute:
        _require_session_for_split_check("ls", session, use_daemon)
        # Split-and-check: the anchor's success is load-bearing — if
        # cd fails, ls would run in the wrong cwd and produce
        # wrong-target results. Three separate _call_execute calls so
        # we can _is_error-gate after the anchor and skip the operation
        # cleanly. All share the persisted lane via session.
        anchor = asyncio.run(_call_execute(
            _anchor_path_cmd(translated), use_daemon, session=session,
        ))
        if _is_error(anchor):
            return _parse_execute_result(anchor, "ls")
        op = asyncio.run(_call_execute("ls", use_daemon, session=session))
        # Best-effort restore — ls already ran; restore failure is
        # cosmetic (next harness cd corrects any drift).
        asyncio.run(_call_execute(
            _restore_cwd_cmd(session), use_daemon, session=session,
        ))
        return _parse_execute_result(op, "ls")
    if translated:
        op = asyncio.run(_call_execute(
            f"ls {_q(translated)}", use_daemon, session=session,
        ))
    else:
        op = asyncio.run(_call_execute("ls", use_daemon, session=session))
    return _parse_execute_result(op, "ls")


def cd(path: str, use_daemon: bool = False, *, session: Any = None) -> dict:
    """Change directory in the accessibility tree.

    Args:
        path: Target path
        use_daemon: Use persistent daemon connection if available
        session: Harness session whose DOMShell lane id is reused / updated

    Returns:
        Dict shaped ``{"output": str}`` on success, or
        ``{"error": str, "output": str}`` on failure.

        Note no ``"path"`` key — ``fs.change_directory`` falls back to
        the input ``path`` arg via ``result.get("path", path)``, so the
        harness's ``working_dir`` ends up at the requested target. The
        ``output`` field carries DOMShell's raw confirmation text for
        display.

    Example:
        >>> cd("/main/div[0]")
        {"output": "✓ Entered /main/div[0]"}
        >>> cd("/missing")
        {"error": "cd: /missing: No such directory",
         "output": "cd: /missing: No such directory"}
    """
    translated, is_absolute = _translate_path(path)
    # cd is the one wrapper where the operation IS the new state — no
    # following operation needs the anchored cwd, so no split-and-check
    # and no restore. Absolute targets anchor via `cd %here%/<rest>` so
    # the result is independent of the lane's current cwd.
    if is_absolute:
        command = _anchor_path_cmd(translated)
    elif translated:
        command = f"cd {_q(translated)}"
    else:
        # Bare/empty `cd` → back to tab root.
        command = _anchor_path_cmd("")
    result = asyncio.run(_call_execute(command, use_daemon, session=session))
    return _parse_execute_result(result, "cd")


def cat(path: str, use_daemon: bool = False, *, session: Any = None) -> dict:
    """Read element content from the accessibility tree.

    Args:
        path: Path to element
        use_daemon: Use persistent daemon connection if available
        session: Harness session whose DOMShell lane id is reused / updated

    Returns:
        Dict with element details including text, role, attributes

    Example:
        >>> cat("/main/button[0]", session=session)   # required for absolute paths
        {"output": "button: Submit\\n..."}
    """
    translated, is_absolute = _translate_path(path)
    # Note: a falsy `translated` (root path `/` or empty string) is no
    # longer rejected here. Pre-migration `fs cat` at the root surfaced
    # DOMShell's own `Usage: cat <name>` error string; the round-5 guard
    # converted that into a Python ValueError, which broke the
    # `fs.read_element(session, "")` fall-through to `session.working_dir`
    # for callers landed at `/`. Removed per @yuh-yang R3 review of
    # `b684732` — `cat ''` reaches DOMShell, which has the same
    # `if (!targetName)` check and returns its standard Usage error.
    if is_absolute:
        _require_session_for_split_check("cat", session, use_daemon)
        # Split-and-check: anchor at tab root, halt if anchor fails,
        # otherwise run relative cat, restore. Anchor success is
        # load-bearing — without it cat resolves the relative path
        # against the wrong cwd.
        anchor = asyncio.run(_call_execute(
            _anchor_path_cmd(""), use_daemon, session=session,
        ))
        if _is_error(anchor):
            return _parse_execute_result(anchor, "cat")
        op = asyncio.run(_call_execute(
            f"cat {_q(translated)}", use_daemon, session=session,
        ))
        asyncio.run(_call_execute(
            _restore_cwd_cmd(session), use_daemon, session=session,
        ))
        return _parse_execute_result(op, "cat")
    op = asyncio.run(_call_execute(
        f"cat {_q(translated)}", use_daemon, session=session,
    ))
    return _parse_execute_result(op, "cat")


def grep(
    pattern: str,
    *,
    path: str = "",
    prev: str = "/",
    use_daemon: bool = False,
    session: Any = None,
) -> dict:
    """Search for pattern in the accessibility tree.

    When ``path`` is provided and is not ``/``, the search is rooted at that
    path: ``cd`` into it, ``grep``, then ``cd`` back to ``prev`` — sent as one
    multi-line ``domshell_execute`` call so all three lines share an MCP
    session (and therefore a DOMShell lane / cwd). Each ``_call_execute`` in
    non-daemon mode opens a fresh stdio session that lands in its own
    DOMShell 2.x lane, so splitting cd/grep/restore across separate calls
    would lose the cwd between them. The trailing ``cd prev`` is delivered as
    the final line of the same command and runs even if ``grep`` errors —
    DOMShell's multi-line splitter continues past errors (see
    `apireno/DOMShell#46 <https://github.com/apireno/DOMShell/issues/46>`_).

    ``path``, ``prev``, and ``use_daemon`` are keyword-only to prevent silent
    breakage of callers written against the pre-migration positional
    signature ``grep(pattern, use_daemon)``.

    Args:
        pattern: Text pattern to search for
        path: Optional path to root the search at. If empty or "/", searches
            from the server-side current working directory.
        prev: Path to restore as cwd after the search. Used only when
            ``path`` is provided. Defaults to "/".
        use_daemon: Use persistent daemon connection if available

    Returns:
        Dict with 'matches' key containing list of matching elements

    Example:
        >>> grep("Login")                                # unrooted — session optional
        {"matches": ["/main/button[0]", "/main/link[1]"], "raw": "..."}
        >>> grep("Login", path="/main", session=session)   # rooted → session required
        {"matches": ["/main/button[0]"], "raw": "..."}
    """
    _assert_single_line("pattern", pattern)

    # DOMShell's parseArgs treats any arg starting with "-" as a flag,
    # with no "--" end-of-options separator and no "-e <pattern>" form
    # (verified against src/background/index.ts:1692 in DOMShell 2.0.2).
    # So `grep -r -- -foo` and `grep -r -e -foo` both fail at the
    # kernel — neither survives parseArgs as a positional. Until
    # DOMShell adds "--" support in a future release, raise a clear
    # Python-side error so the user sees the limitation immediately
    # instead of getting DOMShell's generic "Usage:" reply.
    # (yuh-yang R3 blocker 3, Path B — Python-side soft validation.)
    if pattern.startswith("-"):
        raise ValueError(
            f"grep: patterns starting with '-' are not supported by the "
            f"current DOMShell parser — it would parse {pattern!r} as a "
            f"flag rather than as the search pattern. Known limitation "
            f"tracked upstream; will be resolved when DOMShell's "
            f"parseArgs adds `--` end-of-options support. Workaround: "
            f"drop the leading '-' from the pattern if possible, or "
            f"wait for the upstream fix."
        )
    translated_path, path_abs = _translate_path(path)
    if not translated_path:
        # Unrooted grep — operate on lane cwd, no cd, no restore.
        # `-r` preserves the pre-migration semantic: the old
        # `domshell_grep` tool defaulted to recursive=True (walk all
        # descendants). Plain `grep <pat>` in DOMShell shell only
        # searches the cwd's immediate children, missing nested matches.
        op = asyncio.run(_call_execute(
            f"grep -r {_q(pattern)}", use_daemon, session=session,
        ))
        return _parse_execute_result(op, "grep")

    # `path` was already newline-guarded by `_translate_path` above
    # (round 6's translation-boundary check) so the field-named
    # `_assert_single_line("path", path)` we used to call here would be
    # dead. `prev`, however, is only translated in the relative branch
    # below — the absolute branch doesn't touch it. Keep the explicit
    # field-named guard for `prev` so a newlined-prev kwarg raises a
    # useful error regardless of which branch consumes it.
    _assert_single_line("prev", prev)

    # Both rooted branches (absolute and relative) issue 3 separate
    # `_call_execute` calls — anchor cd, grep, restore cd — and depend on
    # all three landing in the same DOMShell lane. Check session here so
    # the requirement applies uniformly.
    _require_session_for_split_check("grep", session, use_daemon)

    # Split-and-check. Anchor success is load-bearing: if the cd
    # to the rooting path fails, grep would search against the wrong
    # cwd and produce wrong-scope matches.
    if path_abs:
        anchor_cmd = _anchor_path_cmd(translated_path)
        restore_cmd = _restore_cwd_cmd(session)
    else:
        translated_prev, prev_abs = _translate_path(prev)
        anchor_cmd = f"cd {_q(translated_path)}"
        if prev_abs:
            restore_cmd = _anchor_path_cmd(translated_prev)
        else:
            restore_cmd = (
                f"cd {_q(translated_prev)}"
                if translated_prev
                else _anchor_path_cmd("")
            )

    anchor = asyncio.run(_call_execute(anchor_cmd, use_daemon, session=session))
    if _is_error(anchor):
        return _parse_execute_result(anchor, "grep")
    # `-r` preserves the pre-migration recursive default (see unrooted
    # branch above for the full rationale).
    op = asyncio.run(_call_execute(
        f"grep -r {_q(pattern)}", use_daemon, session=session,
    ))
    asyncio.run(_call_execute(restore_cmd, use_daemon, session=session))
    return _parse_execute_result(op, "grep")


def click(path: str, use_daemon: bool = False, *, session: Any = None) -> dict:
    """Click an element in the accessibility tree.

    Args:
        path: Path to element to click
        use_daemon: Use persistent daemon connection if available
        session: Harness session whose DOMShell lane id is reused / updated

    Returns:
        Dict with action result

    Example:
        >>> click("/main/button[0]", session=session)   # required for absolute paths
        {"output": "✓ Clicked\\n[lane: 1]"}
    """
    translated, is_absolute = _translate_path(path)
    if not translated:
        raise ValueError(
            "click: an element name is required — cannot click the tab root."
        )
    if is_absolute:
        _require_session_for_split_check("click", session, use_daemon)
        # Split-and-check: anchor at tab root, halt if anchor fails,
        # otherwise click the relative path, restore. Anchor success is
        # load-bearing — clicking the wrong element if cwd has drifted
        # could trigger an unintended action.
        anchor = asyncio.run(_call_execute(
            _anchor_path_cmd(""), use_daemon, session=session,
        ))
        if _is_error(anchor):
            return _parse_execute_result(anchor, "click")
        op = asyncio.run(_call_execute(
            f"click {_q(translated)}", use_daemon, session=session,
        ))
        asyncio.run(_call_execute(
            _restore_cwd_cmd(session), use_daemon, session=session,
        ))
        return _parse_execute_result(op, "click")
    op = asyncio.run(_call_execute(
        f"click {_q(translated)}", use_daemon, session=session,
    ))
    return _parse_execute_result(op, "click")


def open_url(url: str, use_daemon: bool = False, *, session: Any = None) -> dict:
    """Navigate to a URL in Chrome.

    Args:
        url: URL to navigate to
        use_daemon: Use persistent daemon connection if available
        session: Harness session whose DOMShell lane id is reused / updated

    Returns:
        Dict shaped ``{"output": str, "url": str, "title": str}`` on
        success, or ``{"error": str, "output": str}`` on failure.

        ``url`` and ``title`` are extracted from the DOMShell response
        text via regex (lines starting ``URL:`` / ``Title:``) — they're
        present when DOMShell emits those lines, omitted otherwise.
        ``page.open_page`` doesn't depend on ``url`` (it always calls
        ``session.set_url(url)`` from the input arg), but the same
        parser is used by ``back`` / ``forward`` whose ``page``-layer
        callers DO depend on ``"url" in result``.

    Example:
        >>> open_url("https://example.com")
        {"output": "✓ Opened\\nURL: https://example.com\\nTitle: Example Domain\\n[lane: 1]",
         "url": "https://example.com",
         "title": "Example Domain"}
    """
    result = asyncio.run(
        _call_execute(f"open {_q(url)}", use_daemon, session=session)
    )
    return _parse_execute_result(result, "open")


def reload(use_daemon: bool = False, *, session: Any = None) -> dict:
    """Reload the current page.

    Args:
        use_daemon: Use persistent daemon connection if available
        session: Harness session whose DOMShell lane id is reused / updated

    Returns:
        Dict with reload result
    """
    result = asyncio.run(_call_execute("refresh", use_daemon, session=session))
    return _parse_execute_result(result, "refresh")


def back(use_daemon: bool = False, *, session: Any = None) -> dict:
    """Navigate back in history.

    Args:
        use_daemon: Use persistent daemon connection if available
        session: Harness session whose DOMShell lane id is reused / updated

    Returns:
        Dict shaped ``{"output": str, "url": str, "title": str}`` on
        success, or ``{"error": str, "output": str}`` on failure. ``url``
        and ``title`` are extracted from the response text via regex
        (lines starting ``URL:`` / ``Title:``) and may be omitted if
        the response shape changes upstream — ``page.go_back`` guards
        its ``session.set_url`` update on ``"url" in result``, so a
        missing URL silently skips the update.
    """
    result = asyncio.run(_call_execute("back", use_daemon, session=session))
    return _parse_execute_result(result, "back")


def forward(use_daemon: bool = False, *, session: Any = None) -> dict:
    """Navigate forward in history.

    Args:
        use_daemon: Use persistent daemon connection if available
        session: Harness session whose DOMShell lane id is reused / updated

    Returns:
        Dict shaped ``{"output": str, "url": str, "title": str}`` on
        success, or ``{"error": str, "output": str}`` on failure. ``url``
        and ``title`` are extracted from the response text via regex
        (lines starting ``URL:`` / ``Title:``) and may be omitted if
        the response shape changes upstream — ``page.go_forward`` guards
        its ``session.set_url`` update on ``"url" in result``, so a
        missing URL silently skips the update.
    """
    result = asyncio.run(_call_execute("forward", use_daemon, session=session))
    return _parse_execute_result(result, "forward")


def type_text(
    path: str,
    text: str,
    use_daemon: bool = False,
    *,
    session: Any = None,
) -> dict:
    """Type text into an input element.

    Issued as separate ``domshell_execute`` calls — ``focus``, check for
    error, then ``type`` only if ``focus`` succeeded. Both share the
    persisted lane id (via ``session``), so the focus state from the
    first call carries into the second.

    Why split: DOMShell's multi-line splitter continues past per-line
    errors (apireno/DOMShell#46). That's the right semantic for cleanup
    chains like ``cd / grep / cd back`` (the restore must always run)
    but the WRONG semantic for safety chains like ``focus / type`` — a
    failed ``focus`` followed by a successful ``type`` would dispatch
    keys into whatever was previously focused (potentially a password
    field). Halting between focus and type prevents that.

    Performance note: in non-daemon mode with an absolute path this
    issues up to four ``_call_execute`` calls (anchor ``cd``, focus,
    type, restore ``cd``), and each opens a fresh stdio MCP session —
    so up to four ``npx`` server spawns per call. Relative paths use
    two calls; daemon mode reuses one persistent connection for the
    whole chain regardless of path form. The per-call overhead is
    accepted to keep the wrapper-level error semantics simple; a future
    refactor could share a single ``ClientSession`` across the chain
    (post-merge follow-up).

    Args:
        path: Path to input element
        text: Text to type
        use_daemon: Use persistent daemon connection if available
        session: Harness session whose DOMShell lane id is reused / updated

    Returns:
        Dict with action result. If ``focus`` errors, returns the focus
        result without calling ``type``.

    Raises:
        ValueError: If ``path`` or ``text`` contains a newline. DOMShell's
            ``domshell_execute`` treats newlines as command separators, so
            an embedded newline would inject additional commands. Split
            into multiple ``type_text`` calls for multi-line input.
    """
    _assert_single_line("path", path)
    _assert_single_line("text", text)

    # In daemon mode both halves share the persistent `_daemon_session`
    # naturally — same MCP session means same DOMShell lane, no
    # group_id juggling needed. Only the non-daemon path requires
    # `session.domshell_lane_id` because each `_call_execute` opens a
    # fresh stdio session that would land in its own lane otherwise.
    if session is None and not use_daemon:
        raise ValueError(
            "type_text: a session argument is required in non-daemon mode "
            "so the focus and type calls share a DOMShell lane via group_id. "
            "(Daemon mode shares the persistent connection's lane "
            "automatically and doesn't need session.)"
        )

    translated_path, is_absolute = _translate_path(path)
    if not translated_path:
        raise ValueError(
            "type_text: an input path is required — cannot focus the tab root."
        )

    # type_text is a safety chain (focus → type), NOT a cleanup-line
    # idiom (cd → op → cd back). Cleanup-line patterns want continue-on-
    # error so the restore always runs. Safety chains want the opposite:
    # halt on the first step's error so the second step doesn't dispatch
    # against stale state. Wrapping focus inside `_wrap_absolute` (a
    # multi-line continue-on-error script) re-introduces the trap the
    # round-4 split was designed to prevent — the anchor's leading "✓"
    # text in the combined response masks the focus error, and `type`
    # would land in whatever was previously focused.
    #
    # So for absolute paths we anchor with a SEPARATE _call_execute
    # (one-line `cd %here%`), check for error, focus as a separate call
    # we can _is_error-check, then type, then restore as a separate
    # best-effort call. All four share the persisted lane via session.
    if is_absolute:
        anchor_result = asyncio.run(_call_execute(
            _anchor_path_cmd(""), use_daemon, session=session,
        ))
        if _is_error(anchor_result):
            # Anchor failed — we never moved, so no restore is needed.
            return _parse_execute_result(anchor_result, "focus")

    focus_result = asyncio.run(_call_execute(
        f"focus {_q(translated_path)}", use_daemon, session=session,
    ))
    if _is_error(focus_result):
        # Focus failed — restore cwd before returning so the lane
        # doesn't stay parked at the anchor (only relevant when we
        # actually moved, i.e. the absolute path branch).
        if is_absolute:
            asyncio.run(_call_execute(
                _restore_cwd_cmd(session), use_daemon, session=session,
            ))
        return _parse_execute_result(focus_result, "focus")

    type_result = asyncio.run(_call_execute(
        f"type {_q(text)}", use_daemon, session=session,
    ))

    if is_absolute:
        # Best-effort restore — type already succeeded, so a restore
        # failure is cosmetic. The next harness cd will correct any
        # drift.
        asyncio.run(_call_execute(
            _restore_cwd_cmd(session), use_daemon, session=session,
        ))

    return _parse_execute_result(type_result, "type")


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
