"""
Live Unreal process discovery and trace-control command helpers.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from pathlib import Path

from cli_anything.unrealinsights.utils import unrealinsights_backend as backend

LIVE_BACKEND_ENV = "UNREALINSIGHTS_LIVE_EXEC"


def _process_role(name: str, path: str | None, command_line: str | None) -> str:
    lower_name = name.lower()
    lower_text = " ".join(part for part in (path or "", command_line or "") if part).lower()
    if lower_name in {"powershell.exe", "pwsh.exe", "cmd.exe", "dotnet.exe", "python.exe"}:
        return "helper"
    if lower_name == "unrealinsights.exe":
        return "insights"
    if lower_name == "unrealtraceserver.exe":
        return "trace-server"
    if "unrealeditor" in lower_name or "unrealeditor" in lower_text:
        return "editor"
    if "unrealgame" in lower_name or "-win64-" in lower_name or ".uproject" in lower_text:
        return "game"
    return "unknown"


def _normalize_process(item: dict[str, object]) -> dict[str, object]:
    name = str(item.get("Name") or item.get("name") or "")
    pid = item.get("ProcessId") or item.get("pid")
    path = item.get("ExecutablePath") or item.get("path")
    command_line = item.get("CommandLine") or item.get("command_line")
    return {
        "pid": int(pid) if pid is not None else None,
        "name": name,
        "path": str(path) if path else None,
        "command_line": str(command_line) if command_line else None,
        "started_at": item.get("CreationDate") or item.get("started_at"),
        "role": _process_role(name, str(path) if path else None, str(command_line) if command_line else None),
    }


def _list_windows_unreal_processes() -> list[dict[str, object]]:
    script = (
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.Name -like '*Unreal*' -or $_.CommandLine -like '*.uproject*' } | "
        "Select-Object Name,ProcessId,ExecutablePath,CommandLine,CreationDate | "
        "ConvertTo-Json -Compress"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    text = result.stdout.strip()
    if result.returncode != 0 or not text:
        return []
    data = json.loads(text)
    if isinstance(data, dict):
        data = [data]
    return [_normalize_process(item) for item in data]


def _list_posix_unreal_processes() -> list[dict[str, object]]:
    result = subprocess.run(
        ["ps", "-eo", "pid=,comm=,args="],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    processes = []
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split(None, 2)
        if len(parts) < 2:
            continue
        pid, name = parts[0], parts[1]
        command_line = parts[2] if len(parts) > 2 else ""
        if "Unreal" not in name and "Unreal" not in command_line and ".uproject" not in command_line:
            continue
        processes.append(
            _normalize_process(
                {
                    "pid": pid,
                    "name": Path(name).name,
                    "path": name,
                    "command_line": command_line,
                }
            )
        )
    return processes


def list_unreal_processes(*, include_tools: bool = True) -> dict[str, object]:
    """List local Unreal-related processes."""
    processes = _list_windows_unreal_processes() if os.name == "nt" else _list_posix_unreal_processes()
    processes = [process for process in processes if process["role"] not in ("helper", "unknown")]
    if not include_tools:
        processes = [process for process in processes if process["role"] not in ("insights", "trace-server")]
    processes.sort(key=lambda process: (str(process.get("role")), int(process.get("pid") or 0)))
    return {
        "process_count": len(processes),
        "include_tools": include_tools,
        "processes": processes,
    }


def _render_backend_command(template: str, pid: int, command: str) -> list[str]:
    rendered = template.format(pid=pid, cmd=command, command=command)
    return shlex.split(rendered, posix=os.name != "nt")


def execute_live_command(
    pid: int,
    command: str,
    *,
    backend_command: str | None = None,
    timeout: float | None = None,
) -> dict[str, object]:
    """Send a console command to a live UE process through a configured backend."""
    template = backend_command or os.environ.get(LIVE_BACKEND_ENV, "").strip()
    if not template:
        raise RuntimeError(
            "Live control backend unavailable. Configure UNREALINSIGHTS_LIVE_EXEC "
            "with a command template that accepts {pid} and {cmd}, for example a "
            "SessionServices/ushell wrapper."
        )

    argv = _render_backend_command(template, pid, command)
    result = backend.run_process(argv, timeout=timeout, wait=True)
    result.update(
        {
            "pid": pid,
            "live_command": command,
            "backend": "external-template",
            "backend_template": template,
            "succeeded": (not result["timed_out"] and result["exit_code"] == 0),
        }
    )
    return result


def trace_status(pid: int, *, backend_command: str | None = None, timeout: float | None = None) -> dict[str, object]:
    return execute_live_command(pid, "Trace.Status", backend_command=backend_command, timeout=timeout)


def trace_bookmark(
    pid: int,
    name: str,
    *,
    backend_command: str | None = None,
    timeout: float | None = None,
) -> dict[str, object]:
    return execute_live_command(pid, f"Trace.Bookmark {name}", backend_command=backend_command, timeout=timeout)


def trace_screenshot(
    pid: int,
    name: str,
    *,
    backend_command: str | None = None,
    timeout: float | None = None,
) -> dict[str, object]:
    return execute_live_command(pid, f"Trace.Screenshot {name}", backend_command=backend_command, timeout=timeout)


def trace_snapshot(
    pid: int,
    output_path: str,
    *,
    backend_command: str | None = None,
    timeout: float | None = None,
) -> dict[str, object]:
    return execute_live_command(
        pid,
        f"Trace.SnapshotFile {Path(output_path).expanduser().resolve()}",
        backend_command=backend_command,
        timeout=timeout,
    )


def trace_stop(pid: int, *, backend_command: str | None = None, timeout: float | None = None) -> dict[str, object]:
    return execute_live_command(pid, "Trace.Stop", backend_command=backend_command, timeout=timeout)
