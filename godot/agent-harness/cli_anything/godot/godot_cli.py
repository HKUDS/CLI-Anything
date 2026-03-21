#!/usr/bin/env python3
"""Godot CLI — A stateful command-line interface for game engine operations.

This CLI wraps Godot's powerful game development capabilities into a structured,
agent-friendly interface with JSON output, project state, and REPL mode.

Usage:
    # One-shot commands
    cli-anything-godot project info /path/to/game
    cli-anything-godot export run /path/to/game --preset Linux --output build/game
    cli-anything-godot scene info main.tscn

    # Interactive REPL
    cli-anything-godot
"""

import sys
import os
import json
import shlex
import click
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cli_anything.godot.core.session import Session
from cli_anything.godot.core import project as proj_mod
from cli_anything.godot.core import export as exp_mod

# Global session state
_session: Optional[Session] = None
_json_output = False
_repl_mode = False


def get_session() -> Session:
    global _session
    if _session is None:
        _session = Session()
    return _session


def output(data, message: str = ""):
    if _json_output:
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        if message:
            click.echo(message)
        if isinstance(data, dict):
            _print_dict(data)
        elif isinstance(data, list):
            _print_list(data)
        else:
            click.echo(str(data))


def _print_dict(d: dict, indent: int = 0):
    prefix = "  " * indent
    for k, v in d.items():
        if isinstance(v, dict):
            click.echo(f"{prefix}{k}:")
            _print_dict(v, indent + 1)
        elif isinstance(v, list):
            click.echo(f"{prefix}{k}:")
            _print_list(v, indent + 1)
        else:
            click.echo(f"{prefix}{k}: {v}")


def _print_list(items: list, indent: int = 0):
    prefix = "  " * indent
    for i, item in enumerate(items):
        if isinstance(item, dict):
            click.echo(f"{prefix}[{i}]")
            _print_dict(item, indent + 1)
        else:
            click.echo(f"{prefix}- {item}")


def handle_error(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except FileNotFoundError as e:
            if _json_output:
                click.echo(json.dumps({"error": str(e), "type": "file_not_found"}))
            else:
                click.echo(f"Error: {e}", err=True)
            if not _repl_mode:
                sys.exit(1)
        except (ValueError, IndexError, RuntimeError) as e:
            if _json_output:
                click.echo(json.dumps({"error": str(e), "type": type(e).__name__}))
            else:
                click.echo(f"Error: {e}", err=True)
            if not _repl_mode:
                sys.exit(1)

    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


# ── Main CLI Group ──────────────────────────────────────────────
@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, help="Output as JSON")
@click.pass_context
def cli(ctx, use_json):
    """Godot CLI — Stateful game engine operations from the command line.

    Run without a subcommand to enter interactive REPL mode.
    """
    global _json_output
    _json_output = use_json

    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


# ── Project Commands ──────────────────────────────────────────
@cli.group()
def project():
    """Project management commands."""
    pass


@project.command("info")
@click.argument("dir")
@handle_error
def project_info(dir):
    """Get project.godot info."""
    result = proj_mod.info(dir)
    output(result)


@project.command("run")
@click.argument("dir")
@click.option("--timeout", type=int, default=30, help="Run timeout")
@handle_error
def project_run(dir, timeout):
    """Run the project headless."""
    result = proj_mod.run(dir, timeout=timeout)
    output(result)


@project.command("validate")
@click.argument("dir")
@handle_error
def project_validate(dir):
    """Validate project (check for errors)."""
    result = proj_mod.validate(dir)
    output(result)


# ── Export Commands ──────────────────────────────────────────────
@cli.group()
def export():
    """Export operations."""
    pass


@export.command("presets")
@click.argument("dir")
@handle_error
def export_presets(dir):
    """List export presets."""
    result = exp_mod.presets_list(dir)
    output(result)


@export.command("run")
@click.argument("dir")
@click.option("--preset", required=True, help="Preset name or index")
@click.option("--output", "-o", required=True, help="Output path")
@click.option("--timeout", type=int, default=300, help="Export timeout")
@handle_error
def export_run(dir, preset, output, timeout):
    """Run export preset."""
    result = exp_mod.run_preset(dir, preset, output, timeout=timeout)
    output(result)


@export.command("all")
@click.argument("dir")
@click.option("--output-dir", "-o", required=True, help="Output directory")
@click.option("--timeout", type=int, default=600, help="Export timeout")
@handle_error
def export_all(dir, output_dir, timeout):
    """Export all presets."""
    result = exp_mod.export_all(dir, output_dir, timeout=timeout)
    output(result)


# ── Scene Commands ──────────────────────────────────────────────
@cli.group()
def scene():
    """Scene operations."""
    pass


