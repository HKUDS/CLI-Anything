#!/usr/bin/env python3
"""
LLDB CLI - Command-line interface for LLDB debugger via Python API.
"""

from __future__ import annotations

import json
import os
import shlex
from typing import Optional

import click
from cli_anything.lldb.core.session import MEMORY_FIND_MAX_SCAN_SIZE

_session = None  # type: ignore
_session_file = None


def _set_session_file(path: str | None):
    global _session, _session_file
    if _session_file != path:
        _session = None
        _session_file = path


def _shutdown_session():
    global _session
    if _session is not None:
        shutdown = getattr(_session, "shutdown", None)
        try:
            if callable(shutdown):
                shutdown()
            else:
                _session.destroy()
        finally:
            _session = None


def _parse_int(value: str) -> int:
    return int(value, 0)


def _get_session():
    global _session
    if _session is None:
        from cli_anything.lldb.utils.session_client import RemoteLLDBSessionProxy, resolve_session_file

        _session = RemoteLLDBSessionProxy(resolve_session_file(_session_file))
    return _session


def _session_status(session):
    status_fn = getattr(session, "session_status", None)
    if callable(status_fn):
        status = status_fn()
        if isinstance(status, dict):
            return status
    return {
        "has_target": getattr(session, "target", None) is not None,
        "has_process": getattr(session, "process", None) is not None,
        "process_origin": None,
    }


def _require_target():
    s = _get_session()
    if not _session_status(s).get("has_target"):
        raise click.ClickException("No target. Run: target create --exe <path>")
    return s


def _require_process():
    s = _require_target()
    if not _session_status(s).get("has_process"):
        raise click.ClickException("No process. Run: process launch/attach or core load")
    return s


def _output(ctx: click.Context, data, human_fn=None):
    if ctx.obj.get("json_mode"):
        from cli_anything.lldb.utils.output import output_json

        output_json(data)
    elif human_fn:
        human_fn(data)
    else:
        from cli_anything.lldb.utils.output import output_json

        output_json(data)


def _handle_exc(ctx: click.Context, exc: Exception):
    from cli_anything.lldb.utils.errors import handle_error

    err = handle_error(exc, debug=ctx.obj.get("debug", False))
    if ctx.obj.get("json_mode"):
        from cli_anything.lldb.utils.output import output_json

        output_json(err)
        ctx.exit(1)
    raise click.ClickException(err["error"])


# ===========================================================================
# Root group
# ===========================================================================


@click.group(invoke_without_command=True)
@click.option("--json", "json_mode", is_flag=True, help="Output in JSON format.")
@click.option("--debug", is_flag=True, help="Show debug tracebacks on errors.")
@click.option(
    "--session-file",
    type=click.Path(dir_okay=False),
    default=None,
    help="Optional persistent session state file path.",
)
@click.version_option(package_name="cli-anything-lldb")
@click.pass_context
def cli(ctx, json_mode, debug, session_file):
    """LLDB CLI - stateful debugger harness with REPL and subcommands."""
    from cli_anything.lldb.utils.session_client import resolve_session_file

    ctx.ensure_object(dict)
    ctx.obj["json_mode"] = json_mode
    ctx.obj["debug"] = debug
    ctx.obj["session_file"] = str(resolve_session_file(session_file))
    ctx.obj.setdefault("close_session_on_exit", False)
    _set_session_file(ctx.obj["session_file"])
    if ctx.invoked_subcommand is None:
        ctx.obj["close_session_on_exit"] = True
        ctx.invoke(repl)


@cli.result_callback()
@click.pass_context
def _cleanup(ctx, _result, **_kwargs):
    if ctx.obj.get("close_session_on_exit"):
        _shutdown_session()


# ===========================================================================
# target
# ===========================================================================


@cli.group("target")
def target_group():
    """Target management."""


@target_group.command("create")
@click.option("--exe", "exe_path", required=True, type=click.Path(exists=False))
@click.option("--arch", type=str, default=None, help="Target architecture (optional).")
@click.pass_context
def target_create(ctx, exe_path: str, arch: Optional[str]):
    """Create debug target."""
    try:
        data = _get_session().target_create(exe_path, arch=arch)
        _output(ctx, data)
    except Exception as exc:
        _handle_exc(ctx, exc)


@target_group.command("info")
@click.pass_context
def target_info(ctx):
    """Show target info."""
    try:
        data = _require_target().target_info()
        _output(ctx, data)
    except Exception as exc:
        _handle_exc(ctx, exc)


