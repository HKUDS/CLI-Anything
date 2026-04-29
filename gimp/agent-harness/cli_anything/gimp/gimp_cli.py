#!/usr/bin/env python3
"""GIMP CLI — A stateful command-line interface for image editing.

This CLI provides full image editing capabilities using Pillow as the
backend engine, with a project format that tracks layers, filters,
and history.

Usage:
    # One-shot commands
    python3 -m cli.gimp_cli project new --width 1920 --height 1080
    python3 -m cli.gimp_cli layer add-from-file photo.jpg --name "Background"
    python3 -m cli.gimp_cli filter add brightness --layer 0 --param factor=1.3

    # Interactive REPL
    python3 -m cli.gimp_cli repl
"""

import sys
import os
import json
import shlex
import click
from typing import Optional

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cli_anything.gimp.core.session import Session
from cli_anything.gimp.core import project as proj_mod
from cli_anything.gimp.core import layers as layer_mod
from cli_anything.gimp.core import filters as filt_mod
from cli_anything.gimp.core import canvas as canvas_mod
from cli_anything.gimp.core import media as media_mod
from cli_anything.gimp.core import export as export_mod

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
        except FileExistsError as e:
            if _json_output:
                click.echo(json.dumps({"error": str(e), "type": "file_exists"}))
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
@click.option("--project", "project_path", type=str, default=None,
              help="Path to .gimp-cli.json project file")
@click.option("--dry-run", "dry_run", is_flag=True, default=False,
              help="Run command without saving changes to disk")
@click.pass_context
def cli(ctx, use_json, project_path, dry_run):
    """GIMP CLI — Stateful image editing from the command line.

    Run without a subcommand to enter interactive REPL mode.
    """
    global _json_output
    _json_output = use_json

    if project_path:
        sess = get_session()
        if not sess.has_project():
            proj = proj_mod.open_project(project_path)
            sess.set_project(proj, project_path)

    if ctx.invoked_subcommand is None:
        ctx.invoke(repl, project_path=None)


@cli.result_callback()
def auto_save_on_exit(result, use_json, project_path, dry_run, **kwargs):
    """Auto-save project after one-shot commands if state was modified."""
    if _repl_mode:
        return
    if dry_run:
        return
    sess = get_session()
    if sess.has_project() and sess._modified and sess.project_path:
        try:
            sess.save_session()
        except Exception as e:
            click.echo(f"Warning: Auto-save failed: {e}", err=True)


# ── Project Commands ─────────────────────────────────────────────
@cli.group()
def project():
    """Project management commands."""
    pass


@project.command("new")
@click.option("--width", "-w", type=int, default=1920, help="Canvas width")
@click.option("--height", "-h", type=int, default=1080, help="Canvas height")
@click.option("--mode", type=click.Choice(["RGB", "RGBA", "L", "LA"]), default="RGB")
@click.option("--background", "-bg", default="#ffffff", help="Background color")
@click.option("--dpi", type=int, default=72, help="Resolution in DPI")
@click.option("--name", "-n", default="untitled", help="Project name")
@click.option("--profile", "-p", type=str, default=None, help="Canvas profile")
@click.option("--output", "-o", type=str, default=None, help="Save path")
@handle_error
def project_new(width, height, mode, background, dpi, name, profile, output):
    """Create a new project."""
    proj = proj_mod.create_project(
        width=width, height=height, color_mode=mode,
        background=background, dpi=dpi, name=name, profile=profile,
    )
    sess = get_session()
    sess.set_project(proj, output)
    if output:
        proj_mod.save_project(proj, output)
    output_data = proj_mod.get_project_info(proj)
    globals()["output"](output_data, f"Created project: {name}")


@project.command("open")
@click.argument("path")
@handle_error
def project_open(path):
    """Open an existing project."""
    proj = proj_mod.open_project(path)
    sess = get_session()
    sess.set_project(proj, path)
    info = proj_mod.get_project_info(proj)
    output(info, f"Opened: {path}")


@project.command("save")
@click.argument("path", required=False)
@handle_error
def project_save(path):
    """Save the current project."""
    sess = get_session()
    saved = sess.save_session(path)
    output({"saved": saved}, f"Saved to: {saved}")


@project.command("info")
@handle_error
def project_info():
    """Show project information."""
    sess = get_session()
    info = proj_mod.get_project_info(sess.get_project())
    output(info)


