#!/usr/bin/env python3
"""Inkscape CLI — A stateful command-line interface for vector graphics editing.

This CLI provides full SVG editing capabilities using direct SVG/XML
manipulation, with a project format that tracks objects, layers, and history.

Usage:
    # One-shot commands
    python3 -m cli.inkscape_cli document new --width 1920 --height 1080
    python3 -m cli.inkscape_cli shape add-rect --x 100 --y 100 --width 200 --height 150
    python3 -m cli.inkscape_cli style set-fill 0 "#ff0000"

    # Interactive REPL
    python3 -m cli.inkscape_cli repl
"""

import sys
import os
import json
import shlex
import click
from typing import Optional

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cli_anything.inkscape.core.session import Session
from cli_anything.inkscape.core import document as doc_mod
from cli_anything.inkscape.core import shapes as shape_mod
from cli_anything.inkscape.core import text as text_mod
from cli_anything.inkscape.core import styles as style_mod
from cli_anything.inkscape.core import transforms as xform_mod
from cli_anything.inkscape.core import layers as layer_mod
from cli_anything.inkscape.core import paths as path_mod
from cli_anything.inkscape.core import gradients as grad_mod
from cli_anything.inkscape.core import export as export_mod

# Global session state
_session: Optional[Session] = None
_json_output = False
_repl_mode = False
_auto_save = False


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
              help="Path to .inkscape-cli.json project file")
@click.option("-s", "--save", "auto_save", is_flag=True,
              help="Auto-save project after each mutation command (one-shot mode)")
@click.pass_context
def cli(ctx, use_json, project_path, auto_save):
    """Inkscape CLI — Stateful vector graphics editing from the command line.

    Run without a subcommand to enter interactive REPL mode.

    Use -s/--save to automatically save changes after each mutation command.
    This is useful in one-shot mode where each command runs in a new process.
    """
    global _json_output, _auto_save
    _json_output = use_json
    _auto_save = auto_save

    if project_path:
        sess = get_session()
        if not sess.has_project():
            proj = doc_mod.open_document(project_path)
            sess.set_project(proj, project_path)

    # Register auto-save callback to run after each command
    ctx.call_on_close(_auto_save_callback)

    if ctx.invoked_subcommand is None:
        ctx.invoke(repl, project_path=None)


def _auto_save_callback():
    """Auto-save callback that runs after each command."""
    global _auto_save, _session
    if _auto_save and _session and _session.has_project() and _session._modified:
        # Don't auto-save if we're in REPL mode (user can explicitly save)
        if not _repl_mode:
            try:
                saved = _session.save_session()
                click.echo(f"Auto-saved to: {saved}")
            except Exception as e:
                click.echo(f"Auto-save failed: {e}", err=True)


# ── Document Commands ───────────────────────────────────────────
@cli.group()
def document():
    """Document management commands."""
    pass


@document.command("new")
@click.option("--width", "-w", type=float, default=1920, help="Canvas width")
@click.option("--height", "-h", type=float, default=1080, help="Canvas height")
@click.option("--units", "-u", type=click.Choice(["px", "mm", "cm", "in", "pt", "pc"]),
              default="px")
@click.option("--background", "-bg", default="#ffffff", help="Background color")
@click.option("--name", "-n", default="untitled", help="Document name")
@click.option("--profile", "-p", type=str, default=None, help="Document profile")
@click.option("--output", "-o", type=str, default=None, help="Save path")
@handle_error
def document_new(width, height, units, background, name, profile, output):
    """Create a new document."""
    proj = doc_mod.create_document(
        width=width, height=height, units=units,
        background=background, name=name, profile=profile,
    )
    sess = get_session()
    sess.set_project(proj, output)
    if output:
        doc_mod.save_document(proj, output)
    output_data = doc_mod.get_document_info(proj)
    globals()["output"](output_data, f"Created document: {name}")


