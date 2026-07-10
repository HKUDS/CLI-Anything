#!/usr/bin/env python3
"""
Unreal Insights CLI - trace capture and export harness.
"""

from __future__ import annotations

import os
import shlex
from pathlib import Path

import click

from cli_anything.unrealinsights import __version__
from cli_anything.unrealinsights.core.analyze import analyze_summary
from cli_anything.unrealinsights.core.capture import (
    DEFAULT_CHANNELS,
    capture_status,
    normalize_trace_output_path,
    resolve_capture_target,
    run_capture,
    snapshot_capture,
    stop_capture,
)
from cli_anything.unrealinsights.core.export import execute_export, execute_response_file
from cli_anything.unrealinsights.core.gui import gui_status, open_gui
from cli_anything.unrealinsights.core.live import (
    execute_live_command,
    list_unreal_processes,
    trace_bookmark,
    trace_screenshot,
    trace_snapshot,
    trace_status as live_trace_status,
    trace_stop,
)
from cli_anything.unrealinsights.core.session import UnrealInsightsSession, state_dir
from cli_anything.unrealinsights.core.store import latest_trace_file, list_trace_files, trace_store_info
from cli_anything.unrealinsights.utils.errors import handle_error
from cli_anything.unrealinsights.utils.output import format_size, output_json
from cli_anything.unrealinsights.utils.unrealinsights_backend import (
    ensure_engine_unrealinsights,
    resolve_trace_server_exe,
    resolve_unrealinsights_exe,
)

_repl_mode = False


def _get_session(ctx: click.Context) -> UnrealInsightsSession:
    ctx.ensure_object(dict)
    session = ctx.obj.get("session")
    if session is None:
        session = UnrealInsightsSession.load()
        ctx.obj["session"] = session
    return session


def _output(ctx: click.Context, data, human_fn=None):
    if ctx.obj.get("json_mode"):
        output_json(data)
    elif human_fn:
        human_fn(data)
    else:
        output_json(data)


def _handle_exc(ctx: click.Context, exc: Exception):
    err = handle_error(exc, debug=ctx.obj.get("debug", False))
    if ctx.obj.get("json_mode"):
        output_json(err)
        ctx.exit(1)
    raise click.ClickException(err["error"])


def _resolve_insights(ctx: click.Context) -> dict[str, object]:
    session = _get_session(ctx)
    info = resolve_unrealinsights_exe(session.insights_exe, required=True)
    session.set_insights_exe(info["path"])
    return info


def _resolve_trace_server(ctx: click.Context) -> dict[str, object]:
    session = _get_session(ctx)
    info = resolve_trace_server_exe(session.trace_server_exe, required=False)
    if info["available"]:
        session.set_trace_server_exe(info["path"])
    return info


def _require_trace(ctx: click.Context) -> str:
    session = _get_session(ctx)
    if not session.trace_path:
        raise click.ClickException("No trace selected. Use --trace <path> or `trace set <path>` first.")
    trace_path = Path(session.trace_path).expanduser().resolve()
    if not trace_path.is_file():
        raise click.ClickException(f"Trace file not found: {trace_path}")
    return str(trace_path)


def _human_backend(data: dict[str, object]):
    insights = data["insights"]
    trace_server = data["trace_server"]
    click.echo("Resolved Backends:")
    click.echo(f"  UnrealInsights.exe : {insights['path']} ({insights['source']})")
    click.echo(f"  Version            : {insights.get('version') or 'unknown'}")
    if trace_server["available"]:
        click.echo(f"  UnrealTraceServer  : {trace_server['path']} ({trace_server['source']})")
        click.echo(f"  Version            : {trace_server.get('version') or 'unknown'}")
    else:
        click.echo(f"  UnrealTraceServer  : unavailable ({trace_server.get('error', 'not found')})")


def _human_ensure_insights(data: dict[str, object]):
    insights = data["insights"]
    click.echo(f"Engine root:       {data['engine_root']}")
    click.echo(f"UnrealInsights.exe {insights['path']} ({insights['source']})")
    click.echo(f"Version:           {insights.get('version') or 'unknown'}")
    trace_server = data.get("trace_server")
    if trace_server and trace_server.get("available"):
        click.echo(f"TraceServer:       {trace_server['path']}")
    build = data.get("build")
    if build:
        click.echo(f"Built:             {'yes' if build['succeeded'] else 'no'}")
        click.echo(f"Build log:         {build['log_path']}")


def _human_trace_info(data: dict[str, object]):
    trace_path = data.get("trace_path")
    if not trace_path:
        click.echo("No active trace selected.")
        return
    click.echo(f"Trace:   {trace_path}")
    click.echo(f"Exists:  {'yes' if data.get('exists') else 'no'}")
    if data.get("exists"):
        click.echo(f"Size:    {format_size(data.get('file_size'))}")


