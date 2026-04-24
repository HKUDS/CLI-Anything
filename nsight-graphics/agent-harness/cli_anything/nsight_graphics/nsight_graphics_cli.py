#!/usr/bin/env python3
"""CLI harness for NVIDIA Nsight Graphics orchestration."""

from __future__ import annotations

import json
import os
import shlex

import click

from cli_anything.nsight_graphics.core import cpp_capture, doctor, frame, gpu_trace, launch

_repl_mode = False


def _output(ctx: click.Context, data, human_fn=None):
    if ctx.obj.get("json_mode"):
        from cli_anything.nsight_graphics.utils.output import output_json

        output_json(data)
    elif human_fn:
        human_fn(data)
    else:
        from cli_anything.nsight_graphics.utils.output import output_json

        output_json(data)


def _handle_exc(ctx: click.Context, exc: Exception):
    from cli_anything.nsight_graphics.utils.errors import handle_error

    payload = handle_error(exc, debug=ctx.obj.get("debug", False))
    if ctx.obj.get("json_mode"):
        from cli_anything.nsight_graphics.utils.output import output_json

        output_json(payload)
        ctx.exit(1)
    raise click.ClickException(payload["error"])


def _common_kwargs(ctx: click.Context) -> dict:
    return {
        "nsight_path": ctx.obj.get("nsight_path"),
        "project": ctx.obj.get("project"),
        "output_dir": ctx.obj.get("output_dir"),
        "hostname": ctx.obj.get("hostname"),
        "platform_name": ctx.obj.get("platform_name"),
    }


def _print_gpu_trace_summary(summary: dict) -> None:
    """Render a compact human-readable GPU Trace summary."""
    frame_time = summary.get("frame_time_ms")
    fps = summary.get("fps_estimate")
    if frame_time is not None:
        click.echo(f"Frame time: {frame_time:.3f} ms")
    if fps is not None:
        click.echo(f"Estimated FPS: {fps:.2f}")

    metrics = summary.get("metrics", {})
    if metrics:
        click.echo("Metrics:")
        for label, key in [
            ("Draws", "draw_count"),
            ("Dispatches", "dispatch_count"),
            ("Graphics active %", "graphics_engine_active_pct"),
            ("Compute sync active %", "compute_queue_sync_active_pct"),
            ("SM throughput %", "sm_throughput_pct"),
            ("L2 throughput %", "l2_throughput_pct"),
            ("DRAM throughput %", "dram_throughput_pct"),
        ]:
            value = metrics.get(key)
            if value is None:
                continue
            if isinstance(value, float):
                click.echo(f"  {label}: {value:.3f}")
            else:
                click.echo(f"  {label}: {value}")

    top_events = summary.get("top_events", [])
    if top_events:
        click.echo("Top GPU events:")
        for item in top_events:
            click.echo(f"  - {item['event']}: {item['time_ms']:.3f} ms")

    highlights = summary.get("highlights", [])
    if highlights:
        click.echo("Highlights:")
        for line in highlights:
            click.echo(f"  - {line}")


@click.group(invoke_without_command=True)
@click.option("--json", "json_mode", is_flag=True, help="Output in JSON format.")
@click.option("--debug", is_flag=True, help="Show debug tracebacks on errors.")
@click.option("--nsight-path", type=click.Path(exists=False), default=None, help="Explicit Nsight Graphics install dir or executable.")
@click.option("--project", type=click.Path(exists=False), default=None, help="Nsight Graphics project file.")
@click.option("--output-dir", type=click.Path(exists=False), default=None, help="Output directory for captures or exports.")
@click.option("--hostname", default=None, help="Remote host name.")
@click.option("--platform", "platform_name", default=None, help="Target platform string.")
@click.version_option(package_name="cli-anything-nsight-graphics")
@click.pass_context
def cli(ctx, json_mode, debug, nsight_path, project, output_dir, hostname, platform_name):
    """Nsight Graphics CLI - orchestration wrapper for official tools."""
    ctx.ensure_object(dict)
    ctx.obj["json_mode"] = json_mode
    ctx.obj["debug"] = debug
    if nsight_path is not None:
        ctx.obj["nsight_path"] = nsight_path
    if project is not None:
        ctx.obj["project"] = project
    if output_dir is not None:
        ctx.obj["output_dir"] = output_dir
    if hostname is not None:
        ctx.obj["hostname"] = hostname
    if platform_name is not None:
        ctx.obj["platform_name"] = platform_name
    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