@document.command("open")
@click.argument("path")
@handle_error
def document_open(path):
    """Open an existing project."""
    proj = doc_mod.open_document(path)
    sess = get_session()
    sess.set_project(proj, path)
    info = doc_mod.get_document_info(proj)
    output(info, f"Opened: {path}")


@document.command("save")
@click.argument("path", required=False)
@handle_error
def document_save(path):
    """Save the current project."""
    sess = get_session()
    saved = sess.save_session(path)
    output({"saved": saved}, f"Saved to: {saved}")


@document.command("info")
@handle_error
def document_info():
    """Show document information."""
    sess = get_session()
    info = doc_mod.get_document_info(sess.get_project())
    output(info)


@document.command("profiles")
@handle_error
def document_profiles():
    """List available document profiles."""
    profiles = doc_mod.list_profiles()
    output(profiles, "Available profiles:")


@document.command("canvas-size")
@click.option("--width", "-w", type=float, required=True)
@click.option("--height", "-h", type=float, required=True)
@handle_error
def document_canvas_size(width, height):
    """Set the canvas size."""
    sess = get_session()
    sess.snapshot("Set canvas size")
    result = doc_mod.set_canvas_size(sess.get_project(), width, height)
    output(result, f"Canvas resized: {result['new_size']}")


@document.command("units")
@click.argument("units", type=click.Choice(["px", "mm", "cm", "in", "pt", "pc"]))
@handle_error
def document_units(units):
    """Set the document units."""
    sess = get_session()
    result = doc_mod.set_units(sess.get_project(), units)
    output(result, f"Units changed: {result['old_units']} -> {result['new_units']}")


@document.command("json")
@handle_error
def document_json():
    """Print raw project JSON."""
    sess = get_session()
    click.echo(json.dumps(sess.get_project(), indent=2, default=str))


# ── Shape Commands ──────────────────────────────────────────────
@cli.group()
def shape():
    """Shape management commands."""
    pass


@shape.command("add-rect")
@click.option("--x", type=float, default=0)
@click.option("--y", type=float, default=0)
@click.option("--width", "-w", type=float, default=100)
@click.option("--height", "-h", type=float, default=100)
@click.option("--rx", type=float, default=0, help="Corner radius X")
@click.option("--ry", type=float, default=0, help="Corner radius Y")
@click.option("--name", "-n", default=None)
@click.option("--style", "-s", default=None, help="CSS style string")
@handle_error
def shape_add_rect(x, y, width, height, rx, ry, name, style):
    """Add a rectangle."""
    sess = get_session()
    sess.snapshot("Add rectangle")
    obj = shape_mod.add_rect(sess.get_project(), x=x, y=y, width=width, height=height,
                              rx=rx, ry=ry, name=name, style=style)
    output(obj, f"Added rectangle: {obj['name']}")


@shape.command("add-circle")
@click.option("--cx", type=float, default=50)
@click.option("--cy", type=float, default=50)
@click.option("--r", type=float, default=50, help="Radius")
@click.option("--name", "-n", default=None)
@click.option("--style", "-s", default=None)
@handle_error
def shape_add_circle(cx, cy, r, name, style):
    """Add a circle."""
    sess = get_session()
    sess.snapshot("Add circle")
    obj = shape_mod.add_circle(sess.get_project(), cx=cx, cy=cy, r=r, name=name, style=style)
    output(obj, f"Added circle: {obj['name']}")


@shape.command("add-ellipse")
@click.option("--cx", type=float, default=50)
@click.option("--cy", type=float, default=50)
@click.option("--rx", type=float, default=75)
@click.option("--ry", type=float, default=50)
@click.option("--name", "-n", default=None)
@click.option("--style", "-s", default=None)
@handle_error
def shape_add_ellipse(cx, cy, rx, ry, name, style):
    """Add an ellipse."""
    sess = get_session()
    sess.snapshot("Add ellipse")
    obj = shape_mod.add_ellipse(sess.get_project(), cx=cx, cy=cy, rx=rx, ry=ry,
                                 name=name, style=style)
    output(obj, f"Added ellipse: {obj['name']}")