def _human_export_result(data: dict[str, object]):
    click.echo(f"Trace:     {data['trace_path']}")
    click.echo(f"Command:   {data['exec_command']}")
    click.echo(f"Log:       {data['log_path']}")
    click.echo(f"Exit code: {data['exit_code']}")
    click.echo(f"Status:    {data.get('output_status', 'unknown')}")
    click.echo(f"Success:   {'yes' if data['succeeded'] else 'no'}")
    if data.get("status_message"):
        click.echo(f"Message:   {data['status_message']}")
    if data["output_files"]:
        click.echo("Outputs:")
        for output_path in data["output_files"]:
            click.echo(f"  {output_path}")
    if data["errors"]:
        click.echo("Errors:")
        for line in data["errors"]:
            click.echo(f"  {line}")


def _human_capture_result(data: dict[str, object]):
    click.echo(f"Target exe:   {data['target_exe']}")
    if data.get("project_path"):
        click.echo(f"Project:      {data['project_path']}")
    if data.get("engine_root"):
        click.echo(f"Engine root:  {data['engine_root']}")
    click.echo(f"Trace output: {data['trace_path']}")
    click.echo(f"Channels:     {data['channels']}")
    click.echo(f"Command:      {' '.join(map(str, data['command']))}")
    if data["waited"]:
        click.echo(f"Exit code:    {data['exit_code']}")
        click.echo(f"Trace exists: {'yes' if data['trace_exists'] else 'no'}")
        if data["trace_exists"]:
            click.echo(f"Trace size:   {format_size(data['trace_size'])}")
    else:
        click.echo(f"PID:          {data['pid']}")


def _human_capture_status(data: dict[str, object]):
    if not data.get("active"):
        click.echo("No tracked capture session.")
        return
    click.echo(f"PID:          {data.get('pid')}")
    click.echo(f"Running:      {'yes' if data.get('running') else 'no'}")
    click.echo(f"Target exe:   {data.get('target_exe')}")
    if data.get("project_path"):
        click.echo(f"Project:      {data['project_path']}")
    if data.get("engine_root"):
        click.echo(f"Engine root:  {data['engine_root']}")
    click.echo(f"Trace:        {data.get('trace_path')}")
    click.echo(f"Trace exists: {'yes' if data.get('trace_exists') else 'no'}")
    if data.get("trace_exists"):
        click.echo(f"Trace size:   {format_size(data.get('trace_size'))}")
    if data.get("started_at"):
        click.echo(f"Started at:   {data['started_at']}")


def _human_snapshot_result(data: dict[str, object]):
    click.echo(f"Source trace:   {data['source_trace']}")
    click.echo(f"Snapshot trace: {data['snapshot_trace']}")
    click.echo(f"Exists:         {'yes' if data['snapshot_exists'] else 'no'}")
    if data.get("snapshot_exists"):
        click.echo(f"Size:           {format_size(data.get('snapshot_size'))}")
    click.echo(f"Capture running:{' yes' if data.get('capture_running') else ' no'}")


def _human_stop_result(data: dict[str, object]):
    termination = data["termination"]
    click.echo(f"Requested PID: {termination['requested_pid']}")
    click.echo(f"Stopped:       {'yes' if termination['stopped'] else 'no'}")
    click.echo(f"Exit code:     {termination.get('exit_code')}")


def _human_store_info(data: dict[str, object]):
    click.echo(f"Trace root:    {data['trace_root']}")
    click.echo(f"Store:         {data['store_dir']}")
    click.echo(f"Store exists:  {'yes' if data['store_exists'] else 'no'}")
    click.echo(f"Trace files:   {data['trace_file_count']}")
    trace_server = data["trace_server"]
    if trace_server.get("available"):
        click.echo(f"TraceServer:   {trace_server['path']}")
    else:
        click.echo(f"TraceServer:   unavailable ({trace_server.get('error', 'not found')})")


def _human_store_list(data: dict[str, object]):
    click.echo(f"Store:       {data['store_dir']}")
    click.echo(f"Trace count: {data['trace_count']}")
    for trace in data["traces"][:20]:
        live = " live?" if trace.get("is_live_candidate") else ""
        click.echo(f"  {trace['path']} ({format_size(trace.get('file_size'))}){live}")


def _human_store_latest(data: dict[str, object]):
    latest = data.get("latest")
    if not latest:
        click.echo("No trace file found.")
        return
    click.echo(f"Latest trace: {latest['path']}")
    click.echo(f"Size:         {format_size(latest.get('file_size'))}")
    click.echo(f"Live guess:   {'yes' if latest.get('is_live_candidate') else 'no'}")
    if data.get("set_current"):
        click.echo("Current session trace updated.")