@cli.group("doctor")
def doctor_group():
    """Installation and environment diagnostics."""


@doctor_group.command("info")
@click.pass_context
def doctor_info(ctx):
    """Show installation details and detected capabilities."""
    try:
        data = doctor.get_installation_report(nsight_path=ctx.obj.get("nsight_path"))

        def _human(report):
            click.echo(f"Mode:     {report['compatibility_mode']}")
            click.echo(f"Version:  {report.get('version') or 'unknown'}")
            click.echo(f"Primary:  {report.get('resolved_executable') or 'not found'}")
            click.echo(f"Windows:  {'yes' if report.get('verified_host') else 'unverified'}")
            if report.get("supported_activities"):
                click.echo("Activities:")
                for activity in report["supported_activities"]:
                    click.echo(f"  - {activity}")
            if report.get("warnings"):
                click.echo("Warnings:")
                for warning in report["warnings"]:
                    click.echo(f"  - {warning}")

        _output(ctx, data, _human)
    except Exception as exc:
        _handle_exc(ctx, exc)


@doctor_group.command("versions")
@click.pass_context
def doctor_versions(ctx):
    """List detected Nsight Graphics installations and versions."""
    try:
        data = doctor.list_installations(nsight_path=ctx.obj.get("nsight_path"))

        def _human(report):
            click.echo(f"Found: {report['count']}")
            if report.get("selected_executable"):
                click.echo(f"Selected: {report['selected_executable']}")
            for item in report.get("installations", []):
                marker = "*" if item.get("selected") else " "
                version = item.get("version") or "unknown"
                sources = "+".join(item.get("discovery_sources", []))
                click.echo(f"{marker} {version} [{item['tool_mode']}] ({sources})")
                if item.get("display_name"):
                    click.echo(f"    {item['display_name']}")
                if item.get("install_root"):
                    click.echo(f"    {item['install_root']}")
                elif item.get("registry_key"):
                    click.echo(f"    {item['registry_key']}")
                if item.get("install_source") and item.get("registered_only"):
                    click.echo(f"    source: {item['install_source']}")

        _output(ctx, data, _human)
    except Exception as exc:
        _handle_exc(ctx, exc)


@cli.group("launch")
def launch_group():
    """Launch or attach targets under Nsight Graphics."""


@launch_group.command("detached")
@click.option("--activity", default="Frame Debugger", show_default=True, help="Nsight activity name.")
@click.option("--exe", "exe_path", type=click.Path(exists=False), default=None, help="Target executable path.")
@click.option("--dir", "working_dir", type=click.Path(exists=False), default=None, help="Target working directory.")
@click.option("--arg", "program_args", multiple=True, help="Target argument. Repeat for multiple.")
@click.option("--env", "envs", multiple=True, help="Environment entry KEY=VALUE.")
@click.pass_context
def launch_detached_cmd(ctx, activity, exe_path, working_dir, program_args, envs):
    """Launch a target under Nsight and return immediately."""
    try:
        data = launch.launch_detached(
            activity=activity,
            exe=exe_path,
            working_dir=working_dir,
            args=program_args,
            envs=envs,
            **_common_kwargs(ctx),
        )
        _output(ctx, data)
    except Exception as exc:
        _handle_exc(ctx, exc)


@launch_group.command("attach")
@click.option("--activity", default="Frame Debugger", show_default=True, help="Nsight activity name.")
@click.option("--pid", type=int, required=True, help="PID to attach.")
@click.pass_context
def launch_attach_cmd(ctx, activity, pid):
    """Attach an Nsight activity to a running PID."""
    try:
        data = launch.attach(
            activity=activity,
            pid=pid,
            **_common_kwargs(ctx),
        )
        _output(ctx, data)
    except Exception as exc:
        _handle_exc(ctx, exc)


@cli.group("frame")
def frame_group():
    """Frame Debugger capture commands."""


