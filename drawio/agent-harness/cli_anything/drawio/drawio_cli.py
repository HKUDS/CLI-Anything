#!/usr/bin/env python3
"""Draw.io CLI — A stateful command-line interface for diagram creation.

This CLI manipulates Draw.io XML files directly, providing full diagram
creation capabilities for AI agents and power users.

Usage:
    # One-shot commands
    cli-anything-drawio project new --preset letter -o my_diagram.drawio
    cli-anything-drawio shape add rectangle --label "Hello World"
    cli-anything-drawio connect <source_id> <target_id>

    # Interactive REPL
    cli-anything-drawio repl
"""

import sys
import os
import json
import click
from typing import Optional
from pathlib import Path

# Add harness root to path for direct source execution
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from cli_anything.drawio.core.session import Session
from cli_anything.drawio.core import project as proj_mod
from cli_anything.drawio.core import shapes as shapes_mod
from cli_anything.drawio.core import connectors as conn_mod
from cli_anything.drawio.core import pages as pages_mod
from cli_anything.drawio.core import export as export_mod

# Global session state (persists across commands in REPL mode)
_session: Optional[Session] = None
_json_output = False
_repl_mode = False


def get_session() -> Session:
    """Get or create the global session."""
    global _session
    if _session is None:
        _session = Session()
    return _session


def output(data, message: str = ""):
    """Output result data. JSON mode or human-readable."""
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
    """Pretty-print a dict."""
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
    """Pretty-print a list."""
    prefix = "  " * indent
    for i, item in enumerate(items):
        if isinstance(item, dict):
            click.echo(f"{prefix}[{i}]")
            _print_dict(item, indent + 1)
        else:
            click.echo(f"{prefix}- {item}")


def handle_error(func):
    """Decorator to handle errors consistently."""
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
        except FileExistsError as e:
            if _json_output:
                click.echo(json.dumps({"error": str(e), "type": "file_exists"}))
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
        except Exception as e:
            if _json_output:
                click.echo(json.dumps({"error": str(e), "type": "unexpected"}))
            else:
                click.echo(f"Unexpected error: {e}", err=True)
            if not _repl_mode:
                sys.exit(1)
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


# ============================================================================
# Main CLI group
# ============================================================================

@click.group(invoke_without_command=True)
@click.option("--json", "json_mode", is_flag=True, help="Output in JSON format")
@click.option("--session", "session_id", default=None, help="Session ID to use/resume")
@click.option("--project", "project_path", default=None, help="Open a project file")
@click.pass_context
def cli(ctx, json_mode, session_id, project_path):
    """Draw.io CLI — Diagram creation from the command line.

    A stateful CLI for manipulating draw.io diagram files.
    Designed for AI agents and power users.

    Run without a subcommand to enter interactive REPL mode.
    """
    global _json_output, _session
    _json_output = json_mode

    if session_id:
        _session = Session(session_id)
    else:
        _session = Session()

    if project_path:
        _session.open_project(project_path)

    # Auto-save on exit when --project was used and project was modified
    @ctx.call_on_close
    def _auto_save():
        if project_path and _session and _session.is_open and _session.is_modified:
            _session.save_project()

    if ctx.invoked_subcommand is None:
        ctx.invoke(repl, project_path=None)


# ============================================================================
# Project commands
# ============================================================================

@cli.group()
def project():
    """Project management: new, open, save, info."""
    pass


@project.command("new")
@click.option("--preset", default="letter",
              type=click.Choice(sorted(proj_mod.PAGE_PRESETS.keys())),
              help="Page size preset")
@click.option("--width", type=int, default=None, help="Custom page width")
@click.option("--height", type=int, default=None, help="Custom page height")
@click.option("-o", "--output", "output_path", default=None,
              help="Save the new project to this path")
@handle_error
def project_new(preset, width, height, output_path):
    """Create a new blank diagram."""
    session = get_session()
    result = proj_mod.new_project(session, preset, width, height)
    if output_path:
        save_result = proj_mod.save_project(session, output_path)
        result["saved_to"] = save_result["path"]
    output(result, f"Created new diagram ({result['page_size']})")


@project.command("open")
@click.argument("path")
@handle_error
def project_open(path):
    """Open an existing .drawio project file."""
    session = get_session()
    result = proj_mod.open_project(session, path)
    output(result, f"Opened: {path}")


@project.command("save")
@click.argument("path", required=False)
@handle_error
def project_save(path):
    """Save the current project."""
    session = get_session()
    result = proj_mod.save_project(session, path)
    output(result, f"Saved to: {result['path']}")


