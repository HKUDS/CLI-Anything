"""Daemon domain: status probes, recording control, and the systemd user service.

Recording commands talk to the *running* voxtype daemon (signals + override
files written by `voxtype record ...`). Starting a recording captures the
microphone and, by default, types the transcript into the focused window.
"""

import os
from typing import Optional

from cli_anything.voxtype.utils import voxtype_backend as backend

OUTPUT_MODES = ("type", "clipboard", "paste", "file")
RECORD_ACTIONS = ("start", "stop", "toggle", "cancel")


def runtime_dir() -> str:
    base = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return os.path.join(base, "voxtype")


def status(config_path: Optional[str] = None, extended: bool = True,
           icon_theme: Optional[str] = None) -> dict:
    """Waybar-style status JSON from `voxtype status --format json`."""
    args = ["status", "--format", "json"]
    if extended:
        args.append("--extended")
    if icon_theme:
        args += ["--icon-theme", icon_theme]
    data = backend.run_json(args, config_path, timeout=30)
    data["state"] = data.get("alt") or data.get("class")
    data["running"] = data["state"] not in (None, "stopped", "inactive")
    rt = runtime_dir()
    pid_file = os.path.join(rt, "pid")
    data["pid"] = None
    if os.path.exists(pid_file):
        try:
            with open(pid_file) as f:
                data["pid"] = int(f.read().strip())
        except (ValueError, OSError):
            pass
    data["runtime_dir"] = rt
    return data


def record_args(action: str, output_mode: Optional[str] = None, file_path: Optional[str] = None,
                model: Optional[str] = None, profile: Optional[str] = None,
                auto_submit: Optional[bool] = None, no_osd: bool = False) -> list[str]:
    """Build `voxtype record <action> [...]` arguments (pure; unit-testable)."""
    if action not in RECORD_ACTIONS:
        raise ValueError(f"Unknown record action '{action}'. Valid: {', '.join(RECORD_ACTIONS)}")
    args = ["record", action]
    if action in ("start", "toggle"):
        if output_mode:
            if output_mode not in OUTPUT_MODES:
                raise ValueError(f"Unknown output mode '{output_mode}'. Valid: {', '.join(OUTPUT_MODES)}")
            if output_mode == "file":
                args.append(f"--file={file_path}" if file_path else "--file")
            else:
                args.append(f"--{output_mode}")
        elif file_path:
            args.append(f"--file={file_path}")
        if model:
            args += ["--model", model]
        if profile:
            args += ["--profile", profile]
        if auto_submit is True:
            args.append("--auto-submit")
        elif auto_submit is False:
            args.append("--no-auto-submit")
        if no_osd:
            args.append("--no-osd")
    elif any([output_mode, file_path, model, profile, auto_submit is not None, no_osd]):
        raise ValueError(f"'record {action}' takes no output options")
    return args


def record(action: str, config_path: Optional[str] = None, **opts) -> dict:
    args = record_args(action, **opts)
    proc = backend.run(args, config_path, timeout=30)
    return {"action": action, "args": args[1:], "message": (proc.stdout or proc.stderr).strip()}


def service(action: str) -> dict:
    if action not in ("status", "start", "stop", "restart"):
        raise ValueError(f"Unknown service action '{action}'")
    if action == "status":
        active = backend.systemctl("is-active", check=False).stdout.strip()
        enabled = backend.systemctl("is-enabled", check=False).stdout.strip()
        return {"service": backend.SERVICE_NAME, "active": active, "enabled": enabled,
                "running": active == "active"}
    backend.systemctl(action)
    active = backend.systemctl("is-active", check=False).stdout.strip()
    return {"service": backend.SERVICE_NAME, "action": action, "active": active}


def accel() -> dict:
    return backend.run_json(["info", "accel", "--json"], timeout=60)