@shape.command("add-line")
@click.option("--x1", type=float, default=0)
@click.option("--y1", type=float, default=0)
@click.option("--x2", type=float, default=100)
@click.option("--y2", type=float, default=100)
@click.option("--name", "-n", default=None)
@click.option("--style", "-s", default=None)
@handle_error
def shape_add_line(x1, y1, x2, y2, name, style):
    """Add a line."""
    sess = get_session()
    sess.snapshot("Add line")
    obj = shape_mod.add_line(sess.get_project(), x1=x1, y1=y1, x2=x2, y2=y2,
                              name=name, style=style)
    output(obj, f"Added line: {obj['name']}")


@shape.command("add-polygon")
@click.option("--points", "-p", required=True, help='SVG points, e.g. "50,0 100,100 0,100"')
@click.option("--name", "-n", default=None)
@click.option("--style", "-s", default=None)
@handle_error
def shape_add_polygon(points, name, style):
    """Add a polygon."""
    sess = get_session()
    sess.snapshot("Add polygon")
    obj = shape_mod.add_polygon(sess.get_project(), points=points, name=name, style=style)
    output(obj, f"Added polygon: {obj['name']}")


@shape.command("add-path")
@click.option("--d", required=True, help='SVG path data, e.g. "M 0,0 L 100,0 L 100,100 Z"')
@click.option("--name", "-n", default=None)
@click.option("--style", "-s", default=None)
@handle_error
def shape_add_path(d, name, style):
    """Add a path."""
    sess = get_session()
    sess.snapshot("Add path")
    obj = shape_mod.add_path(sess.get_project(), d=d, name=name, style=style)
    output(obj, f"Added path: {obj['name']}")


@shape.command("add-star")
@click.option("--cx", type=float, default=50)
@click.option("--cy", type=float, default=50)
@click.option("--points", type=int, default=5, help="Number of star points")
@click.option("--outer-r", type=float, default=50, help="Outer radius")
@click.option("--inner-r", type=float, default=25, help="Inner radius")
@click.option("--name", "-n", default=None)
@click.option("--style", "-s", default=None)
@handle_error
def shape_add_star(cx, cy, points, outer_r, inner_r, name, style):
    """Add a star."""
    sess = get_session()
    sess.snapshot("Add star")
    obj = shape_mod.add_star(sess.get_project(), cx=cx, cy=cy, points_count=points,
                              outer_r=outer_r, inner_r=inner_r, name=name, style=style)
    output(obj, f"Added star: {obj['name']}")


@shape.command("remove")
@click.argument("index", type=int)
@handle_error
def shape_remove(index):
    """Remove a shape by index."""
    sess = get_session()
    sess.snapshot(f"Remove object {index}")
    removed = shape_mod.remove_object(sess.get_project(), index)
    output(removed, f"Removed: {removed.get('name', '')}")


@shape.command("duplicate")
@click.argument("index", type=int)
@handle_error
def shape_duplicate(index):
    """Duplicate a shape."""
    sess = get_session()
    sess.snapshot(f"Duplicate object {index}")
    dup = shape_mod.duplicate_object(sess.get_project(), index)
    output(dup, f"Duplicated: {dup['name']}")


@shape.command("list")
@handle_error
def shape_list():
    """List all shapes/objects."""
    sess = get_session()
    objects = shape_mod.list_objects(sess.get_project())
    output(objects, "Objects:")


@shape.command("get")
@click.argument("index", type=int)
@handle_error
def shape_get(index):
    """Get detailed info about a shape."""
    sess = get_session()
    obj = shape_mod.get_object(sess.get_project(), index)
    output(obj)


# ── Text Commands ───────────────────────────────────────────────
@cli.group()
def text():
    """Text management commands."""
    pass