@project.command("info")
@handle_error
def project_info():
    """Show detailed project information."""
    session = get_session()
    result = proj_mod.project_info(session)
    output(result, "Project info:")


@project.command("xml")
@handle_error
def project_xml():
    """Print the raw XML of the current project."""
    session = get_session()
    if not session.is_open:
        raise RuntimeError("No project is open")
    from cli_anything.drawio.utils.drawio_xml import xml_to_string
    click.echo(xml_to_string(session.root))


@project.command("presets")
@handle_error
def project_presets():
    """List available page size presets."""
    result = proj_mod.list_presets()
    output(result, "Page presets:")


# ============================================================================
# Shape commands
# ============================================================================

@cli.group()
def shape():
    """Shape operations: add, remove, move, resize, style."""
    pass


@shape.command("add")
@click.argument("shape_type", default="rectangle")
@click.option("--label", "-l", default="", help="Text label")
@click.option("--x", type=float, default=100, help="X position")
@click.option("--y", type=float, default=100, help="Y position")
@click.option("--width", "-w", type=float, default=120, help="Width")
@click.option("--height", "-h", type=float, default=60, help="Height")
@click.option("--page", type=int, default=0, help="Page index")
@handle_error
def shape_add(shape_type, label, x, y, width, height, page):
    """Add a shape to the diagram.

    SHAPE_TYPE: rectangle, rounded, ellipse, diamond, triangle, hexagon,
    cylinder, cloud, parallelogram, process, document, callout, note, actor, text
    """
    session = get_session()
    result = shapes_mod.add_shape(session, shape_type, x, y, width, height, label, page)
    output(result, f"Added {shape_type}: {result['id']}")


@shape.command("remove")
@click.argument("cell_id")
@click.option("--page", type=int, default=0, help="Page index")
@handle_error
def shape_remove(cell_id, page):
    """Remove a shape by ID."""
    session = get_session()
    result = shapes_mod.remove_shape(session, cell_id, page)
    output(result, f"Removed: {cell_id}")


@shape.command("list")
@click.option("--page", type=int, default=0, help="Page index")
@handle_error
def shape_list(page):
    """List all shapes on a page."""
    session = get_session()
    result = shapes_mod.list_shapes(session, page)
    output(result, f"Shapes ({len(result)}):")


@shape.command("label")
@click.argument("cell_id")
@click.argument("label")
@click.option("--page", type=int, default=0, help="Page index")
@handle_error
def shape_label(cell_id, label, page):
    """Update a shape's label text."""
    session = get_session()
    result = shapes_mod.update_label(session, cell_id, label, page)
    output(result, f"Updated label: {cell_id}")


@shape.command("move")
@click.argument("cell_id")
@click.option("--x", type=float, required=True, help="New X position")
@click.option("--y", type=float, required=True, help="New Y position")
@click.option("--page", type=int, default=0, help="Page index")
@handle_error
def shape_move(cell_id, x, y, page):
    """Move a shape to new coordinates."""
    session = get_session()
    result = shapes_mod.move_shape(session, cell_id, x, y, page)
    output(result, f"Moved: {cell_id}")


@shape.command("resize")
@click.argument("cell_id")
@click.option("--width", "-w", type=float, required=True, help="New width")
@click.option("--height", "-h", type=float, required=True, help="New height")
@click.option("--page", type=int, default=0, help="Page index")
@handle_error
def shape_resize(cell_id, width, height, page):
    """Resize a shape."""
    session = get_session()
    result = shapes_mod.resize_shape(session, cell_id, width, height, page)
    output(result, f"Resized: {cell_id}")


@shape.command("style")
@click.argument("cell_id")
@click.argument("key")
@click.argument("value")
@click.option("--page", type=int, default=0, help="Page index")
@handle_error
def shape_style(cell_id, key, value, page):
    """Set a style property on a shape.

    Common keys: fillColor, strokeColor, fontColor, fontSize, opacity,
    rounded, shadow, dashed, strokeWidth
    """
    session = get_session()
    result = shapes_mod.set_style(session, cell_id, key, value, page)
    output(result, f"Style set: {key}={value}")


@shape.command("info")
@click.argument("cell_id")
@click.option("--page", type=int, default=0, help="Page index")
@handle_error
def shape_info(cell_id, page):
    """Show detailed info about a shape."""
    session = get_session()
    result = shapes_mod.get_shape_info(session, cell_id, page)
    output(result)


@shape.command("types")
@handle_error
def shape_types():
    """List all available shape types."""
    result = shapes_mod.list_shape_types()
    output(result, "Shape types:")