def _human_processes(data: dict[str, object]):
    click.echo(f"Processes: {data['process_count']}")
    for process in data["processes"]:
        click.echo(f"  {process['pid']}  {process['role']}  {process['name']}  {process.get('path') or ''}")


def _human_live_result(data: dict[str, object]):
    click.echo(f"PID:      {data['pid']}")
    click.echo(f"Command:  {data['live_command']}")
    click.echo(f"Backend:  {data['backend']}")
    click.echo(f"Exit:     {data['exit_code']}")
    click.echo(f"Success:  {'yes' if data['succeeded'] else 'no'}")
    if data.get("stdout"):
        click.echo(data["stdout"])
    if data.get("stderr"):
        click.echo(data["stderr"])


def _human_gui_status(data: dict[str, object]):
    click.echo(f"Unreal Insights GUI running: {'yes' if data['running'] else 'no'}")
    for process in data["processes"]:
        click.echo(f"  {process['pid']}  {process.get('path') or process['name']}")


def _human_gui_open(data: dict[str, object]):
    click.echo(f"UnrealInsights.exe: {data['insights_exe']}")
    if data.get("trace_path"):
        click.echo(f"Trace:              {data['trace_path']}")
    click.echo(f"PID:                {data['pid']}")
    click.echo("Mode:               GUI kept running")


def _human_analyze_summary(data: dict[str, object]):
    click.echo(f"Trace:   {data.get('trace_path') or 'not supplied'}")
    click.echo(f"Out dir: {data['out_dir']}")
    click.echo(f"Success: {'yes' if data['succeeded'] else 'no'}")
    top_timers = data["summary"].get("top_timers", [])
    if top_timers:
        click.echo("Top timers:")
        for entry in top_timers[:10]:
            click.echo(f"  {entry['name']}  score={entry.get('score')}")
    if data.get("warnings"):
        click.echo("Warnings:")
        for warning in data["warnings"]:
            click.echo(f"  {warning}")


@click.group(invoke_without_command=True)
@click.option("--json", "json_mode", is_flag=True, help="Output in JSON format.")
@click.option("--debug", is_flag=True, help="Show debug tracebacks on errors.")
@click.option(
    "--trace",
    "-t",
    type=click.Path(exists=False),
    envvar="UNREALINSIGHTS_TRACE",
    help="Path to the active .utrace file.",
)
@click.option(
    "--insights-exe",
    type=click.Path(exists=False),
    envvar="UNREALINSIGHTS_EXE",
    help="Explicit path to UnrealInsights.exe.",
)
@click.option(
    "--trace-server-exe",
    type=click.Path(exists=False),
    envvar="UNREAL_TRACE_SERVER_EXE",
    help="Explicit path to UnrealTraceServer.exe.",
)
@click.version_option(version=__version__)
@click.pass_context
def cli(ctx, json_mode, debug, trace, insights_exe, trace_server_exe):
    """Windows-first Unreal Insights harness with REPL and exporter wrappers."""
    ctx.ensure_object(dict)
    session = _get_session(ctx)
    ctx.obj["json_mode"] = json_mode
    ctx.obj["debug"] = debug

    if trace is not None:
        session.set_trace(trace)
    if insights_exe is not None:
        session.set_insights_exe(insights_exe)
    if trace_server_exe is not None:
        session.set_trace_server_exe(trace_server_exe)

    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


@cli.group("backend")
def backend_group():
    """Backend executable discovery and inspection."""


@backend_group.command("info")
@click.pass_context
def backend_info(ctx):
    """Resolve Unreal Insights backend executables."""
    try:
        data = {
            "insights": _resolve_insights(ctx),
            "trace_server": _resolve_trace_server(ctx),
        }
        _output(ctx, data, _human_backend)
    except Exception as exc:
        _handle_exc(ctx, exc)


@backend_group.command("ensure-insights")
@click.option("--engine-root", required=True, type=click.Path(exists=False), help="UE install root or its Engine subdir.")
@click.option(
    "--build-if-missing/--no-build-if-missing",
    default=True,
    show_default=True,
    help="Build UnrealInsights when it is missing under the given engine root.",
)
@click.option("--configuration", default="Development", show_default=True, help="Build configuration.")
@click.option("--timeout", type=float, default=None, help="Optional build timeout in seconds.")
@click.pass_context
def backend_ensure_insights(ctx, engine_root, build_if_missing, configuration, timeout):
    """Find or build UnrealInsights.exe for a specific engine root."""
    try:
        data = ensure_engine_unrealinsights(
            engine_root,
            build_if_missing=build_if_missing,
            configuration=configuration,
            timeout=timeout,
        )
        session = _get_session(ctx)
        session.set_insights_exe(data["insights"]["path"])
        trace_server = data.get("trace_server")
        if trace_server and trace_server.get("available"):
            session.set_trace_server_exe(trace_server["path"])
        _output(ctx, data, _human_ensure_insights)
    except Exception as exc:
        _handle_exc(ctx, exc)