@frame_group.command("capture")
@click.option("--exe", "exe_path", type=click.Path(exists=False), default=None, help="Target executable path.")
@click.option("--dir", "working_dir", type=click.Path(exists=False), default=None, help="Target working directory.")
@click.option("--arg", "program_args", multiple=True, help="Target argument. Repeat for multiple.")
@click.option("--env", "envs", multiple=True, help="Environment entry KEY=VALUE.")
@click.option("--wait-seconds", type=int, default=None, help="Wait N seconds before capture.")
@click.option("--wait-frames", type=int, default=None, help="Wait N frames before capture.")
@click.option("--wait-hotkey", is_flag=True, help="Wait for the target capture hotkey.")
@click.option("--export-frame-perf-metrics", is_flag=True, help="Export whole-frame performance metrics.")
@click.option("--export-range-perf-metrics", is_flag=True, help="Export per-range performance metrics.")
@click.pass_context
def frame_capture_cmd(
    ctx,
    exe_path,
    working_dir,
    program_args,
    envs,
    wait_seconds,
    wait_frames,
    wait_hotkey,
    export_frame_perf_metrics,
    export_range_perf_metrics,
):
    """Run a Frame Debugger capture."""
    try:
        data = frame.capture_frame(
            exe=exe_path,
            working_dir=working_dir,
            args=program_args,
            envs=envs,
            wait_seconds=wait_seconds,
            wait_frames=wait_frames,
            wait_hotkey=wait_hotkey,
            export_frame_perf_metrics=export_frame_perf_metrics,
            export_range_perf_metrics=export_range_perf_metrics,
            **_common_kwargs(ctx),
        )
        _output(ctx, data)
    except Exception as exc:
        _handle_exc(ctx, exc)


@cli.group("gpu-trace")
def gpu_trace_group():
    """GPU Trace capture commands."""


@gpu_trace_group.command("capture")
@click.option("--exe", "exe_path", type=click.Path(exists=False), default=None, help="Target executable path.")
@click.option("--dir", "working_dir", type=click.Path(exists=False), default=None, help="Target working directory.")
@click.option("--arg", "program_args", multiple=True, help="Target argument. Repeat for multiple.")
@click.option("--env", "envs", multiple=True, help="Environment entry KEY=VALUE.")
@click.option("--start-after-frames", type=int, default=None, help="Wait N frames before trace.")
@click.option("--start-after-submits", type=int, default=None, help="Wait N submits before trace.")
@click.option("--start-after-ms", type=int, default=None, help="Wait N milliseconds before trace.")
@click.option("--start-after-hotkey", is_flag=True, help="Wait for the target capture hotkey.")
@click.option("--max-duration-ms", type=int, default=None, help="Maximum trace duration.")
@click.option("--limit-to-frames", type=int, default=None, help="Trace at most N frames.")
@click.option("--limit-to-submits", type=int, default=None, help="Trace at most N submits.")
@click.option("--auto-export", is_flag=True, help="Automatically export metrics data.")
@click.option("--architecture", default=None, help="Architecture name.")
@click.option("--metric-set-id", default=None, help="Metric set id for the selected architecture.")
@click.option("--multi-pass-metrics", is_flag=True, help="Enable multi-pass metrics.")
@click.option("--real-time-shader-profiler", is_flag=True, help="Enable real-time shader profiler.")
@click.option("--summarize", is_flag=True, help="Parse exported GPU Trace tables and include a summary.")
@click.option("--summary-limit", type=int, default=10, show_default=True, help="Number of top GPU events to include in the summary.")
@click.pass_context
def gpu_trace_capture_cmd(
    ctx,
    exe_path,
    working_dir,
    program_args,
    envs,
    start_after_frames,
    start_after_submits,
    start_after_ms,
    start_after_hotkey,
    max_duration_ms,
    limit_to_frames,
    limit_to_submits,
    auto_export,
    architecture,
    metric_set_id,
    multi_pass_metrics,
    real_time_shader_profiler,
    summarize,
    summary_limit,
):
    """Run a GPU Trace capture."""
    try:
        data = gpu_trace.capture_trace(
            exe=exe_path,
            working_dir=working_dir,
            args=program_args,
            envs=envs,
            start_after_frames=start_after_frames,
            start_after_submits=start_after_submits,
            start_after_ms=start_after_ms,
            start_after_hotkey=start_after_hotkey,
            max_duration_ms=max_duration_ms,
            limit_to_frames=limit_to_frames,
            limit_to_submits=limit_to_submits,
            auto_export=auto_export,
            architecture=architecture,
            metric_set_id=metric_set_id,
            multi_pass_metrics=multi_pass_metrics,
            real_time_shader_profiler=real_time_shader_profiler,
            summarize=summarize,
            summary_limit=summary_limit,
            **_common_kwargs(ctx),
        )
        _output(
            ctx,
            data,
            lambda payload: (
                click.echo(f"Output dir: {payload.get('output_dir')}"),
                click.echo(f"Artifacts: {payload.get('artifact_count', 0)}"),
                _print_gpu_trace_summary(payload["summary"]) if payload.get("summary") else None,
            ),
        )
    except Exception as exc:
        _handle_exc(ctx, exc)