# ===========================================================================
# process
# ===========================================================================


@cli.group("process")
def process_group():
    """Process management."""


@process_group.command("launch")
@click.option("--arg", "args", multiple=True, help="Launch argument. Repeat for multiple.")
@click.option("--env", "envs", multiple=True, help="Environment entry KEY=VALUE.")
@click.option("--cwd", "working_dir", type=click.Path(exists=True), default=None)
@click.option("--stop-at-entry", is_flag=True, help="Stop at the process entry point before user code.")
@click.pass_context
def process_launch(ctx, args, envs, working_dir, stop_at_entry):
    """Launch process for current target."""
    try:
        data = _require_target().launch(
            args=list(args) or None,
            env=list(envs) or None,
            working_dir=working_dir,
            stop_at_entry=stop_at_entry,
        )
        _output(ctx, data)
    except Exception as exc:
        _handle_exc(ctx, exc)


@process_group.command("attach")
@click.option("--pid", type=int, default=None, help="Attach by process ID.")
@click.option("--name", type=str, default=None, help="Attach by process name.")
@click.option("--wait-for", is_flag=True, help="Wait for process launch when attaching by name.")
@click.pass_context
def process_attach(ctx, pid, name, wait_for):
    """Attach to existing process."""
    try:
        s = _require_target()
        if pid is not None:
            data = s.attach_pid(pid)
        elif name:
            data = s.attach_name(name, wait_for=wait_for)
        else:
            raise click.ClickException("Specify --pid or --name")
        _output(ctx, data)
    except Exception as exc:
        _handle_exc(ctx, exc)


@process_group.command("continue")
@click.pass_context
def process_continue(ctx):
    """Continue execution."""
    try:
        data = _require_process().continue_exec()
        _output(ctx, data)
    except Exception as exc:
        _handle_exc(ctx, exc)


@process_group.command("interrupt")
@click.pass_context
def process_interrupt(ctx):
    """Interrupt a running process."""
    try:
        data = _require_process().interrupt()
        _output(ctx, data)
    except Exception as exc:
        _handle_exc(ctx, exc)


@process_group.command("detach")
@click.pass_context
def process_detach(ctx):
    """Detach from process."""
    try:
        data = _require_process().detach()
        _output(ctx, data)
    except Exception as exc:
        _handle_exc(ctx, exc)


@process_group.command("info")
@click.pass_context
def process_info(ctx):
    """Show process status."""
    try:
        data = _require_process().process_info()
        _output(ctx, data)
    except Exception as exc:
        _handle_exc(ctx, exc)


# ===========================================================================
# breakpoint
# ===========================================================================


@cli.group("breakpoint")
def breakpoint_group():
    """Breakpoint operations."""


@breakpoint_group.command("set")
@click.option("--file", "file_path", type=str, default=None)
@click.option("--line", type=int, default=None)
@click.option("--function", type=str, default=None)
@click.option("--condition", type=str, default=None)
@click.option("--allow-pending", is_flag=True, help="Allow unresolved pending breakpoints.")
@click.pass_context
def breakpoint_set(ctx, file_path, line, function, condition, allow_pending):
    """Set a breakpoint by file/line or function."""
    try:
        data = _require_target().breakpoint_set(
            file=file_path,
            line=line,
            function=function,
            condition=condition,
            allow_pending=allow_pending,
        )
        _output(ctx, data)
    except Exception as exc:
        _handle_exc(ctx, exc)


@breakpoint_group.command("list")
@click.pass_context
def breakpoint_list(ctx):
    """List breakpoints."""
    try:
        data = _require_target().breakpoint_list()
        _output(ctx, data)
    except Exception as exc:
        _handle_exc(ctx, exc)


@breakpoint_group.command("delete")
@click.option("--id", "bp_id", required=True, type=int)
@click.pass_context
def breakpoint_delete(ctx, bp_id: int):
    """Delete breakpoint by ID."""
    try:
        data = _require_target().breakpoint_delete(bp_id)
        _output(ctx, data)
    except Exception as exc:
        _handle_exc(ctx, exc)


@breakpoint_group.command("enable")
@click.option("--id", "bp_id", required=True, type=int)
@click.pass_context
def breakpoint_enable(ctx, bp_id: int):
    """Enable breakpoint."""
    try:
        data = _require_target().breakpoint_enable(bp_id, enabled=True)
        _output(ctx, data)
    except Exception as exc:
        _handle_exc(ctx, exc)


