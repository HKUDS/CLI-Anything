"""cli-anything-godot — Agent-native CLI for the Godot game engine.

Commands:
    project create/info/scenes/scripts/resources/reimport
    scene   create/read/add-node
    export  build/presets
    script  run/inline/validate
    engine  version/status
    session start (REPL mode)
"""

import json as json_mod
import os
import shlex
import sys

import click

from cli_anything.godot.utils.godot_backend import (
    get_version,
    is_available,
    find_godot_binary,
)


# ── Output helpers ─────────────────────────────────────────────────────

def _out(ctx, data: dict) -> None:
    """Print result as JSON or human-readable based on context."""
    if ctx.obj.get("json"):
        click.echo(json_mod.dumps(data, indent=2, ensure_ascii=False))
    else:
        status = data.get("status", "")
        if status == "error":
            click.secho(f"Error: {data.get('message', data.get('stderr', 'unknown'))}", fg="red")
            return
        for key, value in data.items():
            if key == "status":
                continue
            if isinstance(value, list):
                click.secho(f"{key} ({len(value)}):", fg="cyan", bold=True)
                for item in value:
                    if isinstance(item, dict):
                        parts = [f"{k}={v}" for k, v in item.items()]
                        click.echo(f"  - {', '.join(parts)}")
                    else:
                        click.echo(f"  - {item}")
            elif isinstance(value, dict):
                click.secho(f"{key}:", fg="cyan", bold=True)
                for k, v in value.items():
                    click.echo(f"  {k}: {v}")
            else:
                click.echo(f"{key}: {value}")


def _handle_error(func):
    """Decorator to catch RuntimeError and format output."""
    import functools

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except RuntimeError as e:
            ctx = click.get_current_context()
            _out(ctx, {"status": "error", "message": str(e)})
            if not ctx.obj.get("repl"):
                sys.exit(1)
    return wrapper


# ── Root CLI group ─────────────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, help="Output JSON for agent consumption.")
@click.option("--project", "-p", "project", default=None, help="Path to Godot project directory.")
@click.pass_context
def cli(ctx, use_json, project):
    """cli-anything-godot — Agent-native CLI for the Godot game engine."""
    ctx.ensure_object(dict)
    ctx.obj["json"] = use_json
    ctx.obj["project"] = os.path.abspath(project) if project else None
    ctx.obj["repl"] = ctx.obj.get("repl", False)
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


def _get_project(ctx) -> str:
    """Resolve project path from context or cwd."""
    p = ctx.obj.get("project") or os.getcwd()
    return os.path.abspath(p)


# ── Project commands ───────────────────────────────────────────────────

@cli.group()
@click.pass_context
def project(ctx):
    """Manage Godot projects — create, inspect, list assets."""
    pass


@project.command("create")
@click.argument("path")
@click.option("--name", default=None, help="Project display name.")
@click.pass_context
@_handle_error
def project_create(ctx, path, name):
    """Create a new Godot project at PATH."""
    from cli_anything.godot.core.project import create_project
    _out(ctx, create_project(os.path.abspath(path), name))


@project.command("info")
@click.pass_context
@_handle_error
def project_info(ctx):
    """Show project metadata from project.godot."""
    from cli_anything.godot.core.project import get_project_info
    _out(ctx, get_project_info(_get_project(ctx)))


@project.command("scenes")
@click.pass_context
@_handle_error
def project_scenes(ctx):
    """List all scene files (.tscn, .scn) in the project."""
    from cli_anything.godot.core.project import list_scenes
    _out(ctx, list_scenes(_get_project(ctx)))


@project.command("scripts")
@click.pass_context
@_handle_error
def project_scripts(ctx):
    """List all GDScript files (.gd) in the project."""
    from cli_anything.godot.core.project import list_scripts
    _out(ctx, list_scripts(_get_project(ctx)))


@project.command("resources")
@click.pass_context
@_handle_error
def project_resources(ctx):
    """List all resource files (.tres, .res) in the project."""
    from cli_anything.godot.core.project import list_resources
    _out(ctx, list_resources(_get_project(ctx)))


@project.command("reimport")
@click.pass_context
@_handle_error
def project_reimport(ctx):
    """Force re-import of all project resources via Godot."""
    from cli_anything.godot.core.project import reimport_project
    _out(ctx, reimport_project(_get_project(ctx)))


# ── Scene commands ─────────────────────────────────────────────────────

@cli.group()
@click.pass_context
def scene(ctx):
    """Create and inspect Godot scenes."""
    pass


@scene.command("create")
@click.argument("scene_path")
@click.option("--root-type", default="Node2D", help="Root node type (Node2D, Node3D, Control...).")
@click.option("--root-name", default=None, help="Root node name.")
@click.pass_context
@_handle_error
def scene_create(ctx, scene_path, root_type, root_name):
    """Create a new .tscn scene file at SCENE_PATH (relative to project)."""
    from cli_anything.godot.core.scene import create_scene
    _out(ctx, create_scene(_get_project(ctx), scene_path, root_type, root_name))


@scene.command("read")
@click.argument("scene_path")
@click.pass_context
@_handle_error
def scene_read(ctx, scene_path):
    """Parse and display the node tree of a .tscn scene."""
    from cli_anything.godot.core.scene import read_scene
    _out(ctx, read_scene(_get_project(ctx), scene_path))


