"""Lightweight, opt-out-able analytics with switchable providers."""

import atexit
import os
import platform
import re
import sys
import threading
import uuid
from pathlib import Path

import requests

from cli_hub import __version__

ANALYTICS_PROVIDER = "posthog"
UMAMI_URL = "https://cloud.umami.is/api/send"
UMAMI_WEBSITE_ID = "a076c661-bed1-405c-a522-813794e688b4"
POSTHOG_API_HOST = "https://us.i.posthog.com"
POSTHOG_PROJECT_TOKEN = "phc_ovP8d5bmjpn8YZnTo7pb6rE3TikcAMgmNVt75o3Ywejz"
HOSTNAME = "clianything.cc"
USER_AGENT = f"Mozilla/5.0 (compatible; cli-anything-hub/{__version__})"
ANALYTICS_ID_FILE = ".analytics_id"

_pending_threads = []
_lock = threading.Lock()

_AGENT_ENV_RULES = (
    ("CLAUDE_CODE", "agent_tool", "claude-code-env"),
    ("CLAUDECODE", "agent_tool", "claude-code-env-alt"),
    ("CODEX", "agent_tool", "codex-env"),
    ("OPENAI_CODEX", "agent_tool", "codex-env-alt"),
    ("CURSOR_SESSION", "agent_tool", "cursor-session-env"),
    ("CURSOR_TRACE_ID", "agent_tool", "cursor-trace-env"),
    ("CLINE_SESSION", "agent_tool", "cline-session-env"),
    ("AIDER", "agent_tool", "aider-env"),
    ("AIDER_SESSION_ID", "agent_tool", "aider-session-env"),
    ("CONTINUE_SESSION", "agent_tool", "continue-session-env"),
    ("OPENHANDS_AGENT", "agent_tool", "openhands-agent-env"),
    ("OPENHANDS_RUNTIME", "agent_tool", "openhands-runtime-env"),
    ("BROWSER_USE", "agent_tool", "browser-use-env"),
    ("STAGEHAND", "agent_tool", "stagehand-env"),
    ("GOOSE_AGENT", "agent_tool", "goose-agent-env"),
    ("ROO_CODE", "agent_tool", "roo-code-env"),
    ("WINDSURF_AGENT", "agent_tool", "windsurf-agent-env"),
)

_PARENT_PROCESS_RULES = (
    ("claude-code-process", "agent_tool", re.compile(r"\bclaude(?:[ -]?code)?\b", re.IGNORECASE)),
    ("codex-process", "agent_tool", re.compile(r"\bcodex(?:-cli)?\b", re.IGNORECASE)),
    ("copilot-process", "agent_tool", re.compile(r"\bcopilot(?:-cli)?\b", re.IGNORECASE)),
    ("cursor-process", "agent_tool", re.compile(r"\bcursor\b", re.IGNORECASE)),
    ("cline-process", "agent_tool", re.compile(r"\bcline\b", re.IGNORECASE)),
    ("aider-process", "agent_tool", re.compile(r"\baider\b", re.IGNORECASE)),
    ("continue-process", "agent_tool", re.compile(r"\bcontinue\b", re.IGNORECASE)),
    ("gemini-process", "agent_tool", re.compile(r"\bgemini(?:-cli)?\b", re.IGNORECASE)),
    ("auggie-process", "agent_tool", re.compile(r"\bauggie(?:-cli)?\b", re.IGNORECASE)),
    ("augment-process", "agent_tool", re.compile(r"\baugment(?:[ -]?agent)?\b", re.IGNORECASE)),
    ("amp-process", "agent_tool", re.compile(r"\bamp(?:code)?\b", re.IGNORECASE)),
    ("opencode-process", "agent_tool", re.compile(r"\bopencode\b", re.IGNORECASE)),
    ("kilo-process", "agent_tool", re.compile(r"\bkilo(?:code)?\b", re.IGNORECASE)),
    ("qodo-process", "agent_tool", re.compile(r"\bqodo\b", re.IGNORECASE)),
    ("kiro-process", "agent_tool", re.compile(r"\bkiro\b", re.IGNORECASE)),
    ("openhands-process", "agent_tool", re.compile(r"\bopenhands\b", re.IGNORECASE)),
    ("browser-use-process", "agent_tool", re.compile(r"\bbrowser[- ]use\b", re.IGNORECASE)),
    ("stagehand-process", "agent_tool", re.compile(r"\bstagehand\b", re.IGNORECASE)),
    ("roo-process", "agent_tool", re.compile(r"\broo(?:-code)?\b", re.IGNORECASE)),
    ("windsurf-process", "agent_tool", re.compile(r"\bwindsurf\b", re.IGNORECASE)),
    ("goose-process", "agent_tool", re.compile(r"\bgoose\b", re.IGNORECASE)),
)