@gpu_trace_group.command("summarize")
@click.option("--input-dir", required=True, type=click.Path(exists=True, file_okay=False), help="GPU Trace export directory to summarize.")
@click.option("--summary-limit", type=int, default=10, show_default=True, help="Number of top GPU events to include in the summary.")
@click.pass_context
def gpu_trace_summarize_cmd(ctx, input_dir, summary_limit):
    """Summarize an existing exported GPU Trace directory."""
    try:
        data = gpu_trace.summarize_export_dir(input_dir, top_n=summary_limit)
        _output(ctx, data, _print_gpu_trace_summary)
    except Exception as exc:
        _handle_exc(ctx, exc)


@cli.group("cpp")
def cpp_group():
    """Generate C++ Capture commands."""


@cpp_group.command("capture")
@click.option("--exe", "exe_path", type=click.Path(exists=False), default=None, help="Target executable path.")
@click.option("--dir", "working_dir", type=click.Path(exists=False), default=None, help="Target working directory.")
@click.option("--arg", "program_args", multiple=True, help="Target argument. Repeat for multiple.")
@click.option("--env", "envs", multiple=True, help="Environment entry KEY=VALUE.")
@click.option("--wait-seconds", type=int, default=None, help="Wait N seconds before capture.")
@click.option("--wait-hotkey", is_flag=True, help="Wait for the target capture hotkey.")
@click.pass_context
def cpp_capture_cmd(ctx, exe_path, working_dir, program_args, envs, wait_seconds, wait_hotkey):
    """Run Generate C++ Capture."""
    try:
        data = cpp_capture.capture_cpp(
            exe=exe_path,
            working_dir=working_dir,
            args=program_args,
            envs=envs,
            wait_seconds=wait_seconds,
            wait_hotkey=wait_hotkey,
            **_common_kwargs(ctx),
        )
        _output(ctx, data)
    except Exception as exc:
        _handle_exc(ctx, exc)


@cli.command()
@click.pass_context
def repl(ctx):
    """Start the interactive REPL."""
    from cli_anything.nsight_graphics.utils.repl_skin import ReplSkin

    global _repl_mode
    _repl_mode = True

    skin = ReplSkin("nsight-graphics", version="0.1.0")
    skin.print_banner()
    session = skin.create_prompt_session()

    commands = {
        "doctor": "info|versions",
        "launch": "detached|attach",
        "frame": "capture",
        "gpu-trace": "capture|summarize",
        "cpp": "capture",
        "help": "Show this help",
        "quit": "Exit REPL",
    }

    try:
        while True:
            try:
                context = os.path.basename(ctx.obj.get("project", "")) if ctx.obj.get("project") else ""
                line = skin.get_input(session, project_name=context, modified=False)
                if not line:
                    continue
                if line.lower() in ("quit", "exit", "q"):
                    skin.print_goodbye()
                    break
                if line.lower() == "help":
                    skin.help(commands)
                    continue

                args = shlex.split(line, posix=os.name != "nt")
                if ctx.obj.get("json_mode"):
                    args = ["--json", *args]
                if ctx.obj.get("debug"):
                    args = ["--debug", *args]
                try:
                    cli.main(args, standalone_mode=False, obj=ctx.obj)
                except SystemExit:
                    pass
                except click.exceptions.UsageError as exc:
                    skin.warning(f"Usage error: {exc}")
                except Exception as exc:
                    if ctx.obj.get("json_mode"):
                        click.echo(json.dumps({"error": str(exc)}, indent=2))
                    else:
                        skin.error(str(exc))
            except (EOFError, KeyboardInterrupt):
                skin.print_goodbye()
                break
    finally:
        _repl_mode = False


def main():
    cli(obj={})


if __name__ == "__main__":
    main()