@scene.command("add-node")
@click.argument("scene_path")
@click.option("--name", "node_name", required=True, help="Name of the new node.")
@click.option("--type", "node_type", required=True, help="Node type (Sprite2D, Camera2D, etc.).")
@click.option("--parent", default=".", help="Parent node path (default: root).")
@click.pass_context
@_handle_error
def scene_add_node(ctx, scene_path, node_name, node_type, parent):
    """Add a child node to an existing scene."""
    from cli_anything.godot.core.scene import add_node
    _out(ctx, add_node(_get_project(ctx), scene_path, node_name, node_type, parent))


# ── Export commands ────────────────────────────────────────────────────

@cli.group("export")
@click.pass_context
def export_group(ctx):
    """Export Godot projects to target platforms."""
    pass


@export_group.command("build")
@click.option("--preset", default=None, help="Export preset name. Omit to export all (Godot 4.3+).")
@click.option("--output", default=None, help="Output file path.")
@click.option("--debug", is_flag=True, help="Use debug export instead of release.")
@click.pass_context
@_handle_error
def export_build(ctx, preset, output, debug):
    """Build/export the project using configured presets."""
    from cli_anything.godot.core.export import export_project
    _out(ctx, export_project(_get_project(ctx), preset, output, debug))


@export_group.command("presets")
@click.pass_context
@_handle_error
def export_presets(ctx):
    """List configured export presets."""
    from cli_anything.godot.core.export import list_export_presets
    _out(ctx, list_export_presets(_get_project(ctx)))


# ── Script commands ────────────────────────────────────────────────────

@cli.group()
@click.pass_context
def script(ctx):
    """Run and validate GDScript files."""
    pass


@script.command("run")
@click.argument("script_path")
@click.option("--timeout", default=60, help="Execution timeout in seconds.")
@click.pass_context
@_handle_error
def script_run(ctx, script_path, timeout):
    """Execute a GDScript file in headless mode. Must extend SceneTree."""
    from cli_anything.godot.core.script import run_script
    _out(ctx, run_script(_get_project(ctx), script_path, timeout))


@script.command("inline")
@click.argument("code")
@click.option("--timeout", default=60, help="Execution timeout in seconds.")
@click.pass_context
@_handle_error
def script_inline(ctx, code, timeout):
    """Run inline GDScript code (wrapped in SceneTree._init).

    Security: The provided code is written to a temp file and executed via
    Godot subprocess. Only use with trusted input.
    """
    from cli_anything.godot.core.script import run_inline
    _out(ctx, run_inline(_get_project(ctx), code, timeout))


@script.command("validate")
@click.argument("script_path")
@click.pass_context
@_handle_error
def script_validate(ctx, script_path):
    """Validate GDScript syntax without executing."""
    from cli_anything.godot.core.script import validate_script
    _out(ctx, validate_script(_get_project(ctx), script_path))


# ── Engine commands ────────────────────────────────────────────────────

@cli.group()
@click.pass_context
def engine(ctx):
    """Godot engine info — version, status."""
    pass


@engine.command("version")
@click.pass_context
@_handle_error
def engine_version(ctx):
    """Show Godot engine version."""
    _out(ctx, get_version())


@engine.command("status")
@click.pass_context
@_handle_error
def engine_status(ctx):
    """Check if Godot binary is available."""
    available = is_available()
    binary = find_godot_binary()
    _out(ctx, {
        "status": "ok",
        "available": available,
        "binary": binary or "not found",
    })


# ── REPL session ───────────────────────────────────────────────────────

@cli.command()
@click.pass_context
def session(ctx):
    """Start an interactive REPL session."""
    ctx.obj["repl"] = True

    try:
        from cli_anything.godot.utils.repl_skin import ReplSkin
        skin = ReplSkin("godot", version="1.0.0")
        skin.print_banner()
    except ImportError:
        skin = None
        click.secho("cli-anything-godot REPL", fg="green", bold=True)
        click.echo("Type 'help' for commands, 'exit' to quit.\n")

    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import InMemoryHistory

    prompt_session = PromptSession(history=InMemoryHistory())
    project_path = ctx.obj.get("project")
    project_name = os.path.basename(project_path) if project_path else "no-project"

    while True:
        try:
            if skin:
                prompt_text = skin.prompt(project_name=project_name, modified=False)
            else:
                prompt_text = f"godot ({project_name})> "

            line = prompt_session.prompt(prompt_text)
            line = line.strip()
            if not line:
                continue
            if line in ("exit", "quit", "q"):
                break
            if line == "help":
                click.echo(cli.get_help(click.Context(cli)))
                continue

            try:
                args = shlex.split(line)
            except ValueError as e:
                click.secho(f"Parse error: {e}", fg="red")
                continue

            try:
                cli.main(args=args, standalone_mode=False, obj=ctx.obj)
            except SystemExit:
                pass
            except click.exceptions.UsageError as e:
                click.secho(str(e), fg="red")

        except KeyboardInterrupt:
            continue
        except EOFError:
            break

    if skin:
        skin.print_goodbye()
    else:
        click.echo("Goodbye.")


# ── Entry point ────────────────────────────────────────────────────────

def main():
    cli()


if __name__ == "__main__":
    main()
