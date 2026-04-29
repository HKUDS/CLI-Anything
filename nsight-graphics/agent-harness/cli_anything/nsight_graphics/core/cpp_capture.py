"""Generate C++ Capture orchestration."""

from __future__ import annotations

from typing import Sequence

from cli_anything.nsight_graphics.utils import nsight_graphics_backend as backend


def capture_cpp(
    *,
    nsight_path: str | None,
    project: str | None,
    output_dir: str | None,
    hostname: str | None,
    platform_name: str | None,
    exe: str | None,
    working_dir: str | None,
    args: Sequence[str],
    envs: Sequence[str],
    wait_seconds: int | None,
    wait_hotkey: bool,
) -> dict:
    """Run Generate C++ Capture."""
    output_dir = backend.prepare_output_dir(output_dir)
    report = backend.probe_installation(nsight_path=nsight_path)
    binaries = report["binaries"]
    backend.require_binary(binaries, "ngfx")
    backend.require_launch_target(project=project, exe=exe)

    backend.ensure_exactly_one(
        "c++ capture trigger",
        {
            "wait_seconds": wait_seconds is not None,
            "wait_hotkey": wait_hotkey,
        },
    )

    extra_args: list[str] = []
    if wait_seconds is not None:
        extra_args.extend(["--wait-seconds", str(wait_seconds)])
    else:
        extra_args.append("--wait-hotkey")

    command = backend.build_unified_command(
        binaries,
        activity="Generate C++ Capture",
        project=project,
        output_dir=output_dir,
        hostname=hostname,
        platform_name=platform_name,
        exe=exe,
        working_dir=working_dir,
        args=args,
        envs=envs,
        extra_args=extra_args,
    )
    result = backend.run_with_artifacts(
        command,
        output_roots=backend.activity_artifact_roots("Generate C++ Capture", output_dir),
        timeout=600,
    )
    result["tool_mode"] = "unified"
    result["activity"] = "Generate C++ Capture"
    result["output_dir"] = output_dir or backend.default_output_dir()
    return result