@cli.group("trace")
def trace_group():
    """Session trace path management."""


@trace_group.command("set")
@click.argument("trace_path", type=click.Path(exists=False))
@click.pass_context
def trace_set(ctx, trace_path):
    """Set the active trace path for this session or REPL."""
    session = _get_session(ctx)
    session.set_trace(trace_path)
    _output(ctx, session.trace_info(), _human_trace_info)


@trace_group.command("info")
@click.pass_context
def trace_info(ctx):
    """Show the active trace path."""
    session = _get_session(ctx)
    _output(ctx, session.trace_info(), _human_trace_info)


@cli.group("store")
def store_group():
    """Trace Store discovery and session selection."""


@store_group.command("info")
@click.option("--store-dir", type=click.Path(exists=False), default=None, help="Explicit Trace Store directory.")
@click.pass_context
def store_info(ctx, store_dir):
    """Inspect the local Unreal Trace Store."""
    try:
        session = _get_session(ctx)
        data = trace_store_info(store_dir=store_dir, trace_server_exe=session.trace_server_exe)
        _output(ctx, data, _human_store_info)
    except Exception as exc:
        _handle_exc(ctx, exc)


@store_group.command("list")
@click.option("--store-dir", type=click.Path(exists=False), default=None, help="Explicit Trace Store directory.")
@click.option("--live-only", is_flag=True, help="Only show recently modified trace files.")
@click.option("--include-cache/--no-include-cache", default=True, show_default=True, help="Include Trace Store .ucache files.")
@click.option("--live-window", type=float, default=60.0, show_default=True, help="Seconds used for live-candidate detection.")
@click.pass_context
def store_list(ctx, store_dir, live_only, include_cache, live_window):
    """List trace files in the Trace Store."""
    try:
        data = list_trace_files(
            store_dir=store_dir,
            live_only=live_only,
            include_cache=include_cache,
            live_window_seconds=live_window,
        )
        _output(ctx, data, _human_store_list)
    except Exception as exc:
        _handle_exc(ctx, exc)


@store_group.command("latest")
@click.option("--store-dir", type=click.Path(exists=False), default=None, help="Explicit Trace Store directory.")
@click.option("--live-only", is_flag=True, help="Only consider recently modified trace files.")
@click.option("--include-cache/--no-include-cache", default=True, show_default=True, help="Include Trace Store .ucache files.")
@click.option("--live-window", type=float, default=60.0, show_default=True, help="Seconds used for live-candidate detection.")
@click.option("--set-current", is_flag=True, help="Set the selected trace as the current session trace.")
@click.pass_context
def store_latest(ctx, store_dir, live_only, include_cache, live_window, set_current):
    """Select the newest trace file in the Trace Store."""
    try:
        data = latest_trace_file(
            store_dir=store_dir,
            live_only=live_only,
            include_cache=include_cache,
            live_window_seconds=live_window,
        )
        latest = data.get("latest")
        if latest and set_current:
            _get_session(ctx).set_trace(latest["path"])
            data["set_current"] = True
        else:
            data["set_current"] = False
        _output(ctx, data, _human_store_latest)
    except Exception as exc:
        _handle_exc(ctx, exc)


@cli.group("capture")
def capture_group():
    """Trace capture orchestration."""


@capture_group.command("run")
@click.argument("target_exe", required=False, type=click.Path(exists=False))
@click.option("--project", type=click.Path(exists=False), default=None, help="Path to a .uproject file.")
@click.option(
    "--engine-root",
    type=click.Path(exists=False),
    default=None,
    help="UE install root such as D:\\Program Files\\Epic Games\\UE_5.5 or its Engine subdir.",
)
@click.option("--target-arg", "target_args", multiple=True, help="Argument to pass to the target executable.")
@click.option("--output-trace", type=click.Path(exists=False), default=None, help="Output .utrace path.")
@click.option("--channels", default=DEFAULT_CHANNELS, show_default=True, help="Comma-separated UE trace channels.")
@click.option("--exec-cmd", "exec_cmds", multiple=True, help="Startup UE console command for -ExecCmds.")
@click.option("--wait", is_flag=True, help="Wait for the target to exit.")
@click.option("--timeout", type=float, default=None, help="Optional timeout in seconds when waiting.")
@click.pass_context
def capture_run(ctx, target_exe, project, engine_root, target_args, output_trace, channels, exec_cmds, wait, timeout):
    """Launch a target executable with UE trace flags in file mode."""
    try:
        session = _get_session(ctx)
        resolved_target_exe, resolved_target_args, launch_info = resolve_capture_target(
            target_exe,
            project=project,
            engine_root=engine_root,
            target_args=target_args,
        )
        resolved_output = normalize_trace_output_path(
            resolved_target_exe,
            output_trace=output_trace,
            current_trace=session.trace_path,
        )
        data = run_capture(
            resolved_target_exe,
            output_trace=resolved_output,
            channels=channels,
            exec_cmds=exec_cmds,
            target_args=resolved_target_args,
            wait=wait,
            timeout=timeout,
        )
        data.update(launch_info)
        session.set_trace(resolved_output)
        if wait:
            session.clear_capture()
        else:
            session.set_capture(
                pid=data.get("pid"),
                target_exe=resolved_target_exe,
                target_args=resolved_target_args,
                trace_path=resolved_output,
                channels=channels,
                project_path=launch_info.get("project_path"),
                engine_root=launch_info.get("engine_root"),
            )
        _output(ctx, data, _human_capture_result)
    except Exception as exc:
        _handle_exc(ctx, exc)