# ============================================================================
# Connector commands
# ============================================================================

@cli.group()
def connect():
    """Connector operations: add, remove, style."""
    pass


@connect.command("add")
@click.argument("source_id")
@click.argument("target_id")
@click.option("--style", "edge_style", default="orthogonal",
              type=click.Choice(["straight", "orthogonal", "curved", "entity-relation"]),
              help="Edge style")
@click.option("--label", "-l", default="", help="Edge label")
@click.option("--page", type=int, default=0, help="Page index")
@handle_error
def connect_add(source_id, target_id, edge_style, label, page):
    """Add a connector between two shapes."""
    session = get_session()
    result = conn_mod.add_connector(session, source_id, target_id, edge_style, label, page)
    output(result, f"Connected: {source_id} → {target_id}")


@connect.command("remove")
@click.argument("edge_id")
@click.option("--page", type=int, default=0, help="Page index")
@handle_error
def connect_remove(edge_id, page):
    """Remove a connector by ID."""
    session = get_session()
    result = conn_mod.remove_connector(session, edge_id, page)
    output(result, f"Removed connector: {edge_id}")


@connect.command("label")
@click.argument("edge_id")
@click.argument("label")
@click.option("--page", type=int, default=0, help="Page index")
@handle_error
def connect_label(edge_id, label, page):
    """Update a connector's label."""
    session = get_session()
    result = conn_mod.update_connector_label(session, edge_id, label, page)
    output(result, f"Updated label: {edge_id}")


@connect.command("style")
@click.argument("edge_id")
@click.argument("key")
@click.argument("value")
@click.option("--page", type=int, default=0, help="Page index")
@handle_error
def connect_style(edge_id, key, value, page):
    """Set a style property on a connector."""
    session = get_session()
    result = conn_mod.set_connector_style(session, edge_id, key, value, page)
    output(result, f"Style set: {key}={value}")


@connect.command("list")
@click.option("--page", type=int, default=0, help="Page index")
@handle_error
def connect_list(page):
    """List all connectors on a page."""
    session = get_session()
    result = conn_mod.list_connectors(session, page)
    output(result, f"Connectors ({len(result)}):")


@connect.command("styles")
@handle_error
def connect_styles():
    """List available edge styles."""
    result = conn_mod.list_edge_styles()
    output(result, "Edge styles:")


# ============================================================================
# Page commands
# ============================================================================

@cli.group()
def page():
    """Page operations: add, remove, rename, list."""
    pass


@page.command("add")
@click.option("--name", default="", help="Page name")
@click.option("--width", type=int, default=850, help="Page width")
@click.option("--height", type=int, default=1100, help="Page height")
@handle_error
def page_add(name, width, height):
    """Add a new page."""
    session = get_session()
    result = pages_mod.add_page(session, name, width, height)
    output(result, f"Added page: {result['name']}")


@page.command("remove")
@click.argument("page_index", type=int)
@handle_error
def page_remove(page_index):
    """Remove a page by index."""
    session = get_session()
    result = pages_mod.remove_page(session, page_index)
    output(result, f"Removed page {page_index}")


@page.command("rename")
@click.argument("page_index", type=int)
@click.argument("name")
@handle_error
def page_rename(page_index, name):
    """Rename a page."""
    session = get_session()
    result = pages_mod.rename_page(session, page_index, name)
    output(result, f"Renamed page {page_index} to: {name}")


@page.command("list")
@handle_error
def page_list():
    """List all pages."""
    session = get_session()
    result = pages_mod.list_pages(session)
    output(result, f"Pages ({len(result)}):")


# ============================================================================
# Export commands
# ============================================================================

@cli.group()
def export():
    """Export operations: render to PNG, PDF, SVG."""
    pass


@export.command("render")
@click.argument("output_path")
@click.option("--format", "-f", "fmt", default="png",
              type=click.Choice(["png", "pdf", "svg", "vsdx", "xml"]),
              help="Output format")
@click.option("--page", "page_index", type=int, default=None, help="Page index to export")
@click.option("--scale", type=float, default=None, help="Scale factor")
@click.option("--width", type=int, default=None, help="Output width (PNG)")
@click.option("--height", type=int, default=None, help="Output height (PNG)")
@click.option("--transparent", is_flag=True, help="Transparent background (PNG)")
@click.option("--crop", is_flag=True, help="Crop to content")
@click.option("--overwrite", is_flag=True, help="Overwrite existing file")
@handle_error
def export_render(output_path, fmt, page_index, scale, width, height,
                  transparent, crop, overwrite):
    """Export the diagram to a file."""
    session = get_session()
    result = export_mod.render_or_save(
        session, output_path, fmt,
        page_index=page_index, scale=scale,
        width=width, height=height,
        transparent=transparent, crop=crop,
        overwrite=overwrite,
    )
    output(result, f"Exported to: {result.get('output', result.get('drawio_file', ''))}")