@breakpoint_group.command("disable")
@click.option("--id", "bp_id", required=True, type=int)
@click.pass_context
def breakpoint_disable(ctx, bp_id: int):
    """Disable breakpoint."""
    try:
        data = _require_target().breakpoint_enable(bp_id, enabled=False)
        _output(ctx, data)
    except Exception as exc:
        _handle_exc(ctx, exc)


# ===========================================================================
# thread
# ===========================================================================


@cli.group("thread")
def thread_group():
    """Thread operations."""


@thread_group.command("list")
@click.pass_context
def thread_list(ctx):
    """List threads."""
    try:
        data = _require_process().threads()
        _output(ctx, data)
    except Exception as exc:
        _handle_exc(ctx, exc)


@thread_group.command("select")
@click.option("--id", "thread_id", required=True, type=int)
@click.pass_context
def thread_select(ctx, thread_id: int):
    """Select thread."""
    try:
        data = _require_process().thread_select(thread_id)
        _output(ctx, data)
    except Exception as exc:
        _handle_exc(ctx, exc)


@thread_group.command("backtrace")
@click.option("--limit", type=int, default=50, show_default=True)
@click.pass_context
def thread_backtrace(ctx, limit: int):
    """Show backtrace of selected thread."""
    try:
        data = _require_process().backtrace(limit=limit)
        _output(ctx, data)
    except Exception as exc:
        _handle_exc(ctx, exc)


@thread_group.command("info")
@click.pass_context
def thread_info(ctx):
    """Show selected thread info."""
    try:
        threads = _require_process().threads().get("threads", [])
        selected = next((t for t in threads if t.get("selected")), None)
        if selected is None:
            raise RuntimeError("No selected thread")
        _output(ctx, selected)
    except Exception as exc:
        _handle_exc(ctx, exc)


# ===========================================================================
# frame
# ===========================================================================


@cli.group("frame")
def frame_group():
    """Frame operations."""


@frame_group.command("select")
@click.option("--index", required=True, type=int)
@click.pass_context
def frame_select(ctx, index: int):
    """Select frame by index in selected thread."""
    try:
        data = _require_process().frame_select(index)
        _output(ctx, data)
    except Exception as exc:
        _handle_exc(ctx, exc)


@frame_group.command("info")
@click.pass_context
def frame_info(ctx):
    """Show selected frame info."""
    try:
        data = _require_process().frame_info()
        _output(ctx, data)
    except Exception as exc:
        _handle_exc(ctx, exc)


@frame_group.command("locals")
@click.pass_context
def frame_locals(ctx):
    """List local variables in selected frame."""
    try:
        data = _require_process().locals()
        _output(ctx, data)
    except Exception as exc:
        _handle_exc(ctx, exc)


# ===========================================================================
# step
# ===========================================================================


@cli.group("step")
def step_group():
    """Single-step execution commands."""


@step_group.command("over")
@click.pass_context
def step_over(ctx):
    """Step over."""
    try:
        data = _require_process().step_over()
        _output(ctx, data)
    except Exception as exc:
        _handle_exc(ctx, exc)


@step_group.command("into")
@click.pass_context
def step_into(ctx):
    """Step into."""
    try:
        data = _require_process().step_into()
        _output(ctx, data)
    except Exception as exc:
        _handle_exc(ctx, exc)


@step_group.command("out")
@click.pass_context
def step_out(ctx):
    """Step out."""
    try:
        data = _require_process().step_out()
        _output(ctx, data)
    except Exception as exc:
        _handle_exc(ctx, exc)


# ===========================================================================
# expr
# ===========================================================================


@cli.command("expr")
@click.argument("expression", nargs=-1, required=True)
@click.pass_context
def expr_eval(ctx, expression):
    """Evaluate expression in selected frame."""
    try:
        expr = " ".join(expression)
        data = _require_process().evaluate(expr)
        _output(ctx, data)
    except Exception as exc:
        _handle_exc(ctx, exc)


# ===========================================================================
# memory
# ===========================================================================


@cli.group("memory")
def memory_group():
    """Memory inspection."""


@memory_group.command("read")
@click.option("--address", required=True, type=str, help="Address, supports hex (e.g. 0x1000).")
@click.option("--size", required=True, type=int, help="Number of bytes to read.")
@click.pass_context
def memory_read(ctx, address: str, size: int):
    """Read process memory."""
    try:
        addr_val = _parse_int(address)
        data = _require_process().read_memory(addr_val, size)
        _output(ctx, data)
    except Exception as exc:
        _handle_exc(ctx, exc)


