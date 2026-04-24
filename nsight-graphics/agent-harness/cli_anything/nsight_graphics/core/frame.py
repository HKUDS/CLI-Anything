"""Frame capture orchestration."""

from __future__ import annotations

from typing import Sequence

from cli_anything.nsight_graphics.utils import nsight_graphics_backend as backend


def _build_unified_frame_args(
    activity: str,
    *,
    wait_seconds: int | None,
    wait_frames: int | None,
    wait_hotkey: bool,
    export_frame_perf_metrics: bool,
    export_range_perf_metrics: bool,
) -> list[str]:
    backend.ensure_exactly_one(
        "frame trigger",
        {
            "wait_seconds": wait_seconds is not None,
            "wait_frames": wait_frames is not None,
            "wait_hotkey": wait_hotkey,
        },
    )

    normalized = activity.lower()
    if normalized == "graphics capture":
        if export_frame_perf_metrics or export_range_perf_metrics:
            raise RuntimeError(
                "Frame performance export flags are not supported by Graphics Capture mode on modern ngfx.exe builds."
            )

        extra_args = ["--frame-count", "1"]
        if wait_seconds is not None:
            extra_args.extend(["--elapsed-time", str(wait_seconds)])
        elif wait_frames is not None:
            extra_args.extend(["--frame-index", str(wait_frames)])
        else:
            extra_args.append("--hotkey-capture")
        return extra_args

    extra_args: list[str] = []
    if wait_seconds is not None:
        extra_args.extend(["--wait-seconds", str(wait_seconds)])
    elif wait_frames is not None:
        extra_args.extend(["--wait-frames", str(wait_frames)])
    else:
        extra_args.append("--wait-hotkey")

    if export_frame_perf_metrics:
        extra_args.append("--export-frame-perf-metrics")
    if export_range_perf_metrics:
        extra_args.append("--export-range-perf-metrics")
    return extra_args


def capture_frame(
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
    wait_frames: int | None,
    wait_hotkey: bool,
    export_frame_perf_metrics: bool,
    export_range_perf_metrics: bool,
) -> dict:
    """Run a Frame Debugger capture."""
    report = backend.probe_installation(nsight_path=nsight_path)
    binaries = report["binaries"]
    activity = backend.resolve_activity_name(report, "Frame Debugger")
    artifact_roots = backend.activity_artifact_roots(activity, output_dir)

    if binaries.get("ngfx"):
        backend.require_launch_target(project=project, exe=exe)
        extra_args = _build_unified_frame_args(
            activity,
            wait_seconds=wait_seconds,
            wait_frames=wait_frames,
            wait_hotkey=wait_hotkey,
            export_frame_perf_metrics=export_frame_perf_metrics,
            export_range_perf_metrics=export_range_perf_metrics,
        )

        command = backend.build_unified_command(
            binaries,
            activity=activity,
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
            output_roots=artifact_roots,
            timeout=300,
        )
        result["tool_mode"] = "unified"
    elif binaries.get("ngfx_capture"):
        if project:
            raise RuntimeError(
                "Project-driven frame capture fallback requires ngfx.exe; "
                "split ngfx-capture mode currently needs --exe."
            )
        if export_frame_perf_metrics or export_range_perf_metrics:
            raise RuntimeError(
                "Frame performance export flags require ngfx.exe Frame Debugger mode."
            )
        if not exe:
            raise ValueError("Specify --exe for split ngfx-capture mode.")

        command = backend.build_split_capture_command(
            binaries,
            exe=exe,
            output_dir=output_dir,
            working_dir=working_dir,
            args=args,
            envs=envs,
            wait_seconds=wait_seconds,
            wait_frames=wait_frames,
            wait_hotkey=wait_hotkey,
        )
        result = backend.run_with_artifacts(
            command,
            output_roots=artifact_roots,
            timeout=300,
        )
        result["tool_mode"] = "split"
    else:
        raise RuntimeError(backend.INSTALL_INSTRUCTIONS)

    result["activity"] = activity
    result["output_dir"] = output_dir or backend.default_output_dir()
    return result