def _prepare_capture_start(ctx: click.Context, replace: bool):
    session = _get_session(ctx)
    status = capture_status(session)
    if status.get("active") and status.get("running"):
        if not replace:
            raise RuntimeError(
                "A capture session is already running. Use `capture status` to inspect it, "
                "`capture stop` to end it, or rerun `capture start` with `--replace`."
            )

        stop_result = stop_capture(session)
        if not stop_result.get("termination", {}).get("stopped"):
            raise RuntimeError("Failed to stop the existing capture session before starting a replacement.")
    elif status.get("active"):
        session.clear_capture()


@capture_group.command("start")
@click.argument("target_exe", required=False, type=click.Path(exists=False))
@click.option("--project", type=click.Path(exists=False), default=None, help="Path to a .uproject file.")
@click.option(
    "--engine-root",
    type=click.Path(exists=False),
    default=None,
    help="UE install root such as D:\\Program Files\\Epic Games\\UE_5.5 or its Engine subdir.",
)
@click.option("--target-arg", "target_args", multiple=True, help="Argument to pass to the target executable.")
@click.option("--output-trace", type=click.Path(exists=False), default=None, help="Output .utrace path.")
@click.option("--channels", default=DEFAULT_CHANNELS, show_default=True, help="Comma-separated UE trace channels.")
@click.option("--exec-cmd", "exec_cmds", multiple=True, help="Startup UE console command for -ExecCmds.")
@click.option("--replace", is_flag=True, help="Stop the currently tracked capture session before starting a new one.")
@click.pass_context
def capture_start(ctx, target_exe, project, engine_root, target_args, output_trace, channels, exec_cmds, replace):
    """Launch a traced target in the background and track the session."""
    try:
        _prepare_capture_start(ctx, replace=replace)
        ctx.invoke(
            capture_run,
            target_exe=target_exe,
            project=project,
            engine_root=engine_root,
            target_args=target_args,
            output_trace=output_trace,
            channels=channels,
            exec_cmds=exec_cmds,
            wait=False,
            timeout=None,
        )
    except Exception as exc:
        _handle_exc(ctx, exc)


@capture_group.command("status")
@click.pass_context
def capture_status_cmd(ctx):
    """Show the tracked background capture status."""
    try:
        data = capture_status(_get_session(ctx))
        _output(ctx, data, _human_capture_status)
    except Exception as exc:
        _handle_exc(ctx, exc)


@capture_group.command("stop")
@click.option("--force", is_flag=True, help="Force terminate the process tree.")
@click.option("--timeout", type=float, default=None, help="Optional stop timeout in seconds.")
@click.pass_context
def capture_stop_cmd(ctx, force, timeout):
    """Stop the tracked capture process."""
    try:
        data = stop_capture(_get_session(ctx), force=force, timeout=timeout)
        _output(ctx, data, _human_stop_result)
    except Exception as exc:
        _handle_exc(ctx, exc)


@capture_group.command("snapshot")
@click.argument("output_trace", required=False, type=click.Path(exists=False))
@click.pass_context
def capture_snapshot_cmd(ctx, output_trace):
    """Create a best-effort snapshot copy of the current trace."""
    try:
        data = snapshot_capture(_get_session(ctx), output_trace=output_trace)
        _output(ctx, data, _human_snapshot_result)
    except Exception as exc:
        _handle_exc(ctx, exc)


@cli.group("live")
def live_group():
    """Live UE process discovery and trace-control command delivery."""


@live_group.command("processes")
@click.option("--include-tools/--no-include-tools", default=True, show_default=True, help="Include UnrealInsights and TraceServer.")
@click.pass_context
def live_processes(ctx, include_tools):
    """List local Unreal-related processes."""
    try:
        data = list_unreal_processes(include_tools=include_tools)
        _output(ctx, data, _human_processes)
    except Exception as exc:
        _handle_exc(ctx, exc)


