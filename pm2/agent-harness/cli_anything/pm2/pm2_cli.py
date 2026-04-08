"""PM2 CLI — Click-based CLI with REPL mode for PM2 process management.

Entry point: cli-anything-pm2
"""

import json
import sys

import click

from .core import processes, lifecycle, logs, system


# ── Helpers ──────────────────────────────────────────────────────────────

def _output(data, as_json: bool):
    """Print data as JSON or formatted text."""
    if as_json:
        if isinstance(data, str):
            click.echo(json.dumps({"result": data}, indent=2))
        else:
            click.echo(json.dumps(data, indent=2, default=str))
    else:
        if isinstance(data, str):
            click.echo(data)
        elif isinstance(data, dict):
            if "message" in data:
                prefix = "OK" if data.get("success", True) else "ERROR"
                click.echo(f"[{prefix}] {data['message']}")
                if data.get("content"):
                    click.echo(data["content"])
                if data.get("instructions"):
                    click.echo(data["instructions"])
            else:
                for k, v in data.items():
                    click.echo(f"  {k}: {v}")
        elif isinstance(data, list):
            if data and isinstance(data[0], dict):
                # Print as table
                if not data:
                    return
                keys = list(data[0].keys())
                # Header
                header = "  ".join(f"{k:<15}" for k in keys)
                click.echo(header)
                click.echo("-" * len(header))
                for row in data:
                    line = "  ".join(f"{str(row.get(k, '')):<15}" for k in keys)
                    click.echo(line)
            else:
                for item in data:
                    click.echo(str(item))


# ── Main Group ───────────────────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.option("--json", "as_json", is_flag=True, default=False,
              help="Output in JSON format.")
@click.pass_context
def main(ctx, as_json):
    """CLI-Anything PM2 — Process management harness for PM2."""
    ctx.ensure_object(dict)
    ctx.obj["json"] = as_json

    if ctx.invoked_subcommand is None:
        # Launch REPL mode
        _run_repl()


# ── Process Group ────────────────────────────────────────────────────────

@main.group()
@click.pass_context
def process(ctx):
    """Process info commands: list, describe, metrics."""
    pass


@process.command("list")
@click.pass_context
def process_list(ctx):
    """List all PM2 processes."""
    as_json = ctx.obj["json"]
    data = processes.list_processes(as_json=as_json)
    _output(data, as_json)


@process.command("describe")
@click.argument("name")
@click.pass_context
def process_describe(ctx, name):
    """Show detailed info for a PM2 process."""
    as_json = ctx.obj["json"]
    data = processes.describe_process(name, as_json=as_json)
    if data is None:
        click.echo(f"Process '{name}' not found.", err=True)
        sys.exit(1)
    _output(data, as_json)


@process.command("metrics")
@click.pass_context
def process_metrics(ctx):
    """Show CPU/memory metrics for all processes."""
    as_json = ctx.obj["json"]
    data = processes.get_metrics(as_json=as_json)
    _output(data, as_json)


# ── Lifecycle Group ──────────────────────────────────────────────────────

@main.group()
@click.pass_context
def lifecycle(ctx):
    """Lifecycle commands: start, stop, restart, delete."""
    pass


@lifecycle.command("restart")
@click.argument("name")
@click.pass_context
def lifecycle_restart(ctx, name):
    """Restart a PM2 process."""
    as_json = ctx.obj["json"]
    data = lifecycle_mod.restart_process(name, as_json=as_json)
    _output(data, as_json)


@lifecycle.command("stop")
@click.argument("name")
@click.pass_context
def lifecycle_stop(ctx, name):
    """Stop a PM2 process."""
    as_json = ctx.obj["json"]
    data = lifecycle_mod.stop_process(name, as_json=as_json)
    _output(data, as_json)


@lifecycle.command("start")
@click.argument("script")
@click.option("--name", default=None, help="Process name.")
@click.pass_context
def lifecycle_start(ctx, script, name):
    """Start a new PM2 process."""
    as_json = ctx.obj["json"]
    data = lifecycle_mod.start_process(script, name=name, as_json=as_json)
    _output(data, as_json)


@lifecycle.command("delete")
@click.argument("name")
@click.pass_context
def lifecycle_delete(ctx, name):
    """Delete a PM2 process."""
    as_json = ctx.obj["json"]
    data = lifecycle_mod.delete_process(name, as_json=as_json)
    _output(data, as_json)


# Alias to avoid name collision with the click group
lifecycle_mod = lifecycle_module = None


def _init_lifecycle_mod():
    """Lazy-init the lifecycle module reference."""
    global lifecycle_mod
    if lifecycle_mod is None:
        from .core import lifecycle as _lc
        lifecycle_mod = _lc


# Patch lifecycle commands to use the module
_init_lifecycle_mod()


# ── Logs Group ───────────────────────────────────────────────────────────

@main.group("logs")
@click.pass_context
def logs_group(ctx):
    """Log commands: view, flush."""
    pass


@logs_group.command("view")
@click.argument("name")
@click.option("--lines", default=20, help="Number of log lines.")
@click.pass_context
def logs_view(ctx, name, lines):
    """View recent logs for a PM2 process."""
    as_json = ctx.obj["json"]
    data = logs.view_logs(name, lines=lines, as_json=as_json)
    _output(data, as_json)


