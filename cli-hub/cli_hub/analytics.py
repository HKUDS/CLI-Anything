"""Lightweight, opt-out-able download event tracking via Umami."""

import atexit
import os
import platform
import threading

import requests

from cli_hub import __version__

UMAMI_URL = "https://cloud.umami.is/api/send"
WEBSITE_ID = "a076c661-bed1-405c-a522-813794e688b4"
HOSTNAME = "clianything.cc"
USER_AGENT = f"Mozilla/5.0 (compatible; cli-anything-hub/{__version__})"

_pending_threads = []
_lock = threading.Lock()


def _flush_pending():
    """Wait for in-flight analytics requests before process exit."""
    with _lock:
        threads = list(_pending_threads)
    for t in threads:
        t.join(timeout=3)


atexit.register(_flush_pending)


def _is_enabled():
    return os.environ.get("CLI_HUB_NO_ANALYTICS", "").strip() not in ("1", "true", "yes")


def _send_event(payload):
    """Send a single event payload. Blocking — callers should use threads."""
    try:
        return requests.post(
            UMAMI_URL, json=payload, timeout=5,
            headers={"User-Agent": USER_AGENT},
        )
    except Exception:
        return None  # analytics must never break the user's workflow


def track_event(event_name, url="/cli-anything-hub", data=None):
    """Fire-and-forget event to Umami. Non-blocking, never raises."""
    if not _is_enabled():
        return

    payload = {
        "type": "event",
        "payload": {
            "website": WEBSITE_ID,
            "hostname": HOSTNAME,
            "url": url,
            "name": event_name,
            "data": data or {},
        },
    }

    t = threading.Thread(target=_send_event, args=(payload,), daemon=True)
    with _lock:
        _pending_threads.append(t)
    t.start()


def track_install(cli_name, version):
    """Track a CLI install event — event name includes the CLI for dashboard visibility."""
    track_event(f"cli-install:{cli_name}", url=f"/cli-anything-hub/install/{cli_name}", data={
        "cli": cli_name,
        "version": version,
        "platform": platform.system().lower(),
    })


def track_uninstall(cli_name):
    """Track a CLI uninstall event."""
    track_event(f"cli-uninstall:{cli_name}", url=f"/cli-anything-hub/uninstall/{cli_name}", data={
        "cli": cli_name,
    })


def track_visit(is_agent=False):
    """Track a visit-human or visit-agent event, matching the hub website's convention."""
    event_name = "visit-agent" if is_agent else "visit-human"
    track_event(event_name, url="/cli-anything-hub", data={
        "source": "cli-anything-hub",
        "platform": platform.system().lower(),
    })


def track_first_run():
    """Send a one-time 'cli-hub-installed' event on first invocation."""
    from pathlib import Path
    marker = Path.home() / ".cli-hub" / ".first_run_sent"
    if marker.exists():
        return
    track_event("cli-anything-hub-installed", url="/cli-anything-hub/installed", data={
        "version": __version__,
        "platform": platform.system().lower(),
    })
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(__version__)
    except Exception:
        pass


def _detect_is_agent():
    """Detect if cli-hub is likely being invoked by an AI agent."""
    indicators = [
        "CLAUDE_CODE",         # Claude Code
        "CODEX",               # OpenAI Codex
        "CURSOR_SESSION",      # Cursor
        "CLINE_SESSION",       # Cline
        "COPILOT",             # GitHub Copilot
        "AIDER",               # Aider
        "CONTINUE_SESSION",    # Continue.dev
    ]
    for var in indicators:
        if os.environ.get(var):
            return True
    # Check if stdin is not a terminal (piped / scripted)
    import sys
    if not sys.stdin.isatty():
        return True
    return False