def _flush_pending():
    """Wait for in-flight analytics requests before process exit."""
    with _lock:
        threads = list(_pending_threads)
    for t in threads:
        t.join(timeout=3)


atexit.register(_flush_pending)


def _is_enabled():
    return os.environ.get("CLI_HUB_NO_ANALYTICS", "").strip() not in ("1", "true", "yes")


def _provider():
    provider = os.environ.get("CLI_HUB_ANALYTICS_PROVIDER", ANALYTICS_PROVIDER).strip().lower()
    return provider if provider in {"posthog", "umami"} else ANALYTICS_PROVIDER


def _analytics_dir():
    return Path.home() / ".cli-hub"


def _stdin_is_tty():
    try:
        return sys.stdin.isatty()
    except Exception:
        return False


def _read_parent_pid(pid):
    status_path = Path("/proc") / str(pid) / "status"
    try:
        for line in status_path.read_text().splitlines():
            if line.startswith("PPid:"):
                parts = line.split()
                return int(parts[1]) if len(parts) > 1 else None
    except Exception:
        return None
    return None


def _read_process_cmdline(pid):
    cmdline_path = Path("/proc") / str(pid) / "cmdline"
    try:
        raw = cmdline_path.read_bytes()
    except Exception:
        return ""
    return raw.replace(b"\x00", b" ").decode("utf-8", errors="ignore").strip()


def _parent_process_commands(max_depth=4):
    commands = []
    pid = os.getpid()
    for _ in range(max_depth):
        pid = _read_parent_pid(pid)
        if not pid or pid <= 1:
            break
        cmd = _read_process_cmdline(pid)
        if cmd:
            commands.append(cmd)
    return commands


def detect_invocation_context():
    """Classify the current cli-hub invocation as human, agent, or scripted."""
    signals = []

    for env_name, category, signal_id in _AGENT_ENV_RULES:
        if os.environ.get(env_name):
            signals.append({"id": signal_id, "category": category})

    for cmd in _parent_process_commands():
        for signal_id, category, pattern in _PARENT_PROCESS_RULES:
            if pattern.search(cmd):
                signals.append({"id": signal_id, "category": category})

    seen = set()
    unique_signals = []
    for signal in signals:
        if signal["id"] in seen:
            continue
        seen.add(signal["id"])
        unique_signals.append(signal)

    stdin_tty = _stdin_is_tty()
    if unique_signals:
        primary = unique_signals[0]
        return {
            "is_agent": True,
            "traffic_type": "agent",
            "category": primary["category"],
            "reason": primary["id"],
            "signals": [signal["id"] for signal in unique_signals],
            "stdin_tty": stdin_tty,
            "is_interactive": stdin_tty,
        }

    if not stdin_tty:
        return {
            "is_agent": True,
            "traffic_type": "agent",
            "category": "scripted_client",
            "reason": "stdin-not-tty",
            "signals": ["stdin-not-tty"],
            "stdin_tty": False,
            "is_interactive": False,
        }

    return {
        "is_agent": False,
        "traffic_type": "human",
        "category": "human",
        "reason": "human",
        "signals": [],
        "stdin_tty": True,
        "is_interactive": True,
    }


def _get_distinct_id():
    override = os.environ.get("CLI_HUB_ANALYTICS_DISTINCT_ID", "").strip()
    if override:
        return override

    marker = _analytics_dir() / ANALYTICS_ID_FILE
    try:
        if marker.exists():
            value = marker.read_text().strip()
            if value:
                return value
        marker.parent.mkdir(parents=True, exist_ok=True)
        value = str(uuid.uuid4())
        marker.write_text(value)
        return value
    except Exception:
        return f"cli-hub-anon-{uuid.uuid4()}"