@logs_group.command("flush")
@click.argument("name", required=False, default=None)
@click.pass_context
def logs_flush(ctx, name):
    """Flush logs for a process (or all if no name given)."""
    as_json = ctx.obj["json"]
    data = logs.flush_logs(name=name, as_json=as_json)
    _output(data, as_json)


# ── System Group ─────────────────────────────────────────────────────────

@main.group("system")
@click.pass_context
def system_group(ctx):
    """System commands: save, startup, version."""
    pass


@system_group.command("save")
@click.pass_context
def system_save(ctx):
    """Save current PM2 process list."""
    as_json = ctx.obj["json"]
    data = system.save(as_json=as_json)
    _output(data, as_json)


@system_group.command("startup")
@click.pass_context
def system_startup(ctx):
    """Generate PM2 startup script."""
    as_json = ctx.obj["json"]
    data = system.startup(as_json=as_json)
    _output(data, as_json)


@system_group.command("version")
@click.pass_context
def system_version(ctx):
    """Show PM2 version."""
    as_json = ctx.obj["json"]
    data = system.version(as_json=as_json)
    _output(data, as_json)


# ── REPL Mode ────────────────────────────────────────────────────────────

def _run_repl():
    """Launch the interactive REPL."""
    from .utils.repl_skin import ReplSkin

    skin = ReplSkin("pm2", version="1.0.0")
    skin.print_banner()

    session = skin.create_prompt_session()

    # REPL command mapping
    repl_commands = {
        "process list":    lambda args, j: _output(processes.list_processes(as_json=j), j),
        "process describe": lambda args, j: _output(
            processes.describe_process(args[0], as_json=j) if args else "Usage: process describe <name>", j
        ),
        "process metrics":  lambda args, j: _output(processes.get_metrics(as_json=j), j),
        "lifecycle restart": lambda args, j: _output(
            lifecycle_mod.restart_process(args[0], as_json=j) if args else "Usage: lifecycle restart <name>", j
        ),
        "lifecycle stop":    lambda args, j: _output(
            lifecycle_mod.stop_process(args[0], as_json=j) if args else "Usage: lifecycle stop <name>", j
        ),
        "lifecycle start":   lambda args, j: _repl_start(args, j),
        "lifecycle delete":  lambda args, j: _output(
            lifecycle_mod.delete_process(args[0], as_json=j) if args else "Usage: lifecycle delete <name>", j
        ),
        "logs view":         lambda args, j: _repl_logs_view(args, j),
        "logs flush":        lambda args, j: _output(logs.flush_logs(name=args[0] if args else None, as_json=j), j),
        "system save":       lambda args, j: _output(system.save(as_json=j), j),
        "system startup":    lambda args, j: _output(system.startup(as_json=j), j),
        "system version":    lambda args, j: _output(system.version(as_json=j), j),
    }

    help_commands = {
        "process list":       "List all PM2 processes",
        "process describe N": "Detailed info for process N",
        "process metrics":    "CPU/memory metrics for all processes",
        "lifecycle start S":  "Start script S [--name N]",
        "lifecycle stop N":   "Stop process N",
        "lifecycle restart N":"Restart process N",
        "lifecycle delete N": "Delete process N",
        "logs view N":        "View logs for process N [--lines 50]",
        "logs flush [N]":     "Flush logs (optionally for process N)",
        "system save":        "Save PM2 process list",
        "system startup":     "Generate startup script",
        "system version":     "Show PM2 version",
        "help":               "Show this help",
        "quit / exit":        "Exit the REPL",
    }

    while True:
        try:
            user_input = skin.get_input(session)
        except (EOFError, KeyboardInterrupt):
            skin.print_goodbye()
            break

        if not user_input:
            continue

        raw = user_input.strip()

        if raw in ("quit", "exit", "q"):
            skin.print_goodbye()
            break

        if raw == "help":
            skin.help(help_commands)
            continue

        # Check for --json flag in input
        as_json = False
        if "--json" in raw:
            as_json = True
            raw = raw.replace("--json", "").strip()

        # Match command
        matched = False
        for cmd_key, handler in repl_commands.items():
            if raw.startswith(cmd_key):
                remainder = raw[len(cmd_key):].strip()
                args = remainder.split() if remainder else []
                try:
                    handler(args, as_json)
                except Exception as e:
                    skin.error(str(e))
                matched = True
                break

        if not matched:
            skin.warning(f"Unknown command: {raw}")
            skin.hint("Type 'help' for available commands.")


def _repl_start(args, as_json):
    """Handle 'lifecycle start' in REPL with --name parsing."""
    if not args:
        click.echo("Usage: lifecycle start <script> [--name <name>]")
        return
    script = args[0]
    name = None
    if "--name" in args:
        idx = args.index("--name")
        if idx + 1 < len(args):
            name = args[idx + 1]
    _output(lifecycle_mod.start_process(script, name=name, as_json=as_json), as_json)


def _repl_logs_view(args, as_json):
    """Handle 'logs view' in REPL with --lines parsing."""
    if not args:
        click.echo("Usage: logs view <name> [--lines N]")
        return
    name = args[0]
    lines = 20
    if "--lines" in args:
        idx = args.index("--lines")
        if idx + 1 < len(args):
            try:
                lines = int(args[idx + 1])
            except ValueError:
                pass
    _output(logs.view_logs(name, lines=lines, as_json=as_json), as_json)


if __name__ == "__main__":
    main()