@scene.command("list")
@click.argument("dir")
@handle_error
def scene_list(dir):
    """List all .tscn/.scn files."""
    result = proj_mod.scenes_list(dir)
    output(result)


@scene.command("info")
@click.argument("file")
@handle_error
def scene_info(file):
    """Get scene info (nodes, resources)."""
    result = proj_mod.scene_info(file)
    output(result)


# ── Script Commands ──────────────────────────────────────────────
@cli.group()
def script():
    """Script operations."""
    pass


@script.command("list")
@click.argument("dir")
@handle_error
def script_list(dir):
    """List all .gd scripts."""
    result = proj_mod.scripts_list(dir)
    output(result)


@script.command("check")
@click.argument("file")
@handle_error
def script_check(file):
    """Check GDScript for syntax errors."""
    result = proj_mod.script_check(file)
    output(result)


# ── Resource Commands ──────────────────────────────────────────────
@cli.group()
def resource():
    """Resource operations."""
    pass


@resource.command("list")
@click.argument("dir")
@handle_error
def resource_list(dir):
    """List resources (textures, sounds, meshes)."""
    result = proj_mod.resources_list(dir)
    output(result)


# ── Import Commands ──────────────────────────────────────────────
@cli.group()
def import_cmd():
    """Import operations."""
    pass


@import_cmd.command("reimport")
@click.argument("dir")
@click.option("--timeout", type=int, default=120, help="Import timeout")
@handle_error
def import_reimport(dir, timeout):
    """Re-import all resources."""
    result = proj_mod.import_reimport(dir, timeout=timeout)
    output(result)


# ── Debug Commands ──────────────────────────────────────────────
@cli.group()
def debug():
    """Debug operations."""
    pass


@debug.command("run")
@click.argument("dir")
@click.option("--port", type=int, default=6007, help="Debug port")
@click.option("--timeout", type=int, default=30, help="Run timeout")
@handle_error
def debug_run(dir, port, timeout):
    """Run with remote debug."""
    result = exp_mod.debug_run(dir, port=port, timeout=timeout)
    output(result)


# ── Build Commands ──────────────────────────────────────────────
@cli.command("build")
@click.argument("dir")
@click.option("--export-preset", "-p", required=True, help="Export preset name")
@click.option("--output", "-o", required=True, help="Output file path")
@click.option("--timeout", type=int, default=300, help="Build timeout")
@handle_error
def build_cmd(dir, export_preset, output, timeout):
    """Build/export the project."""
    result = exp_mod.build(dir, export_preset, output, timeout=timeout)
    output(result)


# ── Session Commands ──────────────────────────────────────────────
@cli.group()
def session():
    """Session management commands."""
    pass


@session.command("status")
@handle_error
def session_status():
    """Show session status."""
    sess = get_session()
    output(sess.status())


@session.command("undo")
@handle_error
def session_undo():
    """Undo the last operation."""
    sess = get_session()
    desc = sess.undo()
    output({"undone": desc}, f"Undone: {desc}")


@session.command("redo")
@handle_error
def session_redo():
    """Redo the last undone operation."""
    sess = get_session()
    desc = sess.redo()
    output({"redone": desc}, f"Redone: {desc}")


@session.command("history")
@handle_error
def session_history():
    """Show undo history."""
    sess = get_session()
    history = sess.list_history()
    output(history, "Undo history:")


# ── REPL ─────────────────────────────────────────────────────────
@cli.command()
@handle_error
def repl():
    """Start interactive REPL session."""
    from cli_anything.godot.utils.repl_skin import ReplSkin

    global _repl_mode
    _repl_mode = True

    skin = ReplSkin("godot", version="1.0.0")
    skin.print_banner()

    pt_session = skin.create_prompt_session()

    _repl_commands = {
        "project": "info|run|validate",
        "export": "presets|run|all",
        "scene": "list|info",
        "script": "list|check",
        "resource": "list",
        "import": "reimport",
        "debug": "run",
        "build": "Build/export project",
        "session": "status|undo|redo|history",
        "help": "Show this help",
        "quit": "Exit REPL",
    }

    while True:
        try:
            line = skin.get_input(pt_session)
            if not line:
                continue
            if line.lower() in ("quit", "exit", "q"):
                skin.print_goodbye()
                break
            if line.lower() == "help":
                skin.help(_repl_commands)
                continue

            try:
                args = shlex.split(line)
            except ValueError:
                args = line.split()
            try:
                cli.main(args, standalone_mode=False)
            except SystemExit:
                pass
            except click.exceptions.UsageError as e:
                skin.warning(f"Usage error: {e}")
            except Exception as e:
                skin.error(f"{e}")

        except (EOFError, KeyboardInterrupt):
            skin.print_goodbye()
            break

    _repl_mode = False


# ── Entry Point ──────────────────────────────────────────────────
def main():
    cli()


if __name__ == "__main__":
    main()