@project.command("profiles")
@handle_error
def project_profiles():
    """List available canvas profiles."""
    profiles = proj_mod.list_profiles()
    output(profiles, "Available profiles:")


@project.command("json")
@handle_error
def project_json():
    """Print raw project JSON."""
    sess = get_session()
    click.echo(json.dumps(sess.get_project(), indent=2, default=str))


# ── Layer Commands ───────────────────────────────────────────────
@cli.group()
def layer():
    """Layer management commands."""
    pass


@layer.command("new")
@click.option("--name", "-n", default="New Layer", help="Layer name")
@click.option("--type", "layer_type", type=click.Choice(["image", "text", "solid"]),
              default="image", help="Layer type")
@click.option("--width", "-w", type=int, default=None, help="Layer width")
@click.option("--height", "-h", type=int, default=None, help="Layer height")
@click.option("--fill", default="transparent", help="Fill: transparent, white, black, or hex")
@click.option("--opacity", type=float, default=1.0, help="Layer opacity 0.0-1.0")
@click.option("--mode", default="normal", help="Blend mode")
@click.option("--position", "-p", type=int, default=None, help="Stack position (0=top)")
@handle_error
def layer_new(name, layer_type, width, height, fill, opacity, mode, position):
    """Create a new blank layer."""
    sess = get_session()
    sess.snapshot(f"Add layer: {name}")
    proj = sess.get_project()
    layer = layer_mod.add_layer(
        proj, name=name, layer_type=layer_type, width=width, height=height,
        fill=fill, opacity=opacity, blend_mode=mode, position=position,
    )
    output(layer, f"Added layer: {name}")


@layer.command("add-from-file")
@click.argument("path")
@click.option("--name", "-n", default=None, help="Layer name")
@click.option("--position", "-p", type=int, default=None, help="Stack position")
@click.option("--opacity", type=float, default=1.0, help="Layer opacity")
@click.option("--mode", default="normal", help="Blend mode")
@handle_error
def layer_add_from_file(path, name, position, opacity, mode):
    """Add a layer from an image file."""
    sess = get_session()
    sess.snapshot(f"Add layer from: {path}")
    proj = sess.get_project()
    layer = layer_mod.add_from_file(
        proj, path=path, name=name, position=position,
        opacity=opacity, blend_mode=mode,
    )
    output(layer, f"Added layer from: {path}")


@layer.command("list")
@handle_error
def layer_list():
    """List all layers."""
    sess = get_session()
    layers = layer_mod.list_layers(sess.get_project())
    output(layers, "Layers (top to bottom):")


@layer.command("remove")
@click.argument("index", type=int)
@handle_error
def layer_remove(index):
    """Remove a layer by index."""
    sess = get_session()
    sess.snapshot(f"Remove layer {index}")
    removed = layer_mod.remove_layer(sess.get_project(), index)
    output(removed, f"Removed layer {index}: {removed.get('name', '')}")


@layer.command("duplicate")
@click.argument("index", type=int)
@handle_error
def layer_duplicate(index):
    """Duplicate a layer."""
    sess = get_session()
    sess.snapshot(f"Duplicate layer {index}")
    dup = layer_mod.duplicate_layer(sess.get_project(), index)
    output(dup, f"Duplicated layer {index}")


@layer.command("move")
@click.argument("index", type=int)
@click.option("--to", type=int, required=True, help="Target position")
@handle_error
def layer_move(index, to):
    """Move a layer to a new position."""
    sess = get_session()
    sess.snapshot(f"Move layer {index} to {to}")
    layer_mod.move_layer(sess.get_project(), index, to)
    output({"moved": index, "to": to}, f"Moved layer {index} to position {to}")


@layer.command("set", context_settings={"ignore_unknown_options": True, "allow_extra_args": True})
@click.pass_context
@click.argument("index", type=int)
@click.argument("prop")
@click.argument("value", required=False)
@handle_error
def layer_set(ctx, index, prop, value):
    """Set a layer property (name, opacity, visible, mode, offset_x, offset_y)."""
    if value is None:
        if not ctx.args:
            raise ValueError("Missing layer property value")
        value = ctx.args[0]
    elif ctx.args:
        value = " ".join([value] + ctx.args)
    sess = get_session()
    sess.snapshot(f"Set layer {index} {prop}={value}")
    layer_mod.set_layer_property(sess.get_project(), index, prop, value)
    output({"layer": index, "property": prop, "value": value},
           f"Set layer {index} {prop} = {value}")