@export.command("formats")
@handle_error
def export_formats():
    """List available export formats."""
    result = export_mod.list_formats()
    output(result, "Export formats:")


# ============================================================================
# Session commands
# ============================================================================

@cli.group()
def session():
    """Session management: status, undo, redo."""
    pass


@session.command("status")
@handle_error
def session_status():
    """Show current session status."""
    s = get_session()
    result = s.status()
    output(result, "Session status:")


@session.command("undo")
@handle_error
def session_undo():
    """Undo the last operation."""
    s = get_session()
    if s.undo():
        output({"action": "undo", "success": True}, "Undo successful")
    else:
        output({"action": "undo", "success": False}, "Nothing to undo")


@session.command("redo")
@handle_error
def session_redo():
    """Redo the last undone operation."""
    s = get_session()
    if s.redo():
        output({"action": "redo", "success": True}, "Redo successful")
    else:
        output({"action": "redo", "success": False}, "Nothing to redo")


@session.command("save-state")
@handle_error
def session_save():
    """Save session state to disk."""
    s = get_session()
    path = s.save_session_state()
    output({"action": "save_session", "path": path}, f"Session saved: {path}")


@session.command("list")
@handle_error
def session_list():
    """List all saved sessions."""
    sessions = Session.list_sessions()
    output(sessions, f"Sessions ({len(sessions)}):")


# ============================================================================
# REPL (Interactive mode)
# ============================================================================

@cli.command()
@click.option("--project", "project_path", default=None,
              help="Open a project on start")
def repl(project_path):
    """Start an interactive REPL session."""
    global _repl_mode
    _repl_mode = True

    s = get_session()
    if project_path:
        s.open_project(project_path)

    from cli_anything.drawio.utils.repl_skin import ReplSkin
    skin = ReplSkin("drawio", version="1.0.0")
    skin.print_banner()

    if project_path:
        skin.info(f"Opened: {project_path}")
        print()

    try:
        _run_repl(s, skin)
    except (KeyboardInterrupt, EOFError):
        skin.print_goodbye()

    _repl_mode = False


REPL_COMMANDS = {
    "help": "Show this help",
    "status": "Show session status",
    "new [preset]": "Create new diagram (letter, a4, 16:9, ...)",
    "open <path>": "Open a .drawio file",
    "save [path]": "Save the project",
    "info": "Show project info",
    "xml": "Print raw XML",
    "add <type> [label]": "Add shape (rectangle, ellipse, diamond, ...)",
    "remove <id>": "Remove a shape or connector",
    "shapes": "List all shapes",
    "label <id> <text>": "Update shape label",
    "move <id> <x> <y>": "Move a shape",
    "resize <id> <w> <h>": "Resize a shape",
    "style <id> <key> <val>": "Set style property",
    "connect <src> <tgt> [style]": "Add connector",
    "connectors": "List all connectors",
    "pages": "List all pages",
    "addpage [name]": "Add a new page",
    "export <path> [format]": "Export diagram (png, pdf, svg)",
    "undo": "Undo last operation",
    "redo": "Redo last undone operation",
    "quit": "Exit the REPL",
}