def _run_live_command(ctx: click.Context, fn, *args, backend_command=None, timeout=None):
    data = fn(*args, backend_command=backend_command, timeout=timeout)
    _output(ctx, data, _human_live_result)


@live_group.command("exec")
@click.option("--pid", required=True, type=int, help="Target UE process id.")
@click.option("--backend-command", default=None, help="External command template accepting {pid} and {cmd}.")
@click.option("--timeout", type=float, default=None, help="Optional backend timeout in seconds.")
@click.argument("command", nargs=-1, required=True)
@click.pass_context
def live_exec(ctx, pid, backend_command, timeout, command):
    """Send a raw console command to a live UE process."""
    try:
        data = execute_live_command(
            pid,
            " ".join(command),
            backend_command=backend_command,
            timeout=timeout,
        )
        _output(ctx, data, _human_live_result)
    except Exception as exc:
        _handle_exc(ctx, exc)


@live_group.command("trace-status")
@click.option("--pid", required=True, type=int, help="Target UE process id.")
@click.option("--backend-command", default=None, help="External command template accepting {pid} and {cmd}.")
@click.option("--timeout", type=float, default=None, help="Optional backend timeout in seconds.")
@click.pass_context
def live_trace_status_cmd(ctx, pid, backend_command, timeout):
    """Run Trace.Status on a live UE process."""
    try:
        _run_live_command(ctx, live_trace_status, pid, backend_command=backend_command, timeout=timeout)
    except Exception as exc:
        _handle_exc(ctx, exc)


@live_group.command("bookmark")
@click.option("--pid", required=True, type=int, help="Target UE process id.")
@click.option("--backend-command", default=None, help="External command template accepting {pid} and {cmd}.")
@click.option("--timeout", type=float, default=None, help="Optional backend timeout in seconds.")
@click.argument("name")
@click.pass_context
def live_bookmark(ctx, pid, backend_command, timeout, name):
    """Insert a Trace.Bookmark marker in a live UE process."""
    try:
        _run_live_command(ctx, trace_bookmark, pid, name, backend_command=backend_command, timeout=timeout)
    except Exception as exc:
        _handle_exc(ctx, exc)


@live_group.command("screenshot")
@click.option("--pid", required=True, type=int, help="Target UE process id.")
@click.option("--backend-command", default=None, help="External command template accepting {pid} and {cmd}.")
@click.option("--timeout", type=float, default=None, help="Optional backend timeout in seconds.")
@click.argument("name")
@click.pass_context
def live_screenshot(ctx, pid, backend_command, timeout, name):
    """Insert a Trace.Screenshot marker in a live UE process."""
    try:
        _run_live_command(ctx, trace_screenshot, pid, name, backend_command=backend_command, timeout=timeout)
    except Exception as exc:
        _handle_exc(ctx, exc)


@live_group.command("snapshot")
@click.option("--pid", required=True, type=int, help="Target UE process id.")
@click.option("--backend-command", default=None, help="External command template accepting {pid} and {cmd}.")
@click.option("--timeout", type=float, default=None, help="Optional backend timeout in seconds.")
@click.argument("output_trace", type=click.Path(exists=False))
@click.pass_context
def live_snapshot(ctx, pid, backend_command, timeout, output_trace):
    """Request a Trace.SnapshotFile from a live UE process."""
    try:
        _run_live_command(ctx, trace_snapshot, pid, output_trace, backend_command=backend_command, timeout=timeout)
    except Exception as exc:
        _handle_exc(ctx, exc)


@live_group.command("stop-trace")
@click.option("--pid", required=True, type=int, help="Target UE process id.")
@click.option("--backend-command", default=None, help="External command template accepting {pid} and {cmd}.")
@click.option("--timeout", type=float, default=None, help="Optional backend timeout in seconds.")
@click.pass_context
def live_stop_trace(ctx, pid, backend_command, timeout):
    """Stop tracing in a live UE process without killing the process."""
    try:
        _run_live_command(ctx, trace_stop, pid, backend_command=backend_command, timeout=timeout)
    except Exception as exc:
        _handle_exc(ctx, exc)


@cli.group("gui")
def gui_group():
    """Unreal Insights GUI co-pilot helpers."""


@gui_group.command("status")
@click.pass_context
def gui_status_cmd(ctx):
    """Show running Unreal Insights GUI processes."""
    try:
        data = gui_status()
        _output(ctx, data, _human_gui_status)
    except Exception as exc:
        _handle_exc(ctx, exc)


