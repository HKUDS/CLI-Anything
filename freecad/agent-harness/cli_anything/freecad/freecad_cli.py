#!/usr/bin/env python3
"""FreeCAD CLI — A stateful command-line interface for 3D parametric modeling.

This CLI provides parametric modeling capabilities using a JSON project format,
with Python script generation for execution via FreeCADCmd.

Usage:
    # Create a new project
    cli-anything-freecad project new -o my_part.json

    # Add a sketch
    cli-anything-freecad --project my_part.json sketch add-circle --radius 10

    # Add a pad (extrude)
    cli-anything-freecad --project my_part.json part pad --length 5

    # Export to STEP
    cli-anything-freecad --project my_part.json export render my_part.step --format step

    # Interactive REPL
    cli-anything-freecad
"""

import sys
import os
import json
import click
from typing import Optional

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cli_anything.freecad.core.session import Session
from cli_anything.freecad.utils.repl_skin import ReplSkin
from cli_anything.freecad.utils import freecad_backend

# Global session state
_session: Optional[Session] = None
_json_output = False
_repl_mode = False


def get_session(project_path: Optional[str] = None) -> Session:
    global _session
    if _session is None:
        _session = Session(project_path)
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
        except Exception as e:
            if _json_output:
                click.echo(json.dumps({"error": str(e), "type": type(e).__name__}))
            else:
                click.echo(f"Error: {e}", err=True)
            if not _repl_mode:
                sys.exit(1)
    return wrapper


@click.group(invoke_without_command=True)
@click.option("--project", "-p", type=click.Path(), help="Path to the JSON project file")
@click.option("--json", "json_out", is_flag=True, help="Output in JSON format for agents")
@click.pass_context
def cli(ctx, project, json_out):
    """FreeCAD CLI for AI Agents."""
    global _json_output, _repl_mode
    _json_output = json_out

    if ctx.invoked_subcommand is None:
        _repl_mode = True
        run_repl(project)
    else:
        # Load session if project path is provided
        get_session(project)


def run_repl(project_path: Optional[str] = None):
    """Run the interactive REPL."""
    session = get_session(project_path)
    skin = ReplSkin(
        name="cli-anything-freecad",
        version="0.1.0",
        description="FreeCAD CLI for AI Agents",
        prompt_prefix="freecad"
    )

    skin.print_banner()
    
    # Simple REPL loop (in a real scenario, this would use prompt-toolkit)
    while True:
        try:
            cmd_line = skin.get_input(session.project_path)
            if not cmd_line:
                continue
            if cmd_line.lower() in ("exit", "quit"):
                break
            
            # Execute command via click
            args = cmd_line.split()
            cli.main(args=args, standalone_mode=False)
            
        except (EOFError, KeyboardInterrupt):
            break
        except Exception as e:
            click.echo(f"Error: {e}")

    skin.print_goodbye()


# --- Project Commands ---

@cli.group()
def project():
    """Project management commands."""
    pass


@project.command(name="new")
@click.option("--output", "-o", "output_path", required=True, type=click.Path(), help="Path to save the new project")
@click.option("--name", "-n", default="Untitled", help="Project name")
@handle_error
def project_new(output_path, name):
    """Create a new FreeCAD project."""
    session = get_session()
    session.data["name"] = name
    session.save(output_path)
    output({"status": "created", "path": output_path}, f"Created new project: {output_path}")


@project.command(name="info")
@handle_error
def project_info():
    """Show current project info."""
    session = get_session()
    output(session.data)


# --- Sketch Commands ---

@cli.group()
def sketch():
    """Sketcher workbench commands."""
    pass


@sketch.command(name="add-circle")
@click.option("--center", "-c", default="0,0", help="Center point (x,y)")
@click.option("--radius", "-r", type=float, required=True, help="Circle radius")
@handle_error
def sketch_add_circle(center, radius):
    """Add a circle to the current sketch."""
    session = get_session()
    cx, cy = map(float, center.split(","))
    obj_id = session.add_object("circle", {"center": [cx, cy], "radius": radius})
    session.save()
    output({"id": obj_id, "type": "circle"}, f"Added circle (id: {obj_id})")


# --- Part Commands ---

@cli.group()
def part():
    """Part Design workbench commands."""
    pass


@part.command(name="pad")
@click.option("--length", "-l", type=float, required=True, help="Extrusion length")
@handle_error
def part_pad(length):
    """Extrude (pad) the current sketch."""
    session = get_session()
    obj_id = session.add_object("pad", {"length": length})
    session.save()
    output({"id": obj_id, "type": "pad"}, f"Added pad (id: {obj_id})")


# --- Export Commands ---

@cli.group()
def export():
    """Export and rendering commands."""
    pass


@export.command(name="render")
@click.option("--output", "-o", "output_path", required=True, type=click.Path(), help="Output file path")
@click.option("--format", "-f", default="step", type=click.Choice(["step", "stl", "obj", "png"]), help="Output format")
@handle_error
def export_render(output_path, format):
    """Render the project to a file via FreeCAD backend."""
    session = get_session()
    
    # Generate Python script for FreeCAD
    script = generate_freecad_script(session.data, output_path, format)
    
    # Execute via backend
    result = freecad_backend.execute_freecad_python(script)
    
    output({"status": "exported", "path": output_path}, f"Exported project to {output_path} via FreeCAD")


def generate_freecad_script(data: dict, output_path: str, format: str) -> str:
    """Generate a FreeCAD Python script from project data."""
    lines = [
        "import FreeCAD",
        "import Part",
        "import Sketcher",
        "import PartDesign",
        "",
        "doc = FreeCAD.newDocument('GeneratedPart')",
        ""
    ]
    
    # Very basic translation logic (for demonstration)
    for obj in data.get("objects", []):
        if obj["type"] == "circle":
            c = obj["params"]["center"]
            r = obj["params"]["radius"]
            lines.append(f"circle = Part.makeCircle({r}, FreeCAD.Vector({c[0]}, {c[1]}, 0))")
            lines.append(f"Part.show(circle)")
        elif obj["type"] == "pad":
            lines.append(f"# Pad logic would go here")
            
    # Export logic
    if format == "step":
        lines.append(f"import ImportGui")
        lines.append(f"Part.export(doc.Objects, '{output_path.replace(os.sep, '/')}')")
    elif format == "png":
        lines.append(f"# Rendering PNG would require GUI or Offscreen renderer")
        
    return "\n".join(lines)


def main():
    cli()


if __name__ == "__main__":
    main()