def _run_repl(s: Session, skin):
    """Run the interactive REPL loop."""
    pt_session = skin.create_prompt_session()

    while True:
        proj_name = ""
        if s.project_path:
            proj_name = os.path.basename(s.project_path)
        elif s.is_open:
            proj_name = "(unsaved)"
        modified = s.is_modified

        try:
            line = skin.get_input(pt_session, project_name=proj_name,
                                  modified=modified).strip()
        except (KeyboardInterrupt, EOFError):
            skin.print_goodbye()
            break

        if not line:
            continue

        parts = line.split()
        cmd = parts[0].lower()
        args = parts[1:]

        try:
            if cmd in ("quit", "exit", "q"):
                skin.print_goodbye()
                break
            elif cmd == "help":
                skin.help(REPL_COMMANDS)
            elif cmd == "status":
                result = s.status()
                _print_dict(result)
            elif cmd == "new":
                preset = args[0] if args else "letter"
                result = proj_mod.new_project(s, preset)
                skin.success(f"Created new diagram ({result['page_size']})")
            elif cmd == "open":
                if not args:
                    skin.error("Usage: open <path>")
                    continue
                result = proj_mod.open_project(s, args[0])
                skin.success(f"Opened: {args[0]}")
            elif cmd == "save":
                path = args[0] if args else None
                result = proj_mod.save_project(s, path)
                skin.success(f"Saved to: {result['path']}")
            elif cmd == "info":
                result = proj_mod.project_info(s)
                _print_dict(result)
            elif cmd == "xml":
                if not s.is_open:
                    skin.error("No project is open")
                    continue
                from cli_anything.drawio.utils.drawio_xml import xml_to_string
                click.echo(xml_to_string(s.root))
            elif cmd == "add":
                shape_type = args[0] if args else "rectangle"
                label = " ".join(args[1:]) if len(args) > 1 else ""
                result = shapes_mod.add_shape(s, shape_type, label=label)
                skin.success(f"Added {shape_type}: {result['id']}")
            elif cmd == "remove":
                if not args:
                    skin.error("Usage: remove <id>")
                    continue
                from cli_anything.drawio.utils import drawio_xml
                cell = drawio_xml.find_cell_by_id(s.root, args[0])
                if cell is None:
                    skin.error(f"Cell not found: {args[0]}")
                    continue
                s.checkpoint()
                drawio_xml.remove_cell(s.root, args[0])
                skin.success(f"Removed: {args[0]}")
            elif cmd == "shapes":
                result = shapes_mod.list_shapes(s)
                for sh in result:
                    click.echo(f"  {sh['id']}: {sh.get('value', '')} ({sh['type']})")
                skin.info(f"Total: {len(result)} shapes")
            elif cmd == "label":
                if len(args) < 2:
                    skin.error("Usage: label <id> <text>")
                    continue
                result = shapes_mod.update_label(s, args[0], " ".join(args[1:]))
                skin.success(f"Updated label: {args[0]}")
            elif cmd == "move":
                if len(args) < 3:
                    skin.error("Usage: move <id> <x> <y>")
                    continue
                result = shapes_mod.move_shape(s, args[0], float(args[1]), float(args[2]))
                skin.success(f"Moved: {args[0]}")
            elif cmd == "resize":
                if len(args) < 3:
                    skin.error("Usage: resize <id> <width> <height>")
                    continue
                result = shapes_mod.resize_shape(s, args[0], float(args[1]), float(args[2]))
                skin.success(f"Resized: {args[0]}")
            elif cmd == "style":
                if len(args) < 3:
                    skin.error("Usage: style <id> <key> <value>")
                    continue
                result = shapes_mod.set_style(s, args[0], args[1], args[2])
                skin.success(f"Style set: {args[1]}={args[2]}")
            elif cmd == "connect":
                if len(args) < 2:
                    skin.error("Usage: connect <source_id> <target_id> [style]")
                    continue
                edge_style = args[2] if len(args) > 2 else "orthogonal"
                result = conn_mod.add_connector(s, args[0], args[1], edge_style)
                skin.success(f"Connected: {args[0]} → {args[1]} ({result['id']})")
            elif cmd == "connectors":
                result = conn_mod.list_connectors(s)
                for e in result:
                    click.echo(f"  {e['id']}: {e.get('source', '')} → {e.get('target', '')} {e.get('value', '')}")
                skin.info(f"Total: {len(result)} connectors")
            elif cmd == "pages":
                result = pages_mod.list_pages(s)
                for p in result:
                    click.echo(f"  [{p['index']}] {p['name']} ({p['cell_count']} cells)")
            elif cmd == "addpage":
                name = " ".join(args) if args else ""
                result = pages_mod.add_page(s, name)
                skin.success(f"Added page: {result['name']}")
            elif cmd == "export":
                if not args:
                    skin.error("Usage: export <path> [format]")
                    continue
                fmt = args[1] if len(args) > 1 else "png"
                result = export_mod.render_or_save(s, args[0], fmt, overwrite=True)
                skin.success(f"Exported to: {result.get('output', result.get('drawio_file', ''))}")
            elif cmd == "undo":
                if s.undo():
                    skin.success("Undo successful")
                else:
                    skin.warning("Nothing to undo")
            elif cmd == "redo":
                if s.redo():
                    skin.success("Redo successful")
                else:
                    skin.warning("Nothing to redo")
            else:
                skin.error(f"Unknown command: {cmd}. Type 'help' for available commands.")
        except Exception as e:
            skin.error(str(e))

def main():
    cli()


if __name__ == "__main__":
    main()