@memory_group.command("find")
@click.argument("needle", required=True, type=str)
@click.option("--start", "start_addr", required=True, type=str, help="Start address (hex/int).")
@click.option(
    "--size",
    required=True,
    type=int,
    help=f"Scan size in bytes (chunked scan, max {MEMORY_FIND_MAX_SCAN_SIZE} bytes).",
)
@click.pass_context
def memory_find(ctx, needle: str, start_addr: str, size: int):
    """Find a UTF-8 needle in memory using a chunked scan."""
    try:
        addr_val = _parse_int(start_addr)
        data = _require_process().find_memory(needle, addr_val, size)
        _output(ctx, data)
    except Exception as exc:
        _handle_exc(ctx, exc)


# ===========================================================================
# core
# ===========================================================================


@cli.group("core")
def core_group():
    """Core dump operations."""


@core_group.command("load")
@click.option("--path", "core_path", required=True, type=click.Path(exists=True))
@click.pass_context
def core_load(ctx, core_path: str):
    """Load a core dump into current target."""
    try:
        data = _require_target().load_core(core_path)
        _output(ctx, data)
    except Exception as exc:
        _handle_exc(ctx, exc)


# ===========================================================================
# dap
# ===========================================================================


@cli.command("dap")
@click.option("--log-file", default=None, type=click.Path(dir_okay=False), help="Optional file for adapter diagnostics.")
@click.option("--profile", default=None, type=click.Path(exists=True, dir_okay=False), help="Stop-rule profile JSON.")
def dap_server(log_file: str | None, profile: str | None):
    """Run a stdio Debug Adapter Protocol server."""
    from cli_anything.lldb.dap import main as dap_main

    args = []
    if log_file:
        args.extend(["--log-file", log_file])
    if profile:
        args.extend(["--profile", profile])
    dap_main(args)


# ===========================================================================
# session
# ===========================================================================


@cli.group("session")
def session_group():
    """Persistent session lifecycle helpers."""


@session_group.command("info")
@click.pass_context
def session_info(ctx):
    """Show the current persistent session status."""
    try:
        data = _session_status(_get_session())
        data["session_file"] = ctx.obj.get("session_file")
        _output(ctx, data)
    except Exception as exc:
        _handle_exc(ctx, exc)


@session_group.command("close")
@click.pass_context
def session_close(ctx):
    """Close the persistent session and clean up debugger state."""
    try:
        _shutdown_session()
        _output(ctx, {"status": "closed", "session_file": ctx.obj.get("session_file")})
    except Exception as exc:
        _handle_exc(ctx, exc)


# ===========================================================================
# repl
# ===========================================================================


@cli.command()
@click.pass_context
def repl(ctx):
    """Start interactive REPL session."""
    from cli_anything.lldb.utils.repl_skin import ReplSkin

    skin = ReplSkin("lldb", version="1.0.0")
    skin.print_banner()
    pt_session = skin.create_prompt_session()

    repl_commands = {
        "target": "create|info",
        "process": "launch|attach|continue|interrupt|detach|info",
        "breakpoint": "set|list|delete|enable|disable",
        "thread": "list|select|backtrace|info",
        "frame": "select|info|locals",
        "step": "over|into|out",
        "expr": "<expression>",
        "memory": "read|find",
        "core": "load",
        "dap": "Run Debug Adapter Protocol server",
        "session": "info|close",
        "help": "Show this help",
        "quit": "Exit REPL",
    }

    try:
        while True:
            try:
                context = ""
                if _session is not None:
                    status = _session_status(_session)
                    if status.get("has_process"):
                        context = status.get("process_origin") or "active"
                    elif status.get("has_target"):
                        context = "target"
                line = skin.get_input(pt_session, project_name=context, modified=False)
                if not line:
                    continue
                if line.lower() in ("quit", "exit", "q"):
                    skin.print_goodbye()
                    break
                if line.lower() == "help":
                    skin.help(repl_commands)
                    continue
                args = shlex.split(line, posix=os.name != "nt")
                if ctx.obj.get("session_file"):
                    args = ["--session-file", ctx.obj["session_file"], *args]
                if ctx.obj.get("json_mode"):
                    args = ["--json", *args]
                if ctx.obj.get("debug"):
                    args = ["--debug", *args]
                try:
                    command_obj = dict(ctx.obj)
                    command_obj["close_session_on_exit"] = False
                    cli.main(args, standalone_mode=False, obj=command_obj)
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
        _shutdown_session()


def main():
    cli(obj={})


if __name__ == "__main__":
    main()