@text.command("add")
@click.option("--text", "-t", required=True, help="Text content")
@click.option("--x", type=float, default=0)
@click.option("--y", type=float, default=50)
@click.option("--font-family", default="sans-serif", help="Font family")
@click.option("--font-size", type=float, default=24, help="Font size in px")
@click.option("--font-weight", default="normal", help="Font weight")
@click.option("--fill", default="#000000", help="Text color")
@click.option("--text-anchor", default="start", help="Alignment: start, middle, end")
@click.option("--name", "-n", default=None)
@handle_error
def text_add(text, x, y, font_family, font_size, font_weight, fill, text_anchor, name):
    """Add a text element."""
    sess = get_session()
    sess.snapshot("Add text")
    obj = text_mod.add_text(sess.get_project(), text=text, x=x, y=y,
                             font_family=font_family, font_size=font_size,
                             font_weight=font_weight, fill=fill,
                             text_anchor=text_anchor, name=name)
    output(obj, f"Added text: {obj['name']}")


@text.command("set")
@click.argument("index", type=int)
@click.argument("prop")
@click.argument("value")
@handle_error
def text_set(index, prop, value):
    """Set a text property (text, font-family, font-size, fill, etc.)."""
    sess = get_session()
    sess.snapshot(f"Set text {index} {prop}")
    text_mod.set_text_property(sess.get_project(), index, prop, value)
    output({"object": index, "property": prop, "value": value},
           f"Set text {index} {prop} = {value}")


@text.command("list")
@handle_error
def text_list():
    """List all text objects."""
    sess = get_session()
    texts = text_mod.list_text_objects(sess.get_project())
    output(texts, "Text objects:")


# ── Style Commands ──────────────────────────────────────────────
@cli.group()
def style():
    """Style management commands."""
    pass


@style.command("set-fill")
@click.argument("index", type=int)
@click.argument("color")
@handle_error
def style_set_fill(index, color):
    """Set the fill color of an object."""
    sess = get_session()
    sess.snapshot(f"Set fill on object {index}")
    style_mod.set_fill(sess.get_project(), index, color)
    output({"object": index, "fill": color}, f"Set fill: {color}")


@style.command("set-stroke")
@click.argument("index", type=int)
@click.argument("color")
@click.option("--width", "-w", type=float, default=None, help="Stroke width")
@handle_error
def style_set_stroke(index, color, width):
    """Set the stroke color (and optionally width) of an object."""
    sess = get_session()
    sess.snapshot(f"Set stroke on object {index}")
    style_mod.set_stroke(sess.get_project(), index, color, width)
    output({"object": index, "stroke": color, "width": width},
           f"Set stroke: {color}")


@style.command("set-opacity")
@click.argument("index", type=int)
@click.argument("opacity", type=float)
@handle_error
def style_set_opacity(index, opacity):
    """Set the opacity of an object (0.0-1.0)."""
    sess = get_session()
    sess.snapshot(f"Set opacity on object {index}")
    style_mod.set_opacity(sess.get_project(), index, opacity)
    output({"object": index, "opacity": opacity}, f"Set opacity: {opacity}")


@style.command("set")
@click.argument("index", type=int)
@click.argument("prop")
@click.argument("value")
@handle_error
def style_set(index, prop, value):
    """Set an arbitrary style property on an object."""
    sess = get_session()
    sess.snapshot(f"Set style {prop} on object {index}")
    style_mod.set_style(sess.get_project(), index, prop, value)
    output({"object": index, "property": prop, "value": value},
           f"Set {prop}: {value}")


@style.command("get")
@click.argument("index", type=int)
@handle_error
def style_get(index):
    """Get the style properties of an object."""
    sess = get_session()
    props = style_mod.get_object_style(sess.get_project(), index)
    output(props)


@style.command("list-properties")
@handle_error
def style_list_properties():
    """List all available style properties."""
    props = style_mod.list_style_properties()
    output(props, "Available style properties:")