@gui_group.command("open")
@click.option("--trace", "trace_override", type=click.Path(exists=False), default=None, help="Trace file to open in the GUI.")
@click.pass_context
def gui_open_cmd(ctx, trace_override):
    """Open Unreal Insights GUI and keep it running."""
    try:
        trace_path = trace_override or _get_session(ctx).trace_path
        insights = _resolve_insights(ctx)
        data = open_gui(insights["path"], trace_path=trace_path)
        _output(ctx, data, _human_gui_open)
    except Exception as exc:
        _handle_exc(ctx, exc)


@gui_group.command("open-latest")
@click.option("--store-dir", type=click.Path(exists=False), default=None, help="Explicit Trace Store directory.")
@click.option("--live-only", is_flag=True, help="Only consider recently modified trace files.")
@click.option("--include-cache/--no-include-cache", default=True, show_default=True, help="Include Trace Store .ucache files.")
@click.pass_context
def gui_open_latest(ctx, store_dir, live_only, include_cache):
    """Open the newest Trace Store trace in Unreal Insights GUI."""
    try:
        latest = latest_trace_file(store_dir=store_dir, live_only=live_only, include_cache=include_cache).get("latest")
        if not latest:
            raise RuntimeError("No trace file found in the Trace Store.")
        _get_session(ctx).set_trace(latest["path"])
        insights = _resolve_insights(ctx)
        data = open_gui(insights["path"], trace_path=latest["path"])
        data["latest"] = latest
        _output(ctx, data, _human_gui_open)
    except Exception as exc:
        _handle_exc(ctx, exc)


@cli.group("export")
def export_group():
    """Offline Unreal Insights exporters."""


def _run_export(
    ctx: click.Context,
    exporter: str,
    output_path: str,
    *,
    columns: str | None = None,
    threads: str | None = None,
    timers: str | None = None,
    start_time: float | None = None,
    end_time: float | None = None,
    region: str | None = None,
    counter: str | None = None,
):
    trace_path = _require_trace(ctx)
    insights = _resolve_insights(ctx)
    data = execute_export(
        insights["path"],
        trace_path,
        exporter,
        output_path,
        insights_version=insights.get("version"),
        columns=columns,
        threads=threads,
        timers=timers,
        start_time=start_time,
        end_time=end_time,
        region=region,
        counter=counter,
    )
    _output(ctx, data, _human_export_result)


@export_group.command("threads")
@click.argument("output_path", type=click.Path(exists=False))
@click.pass_context
def export_threads(ctx, output_path):
    """Export thread metadata."""
    try:
        _run_export(ctx, "threads", output_path)
    except Exception as exc:
        _handle_exc(ctx, exc)


@export_group.command("timers")
@click.argument("output_path", type=click.Path(exists=False))
@click.pass_context
def export_timers(ctx, output_path):
    """Export timer metadata."""
    try:
        _run_export(ctx, "timers", output_path)
    except Exception as exc:
        _handle_exc(ctx, exc)


@export_group.command("timing-events")
@click.argument("output_path", type=click.Path(exists=False))
@click.option("--columns", default=None)
@click.option("--threads", default=None)
@click.option("--timers", default=None)
@click.option("--start-time", type=float, default=None)
@click.option("--end-time", type=float, default=None)
@click.option("--region", default=None)
@click.pass_context
def export_timing_events(ctx, output_path, columns, threads, timers, start_time, end_time, region):
    """Export timing events."""
    try:
        _run_export(
            ctx,
            "timing-events",
            output_path,
            columns=columns,
            threads=threads,
            timers=timers,
            start_time=start_time,
            end_time=end_time,
            region=region,
        )
    except Exception as exc:
        _handle_exc(ctx, exc)


@export_group.command("timer-stats")
@click.argument("output_path", type=click.Path(exists=False))
@click.option("--columns", default=None)
@click.option("--threads", default=None)
@click.option("--timers", default=None)
@click.option("--start-time", type=float, default=None)
@click.option("--end-time", type=float, default=None)
@click.option("--region", default=None)
@click.pass_context
def export_timer_stats(ctx, output_path, columns, threads, timers, start_time, end_time, region):
    """Export aggregated timer statistics."""
    try:
        _run_export(
            ctx,
            "timer-stats",
            output_path,
            columns=columns,
            threads=threads,
            timers=timers,
            start_time=start_time,
            end_time=end_time,
            region=region,
        )
    except Exception as exc:
        _handle_exc(ctx, exc)


@export_group.command("timer-callees")
@click.argument("output_path", type=click.Path(exists=False))
@click.option("--threads", default=None)
@click.option("--timers", default=None)
@click.option("--start-time", type=float, default=None)
@click.option("--end-time", type=float, default=None)
@click.option("--region", default=None)
@click.pass_context
def export_timer_callees(ctx, output_path, threads, timers, start_time, end_time, region):
    """Export timer callee trees."""
    try:
        _run_export(
            ctx,
            "timer-callees",
            output_path,
            threads=threads,
            timers=timers,
            start_time=start_time,
            end_time=end_time,
            region=region,
        )
    except Exception as exc:
        _handle_exc(ctx, exc)


