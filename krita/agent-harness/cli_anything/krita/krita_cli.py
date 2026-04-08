"""cli-anything-krita: CLI harness for Krita digital painting application.

Provides both one-shot subcommands and an interactive REPL for managing
Krita projects, layers, filters, and exports from the command line.
"""

import json
import os
import sys
import functools

import click

from cli_anything.krita.core.project import (
    create_project,
    open_project,
    save_project,
    project_info,
    add_layer,
    remove_layer,
    list_layers,
    set_layer_property,
    add_filter,
    set_canvas,
)
from cli_anything.krita.core.session import Session
from cli_anything.krita.core.export import (
    export_image,
    export_animation,
    list_presets,
    get_supported_formats,
    EXPORT_PRESETS,
)
from cli_anything.krita.utils.krita_backend import find_krita, get_version


# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------
_session = Session()
_current_project = None
_current_project_path = None


def _output(data: dict, ctx: click.Context) -> None:
    """Print output as JSON or human-readable based on --json flag."""
    if ctx.obj.get("json"):
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        for key, val in data.items():
            click.echo(f"  {key}: {val}")


def handle_error(func):
    """Decorator for consistent error handling across commands."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except FileNotFoundError as exc:
            ctx = click.get_current_context()
            if ctx.obj.get("json"):
                click.echo(json.dumps({"error": str(exc), "type": "FileNotFoundError"}))
            else:
                click.echo(f"Error: {exc}", err=True)
            ctx.exit(1)
        except FileExistsError as exc:
            ctx = click.get_current_context()
            if ctx.obj.get("json"):
                click.echo(json.dumps({"error": str(exc), "type": "FileExistsError"}))
            else:
                click.echo(f"Error: {exc}", err=True)
            ctx.exit(1)
        except RuntimeError as exc:
            ctx = click.get_current_context()
            if ctx.obj.get("json"):
                click.echo(json.dumps({"error": str(exc), "type": "RuntimeError"}))
            else:
                click.echo(f"Error: {exc}", err=True)
            ctx.exit(1)
        except Exception as exc:
            ctx = click.get_current_context()
            if ctx.obj.get("json"):
                click.echo(json.dumps({"error": str(exc), "type": type(exc).__name__}))
            else:
                click.echo(f"Error: {exc}", err=True)
            ctx.exit(1)
    return wrapper


def _load_project(ctx: click.Context) -> dict:
    """Load the current project, from --project flag or global state."""
    global _current_project, _current_project_path
    project_path = ctx.obj.get("project")
    if project_path:
        _current_project = open_project(project_path)
        _current_project_path = project_path
    if _current_project is None:
        raise RuntimeError("No project loaded. Use 'project new' or 'project open' first, or pass --project.")
    return _current_project


def _save_current(ctx: click.Context) -> None:
    """Save the current project if a path is known."""
    global _current_project, _current_project_path
    if _current_project and _current_project_path:
        save_project(_current_project, _current_project_path)


# ---------------------------------------------------------------------------
# CLI root
# ---------------------------------------------------------------------------
@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, default=False, help="Output in JSON format.")
@click.option("--project", "-p", type=click.Path(), default=None, help="Path to project JSON file.")
@click.pass_context
def cli(ctx, use_json, project):
    """cli-anything-krita: CLI harness for Krita digital painting."""
    ctx.ensure_object(dict)
    ctx.obj["json"] = use_json
    ctx.obj["project"] = project
    if ctx.invoked_subcommand is None:
        ctx.invoke(repl, project_path=project)


# ---------------------------------------------------------------------------
# Project commands
# ---------------------------------------------------------------------------
@cli.group()
@click.pass_context
def project(ctx):
    """Manage Krita projects."""
    pass


@project.command("new")
@click.option("-n", "--name", default="Untitled", help="Project name.")
@click.option("-w", "--width", default=1920, type=int, help="Canvas width in pixels.")
@click.option("-h", "--height", default=1080, type=int, help="Canvas height in pixels.")
@click.option("--colorspace", default="RGBA", help="Color space (RGBA, CMYKA, GRAYA, LABA, XYZA).")
@click.option("--depth", default="U8", help="Bit depth (U8, U16, F16, F32).")
@click.option("--resolution", default=300, type=int, help="DPI resolution.")
@click.option("-o", "--output", type=click.Path(), default=None, help="Save project JSON to file.")
@click.pass_context
@handle_error
def project_new(ctx, name, width, height, colorspace, depth, resolution, output):
    """Create a new Krita project."""
    global _current_project, _current_project_path
    proj = create_project(
        name=name, width=width, height=height,
        colorspace=colorspace, depth=depth, resolution=resolution,
    )
    _current_project = proj
    if output:
        save_project(proj, output)
        _current_project_path = output
    _session.snapshot(proj, f"Created project '{name}'")
    _output({"status": "created", "name": name, "width": width, "height": height,
             "colorspace": colorspace, "depth": depth, "resolution": resolution,
             "saved_to": output or "(in memory)"}, ctx)


@project.command("open")
@click.argument("path", type=click.Path(exists=True))
@click.pass_context
@handle_error
def project_open(ctx, path):
    """Open an existing project JSON file."""
    global _current_project, _current_project_path
    proj = open_project(path)
    _current_project = proj
    _current_project_path = path
    _session.snapshot(proj, f"Opened project from '{path}'")
    info = project_info(proj)
    _output({"status": "opened", **info}, ctx)


@project.command("save")
@click.option("-o", "--output", type=click.Path(), default=None, help="Save to a new path.")
@click.pass_context
@handle_error
def project_save(ctx, output):
    """Save the current project."""
    global _current_project_path
    proj = _load_project(ctx)
    path = output or _current_project_path
    if not path:
        raise RuntimeError("No output path specified. Use -o or open an existing project.")
    save_project(proj, path)
    _current_project_path = path
    _output({"status": "saved", "path": path}, ctx)


@project.command("info")
@click.pass_context
@handle_error
def project_info_cmd(ctx):
    """Show project information."""
    proj = _load_project(ctx)
    info = project_info(proj)
    _output(info, ctx)


# ---------------------------------------------------------------------------
# Layer commands
# ---------------------------------------------------------------------------
@cli.group()
@click.pass_context
def layer(ctx):
    """Manage layers in the current project."""
    pass


@layer.command("add")
@click.argument("name")
@click.option("-t", "--type", "layer_type", default="paintlayer",
              type=click.Choice(["paintlayer", "grouplayer", "vectorlayer",
                                 "filterlayer", "filllayer", "clonelayer", "filelayer"]),
              help="Layer type.")
@click.option("--opacity", default=255, type=int, help="Layer opacity (0-255).")
@click.option("--blending", default="normal", help="Blending mode.")
@click.option("--hidden", is_flag=True, default=False, help="Create layer hidden.")
@click.pass_context
@handle_error
def layer_add(ctx, name, layer_type, opacity, blending, hidden):
    """Add a new layer to the project."""
    proj = _load_project(ctx)
    add_layer(proj, name, layer_type=layer_type, opacity=opacity,
              visible=not hidden, blending_mode=blending)
    _session.snapshot(proj, f"Added layer '{name}'")
    _save_current(ctx)
    _output({"status": "added", "layer": name, "type": layer_type, "opacity": opacity}, ctx)


@layer.command("remove")
@click.argument("name")
@click.pass_context
@handle_error
def layer_remove(ctx, name):
    """Remove a layer by name."""
    proj = _load_project(ctx)
    remove_layer(proj, name)
    _session.snapshot(proj, f"Removed layer '{name}'")
    _save_current(ctx)
    _output({"status": "removed", "layer": name}, ctx)


@layer.command("list")
@click.pass_context
@handle_error
def layer_list(ctx):
    """List all layers in the project."""
    proj = _load_project(ctx)
    layers = list_layers(proj)
    if ctx.obj.get("json"):
        click.echo(json.dumps(layers, indent=2))
    else:
        for i, lyr in enumerate(layers):
            vis = "visible" if lyr.get("visible", True) else "hidden"
            click.echo(f"  [{i}] {lyr['name']} ({lyr['type']}) opacity={lyr['opacity']} {vis}")


@layer.command("set")
@click.argument("layer_name")
@click.argument("property_name")
@click.argument("value")
@click.pass_context
@handle_error
def layer_set(ctx, layer_name, property_name, value):
    """Set a property on a layer (opacity, visible, blending_mode, locked)."""
    proj = _load_project(ctx)
    # Try to parse value as int or bool
    if value.lower() in ("true", "yes"):
        value = True
    elif value.lower() in ("false", "no"):
        value = False
    else:
        try:
            value = int(value)
        except ValueError:
            pass
    set_layer_property(proj, layer_name, property_name, value)
    _session.snapshot(proj, f"Set {property_name}={value} on layer '{layer_name}'")
    _save_current(ctx)
    _output({"status": "updated", "layer": layer_name, "property": property_name, "value": value}, ctx)


# ---------------------------------------------------------------------------
# Filter commands
# ---------------------------------------------------------------------------
@cli.group()
@click.pass_context
def filter(ctx):
    """Apply filters and effects."""
    pass


@filter.command("apply")
@click.argument("filter_name")
@click.option("-l", "--layer", "layer_name", default=None, help="Target layer name (default: top layer).")
@click.option("-c", "--config", "config_json", default=None, help="Filter config as JSON string.")
@click.pass_context
@handle_error
def filter_apply(ctx, filter_name, layer_name, config_json):
    """Apply a filter to a layer."""
    proj = _load_project(ctx)
    config = json.loads(config_json) if config_json else None
    if layer_name is None and proj.get("layers"):
        layer_name = proj["layers"][-1]["name"]
    add_filter(proj, layer_name, filter_name, config)
    _session.snapshot(proj, f"Applied filter '{filter_name}' to '{layer_name}'")
    _save_current(ctx)
    _output({"status": "applied", "filter": filter_name, "layer": layer_name}, ctx)


@filter.command("list")
@click.pass_context
@handle_error
def filter_list(ctx):
    """List available filters."""
    filters = [
        "blur", "gaussian-blur", "motion-blur", "lens-blur",
        "sharpen", "unsharp-mask",
        "brightness-contrast", "levels", "curves", "hue-saturation",
        "color-balance", "desaturate", "invert", "posterize", "threshold",
        "auto-contrast", "normalize",
        "emboss", "edge-detection", "oil-paint", "pixelize",
        "noise-reduction", "halftone",
    ]
    if ctx.obj.get("json"):
        click.echo(json.dumps({"filters": filters}))
    else:
        click.echo("Available filters:")
        for f in filters:
            click.echo(f"  - {f}")


# ---------------------------------------------------------------------------
# Canvas commands
# ---------------------------------------------------------------------------
@cli.group()
@click.pass_context
def canvas(ctx):
    """Canvas and image operations."""
    pass


@canvas.command("resize")
@click.option("-w", "--width", type=int, default=None, help="New width.")
@click.option("-h", "--height", type=int, default=None, help="New height.")
@click.option("--resolution", type=int, default=None, help="New DPI resolution.")
@click.pass_context
@handle_error
def canvas_resize(ctx, width, height, resolution):
    """Resize the canvas."""
    proj = _load_project(ctx)
    set_canvas(proj, width=width, height=height, resolution=resolution)
    _session.snapshot(proj, f"Resized canvas to {width or '?'}x{height or '?'}")
    _save_current(ctx)
    info = proj["canvas"]
    _output({"status": "resized", "width": info["width"], "height": info["height"],
             "resolution": info["resolution"]}, ctx)


@canvas.command("info")
@click.pass_context
@handle_error
def canvas_info(ctx):
    """Show canvas information."""
    proj = _load_project(ctx)
    _output(proj["canvas"], ctx)


# ---------------------------------------------------------------------------
# Export commands
# ---------------------------------------------------------------------------
@cli.group("export")
@click.pass_context
def export_group(ctx):
    """Export and render operations."""
    pass


@export_group.command("render")
@click.argument("output_path", type=click.Path())
@click.option("-p", "--preset", default="png", type=click.Choice(list(EXPORT_PRESETS.keys())),
              help="Export preset.")
@click.option("--overwrite", is_flag=True, default=False, help="Overwrite existing file.")
@click.pass_context
@handle_error
def export_render(ctx, output_path, preset, overwrite):
    """Export/render the project to a file."""
    proj = _load_project(ctx)
    result = export_image(proj, output_path, preset=preset, overwrite=overwrite)
    _output(result, ctx)


@export_group.command("animation")
@click.argument("output_dir", type=click.Path())
@click.option("-p", "--preset", default="png", help="Frame format preset.")
@click.option("--basename", default="frame", help="Base filename for frames.")
@click.pass_context
@handle_error
def export_anim(ctx, output_dir, preset, basename):
    """Export animation frames."""
    proj = _load_project(ctx)
    result = export_animation(proj, output_dir, preset=preset, basename=basename)
    _output(result, ctx)


@export_group.command("presets")
@click.pass_context
@handle_error
def export_presets(ctx):
    """List available export presets."""
    presets = list_presets()
    if ctx.obj.get("json"):
        click.echo(json.dumps(presets, indent=2))
    else:
        click.echo("Export presets:")
        for p in presets:
            click.echo(f"  {p['name']}: {p['description']}")


@export_group.command("formats")
@click.pass_context
@handle_error
def export_formats(ctx):
    """List supported export formats."""
    formats = get_supported_formats()
    if ctx.obj.get("json"):
        click.echo(json.dumps({"formats": formats}))
    else:
        click.echo("Supported formats:")
        for fmt in formats:
            click.echo(f"  - {fmt}")


# ---------------------------------------------------------------------------
# Session commands
# ---------------------------------------------------------------------------
@cli.group()
@click.pass_context
def session(ctx):
    """Session state and undo/redo."""
    pass


@session.command("undo")
@click.pass_context
@handle_error
def session_undo(ctx):
    """Undo the last operation."""
    global _current_project
    state = _session.undo()
    if state is None:
        _output({"status": "nothing_to_undo"}, ctx)
        return
    _current_project = state
    _save_current(ctx)
    _output({"status": "undone", "history_position": _session.current_index()}, ctx)


@session.command("redo")
@click.pass_context
@handle_error
def session_redo(ctx):
    """Redo the last undone operation."""
    global _current_project
    state = _session.redo()
    if state is None:
        _output({"status": "nothing_to_redo"}, ctx)
        return
    _current_project = state
    _save_current(ctx)
    _output({"status": "redone", "history_position": _session.current_index()}, ctx)


@session.command("history")
@click.pass_context
@handle_error
def session_history(ctx):
    """Show session history."""
    hist = _session.history()
    if ctx.obj.get("json"):
        click.echo(json.dumps(hist, indent=2, default=str))
    else:
        for i, entry in enumerate(hist):
            marker = ">>>" if i == _session.current_index() else "   "
            click.echo(f"  {marker} [{i}] {entry.get('label', '')} ({entry.get('timestamp', '')})")


# ---------------------------------------------------------------------------
# Status command
# ---------------------------------------------------------------------------
@cli.command("status")
@click.pass_context
@handle_error
def status(ctx):
    """Show current status (project, session, Krita version)."""
    global _current_project, _current_project_path
    data = {
        "project_loaded": _current_project is not None,
        "project_path": _current_project_path,
        "history_size": len(_session.history()),
        "can_undo": _session.can_undo(),
        "can_redo": _session.can_redo(),
    }
    if _current_project:
        data["project_name"] = _current_project.get("name", "Unknown")
        c = _current_project.get("canvas", {})
        data["canvas"] = f"{c.get('width', '?')}x{c.get('height', '?')} {c.get('colorspace', '?')} {c.get('depth', '?')}"
        data["layer_count"] = len(_current_project.get("layers", []))
    try:
        data["krita_version"] = get_version()
        data["krita_installed"] = True
    except RuntimeError:
        data["krita_installed"] = False
    _output(data, ctx)


# ---------------------------------------------------------------------------
# REPL
# ---------------------------------------------------------------------------
@cli.command("repl", hidden=True)
@click.option("--project-path", type=click.Path(), default=None)
@click.pass_context
def repl(ctx, project_path):
    """Interactive REPL mode."""
    global _current_project, _current_project_path

    try:
        from cli_anything.krita.utils.repl_skin import ReplSkin
    except ImportError:
        click.echo("REPL requires prompt-toolkit. Install with: pip install prompt-toolkit")
        return

    skin = ReplSkin("krita", version="1.0.0")
    skin.print_banner()

    if project_path:
        try:
            _current_project = open_project(project_path)
            _current_project_path = project_path
            _session.snapshot(_current_project, f"Opened '{project_path}'")
            skin.success(f"Loaded project: {project_path}")
        except Exception as exc:
            skin.error(f"Failed to load project: {exc}")

    try:
        pt_session = skin.create_prompt_session()
    except Exception:
        pt_session = None

    commands_dict = {
        "project new": "Create a new project",
        "project open <path>": "Open a project file",
        "project save [-o path]": "Save current project",
        "project info": "Show project info",
        "layer add <name> [-t type]": "Add a layer",
        "layer remove <name>": "Remove a layer",
        "layer list": "List all layers",
        "layer set <name> <prop> <val>": "Set layer property",
        "filter apply <name> [-l layer]": "Apply a filter",
        "filter list": "List available filters",
        "canvas resize [-w W] [-h H]": "Resize canvas",
        "canvas info": "Show canvas info",
        "export render <path> [-p preset]": "Export to file",
        "export presets": "List export presets",
        "export formats": "List export formats",
        "session undo": "Undo last operation",
        "session redo": "Redo last operation",
        "session history": "Show history",
        "status": "Show current status",
        "help": "Show this help",
        "quit / exit": "Exit REPL",
    }

    while True:
        try:
            proj_name = _current_project.get("name", "") if _current_project else ""
            modified = _session.can_undo()
            line = skin.get_input(pt_session, project_name=proj_name, modified=modified)
        except (EOFError, KeyboardInterrupt):
            break

        if line is None:
            break

        line = line.strip()
        if not line:
            continue
        if line.lower() in ("quit", "exit", "q"):
            break
        if line.lower() == "help":
            skin.help(commands_dict)
            continue

        # Parse and dispatch to Click commands
        args = line.split()
        try:
            cli.main(args=args, standalone_mode=False, **{"parent": ctx, "obj": ctx.obj})
        except SystemExit:
            pass
        except click.exceptions.UsageError as exc:
            skin.error(str(exc))
        except Exception as exc:
            skin.error(str(exc))

    skin.print_goodbye()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    cli(obj={})


if __name__ == "__main__":
    main()