# ── Transform Commands ──────────────────────────────────────────
@cli.group()
def transform():
    """Transform operations (translate, rotate, scale, skew)."""
    pass


@transform.command("translate")
@click.argument("index", type=int)
@click.argument("tx", type=float)
@click.option("--ty", type=float, default=0, help="Y translation")
@handle_error
def transform_translate(index, tx, ty):
    """Translate (move) an object."""
    sess = get_session()
    sess.snapshot(f"Translate object {index}")
    xform_mod.translate(sess.get_project(), index, tx, ty)
    output({"object": index, "translate": f"{tx},{ty}"},
           f"Translated object {index} by ({tx}, {ty})")


@transform.command("rotate")
@click.argument("index", type=int)
@click.argument("angle", type=float)
@click.option("--cx", type=float, default=None, help="Center X")
@click.option("--cy", type=float, default=None, help="Center Y")
@handle_error
def transform_rotate(index, angle, cx, cy):
    """Rotate an object."""
    sess = get_session()
    sess.snapshot(f"Rotate object {index}")
    xform_mod.rotate(sess.get_project(), index, angle, cx, cy)
    output({"object": index, "rotate": angle},
           f"Rotated object {index} by {angle} degrees")


@transform.command("scale")
@click.argument("index", type=int)
@click.argument("sx", type=float)
@click.option("--sy", type=float, default=None, help="Y scale (default=sx)")
@handle_error
def transform_scale(index, sx, sy):
    """Scale an object."""
    sess = get_session()
    sess.snapshot(f"Scale object {index}")
    xform_mod.scale(sess.get_project(), index, sx, sy)
    output({"object": index, "scale": f"{sx},{sy or sx}"},
           f"Scaled object {index} by ({sx}, {sy or sx})")


@transform.command("skew-x")
@click.argument("index", type=int)
@click.argument("angle", type=float)
@handle_error
def transform_skew_x(index, angle):
    """Skew an object horizontally."""
    sess = get_session()
    sess.snapshot(f"Skew X object {index}")
    xform_mod.skew_x(sess.get_project(), index, angle)
    output({"object": index, "skewX": angle},
           f"Skewed object {index} horizontally by {angle} degrees")


@transform.command("skew-y")
@click.argument("index", type=int)
@click.argument("angle", type=float)
@handle_error
def transform_skew_y(index, angle):
    """Skew an object vertically."""
    sess = get_session()
    sess.snapshot(f"Skew Y object {index}")
    xform_mod.skew_y(sess.get_project(), index, angle)
    output({"object": index, "skewY": angle},
           f"Skewed object {index} vertically by {angle} degrees")


@transform.command("get")
@click.argument("index", type=int)
@handle_error
def transform_get(index):
    """Get the current transform of an object."""
    sess = get_session()
    t = xform_mod.get_transform(sess.get_project(), index)
    output(t)


@transform.command("clear")
@click.argument("index", type=int)
@handle_error
def transform_clear(index):
    """Clear all transforms from an object."""
    sess = get_session()
    sess.snapshot(f"Clear transform on object {index}")
    result = xform_mod.clear_transform(sess.get_project(), index)
    output(result, f"Cleared transforms on object {index}")


# ── Layer Commands ──────────────────────────────────────────────
@cli.group()
def layer():
    """Layer management commands."""
    pass


@layer.command("add")
@click.option("--name", "-n", default="New Layer", help="Layer name")
@click.option("--visible/--hidden", default=True)
@click.option("--opacity", type=float, default=1.0)
@click.option("--position", type=int, default=None, help="Stack position")
@handle_error
def layer_add(name, visible, opacity, position):
    """Add a new layer."""
    sess = get_session()
    sess.snapshot(f"Add layer: {name}")
    layer = layer_mod.add_layer(sess.get_project(), name=name, visible=visible,
                                 opacity=opacity, position=position)
    output(layer, f"Added layer: {layer['name']}")


