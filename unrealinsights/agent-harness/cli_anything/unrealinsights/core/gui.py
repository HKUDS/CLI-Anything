"""
Unreal Insights GUI process helpers.
"""

from __future__ import annotations

from pathlib import Path

from cli_anything.unrealinsights.core.live import list_unreal_processes
from cli_anything.unrealinsights.utils import unrealinsights_backend as backend


def build_gui_command(insights_exe: str, trace_path: str | None = None, *, log: bool = True) -> list[str]:
    """Build a GUI UnrealInsights command line without headless flags."""
    command = [str(Path(insights_exe).expanduser().resolve())]
    if trace_path:
        command.append(f"-OpenTraceFile={Path(trace_path).expanduser().resolve()}")
    if log:
        command.append("-log")
    return command


def open_gui(insights_exe: str, trace_path: str | None = None) -> dict[str, object]:
    """Open Unreal Insights GUI and keep it running."""
    command = build_gui_command(insights_exe, trace_path)
    result = backend.run_process(command, wait=False)
    result.update(
        {
            "insights_exe": str(Path(insights_exe).expanduser().resolve()),
            "trace_path": str(Path(trace_path).expanduser().resolve()) if trace_path else None,
            "mode": "gui",
            "kept_running": True,
        }
    )
    return result


def gui_status() -> dict[str, object]:
    """Return currently running Unreal Insights GUI processes."""
    processes = [
        process
        for process in list_unreal_processes(include_tools=True)["processes"]
        if process.get("role") == "insights"
    ]
    return {
        "running": bool(processes),
        "process_count": len(processes),
        "processes": processes,
    }