@layer.command("flatten")
@handle_error
def layer_flatten():
    """Flatten all visible layers."""
    sess = get_session()
    sess.snapshot("Flatten layers")
    layer_mod.flatten_layers(sess.get_project())
    output({"status": "flatten_pending"}, "Layers marked for flattening (applied on export)")


@layer.command("merge-down")
@click.argument("index", type=int)
@handle_error
def layer_merge_down(index):
    """Merge a layer with the one below it."""
    sess = get_session()
    sess.snapshot(f"Merge down layer {index}")
    layer_mod.merge_down(sess.get_project(), index)
    output({"status": "merge_pending", "layer": index},
           f"Layer {index} marked for merge-down (applied on export)")


# ── Canvas Commands ──────────────────────────────────────────────
@cli.group()
def canvas():
    """Canvas operations."""
    pass


@canvas.command("info")
@handle_error
def canvas_info():
    """Show canvas information."""
    sess = get_session()
    info = canvas_mod.get_canvas_info(sess.get_project())
    output(info)


@canvas.command("resize")
@click.option("--width", "-w", type=int, required=True)
@click.option("--height", "-h", type=int, required=True)
@click.option("--anchor", default="center",
              help="Anchor: center, top-left, top-right, bottom-left, bottom-right, top, bottom, left, right")
@handle_error
def canvas_resize(width, height, anchor):
    """Resize the canvas (without scaling content)."""
    sess = get_session()
    sess.snapshot(f"Resize canvas to {width}x{height}")
    result = canvas_mod.resize_canvas(sess.get_project(), width, height, anchor)
    output(result, f"Canvas resized to {width}x{height}")


@canvas.command("scale")
@click.option("--width", "-w", type=int, required=True)
@click.option("--height", "-h", type=int, required=True)
@click.option("--resample", default="lanczos",
              type=click.Choice(["nearest", "bilinear", "bicubic", "lanczos"]))
@handle_error
def canvas_scale(width, height, resample):
    """Scale the canvas and all content proportionally."""
    sess = get_session()
    sess.snapshot(f"Scale canvas to {width}x{height}")
    result = canvas_mod.scale_canvas(sess.get_project(), width, height, resample)
    output(result, f"Canvas scaled to {width}x{height}")


@canvas.command("crop")
@click.option("--left", "-l", type=int, required=True)
@click.option("--top", "-t", type=int, required=True)
@click.option("--right", "-r", type=int, required=True)
@click.option("--bottom", "-b", type=int, required=True)
@handle_error
def canvas_crop(left, top, right, bottom):
    """Crop the canvas to a rectangle."""
    sess = get_session()
    sess.snapshot(f"Crop canvas ({left},{top})-({right},{bottom})")
    result = canvas_mod.crop_canvas(sess.get_project(), left, top, right, bottom)
    output(result, "Canvas cropped")


@canvas.command("mode")
@click.argument("mode", type=click.Choice(["RGB", "RGBA", "L", "LA", "CMYK", "P"]))
@handle_error
def canvas_mode(mode):
    """Set the canvas color mode."""
    sess = get_session()
    sess.snapshot(f"Change mode to {mode}")
    result = canvas_mod.set_mode(sess.get_project(), mode)
    output(result, f"Canvas mode changed to {mode}")


@canvas.command("dpi")
@click.argument("dpi", type=int)
@handle_error
def canvas_dpi(dpi):
    """Set the canvas DPI."""
    sess = get_session()
    result = canvas_mod.set_dpi(sess.get_project(), dpi)
    output(result, f"DPI set to {dpi}")


# ── Filter Commands ──────────────────────────────────────────────
@cli.group("filter")
def filter_group():
    """Filter management commands."""
    pass


@filter_group.command("list-available")
@click.option("--category", "-c", type=str, default=None,
              help="Filter by category: adjustment, blur, stylize, transform")
@handle_error
def filter_list_available(category):
    """List all available filters."""
    filters = filt_mod.list_available(category)
    output(filters, "Available filters:")


@filter_group.command("info")
@click.argument("name")
@handle_error
def filter_info(name):
    """Show details about a filter."""
    info = filt_mod.get_filter_info(name)
    output(info)