@layer.command("remove")
@click.argument("index", type=int)
@handle_error
def layer_remove(index):
    """Remove a layer by index."""
    sess = get_session()
    sess.snapshot(f"Remove layer {index}")
    removed = layer_mod.remove_layer(sess.get_project(), index)
    output(removed, f"Removed layer: {removed.get('name', '')}")


@layer.command("move-object")
@click.argument("object_index", type=int)
@click.argument("layer_index", type=int)
@handle_error
def layer_move_object(object_index, layer_index):
    """Move an object to a different layer."""
    sess = get_session()
    sess.snapshot(f"Move object {object_index} to layer {layer_index}")
    result = layer_mod.move_to_layer(sess.get_project(), object_index, layer_index)
    output(result, f"Moved {result['object']} to {result['target_layer']}")


@layer.command("set")
@click.argument("index", type=int)
@click.argument("prop")
@click.argument("value")
@handle_error
def layer_set(index, prop, value):
    """Set a layer property (name, visible, locked, opacity)."""
    sess = get_session()
    sess.snapshot(f"Set layer {index} {prop}")
    layer_mod.set_layer_property(sess.get_project(), index, prop, value)
    output({"layer": index, "property": prop, "value": value},
           f"Set layer {index} {prop} = {value}")


@layer.command("list")
@handle_error
def layer_list():
    """List all layers."""
    sess = get_session()
    layers = layer_mod.list_layers(sess.get_project())
    output(layers, "Layers:")


@layer.command("reorder")
@click.argument("from_index", type=int)
@click.argument("to_index", type=int)
@handle_error
def layer_reorder(from_index, to_index):
    """Move a layer from one position to another."""
    sess = get_session()
    sess.snapshot(f"Reorder layer {from_index} to {to_index}")
    result = layer_mod.reorder_layers(sess.get_project(), from_index, to_index)
    output(result, f"Moved layer: {result['layer']}")


@layer.command("get")
@click.argument("index", type=int)
@handle_error
def layer_get(index):
    """Get detailed info about a layer."""
    sess = get_session()
    layer = layer_mod.get_layer(sess.get_project(), index)
    output(layer)


# ── Path Commands ───────────────────────────────────────────────
@cli.group("path")
def path_group():
    """Path boolean operations."""
    pass


@path_group.command("union")
@click.argument("index_a", type=int)
@click.argument("index_b", type=int)
@click.option("--name", "-n", default=None)
@handle_error
def path_union(index_a, index_b, name):
    """Union of two objects."""
    sess = get_session()
    sess.snapshot(f"Path union {index_a} + {index_b}")
    result = path_mod.path_union(sess.get_project(), index_a, index_b, name)
    output(result, f"Union created: {result['name']}")


@path_group.command("intersection")
@click.argument("index_a", type=int)
@click.argument("index_b", type=int)
@click.option("--name", "-n", default=None)
@handle_error
def path_intersection(index_a, index_b, name):
    """Intersection of two objects."""
    sess = get_session()
    sess.snapshot(f"Path intersection {index_a} & {index_b}")
    result = path_mod.path_intersection(sess.get_project(), index_a, index_b, name)
    output(result, f"Intersection created: {result['name']}")


@path_group.command("difference")
@click.argument("index_a", type=int)
@click.argument("index_b", type=int)
@click.option("--name", "-n", default=None)
@handle_error
def path_difference(index_a, index_b, name):
    """Difference of two objects (A minus B)."""
    sess = get_session()
    sess.snapshot(f"Path difference {index_a} - {index_b}")
    result = path_mod.path_difference(sess.get_project(), index_a, index_b, name)
    output(result, f"Difference created: {result['name']}")