def _posthog_capture_url():
    host = os.environ.get("CLI_HUB_POSTHOG_API_HOST", POSTHOG_API_HOST).rstrip("/")
    return f"{host}/capture/"


def _build_umami_payload(event_name, url, data):
    return {
        "type": "event",
        "payload": {
            "website": UMAMI_WEBSITE_ID,
            "hostname": HOSTNAME,
            "url": url,
            "name": event_name,
            "data": data,
        },
    }


def _build_posthog_payload(event_name, url, data):
    return {
        "api_key": os.environ.get("CLI_HUB_POSTHOG_PROJECT_TOKEN", POSTHOG_PROJECT_TOKEN),
        "event": event_name,
        "distinct_id": _get_distinct_id(),
        "properties": {
            "$current_url": f"https://{HOSTNAME}{url}",
            "hostname": HOSTNAME,
            "source": "cli",
            "channel": "cli-hub",
            "hub_version": __version__,
            **(data or {}),
        },
    }


def _send_event(payload):
    """Send a single event payload. Blocking — callers should use threads."""
    try:
        if _provider() == "umami":
            return requests.post(
                UMAMI_URL,
                json=payload,
                timeout=5,
                headers={"User-Agent": USER_AGENT},
            )
        return requests.post(
            _posthog_capture_url(),
            json=payload,
            timeout=5,
            headers={"User-Agent": USER_AGENT},
        )
    except Exception:
        return None  # analytics must never break the user's workflow


def track_event(event_name, url="/cli-anything-hub", data=None):
    """Fire-and-forget event to the active provider. Non-blocking, never raises."""
    if not _is_enabled():
        return

    event_data = data or {}
    if _provider() == "umami":
        payload = _build_umami_payload(event_name, url, event_data)
    else:
        payload = _build_posthog_payload(event_name, url, event_data)

    t = threading.Thread(target=_send_event, args=(payload,), daemon=True)
    with _lock:
        _pending_threads.append(t)
    t.start()


def track_install(cli_name, version):
    """Track a CLI install event. CLI name goes in properties, not the event name,
    so the event catalog stays flat and dashboards can break down by properties.cli."""
    track_event("cli-install", url=f"/cli-anything-hub/install/{cli_name}", data={
        "cli": cli_name,
        "version": version,
        "platform": platform.system().lower(),
    })


def track_uninstall(cli_name):
    """Track a CLI uninstall event."""
    track_event("cli-uninstall", url=f"/cli-anything-hub/uninstall/{cli_name}", data={
        "cli": cli_name,
        "platform": platform.system().lower(),
    })


def track_launch(cli_name):
    """Track a CLI launch event — fires when a user runs `cli-hub launch <name>`.
    Distinct from install: this is actual usage signal."""
    track_event("cli-launch", url=f"/cli-anything-hub/launch/{cli_name}", data={
        "cli": cli_name,
        "platform": platform.system().lower(),
    })


def track_visit(is_agent=False, command="root", detection=None):
    """Track a cli-hub invocation using the new cli-hub call event."""
    stdin_tty = _stdin_is_tty()
    context = detection or {
        "is_agent": is_agent,
        "traffic_type": "agent" if is_agent else "human",
        "category": "legacy-agent" if is_agent else "human",
        "reason": "legacy-flag" if is_agent else "human",
        "signals": ["legacy-flag"] if is_agent else [],
        "stdin_tty": stdin_tty,
        "is_interactive": stdin_tty,
    }
    track_event("cli-hub call", url="/cli-anything-hub/call", data={
        "command": command,
        "is_agent": context["is_agent"],
        "traffic_type": context["traffic_type"],
        "agent_category": context["category"],
        "agent_reason": context["reason"],
        "agent_signals": context["signals"][:12],
        "stdin_tty": context["stdin_tty"],
        "is_interactive": context["is_interactive"],
        "platform": platform.system().lower(),
    })


def track_first_run():
    """Send a one-time 'cli-hub-installed' event on first invocation."""
    marker = _analytics_dir() / ".first_run_sent"
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
    return detect_invocation_context()["is_agent"]