@filter_group.command("add")
@click.argument("name")
@click.option("--layer", "-l", "layer_index", type=int, default=0, help="Layer index")
@click.option("--param", "-p", multiple=True, help="Parameter: key=value")
@handle_error
def filter_add(name, layer_index, param):
    """Add a filter to a layer."""
    params = {}
    for p in param:
        if "=" not in p:
            raise ValueError(f"Invalid param format: '{p}'. Use key=value.")
        k, v = p.split("=", 1)
        try:
            v = float(v) if "." in v else int(v)
        except ValueError:
            pass
        params[k] = v

    sess = get_session()
    sess.snapshot(f"Add filter {name} to layer {layer_index}")
    result = filt_mod.add_filter(sess.get_project(), name, layer_index, params)
    output(result, f"Added filter: {name}")


@filter_group.command("remove")
@click.argument("filter_index", type=int)
@click.option("--layer", "-l", "layer_index", type=int, default=0)
@handle_error
def filter_remove(filter_index, layer_index):
    """Remove a filter by index."""
    sess = get_session()
    sess.snapshot(f"Remove filter {filter_index} from layer {layer_index}")
    result = filt_mod.remove_filter(sess.get_project(), filter_index, layer_index)
    output(result, f"Removed filter {filter_index}")


@filter_group.command("set")
@click.argument("filter_index", type=int)
@click.argument("param")
@click.argument("value")
@click.option("--layer", "-l", "layer_index", type=int, default=0)
@handle_error
def filter_set(filter_index, param, value, layer_index):
    """Set a filter parameter."""
    try:
        value = float(value) if "." in str(value) else int(value)
    except ValueError:
        pass
    sess = get_session()
    sess.snapshot(f"Set filter {filter_index} {param}={value}")
    filt_mod.set_filter_param(sess.get_project(), filter_index, param, value, layer_index)
    output({"filter": filter_index, "param": param, "value": value},
           f"Set filter {filter_index} {param} = {value}")


@filter_group.command("list")
@click.option("--layer", "-l", "layer_index", type=int, default=0)
@handle_error
def filter_list(layer_index):
    """List filters on a layer."""
    sess = get_session()
    filters = filt_mod.list_filters(sess.get_project(), layer_index)
    output(filters, f"Filters on layer {layer_index}:")


# ── Media Commands ───────────────────────────────────────────────
@cli.group()
def media():
    """Media file operations."""
    pass


@media.command("probe")
@click.argument("path")
@handle_error
def media_probe(path):
    """Analyze an image file."""
    info = media_mod.probe_image(path)
    output(info)


@media.command("list")
@handle_error
def media_list():
    """List media files referenced in the project."""
    sess = get_session()
    media = media_mod.list_media_in_project(sess.get_project())
    output(media, "Referenced media files:")


@media.command("check")
@handle_error
def media_check():
    """Check that all referenced media files exist."""
    sess = get_session()
    result = media_mod.check_media(sess.get_project())
    output(result)


@media.command("histogram")
@click.argument("path")
@handle_error
def media_histogram(path):
    """Show histogram analysis of an image."""
    result = media_mod.get_image_histogram(path)
    output(result)


# ── Export Commands ──────────────────────────────────────────────
@cli.group("export")
def export_group():
    """Export/render commands."""
    pass


@export_group.command("presets")
@handle_error
def export_presets():
    """List export presets."""
    presets = export_mod.list_presets()
    output(presets, "Export presets:")


@export_group.command("preset-info")
@click.argument("name")
@handle_error
def export_preset_info(name):
    """Show preset details."""
    info = export_mod.get_preset_info(name)
    output(info)


@export_group.command("render")
@click.argument("output_path")
@click.option("--preset", "-p", default="png", help="Export preset")
@click.option("--overwrite", is_flag=True, help="Overwrite existing file")
@click.option("--quality", "-q", type=int, default=None, help="Quality override")
@click.option("--format", "fmt", type=str, default=None, help="Format override")
@handle_error
def export_render(output_path, preset, overwrite, quality, fmt):
    """Render the project to an image file."""
    sess = get_session()
    result = export_mod.render(
        sess.get_project(), output_path,
        preset=preset, overwrite=overwrite,
        quality=quality, format_override=fmt,
    )
    output(result, f"Rendered to: {output_path}")


# ── Session Commands ─────────────────────────────────────────────
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