@path_group.command("exclusion")
@click.argument("index_a", type=int)
@click.argument("index_b", type=int)
@click.option("--name", "-n", default=None)
@handle_error
def path_exclusion(index_a, index_b, name):
    """Exclusion (XOR) of two objects."""
    sess = get_session()
    sess.snapshot(f"Path exclusion {index_a} ^ {index_b}")
    result = path_mod.path_exclusion(sess.get_project(), index_a, index_b, name)
    output(result, f"Exclusion created: {result['name']}")


@path_group.command("convert")
@click.argument("index", type=int)
@handle_error
def path_convert(index):
    """Convert a shape to a path."""
    sess = get_session()
    sess.snapshot(f"Convert object {index} to path")
    result = path_mod.convert_to_path(sess.get_project(), index)
    output(result, f"Converted to path: {result['name']}")


@path_group.command("list-operations")
@handle_error
def path_list_ops():
    """List available path boolean operations."""
    ops = path_mod.list_path_operations()
    output(ops, "Path operations:")


# ── Gradient Commands ───────────────────────────────────────────
@cli.group()
def gradient():
    """Gradient management commands."""
    pass


@gradient.command("add-linear")
@click.option("--x1", type=float, default=0)
@click.option("--y1", type=float, default=0)
@click.option("--x2", type=float, default=1)
@click.option("--y2", type=float, default=0)
@click.option("--color1", default="#000000", help="Start color")
@click.option("--color2", default="#ffffff", help="End color")
@click.option("--name", "-n", default=None)
@handle_error
def gradient_add_linear(x1, y1, x2, y2, color1, color2, name):
    """Add a linear gradient."""
    stops = [
        {"offset": 0, "color": color1, "opacity": 1},
        {"offset": 1, "color": color2, "opacity": 1},
    ]
    sess = get_session()
    sess.snapshot("Add linear gradient")
    grad = grad_mod.add_linear_gradient(sess.get_project(), stops=stops,
                                         x1=x1, y1=y1, x2=x2, y2=y2, name=name)
    output(grad, f"Added linear gradient: {grad['name']}")


@gradient.command("add-radial")
@click.option("--cx", type=float, default=0.5)
@click.option("--cy", type=float, default=0.5)
@click.option("--r", type=float, default=0.5)
@click.option("--color1", default="#ffffff", help="Center color")
@click.option("--color2", default="#000000", help="Edge color")
@click.option("--name", "-n", default=None)
@handle_error
def gradient_add_radial(cx, cy, r, color1, color2, name):
    """Add a radial gradient."""
    stops = [
        {"offset": 0, "color": color1, "opacity": 1},
        {"offset": 1, "color": color2, "opacity": 1},
    ]
    sess = get_session()
    sess.snapshot("Add radial gradient")
    grad = grad_mod.add_radial_gradient(sess.get_project(), stops=stops,
                                         cx=cx, cy=cy, r=r, name=name)
    output(grad, f"Added radial gradient: {grad['name']}")


@gradient.command("apply")
@click.argument("gradient_index", type=int)
@click.argument("object_index", type=int)
@click.option("--target", "-t", default="fill", help="fill or stroke")
@handle_error
def gradient_apply(gradient_index, object_index, target):
    """Apply a gradient to an object."""
    sess = get_session()
    sess.snapshot(f"Apply gradient {gradient_index} to object {object_index}")
    result = grad_mod.apply_gradient(sess.get_project(), object_index, gradient_index, target)
    output(result, f"Applied gradient to {result['object']}")


@gradient.command("list")
@handle_error
def gradient_list():
    """List all gradients."""
    sess = get_session()
    grads = grad_mod.list_gradients(sess.get_project())
    output(grads, "Gradients:")


# ── Export Commands ─────────────────────────────────────────────
@cli.group("export")
def export_group():
    """Export/render commands."""
    pass


