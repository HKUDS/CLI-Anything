"""Launch and attach helpers."""

from __future__ import annotations

from typing import Sequence

from cli_anything.nsight_graphics.utils import nsight_graphics_backend as backend


def launch_detached(
    *,
    nsight_path: str | None,
    activity: str,
    project: str | None,
    output_dir: str | None,
    hostname: str | None,
    platform_name: str | None,
    exe: str | None,
    working_dir: str | None,
    args: Sequence[str],
    envs: Sequence[str],
) -> dict:
    """Launch a target under Nsight and exit immediately."""
    report = backend.probe_installation(nsight_path=nsight_path)
    binaries = report["binaries"]
    resolved_activity = backend.resolve_activity_name(report, activity)
    backend.require_binary(binaries, "ngfx")
    backend.require_launch_target(project=project, exe=exe)

    command = backend.build_unified_command(
        binaries,
        activity=resolved_activity,
        project=project,
        output_dir=output_dir,
        hostname=hostname,
        platform_name=platform_name,
        exe=exe,
        working_dir=working_dir,
        args=args,
        envs=envs,
        launch_detached=True,
    )
    result = backend.run_command(command, timeout=120)
    result["tool_mode"] = "unified"
    result["activity"] = resolved_activity
    return result


def attach(
    *,
    nsight_path: str | None,
    activity: str,
    pid: int,
    project: str | None,
    output_dir: str | None,
    hostname: str | None,
    platform_name: str | None,
) -> dict:
    """Attach an activity to a running PID."""
    report = backend.probe_installation(nsight_path=nsight_path)
    binaries = report["binaries"]
    resolved_activity = backend.resolve_activity_name(report, activity)
    backend.require_binary(binaries, "ngfx")

    command = backend.build_unified_command(
        binaries,
        activity=resolved_activity,
        project=project,
        output_dir=output_dir,
        hostname=hostname,
        platform_name=platform_name,
        attach_pid=pid,
    )
    result = backend.run_command(command, timeout=120)
    result["tool_mode"] = "unified"
    result["activity"] = resolved_activity
    result["pid"] = pid
    return result