# ── Draw Commands ────────────────────────────────────────────────
@cli.group()
def draw():
    """Drawing operations (applied at render time)."""
    pass


@draw.command("text")
@click.option("--layer", "-l", "layer_index", type=int, default=0)
@click.option("--text", "-t", required=True, help="Text to draw")
@click.option("--x", type=int, default=0, help="X position")
@click.option("--y", type=int, default=0, help="Y position")
@click.option("--font", default="Arial", help="Font name")
@click.option("--size", type=int, default=24, help="Font size")
@click.option("--color", default="#000000", help="Text color (hex)")
@handle_error
def draw_text(layer_index, text, x, y, font, size, color):
    """Draw text on a layer as a persisted draw operation."""
    sess = get_session()
    sess.snapshot(f"Draw text on layer {layer_index}")
    proj = sess.get_project()
    layers = proj.get("layers", [])
    if layer_index < 0 or layer_index >= len(layers):
        raise IndexError(f"Layer index {layer_index} out of range")
    layer = layers[layer_index]
    layer.setdefault("draw_ops", []).append({
        "type": "text",
        "text": text,
        "x": x,
        "y": y,
        "font": font,
        "size": size,
        "color": color,
    })
    output({"layer": layer_index, "text": text}, f"Drew text on layer {layer_index}")


@draw.command("rect")
@click.option("--layer", "-l", "layer_index", type=int, default=0)
@click.option("--x1", type=int, required=True)
@click.option("--y1", type=int, required=True)
@click.option("--x2", type=int, required=True)
@click.option("--y2", type=int, required=True)
@click.option("--fill", default=None, help="Fill color (hex)")
@click.option("--outline", default=None, help="Outline color (hex)")
@click.option("--width", "line_width", type=int, default=1, help="Outline width")
@handle_error
def draw_rect(layer_index, x1, y1, x2, y2, fill, outline, line_width):
    """Draw a rectangle (stored as drawing operation)."""
    sess = get_session()
    sess.snapshot(f"Draw rect on layer {layer_index}")
    proj = sess.get_project()
    layers = proj.get("layers", [])
    if layer_index < 0 or layer_index >= len(layers):
        raise IndexError(f"Layer index {layer_index} out of range")
    layer = layers[layer_index]
    if "draw_ops" not in layer:
        layer["draw_ops"] = []
    layer["draw_ops"].append({
        "type": "rect",
        "x1": x1, "y1": y1, "x2": x2, "y2": y2,
        "fill": fill, "outline": outline, "width": line_width,
    })
    output({"layer": layer_index, "shape": "rect", "coords": f"({x1},{y1})-({x2},{y2})"},
           f"Drew rectangle on layer {layer_index}")


# ── REPL ─────────────────────────────────────────────────────────
@cli.command()
@click.option("--project", "project_path", type=str, default=None)
@handle_error
def repl(project_path):
    """Start interactive REPL session."""
    from cli_anything.gimp.utils.repl_skin import ReplSkin

    global _repl_mode
    _repl_mode = True

    skin = ReplSkin("gimp", version="1.0.0")

    if project_path:
        sess = get_session()
        proj = proj_mod.open_project(project_path)
        sess.set_project(proj, project_path)

    skin.print_banner()

    pt_session = skin.create_prompt_session()

    _repl_commands = {
        "project":  "new|open|save|info|profiles|json",
        "layer":    "new|add-from-file|list|remove|duplicate|move|set|flatten|merge-down",
        "canvas":   "info|resize|scale|crop|mode|dpi",
        "filter":   "list-available|info|add|remove|set|list",
        "media":    "probe|list|check|histogram",
        "export":   "presets|preset-info|render",
        "draw":     "text|rect",
        "session":  "status|undo|redo|history",
        "help":     "Show this help",
        "quit":     "Exit REPL",
    }

    while True:
        try:
            # Determine project name for prompt
            try:
                sess = get_session()
                proj_name = ""
                if sess.has_project():
                    p = sess.get_project()
                    proj_name = p.get("name", "") if isinstance(p, dict) else ""
            except Exception:
                proj_name = ""

            line = skin.get_input(pt_session, project_name=proj_name, modified=False)
            if not line:
                continue
            if line.lower() in ("quit", "exit", "q"):
                skin.print_goodbye()
                break
            if line.lower() == "help":
                skin.help(_repl_commands)
                continue

            # Parse and execute command (shlex handles quoted strings with spaces)
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