@export_group.command("png")
@click.argument("output_path")
@click.option("--width", "-w", type=int, default=None)
@click.option("--height", "-h", type=int, default=None)
@click.option("--dpi", type=int, default=96)
@click.option("--background", "-bg", default=None)
@click.option("--overwrite", is_flag=True)
@handle_error
def export_png(output_path, width, height, dpi, background, overwrite):
    """Render the document to PNG."""
    sess = get_session()
    result = export_mod.render_to_png(
        sess.get_project(), output_path, width=width, height=height,
        dpi=dpi, background=background, overwrite=overwrite,
    )
    output(result, f"Rendered: {output_path}")


@export_group.command("svg")
@click.argument("output_path")
@click.option("--overwrite", is_flag=True)
@handle_error
def export_svg(output_path, overwrite):
    """Export the document as SVG."""
    sess = get_session()
    result = export_mod.export_svg(sess.get_project(), output_path, overwrite=overwrite)
    output(result, f"Exported SVG: {output_path}")


@export_group.command("pdf")
@click.argument("output_path")
@click.option("--overwrite", is_flag=True)
@handle_error
def export_pdf(output_path, overwrite):
    """Export the document as PDF (requires Inkscape)."""
    sess = get_session()
    result = export_mod.export_pdf(sess.get_project(), output_path, overwrite=overwrite)
    output(result, f"Export PDF: {output_path}")


@export_group.command("presets")
@handle_error
def export_presets():
    """List export presets."""
    presets = export_mod.list_presets()
    output(presets, "Export presets:")


# ── Session Commands ────────────────────────────────────────────
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


# ── REPL ────────────────────────────────────────────────────────
@cli.command()
@click.option("--project", "project_path", type=str, default=None)
@handle_error
def repl(project_path):
    """Start interactive REPL session."""
    from cli_anything.inkscape.utils.repl_skin import ReplSkin

    global _repl_mode
    _repl_mode = True

    skin = ReplSkin("inkscape", version="1.0.0")

    if project_path:
        sess = get_session()
        proj = doc_mod.open_document(project_path)
        sess.set_project(proj, project_path)

    skin.print_banner()

    pt_session = skin.create_prompt_session()

    # Determine the current project name for the prompt
    def _current_project_name():
        try:
            s = get_session()
            if s.has_project():
                return s.project_path or "untitled"
        except Exception:
            pass
        return ""

    while True:
        try:
            project_name = _current_project_name()
            line = skin.get_input(pt_session, project_name=project_name, modified=False).strip()
            if not line:
                continue
            if line.lower() in ("quit", "exit", "q"):
                skin.print_goodbye()
                break
            if line.lower() == "help":
                _repl_help(skin)
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
                skin.error(f"Usage error: {e}")
            except Exception as e:
                skin.error(f"{e}")

        except (EOFError, KeyboardInterrupt):
            skin.print_goodbye()
            break

    _repl_mode = False


def _repl_help(skin=None):
    commands = {
        "document new|open|save|info|profiles|canvas-size|units|json": "Document management",
        "shape add-rect|add-circle|add-ellipse|add-line|add-polygon|add-path|add-star|remove|duplicate|list|get": "Shape operations",
        "text add|set|list": "Text management",
        "style set-fill|set-stroke|set-opacity|set|get|list-properties": "Style properties",
        "transform translate|rotate|scale|skew-x|skew-y|get|clear": "Transform operations",
        "layer add|remove|move-object|set|list|reorder|get": "Layer management",
        "path union|intersection|difference|exclusion|convert|list-operations": "Path boolean operations",
        "gradient add-linear|add-radial|apply|list": "Gradient management",
        "export png|svg|pdf|presets": "Export/render",
        "session status|undo|redo|history": "Session management",
        "help": "Show this help",
        "quit": "Exit REPL",
    }
    if skin is not None:
        skin.help(commands)
    else:
        click.echo("\nCommands:")
        for cmd, desc in commands.items():
            click.echo(f"  {cmd:60s}  {desc}")
        click.echo()


# ── Entry Point ─────────────────────────────────────────────────
def main():
    cli()


if __name__ == "__main__":
    main()