@export_group.command("counters")
@click.argument("output_path", type=click.Path(exists=False))
@click.pass_context
def export_counters(ctx, output_path):
    """Export the counter list."""
    try:
        _run_export(ctx, "counters", output_path)
    except Exception as exc:
        _handle_exc(ctx, exc)


@export_group.command("counter-values")
@click.argument("output_path", type=click.Path(exists=False))
@click.option("--counter", default=None)
@click.option("--columns", default=None)
@click.option("--start-time", type=float, default=None)
@click.option("--end-time", type=float, default=None)
@click.option("--region", default=None)
@click.pass_context
def export_counter_values(ctx, output_path, counter, columns, start_time, end_time, region):
    """Export counter values."""
    try:
        _run_export(
            ctx,
            "counter-values",
            output_path,
            counter=counter,
            columns=columns,
            start_time=start_time,
            end_time=end_time,
            region=region,
        )
    except Exception as exc:
        _handle_exc(ctx, exc)


@cli.group("batch")
def batch_group():
    """Batch export workflows."""


@batch_group.command("run-rsp")
@click.argument("rsp_path", type=click.Path(exists=False))
@click.pass_context
def batch_run_rsp(ctx, rsp_path):
    """Execute a response file using UnrealInsights.exe."""
    try:
        trace_path = _require_trace(ctx)
        insights = _resolve_insights(ctx)
        data = execute_response_file(
            insights["path"],
            trace_path,
            rsp_path,
            insights_version=insights.get("version"),
        )
        _output(ctx, data, _human_export_result)
    except Exception as exc:
        _handle_exc(ctx, exc)


@cli.group("analyze")
def analyze_group():
    """Export and summarize Unreal Insights timing/counter data."""


@analyze_group.command("summary")
@click.option("--trace", "trace_override", type=click.Path(exists=False), default=None, help="Trace file to analyze.")
@click.option("--out", "out_dir", required=True, type=click.Path(exists=False), help="Directory for exports and summary inputs.")
@click.option("--skip-export", is_flag=True, help="Summarize existing CSV exports without launching UnrealInsights.exe.")
@click.option("--limit", type=int, default=20, show_default=True, help="Maximum entries per summary list.")
@click.pass_context
def analyze_summary_cmd(ctx, trace_override, out_dir, skip_export, limit):
    """Run the standard exporter bundle and summarize hot spots."""
    try:
        trace_path = None
        insights = None
        if trace_override:
            trace_path = str(Path(trace_override).expanduser().resolve())
            _get_session(ctx).set_trace(trace_path)
        elif not skip_export:
            trace_path = _require_trace(ctx)
        elif _get_session(ctx).trace_path:
            trace_path = _get_session(ctx).trace_path

        if not skip_export:
            insights = _resolve_insights(ctx)

        data = analyze_summary(
            insights["path"] if insights else None,
            trace_path,
            out_dir,
            insights_version=insights.get("version") if insights else None,
            skip_export=skip_export,
            limit=limit,
        )
        _output(ctx, data, _human_analyze_summary)
    except Exception as exc:
        _handle_exc(ctx, exc)


@cli.command()
@click.pass_context
def repl(ctx):
    """Start the interactive REPL."""
    from cli_anything.unrealinsights.utils.repl_skin import ReplSkin

    global _repl_mode
    _repl_mode = True

    session = _get_session(ctx)
    skin = ReplSkin("unrealinsights", version=__version__, history_file=str(state_dir() / "history"))
    skin.print_banner()
    pt_session = skin.create_prompt_session()

    repl_commands = {
        "backend": "info|ensure-insights",
        "trace": "set|info",
        "store": "info|list|latest",
        "capture": "run|start|status|stop|snapshot",
        "live": "processes|exec|trace-status|bookmark|screenshot|snapshot|stop-trace",
        "gui": "status|open|open-latest",
        "export": "threads|timers|timing-events|timer-stats|timer-callees|counters|counter-values",
        "batch": "run-rsp",
        "analyze": "summary",
        "help": "Show this help",
        "quit": "Exit REPL",
    }

    try:
        while True:
            try:
                trace_name = Path(session.trace_path).name if session.trace_path else ""
                line = skin.get_input(pt_session, project_name=trace_name, modified=False)
                if not line:
                    continue
                if line.lower() in ("quit", "exit", "q"):
                    skin.print_goodbye()
                    break
                if line.lower() == "help":
                    skin.help(repl_commands)
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
                        output_json({"error": str(exc)})
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
