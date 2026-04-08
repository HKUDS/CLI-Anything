#!/usr/bin/env python3
"""cli-anything-freecad — CLI harness for FreeCAD parametric 3D CAD modeler.

Provides stateful CLI and REPL interface for creating, modifying, and exporting
FreeCAD 3D models without a GUI. Designed for AI agent consumption.
"""

from __future__ import annotations

import json
import os
import sys
from functools import wraps
from typing import Any, Optional

import click

from cli_anything.freecad.core import (
    document as doc_mod,
    parts as parts_mod,
    sketch as sketch_mod,
    body as body_mod,
    materials as mat_mod,
    export as export_mod,
    measure as measure_mod,
    spreadsheet as spread_mod,
    mesh as mesh_mod,
    draft as draft_mod,
    surface as surface_mod,
    import_mod as import_mod,
    assembly as asm_mod,
    techdraw as td_mod,
    fem as fem_mod,
    cam as cam_mod,
)
from cli_anything.freecad.core.session import Session

# ── Global state ─────────────────────────────────────────────────────

_session: Optional[Session] = None
_json_output: bool = False
_repl_mode: bool = False


def get_session() -> Session:
    """Get or create the global session."""
    global _session
    if _session is None:
        _session = Session()
    return _session


# ── Output helpers ───────────────────────────────────────────────────

def output(data: Any, message: str = "") -> None:
    """Print data as JSON or human-readable."""
    if _json_output:
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        if message:
            click.echo(message)
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, (dict, list)):
                    click.echo(f"  {k}: {json.dumps(v, default=str)}")
                else:
                    click.echo(f"  {k}: {v}")
        elif isinstance(data, list):
            for i, item in enumerate(data):
                if isinstance(item, dict):
                    label = item.get("name", item.get("type", f"#{i}"))
                    click.echo(f"  [{i}] {label}")
                    for k, v in item.items():
                        if k != "name":
                            click.echo(f"      {k}: {v}")
                else:
                    click.echo(f"  [{i}] {item}")


def handle_error(f):
    """Decorator to handle errors gracefully in CLI and REPL modes."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except (FileNotFoundError, ValueError, IndexError,
                RuntimeError, FileExistsError, KeyError, TypeError) as e:
            if _json_output:
                click.echo(json.dumps({"error": str(e)}, indent=2), err=True)
            else:
                click.echo(f"Error: {e}", err=True)
            if not _repl_mode:
                sys.exit(1)
    return wrapper


# ── Argument parsing helpers ─────────────────────────────────────────

def _parse_vec3(s: str) -> list[float]:
    """Parse 'x,y,z' string to [float, float, float]."""
    parts = s.split(",")
    if len(parts) != 3:
        raise ValueError(f"Expected x,y,z format, got: {s}")
    return [float(x.strip()) for x in parts]


def _parse_vec2(s: str) -> list[float]:
    """Parse 'x,y' string to [float, float]."""
    parts = s.split(",")
    if len(parts) != 2:
        raise ValueError(f"Expected x,y format, got: {s}")
    return [float(x.strip()) for x in parts]


def _parse_params(params: tuple) -> dict[str, float] | None:
    """Parse ('key=value', ...) to dict."""
    if not params:
        return None
    result = {}
    for p in params:
        if "=" not in p:
            raise ValueError(f"Param must be key=value, got: {p}")
        k, v = p.split("=", 1)
        result[k.strip()] = float(v.strip())
    return result


def _parse_indices(s: str) -> list[int]:
    """Parse comma-separated int list string '1,2,3' to [1, 2, 3]."""
    return [int(x.strip()) for x in s.split(",")]


def _parse_points(s: str) -> list[list[float]]:
    """Parse semicolon-separated points 'x,y,z;x,y,z;...' to list of vec3."""
    points = []
    for pt_str in s.split(";"):
        pt_str = pt_str.strip()
        if pt_str:
            points.append(_parse_vec3(pt_str))
    return points


def _parse_points_2d(s: str) -> list[list[float]]:
    """Parse semicolon-separated 2D points 'x,y;x,y;...' to list of vec2."""
    points = []
    for pt_str in s.split(";"):
        pt_str = pt_str.strip()
        if pt_str:
            points.append(_parse_vec2(pt_str))
    return points


def _parse_references(s: str) -> list:
    """Parse comma-separated references (ints or strings)."""
    refs = []
    for item in s.split(","):
        item = item.strip()
        try:
            refs.append(int(item))
        except ValueError:
            refs.append(item)
    return refs


# Use output_fn as alias for output to avoid collision with click.argument("output")
output_fn = output


# ── Main CLI group ───────────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, help="Output in JSON format.")
@click.option("--project", "-p", type=click.Path(), help="Load project file.")
@click.pass_context
def cli(ctx: click.Context, use_json: bool, project: Optional[str]) -> None:
    """cli-anything-freecad — CLI harness for FreeCAD 3D CAD modeler."""
    global _json_output
    _json_output = use_json

    if project:
        sess = get_session()
        proj = doc_mod.open_document(project)
        sess.set_project(proj, path=project)

        # Auto-save after one-shot commands when --project is used
        def _auto_save():
            if sess._modified and sess.project_path and not _repl_mode:
                sess.save_session()

        ctx.call_on_close(_auto_save)

    if ctx.invoked_subcommand is None:
        ctx.invoke(repl, project_path=project)


# ── Document commands ────────────────────────────────────────────────

@cli.group("document")
def document_group():
    """Document management commands."""
    pass


@document_group.command("new")
@click.option("--name", "-n", default="Untitled", help="Document name.")
@click.option("--units", "-u", default="mm", help="Units (mm, m, in).")
@click.option("--profile", help="Use a preset profile.")
@click.option("--output", "-o", type=click.Path(), help="Save to file.")
@handle_error
def document_new(name: str, units: str, profile: Optional[str],
                 output: Optional[str]) -> None:
    """Create a new FreeCAD document."""
    sess = get_session()
    proj = doc_mod.create_document(name=name, units=units, profile=profile)
    path = None
    if output:
        path = doc_mod.save_document(proj, output)
    sess.set_project(proj, path=path)
    result = doc_mod.get_document_info(proj)
    if path:
        result["saved_to"] = path
    output_fn(result, f"Created document: {name}")


@document_group.command("open")
@click.argument("path", type=click.Path(exists=True))
@handle_error
def document_open(path: str) -> None:
    """Open an existing document."""
    sess = get_session()
    proj = doc_mod.open_document(path)
    sess.set_project(proj, path=path)
    result = doc_mod.get_document_info(proj)
    output_fn(result, f"Opened: {path}")


@document_group.command("save")
@click.option("--output", "-o", type=click.Path(), help="Save to new path.")
@handle_error
def document_save(output: Optional[str]) -> None:
    """Save the current document."""
    sess = get_session()
    proj = sess.get_project()
    path = sess.save_session(path=output)
    result = {"saved_to": path}
    output_fn(result, f"Saved: {path}")


@document_group.command("info")
@handle_error
def document_info() -> None:
    """Show document information."""
    sess = get_session()
    proj = sess.get_project()
    result = doc_mod.get_document_info(proj)
    output_fn(result, "Document info:")


@document_group.command("profiles")
@handle_error
def document_profiles() -> None:
    """List available document profiles."""
    result = doc_mod.list_profiles()
    output_fn(result, "Available profiles:")


# ── Part commands ────────────────────────────────────────────────────

@cli.group("part")
def part_group():
    """3D part/primitive management commands."""
    pass


@part_group.command("add")
@click.argument("part_type", default="box")
@click.option("--name", "-n", help="Part name.")
@click.option("--position", "-pos", help="Position as x,y,z (e.g. 0,0,0).")
@click.option("--rotation", "-rot", help="Rotation as x,y,z degrees.")
@click.option("--param", "-P", multiple=True, help="Param as key=value.")
@handle_error
def part_add(part_type: str, name: Optional[str], position: Optional[str],
             rotation: Optional[str], param: tuple) -> None:
    """Add a 3D primitive part (box, cylinder, sphere, cone, torus, wedge, helix, spiral, thread)."""
    sess = get_session()
    sess.snapshot(f"Add part: {part_type}")
    proj = sess.get_project()

    pos = _parse_vec3(position) if position else None
    rot = _parse_vec3(rotation) if rotation else None
    params = _parse_params(param)

    result = parts_mod.add_part(proj, part_type=part_type, name=name,
                                position=pos, rotation=rot, params=params)
    output_fn(result, f"Added {part_type}: {result.get('name', '')}")


@part_group.command("remove")
@click.argument("index", type=int)
@handle_error
def part_remove(index: int) -> None:
    """Remove a part by index."""
    sess = get_session()
    sess.snapshot(f"Remove part #{index}")
    proj = sess.get_project()
    result = parts_mod.remove_part(proj, index)
    output_fn(result, f"Removed: {result.get('name', f'#{index}')}")


@part_group.command("list")
@handle_error
def part_list() -> None:
    """List all parts."""
    sess = get_session()
    proj = sess.get_project()
    result = parts_mod.list_parts(proj)
    output_fn(result, f"{len(result)} part(s):")


@part_group.command("get")
@click.argument("index", type=int)
@handle_error
def part_get(index: int) -> None:
    """Get details of a part by index."""
    sess = get_session()
    proj = sess.get_project()
    result = parts_mod.get_part(proj, index)
    output_fn(result, f"Part #{index}:")


@part_group.command("transform")
@click.argument("index", type=int)
@click.option("--position", "-pos", help="New position as x,y,z.")
@click.option("--rotation", "-rot", help="New rotation as x,y,z degrees.")
@handle_error
def part_transform(index: int, position: Optional[str],
                   rotation: Optional[str]) -> None:
    """Transform a part (position and/or rotation)."""
    sess = get_session()
    sess.snapshot(f"Transform part #{index}")
    proj = sess.get_project()
    pos = _parse_vec3(position) if position else None
    rot = _parse_vec3(rotation) if rotation else None
    result = parts_mod.transform_part(proj, index, position=pos, rotation=rot)
    output_fn(result, f"Transformed: {result.get('name', f'#{index}')}")


@part_group.command("boolean")
@click.argument("operation", type=click.Choice(["cut", "fuse", "common"]))
@click.argument("base_index", type=int)
@click.argument("tool_index", type=int)
@click.option("--name", "-n", help="Name for result.")
@handle_error
def part_boolean(operation: str, base_index: int, tool_index: int,
                 name: Optional[str]) -> None:
    """Perform boolean operation (cut, fuse, common) on two parts."""
    sess = get_session()
    sess.snapshot(f"Boolean {operation}: #{base_index} vs #{tool_index}")
    proj = sess.get_project()
    result = parts_mod.boolean_op(proj, operation, base_index, tool_index,
                                  name=name)
    output_fn(result, f"Boolean {operation}: {result.get('name', '')}")


@part_group.command("copy")
@click.argument("index", type=int)
@click.option("--name", "-n", help="Name for copy.")
@handle_error
def part_copy(index: int, name: Optional[str]) -> None:
    """Copy a part by index."""
    sess = get_session()
    sess.snapshot(f"Copy part #{index}")
    proj = sess.get_project()
    result = parts_mod.copy_part(proj, index, name=name)
    output_fn(result, f"Copied: {result.get('name', '')}")


@part_group.command("mirror")
@click.argument("index", type=int)
@click.option("--plane", default="XY", type=click.Choice(["XY", "XZ", "YZ"]),
              help="Mirror plane.")
@click.option("--name", "-n", help="Name for result.")
@handle_error
def part_mirror(index: int, plane: str, name: Optional[str]) -> None:
    """Create a mirrored copy of a part."""
    sess = get_session()
    sess.snapshot(f"Mirror part #{index}")
    proj = sess.get_project()
    result = parts_mod.mirror_part(proj, index, plane=plane, name=name)
    output_fn(result, f"Mirrored: {result.get('name', '')}")


@part_group.command("scale")
@click.argument("index", type=int)
@click.argument("factor", type=str)
@click.option("--name", "-n", help="Name for result.")
@handle_error
def part_scale(index: int, factor: str, name: Optional[str]) -> None:
    """Scale a part by a uniform factor or x,y,z factors."""
    sess = get_session()
    sess.snapshot(f"Scale part #{index}")
    proj = sess.get_project()
    if "," in factor:
        fac = _parse_vec3(factor)
    else:
        fac = float(factor)
    result = parts_mod.scale_part(proj, index, factor=fac, name=name)
    output_fn(result, f"Scaled: {result.get('name', '')}")


@part_group.command("offset")
@click.argument("index", type=int)
@click.argument("distance", type=float)
@click.option("--name", "-n", help="Name for result.")
@handle_error
def part_offset(index: int, distance: float, name: Optional[str]) -> None:
    """Create an offset shell of a part."""
    sess = get_session()
    sess.snapshot(f"Offset part #{index}")
    proj = sess.get_project()
    result = parts_mod.offset_shape(proj, index, distance=distance, name=name)
    output_fn(result, f"Offset: {result.get('name', '')}")


@part_group.command("thickness")
@click.argument("index", type=int)
@click.argument("thickness_val", type=float)
@click.option("--faces", default="all", help="Faces: 'all' or comma-sep indices.")
@click.option("--name", "-n", help="Name for result.")
@handle_error
def part_thickness(index: int, thickness_val: float, faces: str,
                   name: Optional[str]) -> None:
    """Hollow a solid by applying wall thickness."""
    sess = get_session()
    sess.snapshot(f"Thickness part #{index}")
    proj = sess.get_project()
    result = parts_mod.thickness_part(proj, index, thickness=thickness_val,
                                      faces=faces, name=name)
    output_fn(result, f"Thickness: {result.get('name', '')}")


@part_group.command("compound")
@click.argument("indices", type=str)
@click.option("--name", "-n", help="Name for compound.")
@handle_error
def part_compound(indices: str, name: Optional[str]) -> None:
    """Group parts into a compound (comma-separated indices)."""
    sess = get_session()
    sess.snapshot("Create compound")
    proj = sess.get_project()
    idx_list = _parse_indices(indices)
    result = parts_mod.compound_parts(proj, idx_list, name=name)
    output_fn(result, f"Compound: {result.get('name', '')}")


@part_group.command("explode")
@click.argument("index", type=int)
@handle_error
def part_explode(index: int) -> None:
    """Explode a compound into individual parts."""
    sess = get_session()
    sess.snapshot(f"Explode compound #{index}")
    proj = sess.get_project()
    result = parts_mod.explode_compound(proj, index)
    output_fn(result, f"Exploded {len(result)} part(s)")


@part_group.command("fillet-3d")
@click.argument("index", type=int)
@click.option("--radius", "-r", default=1.0, type=float, help="Fillet radius.")
@click.option("--edges", default="all", help="Edges: 'all' or comma-sep indices.")
@click.option("--name", "-n", help="Name for result.")
@handle_error
def part_fillet_3d(index: int, radius: float, edges: str,
                   name: Optional[str]) -> None:
    """Apply a 3D fillet to a part."""
    sess = get_session()
    sess.snapshot(f"Fillet-3d part #{index}")
    proj = sess.get_project()
    result = parts_mod.fillet_3d(proj, index, radius=radius, edges=edges, name=name)
    output_fn(result, f"Fillet-3D: {result.get('name', '')}")


@part_group.command("chamfer-3d")
@click.argument("index", type=int)
@click.option("--size", "-s", default=1.0, type=float, help="Chamfer size.")
@click.option("--edges", default="all", help="Edges: 'all' or comma-sep indices.")
@click.option("--name", "-n", help="Name for result.")
@handle_error
def part_chamfer_3d(index: int, size: float, edges: str,
                    name: Optional[str]) -> None:
    """Apply a 3D chamfer to a part."""
    sess = get_session()
    sess.snapshot(f"Chamfer-3d part #{index}")
    proj = sess.get_project()
    result = parts_mod.chamfer_3d(proj, index, size=size, edges=edges, name=name)
    output_fn(result, f"Chamfer-3D: {result.get('name', '')}")


@part_group.command("loft")
@click.argument("section_indices", type=str)
@click.option("--solid/--no-solid", default=True, help="Create solid.")
@click.option("--ruled", is_flag=True, help="Use ruled surfaces.")
@click.option("--name", "-n", help="Name for result.")
@handle_error
def part_loft(section_indices: str, solid: bool, ruled: bool,
              name: Optional[str]) -> None:
    """Loft through cross-section parts (comma-separated indices)."""
    sess = get_session()
    sess.snapshot("Loft parts")
    proj = sess.get_project()
    idx_list = _parse_indices(section_indices)
    result = parts_mod.loft_parts(proj, idx_list, solid=solid, ruled=ruled, name=name)
    output_fn(result, f"Loft: {result.get('name', '')}")


@part_group.command("sweep")
@click.argument("profile_index", type=int)
@click.argument("path_index", type=int)
@click.option("--name", "-n", help="Name for result.")
@handle_error
def part_sweep(profile_index: int, path_index: int, name: Optional[str]) -> None:
    """Sweep a profile shape along a path."""
    sess = get_session()
    sess.snapshot("Sweep part")
    proj = sess.get_project()
    result = parts_mod.sweep_part(proj, profile_index, path_index, name=name)
    output_fn(result, f"Sweep: {result.get('name', '')}")


@part_group.command("revolve")
@click.argument("index", type=int)
@click.option("--axis", default="Z", type=click.Choice(["X", "Y", "Z"]),
              help="Revolution axis.")
@click.option("--angle", "-a", default=360.0, type=float, help="Angle in degrees.")
@click.option("--name", "-n", help="Name for result.")
@handle_error
def part_revolve(index: int, axis: str, angle: float, name: Optional[str]) -> None:
    """Revolve a part around an axis."""
    sess = get_session()
    sess.snapshot(f"Revolve part #{index}")
    proj = sess.get_project()
    result = parts_mod.revolve_part(proj, index, axis=axis, angle=angle, name=name)
    output_fn(result, f"Revolve: {result.get('name', '')}")


@part_group.command("extrude")
@click.argument("index", type=int)
@click.option("--direction", "-d", help="Direction as x,y,z.")
@click.option("--length", "-l", default=10.0, type=float, help="Extrusion length.")
@click.option("--name", "-n", help="Name for result.")
@handle_error
def part_extrude(index: int, direction: Optional[str], length: float,
                 name: Optional[str]) -> None:
    """Extrude a part along a direction."""
    sess = get_session()
    sess.snapshot(f"Extrude part #{index}")
    proj = sess.get_project()
    dir_vec = _parse_vec3(direction) if direction else None
    result = parts_mod.extrude_part(proj, index, direction=dir_vec, length=length,
                                    name=name)
    output_fn(result, f"Extrude: {result.get('name', '')}")


@part_group.command("section")
@click.argument("index", type=int)
@click.option("--plane", default="XY", type=click.Choice(["XY", "XZ", "YZ"]),
              help="Section plane.")
@click.option("--offset", default=0.0, type=float, help="Plane offset.")
@click.option("--name", "-n", help="Name for result.")
@handle_error
def part_section(index: int, plane: str, offset: float,
                 name: Optional[str]) -> None:
    """Create a cross-section of a part."""
    sess = get_session()
    sess.snapshot(f"Section part #{index}")
    proj = sess.get_project()
    result = parts_mod.section_part(proj, index, plane=plane, offset=offset, name=name)
    output_fn(result, f"Section: {result.get('name', '')}")


@part_group.command("slice")
@click.argument("index", type=int)
@click.option("--plane", default="XY", type=click.Choice(["XY", "XZ", "YZ"]),
              help="Slice plane.")
@click.option("--offset", default=0.0, type=float, help="Plane offset.")
@handle_error
def part_slice(index: int, plane: str, offset: float) -> None:
    """Slice a part into two halves."""
    sess = get_session()
    sess.snapshot(f"Slice part #{index}")
    proj = sess.get_project()
    result = parts_mod.slice_part(proj, index, plane=plane, offset=offset)
    output_fn(result, "Sliced part into two halves")


@part_group.command("line-3d")
@click.option("--start", "-s", default="0,0,0", help="Start point x,y,z.")
@click.option("--end", "-e", default="10,0,0", help="End point x,y,z.")
@click.option("--name", "-n", help="Part name.")
@handle_error
def part_line_3d(start: str, end: str, name: Optional[str]) -> None:
    """Add a 3D line (edge) between two points."""
    sess = get_session()
    sess.snapshot("Add line-3d")
    proj = sess.get_project()
    s = _parse_vec3(start)
    e = _parse_vec3(end)
    result = parts_mod.add_line_3d(proj, start=s, end=e, name=name)
    output_fn(result, f"Added line-3d: {result.get('name', '')}")


@part_group.command("wire")
@click.argument("points_str", type=str)
@click.option("--closed", is_flag=True, help="Close the wire.")
@click.option("--name", "-n", help="Part name.")
@handle_error
def part_wire(points_str: str, closed: bool, name: Optional[str]) -> None:
    """Add a wire from semicolon-separated x,y,z points."""
    sess = get_session()
    sess.snapshot("Add wire")
    proj = sess.get_project()
    pts = _parse_points(points_str)
    result = parts_mod.add_wire(proj, points=pts, closed=closed, name=name)
    output_fn(result, f"Added wire: {result.get('name', '')}")


@part_group.command("polygon-3d")
@click.option("--center", "-c", default="0,0,0", help="Center x,y,z.")
@click.option("--sides", default=6, type=int, help="Number of sides.")
@click.option("--radius", "-r", default=5.0, type=float, help="Radius.")
@click.option("--normal", default="0,0,1", help="Normal vector x,y,z.")
@click.option("--name", "-n", help="Part name.")
@handle_error
def part_polygon_3d(center: str, sides: int, radius: float, normal: str,
                    name: Optional[str]) -> None:
    """Add a regular polygon in 3D space."""
    sess = get_session()
    sess.snapshot("Add polygon-3d")
    proj = sess.get_project()
    c = _parse_vec3(center)
    n = _parse_vec3(normal)
    result = parts_mod.add_polygon_3d(proj, center=c, sides=sides, radius=radius,
                                      normal=n, name=name)
    output_fn(result, f"Added polygon-3d: {result.get('name', '')}")


@part_group.command("info")
@click.argument("index", type=int)
@handle_error
def part_info(index: int) -> None:
    """Get detailed information about a part."""
    sess = get_session()
    proj = sess.get_project()
    result = parts_mod.part_info(proj, index)
    output_fn(result, f"Part #{index} info:")


# ── Sketch commands ──────────────────────────────────────────────────

@cli.group("sketch")
def sketch_group():
    """2D sketch commands."""
    pass


@sketch_group.command("new")
@click.option("--name", "-n", help="Sketch name.")
@click.option("--plane", default="XY", type=click.Choice(["XY", "XZ", "YZ"]),
              help="Sketch plane.")
@click.option("--offset", default=0.0, type=float, help="Plane offset.")
@handle_error
def sketch_new(name: Optional[str], plane: str, offset: float) -> None:
    """Create a new sketch."""
    sess = get_session()
    sess.snapshot("New sketch")
    proj = sess.get_project()
    result = sketch_mod.create_sketch(proj, name=name, plane=plane, offset=offset)
    output_fn(result, f"Created sketch: {result.get('name', '')}")


@sketch_group.command("add-line")
@click.argument("sketch_index", type=int)
@click.option("--start", "-s", default="0,0", help="Start point x,y.")
@click.option("--end", "-e", default="10,0", help="End point x,y.")
@handle_error
def sketch_add_line(sketch_index: int, start: str, end: str) -> None:
    """Add a line to a sketch."""
    sess = get_session()
    sess.snapshot(f"Add line to sketch #{sketch_index}")
    proj = sess.get_project()
    s = _parse_vec2(start)
    e = _parse_vec2(end)
    result = sketch_mod.add_line(proj, sketch_index, start=s, end=e)
    output_fn(result, "Added line")


@sketch_group.command("add-circle")
@click.argument("sketch_index", type=int)
@click.option("--center", "-c", default="0,0", help="Center x,y.")
@click.option("--radius", "-r", default=5.0, type=float, help="Radius.")
@handle_error
def sketch_add_circle(sketch_index: int, center: str, radius: float) -> None:
    """Add a circle to a sketch."""
    sess = get_session()
    sess.snapshot(f"Add circle to sketch #{sketch_index}")
    proj = sess.get_project()
    c = _parse_vec2(center)
    result = sketch_mod.add_circle(proj, sketch_index, center=c, radius=radius)
    output_fn(result, "Added circle")


@sketch_group.command("add-rect")
@click.argument("sketch_index", type=int)
@click.option("--corner", "-c", default="0,0", help="Corner x,y.")
@click.option("--width", "-w", default=10.0, type=float, help="Width.")
@click.option("--height", "-h", default=10.0, type=float, help="Height.")
@handle_error
def sketch_add_rect(sketch_index: int, corner: str, width: float,
                    height: float) -> None:
    """Add a rectangle to a sketch."""
    sess = get_session()
    sess.snapshot(f"Add rectangle to sketch #{sketch_index}")
    proj = sess.get_project()
    c = _parse_vec2(corner)
    result = sketch_mod.add_rectangle(proj, sketch_index, corner=c,
                                      width=width, height=height)
    output_fn(result, "Added rectangle")


@sketch_group.command("add-arc")
@click.argument("sketch_index", type=int)
@click.option("--center", "-c", default="0,0", help="Center x,y.")
@click.option("--radius", "-r", default=5.0, type=float, help="Radius.")
@click.option("--start-angle", default=0.0, type=float, help="Start angle (deg).")
@click.option("--end-angle", default=90.0, type=float, help="End angle (deg).")
@handle_error
def sketch_add_arc(sketch_index: int, center: str, radius: float,
                   start_angle: float, end_angle: float) -> None:
    """Add an arc to a sketch."""
    sess = get_session()
    sess.snapshot(f"Add arc to sketch #{sketch_index}")
    proj = sess.get_project()
    c = _parse_vec2(center)
    result = sketch_mod.add_arc(proj, sketch_index, center=c, radius=radius,
                                start_angle=start_angle, end_angle=end_angle)
    output_fn(result, "Added arc")


@sketch_group.command("constrain")
@click.argument("sketch_index", type=int)
@click.argument("constraint_type")
@click.option("--elements", "-e", required=True, help="Element indices (comma-sep).")
@click.option("--value", "-v", type=float, help="Constraint value.")
@handle_error
def sketch_constrain(sketch_index: int, constraint_type: str,
                     elements: str, value: Optional[float]) -> None:
    """Add a constraint to a sketch."""
    sess = get_session()
    sess.snapshot(f"Add constraint to sketch #{sketch_index}")
    proj = sess.get_project()
    elems = [int(x.strip()) for x in elements.split(",")]
    result = sketch_mod.add_constraint(proj, sketch_index, constraint_type,
                                       elems, value=value)
    output_fn(result, f"Added constraint: {constraint_type}")


@sketch_group.command("close")
@click.argument("sketch_index", type=int)
@handle_error
def sketch_close(sketch_index: int) -> None:
    """Close/finalize a sketch."""
    sess = get_session()
    sess.snapshot(f"Close sketch #{sketch_index}")
    proj = sess.get_project()
    result = sketch_mod.close_sketch(proj, sketch_index)
    output_fn(result, "Sketch closed")


@sketch_group.command("list")
@handle_error
def sketch_list() -> None:
    """List all sketches."""
    sess = get_session()
    proj = sess.get_project()
    result = sketch_mod.list_sketches(proj)
    output_fn(result, f"{len(result)} sketch(es):")


@sketch_group.command("get")
@click.argument("index", type=int)
@handle_error
def sketch_get(index: int) -> None:
    """Get sketch details."""
    sess = get_session()
    proj = sess.get_project()
    result = sketch_mod.get_sketch(proj, index)
    output_fn(result, f"Sketch #{index}:")


@sketch_group.command("add-point")
@click.argument("sketch_index", type=int)
@click.option("--position", "-p", default="0,0", help="Position x,y.")
@handle_error
def sketch_add_point(sketch_index: int, position: str) -> None:
    """Add a point to a sketch."""
    sess = get_session()
    sess.snapshot(f"Add point to sketch #{sketch_index}")
    proj = sess.get_project()
    pos = _parse_vec2(position)
    result = sketch_mod.add_point(proj, sketch_index, position=pos)
    output_fn(result, "Added point")


@sketch_group.command("add-ellipse")
@click.argument("sketch_index", type=int)
@click.option("--center", "-c", default="0,0", help="Center x,y.")
@click.option("--major-radius", default=10.0, type=float, help="Semi-major axis.")
@click.option("--minor-radius", default=5.0, type=float, help="Semi-minor axis.")
@click.option("--angle", default=0.0, type=float, help="Rotation angle (deg).")
@handle_error
def sketch_add_ellipse(sketch_index: int, center: str, major_radius: float,
                       minor_radius: float, angle: float) -> None:
    """Add an ellipse to a sketch."""
    sess = get_session()
    sess.snapshot(f"Add ellipse to sketch #{sketch_index}")
    proj = sess.get_project()
    c = _parse_vec2(center)
    result = sketch_mod.add_ellipse(proj, sketch_index, center=c,
                                    major_radius=major_radius,
                                    minor_radius=minor_radius, angle=angle)
    output_fn(result, "Added ellipse")


@sketch_group.command("add-polygon")
@click.argument("sketch_index", type=int)
@click.option("--center", "-c", default="0,0", help="Center x,y.")
@click.option("--sides", default=6, type=int, help="Number of sides.")
@click.option("--radius", "-r", default=5.0, type=float, help="Radius.")
@handle_error
def sketch_add_polygon(sketch_index: int, center: str, sides: int,
                       radius: float) -> None:
    """Add a regular polygon to a sketch."""
    sess = get_session()
    sess.snapshot(f"Add polygon to sketch #{sketch_index}")
    proj = sess.get_project()
    c = _parse_vec2(center)
    result = sketch_mod.add_polygon_sketch(proj, sketch_index, center=c,
                                           sides=sides, radius=radius)
    output_fn(result, "Added polygon")


@sketch_group.command("add-bspline")
@click.argument("sketch_index", type=int)
@click.argument("points_str", type=str)
@click.option("--closed", is_flag=True, help="Close the B-spline.")
@handle_error
def sketch_add_bspline(sketch_index: int, points_str: str, closed: bool) -> None:
    """Add a B-spline to a sketch (semicolon-separated x,y points)."""
    sess = get_session()
    sess.snapshot(f"Add bspline to sketch #{sketch_index}")
    proj = sess.get_project()
    pts = _parse_points_2d(points_str)
    result = sketch_mod.add_bspline(proj, sketch_index, points=pts, closed=closed)
    output_fn(result, "Added B-spline")


@sketch_group.command("add-slot")
@click.argument("sketch_index", type=int)
@click.option("--center1", default="0,0", help="First center x,y.")
@click.option("--center2", default="10,0", help="Second center x,y.")
@click.option("--radius", "-r", default=2.0, type=float, help="Radius.")
@handle_error
def sketch_add_slot(sketch_index: int, center1: str, center2: str,
                    radius: float) -> None:
    """Add a slot (obround) shape to a sketch."""
    sess = get_session()
    sess.snapshot(f"Add slot to sketch #{sketch_index}")
    proj = sess.get_project()
    c1 = _parse_vec2(center1)
    c2 = _parse_vec2(center2)
    result = sketch_mod.add_slot(proj, sketch_index, center1=c1, center2=c2,
                                 radius=radius)
    output_fn(result, "Added slot")


@sketch_group.command("edit-element")
@click.argument("sketch_index", type=int)
@click.argument("elem_id", type=int)
@click.option("--param", "-P", multiple=True, help="Property as key=value.")
@handle_error
def sketch_edit_element(sketch_index: int, elem_id: int, param: tuple) -> None:
    """Edit a sketch element's properties."""
    sess = get_session()
    sess.snapshot(f"Edit element {elem_id} in sketch #{sketch_index}")
    proj = sess.get_project()
    props = {}
    for p in param:
        if "=" not in p:
            raise ValueError(f"Param must be key=value, got: {p}")
        k, v = p.split("=", 1)
        k = k.strip()
        v = v.strip()
        if k in ("start", "end", "center", "position"):
            props[k] = _parse_vec2(v)
        elif k == "radius":
            props[k] = float(v)
        else:
            try:
                props[k] = float(v)
            except ValueError:
                props[k] = v
    result = sketch_mod.edit_element(proj, sketch_index, elem_id, **props)
    output_fn(result, f"Edited element {elem_id}")


@sketch_group.command("remove-element")
@click.argument("sketch_index", type=int)
@click.argument("elem_id", type=int)
@handle_error
def sketch_remove_element(sketch_index: int, elem_id: int) -> None:
    """Remove an element from a sketch."""
    sess = get_session()
    sess.snapshot(f"Remove element {elem_id} from sketch #{sketch_index}")
    proj = sess.get_project()
    result = sketch_mod.remove_element(proj, sketch_index, elem_id)
    output_fn(result, f"Removed element {elem_id}")


@sketch_group.command("remove-constraint")
@click.argument("sketch_index", type=int)
@click.argument("constraint_id", type=int)
@handle_error
def sketch_remove_constraint(sketch_index: int, constraint_id: int) -> None:
    """Remove a constraint from a sketch."""
    sess = get_session()
    sess.snapshot(f"Remove constraint {constraint_id} from sketch #{sketch_index}")
    proj = sess.get_project()
    result = sketch_mod.remove_constraint(proj, sketch_index, constraint_id)
    output_fn(result, f"Removed constraint {constraint_id}")


@sketch_group.command("edit-constraint")
@click.argument("sketch_index", type=int)
@click.argument("constraint_id", type=int)
@click.option("--value", "-v", type=float, help="New constraint value.")
@handle_error
def sketch_edit_constraint(sketch_index: int, constraint_id: int,
                           value: Optional[float]) -> None:
    """Edit a constraint value."""
    sess = get_session()
    sess.snapshot(f"Edit constraint {constraint_id} in sketch #{sketch_index}")
    proj = sess.get_project()
    result = sketch_mod.edit_constraint(proj, sketch_index, constraint_id,
                                        value=value)
    output_fn(result, f"Edited constraint {constraint_id}")


@sketch_group.command("mirror")
@click.argument("sketch_index", type=int)
@click.option("--elements", "-e", required=True, help="Element IDs (comma-sep).")
@click.option("--axis-elem-id", required=True, type=int, help="Axis element ID.")
@handle_error
def sketch_mirror(sketch_index: int, elements: str, axis_elem_id: int) -> None:
    """Mirror elements about an axis element."""
    sess = get_session()
    sess.snapshot(f"Mirror elements in sketch #{sketch_index}")
    proj = sess.get_project()
    elem_ids = _parse_indices(elements)
    result = sketch_mod.mirror_elements(proj, sketch_index, elem_ids=elem_ids,
                                        axis_elem_id=axis_elem_id)
    output_fn(result, "Mirrored elements")


@sketch_group.command("offset")
@click.argument("sketch_index", type=int)
@click.option("--elements", "-e", required=True, help="Element IDs (comma-sep).")
@click.option("--distance", "-d", required=True, type=float, help="Offset distance.")
@handle_error
def sketch_offset(sketch_index: int, elements: str, distance: float) -> None:
    """Offset wire elements by a distance."""
    sess = get_session()
    sess.snapshot(f"Offset elements in sketch #{sketch_index}")
    proj = sess.get_project()
    elem_ids = _parse_indices(elements)
    result = sketch_mod.offset_wire(proj, sketch_index, elem_ids=elem_ids,
                                    distance=distance)
    output_fn(result, "Offset elements")


@sketch_group.command("trim")
@click.argument("sketch_index", type=int)
@click.argument("elem_id", type=int)
@click.option("--keep-side", default="start", type=click.Choice(["start", "end"]),
              help="Side to keep.")
@handle_error
def sketch_trim(sketch_index: int, elem_id: int, keep_side: str) -> None:
    """Trim a sketch element."""
    sess = get_session()
    sess.snapshot(f"Trim element {elem_id} in sketch #{sketch_index}")
    proj = sess.get_project()
    result = sketch_mod.trim_element(proj, sketch_index, elem_id,
                                     keep_side=keep_side)
    output_fn(result, f"Trimmed element {elem_id}")


@sketch_group.command("extend")
@click.argument("sketch_index", type=int)
@click.argument("elem_id", type=int)
@click.argument("target_elem_id", type=int)
@handle_error
def sketch_extend(sketch_index: int, elem_id: int, target_elem_id: int) -> None:
    """Extend a sketch element to a target element."""
    sess = get_session()
    sess.snapshot(f"Extend element {elem_id} in sketch #{sketch_index}")
    proj = sess.get_project()
    result = sketch_mod.extend_element(proj, sketch_index, elem_id,
                                       target_elem_id=target_elem_id)
    output_fn(result, f"Extended element {elem_id}")


@sketch_group.command("validate")
@click.argument("sketch_index", type=int)
@handle_error
def sketch_validate(sketch_index: int) -> None:
    """Validate a sketch for errors."""
    sess = get_session()
    proj = sess.get_project()
    result = sketch_mod.validate_sketch(proj, sketch_index)
    output_fn(result, "Sketch validation:")


@sketch_group.command("solve-status")
@click.argument("sketch_index", type=int)
@handle_error
def sketch_solve_status(sketch_index: int) -> None:
    """Show constraint solving status of a sketch."""
    sess = get_session()
    proj = sess.get_project()
    result = sketch_mod.solve_status(proj, sketch_index)
    output_fn(result, "Solve status:")


@sketch_group.command("set-construction")
@click.argument("sketch_index", type=int)
@click.argument("elem_id", type=int)
@click.option("--flag/--no-flag", default=True, help="Construction flag.")
@handle_error
def sketch_set_construction(sketch_index: int, elem_id: int, flag: bool) -> None:
    """Toggle construction geometry flag on an element."""
    sess = get_session()
    sess.snapshot(f"Set construction on element {elem_id}")
    proj = sess.get_project()
    result = sketch_mod.set_construction(proj, sketch_index, elem_id, flag=flag)
    output_fn(result, f"Set construction={flag} on element {elem_id}")


@sketch_group.command("project-external")
@click.argument("sketch_index", type=int)
@click.argument("part_index", type=int)
@click.option("--edge-ref", help="Edge reference (e.g. Edge1).")
@click.option("--mode", type=click.Choice(["projection", "reference"]),
              default="projection", help="Projection mode (FreeCAD 1.1).")
@handle_error
def sketch_project_external(sketch_index: int, part_index: int,
                            edge_ref: Optional[str], mode: str) -> None:
    """Project external geometry into a sketch."""
    sess = get_session()
    sess.snapshot(f"Project external into sketch #{sketch_index}")
    proj = sess.get_project()
    result = sketch_mod.project_external(proj, sketch_index, part_index,
                                         edge_ref=edge_ref, mode=mode)
    output_fn(result, "Projected external geometry")


@sketch_group.command("intersection")
@click.argument("sketch_index", type=int)
@click.argument("body_index", type=int)
@handle_error
def sketch_intersection(sketch_index, body_index):
    """Create external geometry from sketch-plane intersection (FreeCAD 1.1)."""
    sess = get_session()
    proj = sess.get_project()
    result = sketch_mod.intersection_external(proj, sketch_index, body_index)
    output_fn(result, "Intersection reference created.")


@sketch_group.command("add-external-face")
@click.argument("sketch_index", type=int)
@click.argument("part_index", type=int)
@click.option("--face-ref", required=True, help="Face reference string")
@handle_error
def sketch_add_external_face(sketch_index, part_index, face_ref):
    """Create external geometry from face selection (FreeCAD 1.1)."""
    sess = get_session()
    proj = sess.get_project()
    result = sketch_mod.add_external_from_face(proj, sketch_index, part_index, face_ref)
    output_fn(result, "Face reference created.")


# ── Body commands ────────────────────────────────────────────────────

@cli.group("body")
def body_group():
    """PartDesign body commands."""
    pass


@body_group.command("new")
@click.option("--name", "-n", help="Body name.")
@handle_error
def body_new(name: Optional[str]) -> None:
    """Create a new PartDesign body."""
    sess = get_session()
    sess.snapshot("New body")
    proj = sess.get_project()
    result = body_mod.create_body(proj, name=name)
    output_fn(result, f"Created body: {result.get('name', '')}")


@body_group.command("pad")
@click.argument("body_index", type=int)
@click.argument("sketch_index", type=int)
@click.option("--length", "-l", default=10.0, type=float, help="Pad length.")
@click.option("--symmetric", is_flag=True, help="Symmetric pad.")
@click.option("--reversed", "is_reversed", is_flag=True, help="Reverse direction.")
@handle_error
def body_pad(body_index: int, sketch_index: int, length: float,
             symmetric: bool, is_reversed: bool) -> None:
    """Add a pad (extrusion) feature to a body."""
    sess = get_session()
    sess.snapshot(f"Pad body #{body_index}")
    proj = sess.get_project()
    result = body_mod.pad(proj, body_index, sketch_index, length=length,
                          symmetric=symmetric, reversed=is_reversed)
    output_fn(result, "Added pad feature")


@body_group.command("pocket")
@click.argument("body_index", type=int)
@click.argument("sketch_index", type=int)
@click.option("--length", "-l", default=5.0, type=float, help="Pocket depth.")
@click.option("--symmetric", is_flag=True, help="Symmetric pocket.")
@click.option("--reversed", "is_reversed", is_flag=True, help="Reverse direction.")
@handle_error
def body_pocket(body_index: int, sketch_index: int, length: float,
                symmetric: bool, is_reversed: bool) -> None:
    """Add a pocket (cut extrusion) feature to a body."""
    sess = get_session()
    sess.snapshot(f"Pocket body #{body_index}")
    proj = sess.get_project()
    result = body_mod.pocket(proj, body_index, sketch_index, length=length,
                             symmetric=symmetric, reversed=is_reversed)
    output_fn(result, "Added pocket feature")


@body_group.command("fillet")
@click.argument("body_index", type=int)
@click.option("--radius", "-r", default=1.0, type=float, help="Fillet radius.")
@click.option("--edges", default="all", help="Edges: 'all' or comma-sep indices.")
@handle_error
def body_fillet(body_index: int, radius: float, edges: str) -> None:
    """Add a fillet feature to a body."""
    sess = get_session()
    sess.snapshot(f"Fillet body #{body_index}")
    proj = sess.get_project()
    edge_val = edges if edges == "all" else [int(x) for x in edges.split(",")]
    result = body_mod.fillet(proj, body_index, radius=radius, edges=edge_val)
    output_fn(result, "Added fillet feature")


@body_group.command("chamfer")
@click.argument("body_index", type=int)
@click.option("--size", "-s", default=1.0, type=float, help="Chamfer size.")
@click.option("--edges", default="all", help="Edges: 'all' or comma-sep indices.")
@handle_error
def body_chamfer(body_index: int, size: float, edges: str) -> None:
    """Add a chamfer feature to a body."""
    sess = get_session()
    sess.snapshot(f"Chamfer body #{body_index}")
    proj = sess.get_project()
    edge_val = edges if edges == "all" else [int(x) for x in edges.split(",")]
    result = body_mod.chamfer(proj, body_index, size=size, edges=edge_val)
    output_fn(result, "Added chamfer feature")


@body_group.command("revolution")
@click.argument("body_index", type=int)
@click.argument("sketch_index", type=int)
@click.option("--angle", "-a", default=360.0, type=float, help="Revolution angle.")
@click.option("--axis", default="Z", type=click.Choice(["X", "Y", "Z"]),
              help="Revolution axis.")
@click.option("--reversed", "is_reversed", is_flag=True, help="Reverse direction.")
@handle_error
def body_revolution(body_index: int, sketch_index: int, angle: float,
                    axis: str, is_reversed: bool) -> None:
    """Add a revolution feature to a body."""
    sess = get_session()
    sess.snapshot(f"Revolution body #{body_index}")
    proj = sess.get_project()
    result = body_mod.revolution(proj, body_index, sketch_index, angle=angle,
                                 axis=axis, reversed=is_reversed)
    output_fn(result, "Added revolution feature")


@body_group.command("list")
@handle_error
def body_list() -> None:
    """List all bodies."""
    sess = get_session()
    proj = sess.get_project()
    result = body_mod.list_bodies(proj)
    output_fn(result, f"{len(result)} body/bodies:")


@body_group.command("get")
@click.argument("index", type=int)
@handle_error
def body_get(index: int) -> None:
    """Get body details."""
    sess = get_session()
    proj = sess.get_project()
    result = body_mod.get_body(proj, index)
    output_fn(result, f"Body #{index}:")


@body_group.command("groove")
@click.argument("body_index", type=int)
@click.argument("sketch_index", type=int)
@click.option("--angle", "-a", default=360.0, type=float, help="Groove angle.")
@click.option("--axis", default="Z", type=click.Choice(["X", "Y", "Z"]),
              help="Revolution axis.")
@click.option("--reversed", "is_reversed", is_flag=True, help="Reverse direction.")
@handle_error
def body_groove(body_index: int, sketch_index: int, angle: float,
                axis: str, is_reversed: bool) -> None:
    """Add a groove (subtractive revolution) feature."""
    sess = get_session()
    sess.snapshot(f"Groove body #{body_index}")
    proj = sess.get_project()
    result = body_mod.groove(proj, body_index, sketch_index, angle=angle,
                             axis=axis, reversed=is_reversed)
    output_fn(result, "Added groove feature")


@body_group.command("additive-loft")
@click.argument("body_index", type=int)
@click.argument("sketch_indices", type=str)
@click.option("--solid/--no-solid", default=True, help="Create solid.")
@click.option("--ruled", is_flag=True, help="Use ruled surfaces.")
@handle_error
def body_additive_loft(body_index: int, sketch_indices: str,
                       solid: bool, ruled: bool) -> None:
    """Add an additive loft feature (comma-separated sketch indices)."""
    sess = get_session()
    sess.snapshot(f"Additive loft body #{body_index}")
    proj = sess.get_project()
    idx_list = _parse_indices(sketch_indices)
    result = body_mod.additive_loft(proj, body_index, sketch_indices=idx_list,
                                    solid=solid, ruled=ruled)
    output_fn(result, "Added additive loft")


@body_group.command("additive-pipe")
@click.argument("body_index", type=int)
@click.argument("profile_sketch_index", type=int)
@click.argument("path_sketch_index", type=int)
@handle_error
def body_additive_pipe(body_index: int, profile_sketch_index: int,
                       path_sketch_index: int) -> None:
    """Add an additive pipe (sweep) feature."""
    sess = get_session()
    sess.snapshot(f"Additive pipe body #{body_index}")
    proj = sess.get_project()
    result = body_mod.additive_pipe(proj, body_index, profile_sketch_index,
                                    path_sketch_index)
    output_fn(result, "Added additive pipe")


@body_group.command("additive-helix")
@click.argument("body_index", type=int)
@click.argument("sketch_index", type=int)
@click.option("--pitch", default=5.0, type=float, help="Helix pitch.")
@click.option("--height", default=20.0, type=float, help="Helix height.")
@click.option("--turns", type=float, help="Number of turns (overrides height).")
@handle_error
def body_additive_helix(body_index: int, sketch_index: int, pitch: float,
                        height: float, turns: Optional[float]) -> None:
    """Add an additive helix feature."""
    sess = get_session()
    sess.snapshot(f"Additive helix body #{body_index}")
    proj = sess.get_project()
    result = body_mod.additive_helix(proj, body_index, sketch_index, pitch=pitch,
                                     height=height, turns=turns)
    output_fn(result, "Added additive helix")


@body_group.command("subtractive-loft")
@click.argument("body_index", type=int)
@click.argument("sketch_indices", type=str)
@click.option("--solid/--no-solid", default=True, help="Create solid.")
@click.option("--ruled", is_flag=True, help="Use ruled surfaces.")
@handle_error
def body_subtractive_loft(body_index: int, sketch_indices: str,
                          solid: bool, ruled: bool) -> None:
    """Add a subtractive loft feature (comma-separated sketch indices)."""
    sess = get_session()
    sess.snapshot(f"Subtractive loft body #{body_index}")
    proj = sess.get_project()
    idx_list = _parse_indices(sketch_indices)
    result = body_mod.subtractive_loft(proj, body_index, sketch_indices=idx_list,
                                       solid=solid, ruled=ruled)
    output_fn(result, "Added subtractive loft")


@body_group.command("subtractive-pipe")
@click.argument("body_index", type=int)
@click.argument("profile_sketch_index", type=int)
@click.argument("path_sketch_index", type=int)
@handle_error
def body_subtractive_pipe(body_index: int, profile_sketch_index: int,
                          path_sketch_index: int) -> None:
    """Add a subtractive pipe (sweep cut) feature."""
    sess = get_session()
    sess.snapshot(f"Subtractive pipe body #{body_index}")
    proj = sess.get_project()
    result = body_mod.subtractive_pipe(proj, body_index, profile_sketch_index,
                                       path_sketch_index)
    output_fn(result, "Added subtractive pipe")


@body_group.command("subtractive-helix")
@click.argument("body_index", type=int)
@click.argument("sketch_index", type=int)
@click.option("--pitch", default=5.0, type=float, help="Helix pitch.")
@click.option("--height", default=20.0, type=float, help="Helix height.")
@click.option("--turns", type=float, help="Number of turns (overrides height).")
@handle_error
def body_subtractive_helix(body_index: int, sketch_index: int, pitch: float,
                           height: float, turns: Optional[float]) -> None:
    """Add a subtractive helix feature."""
    sess = get_session()
    sess.snapshot(f"Subtractive helix body #{body_index}")
    proj = sess.get_project()
    result = body_mod.subtractive_helix(proj, body_index, sketch_index, pitch=pitch,
                                        height=height, turns=turns)
    output_fn(result, "Added subtractive helix")


# -- Body: Additive primitives --

@body_group.command("additive-box")
@click.argument("body_index", type=int)
@click.option("--length", "-l", default=10.0, type=float)
@click.option("--width", "-w", default=10.0, type=float)
@click.option("--height", "-h", default=10.0, type=float)
@handle_error
def body_additive_box(body_index: int, length: float, width: float,
                      height: float) -> None:
    """Add an additive box primitive."""
    sess = get_session()
    sess.snapshot(f"Additive box body #{body_index}")
    proj = sess.get_project()
    result = body_mod.additive_box(proj, body_index, length=length, width=width,
                                   height=height)
    output_fn(result, "Added additive box")


@body_group.command("additive-cylinder")
@click.argument("body_index", type=int)
@click.option("--radius", "-r", default=5.0, type=float)
@click.option("--height", "-h", default=10.0, type=float)
@handle_error
def body_additive_cylinder(body_index: int, radius: float, height: float) -> None:
    """Add an additive cylinder primitive."""
    sess = get_session()
    sess.snapshot(f"Additive cylinder body #{body_index}")
    proj = sess.get_project()
    result = body_mod.additive_cylinder(proj, body_index, radius=radius, height=height)
    output_fn(result, "Added additive cylinder")


@body_group.command("additive-sphere")
@click.argument("body_index", type=int)
@click.option("--radius", "-r", default=5.0, type=float)
@handle_error
def body_additive_sphere(body_index: int, radius: float) -> None:
    """Add an additive sphere primitive."""
    sess = get_session()
    sess.snapshot(f"Additive sphere body #{body_index}")
    proj = sess.get_project()
    result = body_mod.additive_sphere(proj, body_index, radius=radius)
    output_fn(result, "Added additive sphere")


@body_group.command("additive-cone")
@click.argument("body_index", type=int)
@click.option("--radius1", default=5.0, type=float)
@click.option("--radius2", default=0.0, type=float)
@click.option("--height", "-h", default=10.0, type=float)
@handle_error
def body_additive_cone(body_index: int, radius1: float, radius2: float,
                       height: float) -> None:
    """Add an additive cone primitive."""
    sess = get_session()
    sess.snapshot(f"Additive cone body #{body_index}")
    proj = sess.get_project()
    result = body_mod.additive_cone(proj, body_index, radius1=radius1,
                                    radius2=radius2, height=height)
    output_fn(result, "Added additive cone")


@body_group.command("additive-torus")
@click.argument("body_index", type=int)
@click.option("--radius1", default=10.0, type=float)
@click.option("--radius2", default=2.0, type=float)
@handle_error
def body_additive_torus(body_index: int, radius1: float, radius2: float) -> None:
    """Add an additive torus primitive."""
    sess = get_session()
    sess.snapshot(f"Additive torus body #{body_index}")
    proj = sess.get_project()
    result = body_mod.additive_torus(proj, body_index, radius1=radius1,
                                     radius2=radius2)
    output_fn(result, "Added additive torus")


@body_group.command("additive-wedge")
@click.argument("body_index", type=int)
@click.option("--param", "-P", multiple=True, help="Wedge param as key=value.")
@handle_error
def body_additive_wedge(body_index: int, param: tuple) -> None:
    """Add an additive wedge primitive."""
    sess = get_session()
    sess.snapshot(f"Additive wedge body #{body_index}")
    proj = sess.get_project()
    params = _parse_params(param) or {}
    result = body_mod.additive_wedge(proj, body_index, **params)
    output_fn(result, "Added additive wedge")


# -- Body: Subtractive primitives --

@body_group.command("subtractive-box")
@click.argument("body_index", type=int)
@click.option("--length", "-l", default=10.0, type=float)
@click.option("--width", "-w", default=10.0, type=float)
@click.option("--height", "-h", default=10.0, type=float)
@handle_error
def body_subtractive_box(body_index: int, length: float, width: float,
                         height: float) -> None:
    """Add a subtractive box primitive."""
    sess = get_session()
    sess.snapshot(f"Subtractive box body #{body_index}")
    proj = sess.get_project()
    result = body_mod.subtractive_box(proj, body_index, length=length, width=width,
                                      height=height)
    output_fn(result, "Added subtractive box")


@body_group.command("subtractive-cylinder")
@click.argument("body_index", type=int)
@click.option("--radius", "-r", default=5.0, type=float)
@click.option("--height", "-h", default=10.0, type=float)
@handle_error
def body_subtractive_cylinder(body_index: int, radius: float,
                              height: float) -> None:
    """Add a subtractive cylinder primitive."""
    sess = get_session()
    sess.snapshot(f"Subtractive cylinder body #{body_index}")
    proj = sess.get_project()
    result = body_mod.subtractive_cylinder(proj, body_index, radius=radius,
                                           height=height)
    output_fn(result, "Added subtractive cylinder")


@body_group.command("subtractive-sphere")
@click.argument("body_index", type=int)
@click.option("--radius", "-r", default=5.0, type=float)
@handle_error
def body_subtractive_sphere(body_index: int, radius: float) -> None:
    """Add a subtractive sphere primitive."""
    sess = get_session()
    sess.snapshot(f"Subtractive sphere body #{body_index}")
    proj = sess.get_project()
    result = body_mod.subtractive_sphere(proj, body_index, radius=radius)
    output_fn(result, "Added subtractive sphere")


@body_group.command("subtractive-cone")
@click.argument("body_index", type=int)
@click.option("--radius1", default=5.0, type=float)
@click.option("--radius2", default=0.0, type=float)
@click.option("--height", "-h", default=10.0, type=float)
@handle_error
def body_subtractive_cone(body_index: int, radius1: float, radius2: float,
                          height: float) -> None:
    """Add a subtractive cone primitive."""
    sess = get_session()
    sess.snapshot(f"Subtractive cone body #{body_index}")
    proj = sess.get_project()
    result = body_mod.subtractive_cone(proj, body_index, radius1=radius1,
                                       radius2=radius2, height=height)
    output_fn(result, "Added subtractive cone")


@body_group.command("subtractive-torus")
@click.argument("body_index", type=int)
@click.option("--radius1", default=10.0, type=float)
@click.option("--radius2", default=2.0, type=float)
@handle_error
def body_subtractive_torus(body_index: int, radius1: float,
                           radius2: float) -> None:
    """Add a subtractive torus primitive."""
    sess = get_session()
    sess.snapshot(f"Subtractive torus body #{body_index}")
    proj = sess.get_project()
    result = body_mod.subtractive_torus(proj, body_index, radius1=radius1,
                                        radius2=radius2)
    output_fn(result, "Added subtractive torus")


@body_group.command("subtractive-wedge")
@click.argument("body_index", type=int)
@click.option("--param", "-P", multiple=True, help="Wedge param as key=value.")
@handle_error
def body_subtractive_wedge(body_index: int, param: tuple) -> None:
    """Add a subtractive wedge primitive."""
    sess = get_session()
    sess.snapshot(f"Subtractive wedge body #{body_index}")
    proj = sess.get_project()
    params = _parse_params(param) or {}
    result = body_mod.subtractive_wedge(proj, body_index, **params)
    output_fn(result, "Added subtractive wedge")


# -- Body: Dress-up features --

@body_group.command("draft-feature")
@click.argument("body_index", type=int)
@click.argument("angle", type=float)
@click.option("--faces", default="all", help="Faces: 'all' or comma-sep indices.")
@click.option("--pull-direction", help="Pull direction as x,y,z.")
@handle_error
def body_draft_feature(body_index: int, angle: float, faces: str,
                       pull_direction: Optional[str]) -> None:
    """Add a draft (taper) feature."""
    sess = get_session()
    sess.snapshot(f"Draft feature body #{body_index}")
    proj = sess.get_project()
    face_val = faces if faces == "all" else _parse_indices(faces)
    pd = _parse_vec3(pull_direction) if pull_direction else None
    result = body_mod.draft_feature(proj, body_index, angle=angle, faces=face_val,
                                    pull_direction=pd)
    output_fn(result, "Added draft feature")


@body_group.command("thickness-feature")
@click.argument("body_index", type=int)
@click.argument("thickness_val", type=float)
@click.option("--faces", default="all", help="Faces: 'all' or comma-sep indices.")
@click.option("--join", default="arc", type=click.Choice(["arc", "tangent", "intersection"]))
@handle_error
def body_thickness_feature(body_index: int, thickness_val: float,
                           faces: str, join: str) -> None:
    """Add a thickness (shell) feature."""
    sess = get_session()
    sess.snapshot(f"Thickness feature body #{body_index}")
    proj = sess.get_project()
    face_val = faces if faces == "all" else _parse_indices(faces)
    result = body_mod.thickness_feature(proj, body_index, thickness=thickness_val,
                                        faces=face_val, join=join)
    output_fn(result, "Added thickness feature")


@body_group.command("hole")
@click.argument("body_index", type=int)
@click.argument("sketch_index", type=int)
@click.option("--diameter", "-d", default=5.0, type=float, help="Hole diameter.")
@click.option("--depth", default=10.0, type=float, help="Hole depth.")
@click.option("--threaded", is_flag=True, help="Threaded hole.")
@click.option("--thread-pitch", type=float, help="Thread pitch.")
@click.option("--thread-standard", type=click.Choice(["metric", "BSW", "BSF", "BSP", "NPT"]),
              default="metric", help="Thread standard (FreeCAD 1.1).")
@click.option("--tapered", is_flag=True, help="Tapered hole (FreeCAD 1.1).")
@click.option("--taper-angle", type=float, default=None, help="Taper angle (FreeCAD 1.1).")
@handle_error
def body_hole(body_index: int, sketch_index: int, diameter: float,
              depth: float, threaded: bool, thread_pitch: Optional[float],
              thread_standard: str, tapered: bool,
              taper_angle: Optional[float]) -> None:
    """Add a hole feature to a body."""
    sess = get_session()
    sess.snapshot(f"Hole body #{body_index}")
    proj = sess.get_project()
    result = body_mod.hole_feature(proj, body_index, sketch_index,
                                   diameter=diameter, depth=depth,
                                   threaded=threaded, thread_pitch=thread_pitch,
                                   thread_standard=thread_standard,
                                   tapered=tapered, taper_angle=taper_angle)
    output_fn(result, "Added hole feature")


# -- Body: Pattern features --

@body_group.command("linear-pattern")
@click.argument("body_index", type=int)
@click.option("--direction", "-d", default="1,0,0", help="Direction as x,y,z.")
@click.option("--length", "-l", default=50.0, type=float, help="Pattern length.")
@click.option("--occurrences", default=3, type=int, help="Number of occurrences.")
@handle_error
def body_linear_pattern(body_index: int, direction: str, length: float,
                        occurrences: int) -> None:
    """Add a linear pattern feature."""
    sess = get_session()
    sess.snapshot(f"Linear pattern body #{body_index}")
    proj = sess.get_project()
    dir_vec = _parse_vec3(direction)
    result = body_mod.linear_pattern(proj, body_index, direction=dir_vec,
                                     length=length, occurrences=occurrences)
    output_fn(result, "Added linear pattern")


@body_group.command("polar-pattern")
@click.argument("body_index", type=int)
@click.option("--axis", default="Z", type=click.Choice(["X", "Y", "Z"]))
@click.option("--angle", "-a", default=360.0, type=float, help="Total angle.")
@click.option("--occurrences", default=6, type=int, help="Number of occurrences.")
@handle_error
def body_polar_pattern(body_index: int, axis: str, angle: float,
                       occurrences: int) -> None:
    """Add a polar pattern feature."""
    sess = get_session()
    sess.snapshot(f"Polar pattern body #{body_index}")
    proj = sess.get_project()
    result = body_mod.polar_pattern(proj, body_index, axis=axis, angle=angle,
                                    occurrences=occurrences)
    output_fn(result, "Added polar pattern")


@body_group.command("mirrored")
@click.argument("body_index", type=int)
@click.option("--plane", default="XY", type=click.Choice(["XY", "XZ", "YZ"]))
@handle_error
def body_mirrored(body_index: int, plane: str) -> None:
    """Add a mirrored feature."""
    sess = get_session()
    sess.snapshot(f"Mirrored body #{body_index}")
    proj = sess.get_project()
    result = body_mod.mirrored_feature(proj, body_index, plane=plane)
    output_fn(result, "Added mirrored feature")


@body_group.command("multi-transform")
@click.argument("body_index", type=int)
@click.argument("transforms_json", type=str)
@handle_error
def body_multi_transform(body_index: int, transforms_json: str) -> None:
    """Add a multi-transform feature (JSON array of transformations)."""
    sess = get_session()
    sess.snapshot(f"Multi-transform body #{body_index}")
    proj = sess.get_project()
    transforms = json.loads(transforms_json)
    result = body_mod.multi_transform(proj, body_index, transformations=transforms)
    output_fn(result, "Added multi-transform")


# -- Body: Datum features --

@body_group.command("datum-plane")
@click.argument("body_index", type=int)
@click.option("--offset", default=0.0, type=float, help="Offset from reference.")
@click.option("--reference", default="XY", type=click.Choice(["XY", "XZ", "YZ"]))
@click.option("--attachment-mode", type=str, default=None, help="Attachment mode (FreeCAD 1.1).")
@click.option("--attachment-refs", type=str, default=None,
              help="Comma-separated attachment references (FreeCAD 1.1).")
@handle_error
def body_datum_plane(body_index: int, offset: float, reference: str,
                     attachment_mode: Optional[str],
                     attachment_refs: Optional[str]) -> None:
    """Add a datum plane to a body."""
    sess = get_session()
    sess.snapshot(f"Datum plane body #{body_index}")
    proj = sess.get_project()
    att_refs = [r.strip() for r in attachment_refs.split(",")] if attachment_refs else None
    result = body_mod.datum_plane(proj, body_index, offset=offset, reference=reference,
                                  attachment_mode=attachment_mode,
                                  attachment_refs=att_refs)
    output_fn(result, "Added datum plane")


@body_group.command("datum-line")
@click.argument("body_index", type=int)
@click.option("--point", default="0,0,0", help="Base point x,y,z.")
@click.option("--direction", "-d", default="0,0,1", help="Direction x,y,z.")
@click.option("--attachment-mode", type=str, default=None, help="Attachment mode (FreeCAD 1.1).")
@click.option("--attachment-refs", type=str, default=None,
              help="Comma-separated attachment references (FreeCAD 1.1).")
@handle_error
def body_datum_line(body_index: int, point: str, direction: str,
                    attachment_mode: Optional[str],
                    attachment_refs: Optional[str]) -> None:
    """Add a datum line to a body."""
    sess = get_session()
    sess.snapshot(f"Datum line body #{body_index}")
    proj = sess.get_project()
    pt = _parse_vec3(point)
    d = _parse_vec3(direction)
    att_refs = [r.strip() for r in attachment_refs.split(",")] if attachment_refs else None
    result = body_mod.datum_line(proj, body_index, point=pt, direction=d,
                                 attachment_mode=attachment_mode,
                                 attachment_refs=att_refs)
    output_fn(result, "Added datum line")


@body_group.command("datum-point")
@click.argument("body_index", type=int)
@click.option("--position", "-p", default="0,0,0", help="Position x,y,z.")
@click.option("--attachment-mode", type=str, default=None, help="Attachment mode (FreeCAD 1.1).")
@click.option("--attachment-refs", type=str, default=None,
              help="Comma-separated attachment references (FreeCAD 1.1).")
@handle_error
def body_datum_point(body_index: int, position: str,
                     attachment_mode: Optional[str],
                     attachment_refs: Optional[str]) -> None:
    """Add a datum point to a body."""
    sess = get_session()
    sess.snapshot(f"Datum point body #{body_index}")
    proj = sess.get_project()
    pos = _parse_vec3(position)
    att_refs = [r.strip() for r in attachment_refs.split(",")] if attachment_refs else None
    result = body_mod.datum_point(proj, body_index, position=pos,
                                  attachment_mode=attachment_mode,
                                  attachment_refs=att_refs)
    output_fn(result, "Added datum point")


@body_group.command("shape-binder")
@click.argument("body_index", type=int)
@click.argument("source_body_index", type=int)
@click.option("--feature-ref", help="Feature reference in source body.")
@handle_error
def body_shape_binder(body_index: int, source_body_index: int,
                      feature_ref: Optional[str]) -> None:
    """Add a shape binder referencing geometry from another body."""
    sess = get_session()
    sess.snapshot(f"Shape binder body #{body_index}")
    proj = sess.get_project()
    result = body_mod.shape_binder(proj, body_index, source_body_index,
                                   feature_ref=feature_ref)
    output_fn(result, "Added shape binder")


@body_group.command("local-coordinate-system")
@click.argument("body_index", type=int)
@click.option("--position", default=None, help="Position as x,y,z")
@click.option("--x-axis", default=None, help="X axis direction as x,y,z")
@click.option("--y-axis", default=None, help="Y axis direction as x,y,z")
@click.option("--z-axis", default=None, help="Z axis direction as x,y,z")
@handle_error
def body_local_coordinate_system(body_index, position, x_axis, y_axis, z_axis):
    """Add a local coordinate system to a body (FreeCAD 1.1)."""
    sess = get_session()
    proj = sess.get_project()
    pos = _parse_vec3(position) if position else None
    xa = _parse_vec3(x_axis) if x_axis else None
    ya = _parse_vec3(y_axis) if y_axis else None
    za = _parse_vec3(z_axis) if z_axis else None
    result = body_mod.local_coordinate_system(proj, body_index, pos, xa, ya, za)
    output_fn(result, "Local coordinate system added.")


@body_group.command("toggle-freeze")
@click.argument("body_index", type=int)
@click.argument("feature_index", type=int)
@handle_error
def body_toggle_freeze(body_index, feature_index):
    """Toggle frozen state of a feature (FreeCAD 1.1)."""
    sess = get_session()
    proj = sess.get_project()
    result = body_mod.toggle_freeze(proj, body_index, feature_index)
    state = "frozen" if result.get("frozen") else "unfrozen"
    output_fn(result, f"Feature {feature_index} is now {state}.")


# ── Material commands ────────────────────────────────────────────────

@cli.group("material")
def material_group():
    """Material management commands."""
    pass


@material_group.command("create")
@click.option("--name", "-n", default="Material", help="Material name.")
@click.option("--preset", help="Use a material preset.")
@click.option("--color", help="Color as r,g,b,a (0.0-1.0).")
@click.option("--metallic", type=float, help="Metallic factor (0-1).")
@click.option("--roughness", type=float, help="Roughness factor (0-1).")
@handle_error
def material_create(name: str, preset: Optional[str], color: Optional[str],
                    metallic: Optional[float], roughness: Optional[float]) -> None:
    """Create a new material."""
    sess = get_session()
    sess.snapshot(f"Create material: {name}")
    proj = sess.get_project()
    c = [float(x) for x in color.split(",")] if color else None
    kwargs: dict[str, Any] = {"name": name}
    if preset:
        kwargs["preset"] = preset
    if c:
        kwargs["color"] = c
    if metallic is not None:
        kwargs["metallic"] = metallic
    if roughness is not None:
        kwargs["roughness"] = roughness
    result = mat_mod.create_material(proj, **kwargs)
    output_fn(result, f"Created material: {result.get('name', name)}")


@material_group.command("assign")
@click.argument("material_index", type=int)
@click.argument("part_index", type=int)
@handle_error
def material_assign(material_index: int, part_index: int) -> None:
    """Assign a material to a part."""
    sess = get_session()
    sess.snapshot(f"Assign material #{material_index} to part #{part_index}")
    proj = sess.get_project()
    result = mat_mod.assign_material(proj, material_index, part_index)
    output_fn(result, "Material assigned")


@material_group.command("list")
@handle_error
def material_list() -> None:
    """List all materials."""
    sess = get_session()
    proj = sess.get_project()
    result = mat_mod.list_materials(proj)
    output_fn(result, f"{len(result)} material(s):")


@material_group.command("get")
@click.argument("index", type=int)
@handle_error
def material_get(index: int) -> None:
    """Get material details."""
    sess = get_session()
    proj = sess.get_project()
    result = mat_mod.get_material(proj, index)
    output_fn(result, f"Material #{index}:")


@material_group.command("set")
@click.argument("index", type=int)
@click.argument("prop")
@click.argument("value")
@handle_error
def material_set(index: int, prop: str, value: str) -> None:
    """Set a material property."""
    sess = get_session()
    sess.snapshot(f"Set material #{index} {prop}")
    proj = sess.get_project()
    if prop == "color":
        val: Any = [float(x) for x in value.split(",")]
    elif prop in ("metallic", "roughness"):
        val = float(value)
    else:
        val = value
    mat_mod.set_material_property(proj, index, prop, val)
    result = mat_mod.get_material(proj, index)
    output_fn(result, f"Updated material #{index}")


@material_group.command("presets")
@handle_error
def material_presets() -> None:
    """List available material presets."""
    result = mat_mod.list_presets()
    output_fn(result, "Available presets:")


@material_group.command("import-material")
@click.argument("path", type=click.Path())
@handle_error
def material_import(path: str) -> None:
    """Import a material from a JSON file."""
    sess = get_session()
    sess.snapshot("Import material")
    proj = sess.get_project()
    result = mat_mod.import_material(proj, path)
    output_fn(result, f"Imported material: {result.get('name', '')}")


@material_group.command("export-material")
@click.argument("index", type=int)
@click.argument("path", type=click.Path())
@handle_error
def material_export(index: int, path: str) -> None:
    """Export a material to a JSON file."""
    sess = get_session()
    proj = sess.get_project()
    result = mat_mod.export_material(proj, index, path)
    output_fn(result, f"Exported: {result.get('path', path)}")


# ── Export commands ──────────────────────────────────────────────────

@cli.group("export")
def export_group():
    """Export and rendering commands."""
    pass


@export_group.command("render")
@click.argument("output_path", type=click.Path())
@click.option("--preset", "-p", default="step", help="Export preset.")
@click.option("--overwrite", is_flag=True, help="Overwrite existing file.")
@handle_error
def export_render(output_path: str, preset: str, overwrite: bool) -> None:
    """Export/render the project to a file."""
    sess = get_session()
    proj = sess.get_project()
    result = export_mod.export_project(proj, output_path, preset=preset,
                                       overwrite=overwrite)
    output_fn(result, f"Exported: {result.get('output', output_path)}")


@export_group.command("info")
@handle_error
def export_info() -> None:
    """Show export information for the current project."""
    sess = get_session()
    proj = sess.get_project()
    result = export_mod.get_export_info(proj)
    output_fn(result, "Export info:")


@export_group.command("presets")
@handle_error
def export_presets() -> None:
    """List available export presets."""
    result = export_mod.list_presets()
    output_fn(result, "Export presets:")


# ── Session commands ─────────────────────────────────────────────────

@cli.group("session")
def session_group():
    """Session management commands."""
    pass


@session_group.command("undo")
@handle_error
def session_undo() -> None:
    """Undo the last operation."""
    sess = get_session()
    desc = sess.undo()
    if desc:
        result = {"undone": desc}
        output_fn(result, f"Undone: {desc}")
    else:
        output_fn({"message": "Nothing to undo"}, "Nothing to undo")


@session_group.command("redo")
@handle_error
def session_redo() -> None:
    """Redo the last undone operation."""
    sess = get_session()
    desc = sess.redo()
    if desc:
        result = {"redone": desc}
        output_fn(result, f"Redone: {desc}")
    else:
        output_fn({"message": "Nothing to redo"}, "Nothing to redo")


@session_group.command("status")
@handle_error
def session_status() -> None:
    """Show session status."""
    sess = get_session()
    result = sess.status()
    output_fn(result, "Session status:")


@session_group.command("history")
@handle_error
def session_history() -> None:
    """Show undo history."""
    sess = get_session()
    result = sess.list_history()
    output_fn(result, f"{len(result)} history entries:")


# ── Measure commands ─────────────────────────────────────────────────

@cli.group("measure")
def measure_group():
    """Measurement and geometry analysis commands."""
    pass


@measure_group.command("distance")
@click.argument("index1", type=int)
@click.argument("index2", type=int)
@handle_error
def measure_distance(index1: int, index2: int) -> None:
    """Measure distance between two parts."""
    sess = get_session()
    proj = sess.get_project()
    result = measure_mod.measure_distance(proj, index1, index2)
    output_fn(result, f"Distance: {result.get('distance', 'N/A')}")


@measure_group.command("length")
@click.argument("index", type=int)
@click.option("--edge-ref", help="Edge reference (e.g. Edge1).")
@handle_error
def measure_length(index: int, edge_ref: Optional[str]) -> None:
    """Measure length of a part edge."""
    sess = get_session()
    proj = sess.get_project()
    result = measure_mod.measure_length(proj, index, edge_ref=edge_ref)
    output_fn(result, f"Length: {result.get('length', 'N/A')}")


@measure_group.command("angle")
@click.argument("index1", type=int)
@click.argument("index2", type=int)
@handle_error
def measure_angle(index1: int, index2: int) -> None:
    """Measure angle between two parts."""
    sess = get_session()
    proj = sess.get_project()
    result = measure_mod.measure_angle(proj, index1, index2)
    output_fn(result, f"Angle: {result.get('angle_deg', 'N/A')} deg")


@measure_group.command("area")
@click.argument("index", type=int)
@handle_error
def measure_area(index: int) -> None:
    """Measure surface area of a part."""
    sess = get_session()
    proj = sess.get_project()
    result = measure_mod.measure_area(proj, index)
    output_fn(result, f"Area: {result.get('area', 'N/A')}")


@measure_group.command("volume")
@click.argument("index", type=int)
@handle_error
def measure_volume(index: int) -> None:
    """Measure volume of a part."""
    sess = get_session()
    proj = sess.get_project()
    result = measure_mod.measure_volume(proj, index)
    output_fn(result, f"Volume: {result.get('volume', 'N/A')}")


@measure_group.command("radius")
@click.argument("index", type=int)
@handle_error
def measure_radius(index: int) -> None:
    """Measure radius of a cylindrical/spherical part."""
    sess = get_session()
    proj = sess.get_project()
    result = measure_mod.measure_radius(proj, index)
    output_fn(result, f"Radius: {result.get('radius', 'N/A')}")


@measure_group.command("diameter")
@click.argument("index", type=int)
@handle_error
def measure_diameter(index: int) -> None:
    """Measure diameter of a cylindrical/spherical part."""
    sess = get_session()
    proj = sess.get_project()
    result = measure_mod.measure_diameter(proj, index)
    output_fn(result, f"Diameter: {result.get('diameter', 'N/A')}")


@measure_group.command("position")
@click.argument("index", type=int)
@handle_error
def measure_position(index: int) -> None:
    """Get the position of a part."""
    sess = get_session()
    proj = sess.get_project()
    result = measure_mod.measure_position(proj, index)
    output_fn(result, f"Position: {result.get('position', 'N/A')}")


@measure_group.command("center-of-mass")
@click.argument("index", type=int)
@handle_error
def measure_center_of_mass(index: int) -> None:
    """Estimate center of mass of a part."""
    sess = get_session()
    proj = sess.get_project()
    result = measure_mod.measure_center_of_mass(proj, index)
    output_fn(result, f"Center of mass: {result.get('center_of_mass', 'N/A')}")


@measure_group.command("bounding-box")
@click.argument("index", type=int)
@handle_error
def measure_bounding_box(index: int) -> None:
    """Compute bounding box of a part."""
    sess = get_session()
    proj = sess.get_project()
    result = measure_mod.measure_bounding_box(proj, index)
    output_fn(result, "Bounding box:")


@measure_group.command("inertia")
@click.argument("index", type=int)
@handle_error
def measure_inertia(index: int) -> None:
    """Estimate principal moments of inertia."""
    sess = get_session()
    proj = sess.get_project()
    result = measure_mod.measure_inertia(proj, index)
    output_fn(result, "Inertia:")


@measure_group.command("check-geometry")
@click.argument("index", type=int)
@click.option("--include-valid", is_flag=True, help="Include valid shape entries in report.")
@click.option("--skip", default=None, type=str, help="Comma-separated part indices to skip.")
@handle_error
def measure_check_geometry(index: int, include_valid: bool, skip: Optional[str]) -> None:
    """Perform geometry validation on a part."""
    sess = get_session()
    proj = sess.get_project()
    skip_list = [int(x.strip()) for x in skip.split(",")] if skip else None
    result = measure_mod.check_geometry(proj, index, include_valid=include_valid,
                                        skip_objects=skip_list)
    output_fn(result, "Geometry check:")


# ── Spreadsheet commands ─────────────────────────────────────────────

@cli.group("spreadsheet")
def spreadsheet_group():
    """Spreadsheet commands."""
    pass


@spreadsheet_group.command("new")
@click.option("--name", "-n", help="Spreadsheet name.")
@handle_error
def spreadsheet_new(name: Optional[str]) -> None:
    """Create a new spreadsheet."""
    sess = get_session()
    sess.snapshot("New spreadsheet")
    proj = sess.get_project()
    result = spread_mod.create_spreadsheet(proj, name=name)
    output_fn(result, f"Created spreadsheet: {result.get('name', '')}")


@spreadsheet_group.command("set-cell")
@click.argument("sheet_index", type=int)
@click.argument("cell_ref", type=str)
@click.argument("value", type=str)
@handle_error
def spreadsheet_set_cell(sheet_index: int, cell_ref: str, value: str) -> None:
    """Set a cell value in a spreadsheet."""
    sess = get_session()
    sess.snapshot(f"Set cell {cell_ref} in sheet #{sheet_index}")
    proj = sess.get_project()
    # Try to parse as number
    try:
        val: Any = float(value)
        if val == int(val) and "." not in value:
            val = int(val)
    except ValueError:
        val = value
    result = spread_mod.set_cell(proj, sheet_index, cell_ref, val)
    output_fn(result, f"Set {cell_ref} = {val}")


@spreadsheet_group.command("get-cell")
@click.argument("sheet_index", type=int)
@click.argument("cell_ref", type=str)
@handle_error
def spreadsheet_get_cell(sheet_index: int, cell_ref: str) -> None:
    """Get a cell value from a spreadsheet."""
    sess = get_session()
    proj = sess.get_project()
    result = spread_mod.get_cell(proj, sheet_index, cell_ref)
    output_fn(result, f"{cell_ref}: {result.get('value', 'empty')}")


@spreadsheet_group.command("set-alias")
@click.argument("sheet_index", type=int)
@click.argument("cell_ref", type=str)
@click.argument("alias", type=str)
@handle_error
def spreadsheet_set_alias(sheet_index: int, cell_ref: str, alias: str) -> None:
    """Assign an alias to a cell."""
    sess = get_session()
    sess.snapshot(f"Set alias {alias} for {cell_ref}")
    proj = sess.get_project()
    result = spread_mod.set_alias(proj, sheet_index, cell_ref, alias)
    output_fn(result, f"Alias '{alias}' -> {cell_ref}")


@spreadsheet_group.command("import-csv")
@click.argument("sheet_index", type=int)
@click.argument("path", type=click.Path(exists=True))
@click.option("--start-cell", default="A1", help="Top-left cell for import.")
@handle_error
def spreadsheet_import_csv(sheet_index: int, path: str, start_cell: str) -> None:
    """Import CSV data into a spreadsheet."""
    sess = get_session()
    sess.snapshot(f"Import CSV into sheet #{sheet_index}")
    proj = sess.get_project()
    result = spread_mod.import_csv(proj, sheet_index, path, start_cell=start_cell)
    output_fn(result, f"Imported {result.get('rows_imported', 0)} rows")


@spreadsheet_group.command("export-csv")
@click.argument("sheet_index", type=int)
@click.argument("path", type=click.Path())
@handle_error
def spreadsheet_export_csv(sheet_index: int, path: str) -> None:
    """Export a spreadsheet to CSV."""
    sess = get_session()
    proj = sess.get_project()
    result = spread_mod.export_csv(proj, sheet_index, path)
    output_fn(result, f"Exported: {result.get('path', path)}")


@spreadsheet_group.command("list")
@handle_error
def spreadsheet_list() -> None:
    """List all spreadsheets."""
    sess = get_session()
    proj = sess.get_project()
    result = spread_mod.list_spreadsheets(proj)
    output_fn(result, f"{len(result)} spreadsheet(s):")


# ── Mesh commands ────────────────────────────────────────────────────

@cli.group("mesh")
def mesh_group():
    """Mesh operations commands."""
    pass


@mesh_group.command("import")
@click.argument("path", type=click.Path())
@click.option("--name", "-n", help="Mesh name.")
@handle_error
def mesh_import(path: str, name: Optional[str]) -> None:
    """Import a mesh file."""
    sess = get_session()
    sess.snapshot("Import mesh")
    proj = sess.get_project()
    result = mesh_mod.import_mesh(proj, path, name=name)
    output_fn(result, f"Imported mesh: {result.get('name', '')}")


@mesh_group.command("from-shape")
@click.argument("part_index", type=int)
@click.option("--name", "-n", help="Mesh name.")
@click.option("--max-length", type=float, help="Max edge length.")
@click.option("--deviation", default=0.1, type=float, help="Surface deviation.")
@handle_error
def mesh_from_shape(part_index: int, name: Optional[str],
                    max_length: Optional[float], deviation: float) -> None:
    """Tessellate a part into a mesh."""
    sess = get_session()
    sess.snapshot(f"Mesh from shape #{part_index}")
    proj = sess.get_project()
    result = mesh_mod.mesh_from_shape(proj, part_index, name=name,
                                      max_length=max_length, deviation=deviation)
    output_fn(result, f"Created mesh: {result.get('name', '')}")


@mesh_group.command("export")
@click.argument("mesh_index", type=int)
@click.argument("path", type=click.Path())
@click.option("--format", "fmt", default="stl", help="Export format.")
@handle_error
def mesh_export(mesh_index: int, path: str, fmt: str) -> None:
    """Export a mesh to file."""
    sess = get_session()
    proj = sess.get_project()
    result = mesh_mod.export_mesh(proj, mesh_index, path, format=fmt)
    output_fn(result, f"Export mesh: {result.get('path', path)}")


@mesh_group.command("info")
@click.argument("mesh_index", type=int)
@handle_error
def mesh_info(mesh_index: int) -> None:
    """Show mesh information."""
    sess = get_session()
    proj = sess.get_project()
    result = mesh_mod.mesh_info(proj, mesh_index)
    output_fn(result, f"Mesh #{mesh_index}:")


@mesh_group.command("analyze")
@click.argument("mesh_index", type=int)
@handle_error
def mesh_analyze(mesh_index: int) -> None:
    """Analyze a mesh."""
    sess = get_session()
    proj = sess.get_project()
    result = mesh_mod.analyze_mesh(proj, mesh_index)
    output_fn(result, "Mesh analysis:")


@mesh_group.command("check")
@click.argument("mesh_index", type=int)
@handle_error
def mesh_check(mesh_index: int) -> None:
    """Check a mesh for problems."""
    sess = get_session()
    proj = sess.get_project()
    result = mesh_mod.check_mesh(proj, mesh_index)
    output_fn(result, "Mesh check:")


@mesh_group.command("boolean")
@click.argument("op", type=click.Choice(["union", "difference", "intersection"]))
@click.argument("base_index", type=int)
@click.argument("tool_index", type=int)
@click.option("--name", "-n", help="Name for result.")
@handle_error
def mesh_boolean(op: str, base_index: int, tool_index: int,
                 name: Optional[str]) -> None:
    """Perform boolean operation on two meshes."""
    sess = get_session()
    sess.snapshot(f"Mesh boolean {op}")
    proj = sess.get_project()
    result = mesh_mod.mesh_boolean(proj, op, base_index, tool_index, name=name)
    output_fn(result, f"Mesh boolean {op}: {result.get('name', '')}")


@mesh_group.command("decimate")
@click.argument("mesh_index", type=int)
@click.option("--target-faces", default=1000, type=int, help="Target face count.")
@handle_error
def mesh_decimate(mesh_index: int, target_faces: int) -> None:
    """Decimate (simplify) a mesh."""
    sess = get_session()
    sess.snapshot(f"Decimate mesh #{mesh_index}")
    proj = sess.get_project()
    result = mesh_mod.decimate_mesh(proj, mesh_index, target_faces=target_faces)
    output_fn(result, "Decimated mesh")


@mesh_group.command("remesh")
@click.argument("mesh_index", type=int)
@click.option("--target-length", default=1.0, type=float, help="Target edge length.")
@handle_error
def mesh_remesh(mesh_index: int, target_length: float) -> None:
    """Remesh with uniform edge lengths."""
    sess = get_session()
    sess.snapshot(f"Remesh #{mesh_index}")
    proj = sess.get_project()
    result = mesh_mod.remesh_mesh(proj, mesh_index, target_length=target_length)
    output_fn(result, "Remeshed")


@mesh_group.command("smooth")
@click.argument("mesh_index", type=int)
@click.option("--iterations", default=3, type=int, help="Smoothing passes.")
@click.option("--factor", default=0.5, type=float, help="Smoothing factor (0-1).")
@handle_error
def mesh_smooth(mesh_index: int, iterations: int, factor: float) -> None:
    """Smooth a mesh."""
    sess = get_session()
    sess.snapshot(f"Smooth mesh #{mesh_index}")
    proj = sess.get_project()
    result = mesh_mod.smooth_mesh(proj, mesh_index, iterations=iterations,
                                  factor=factor)
    output_fn(result, "Smoothed mesh")


@mesh_group.command("repair")
@click.argument("mesh_index", type=int)
@handle_error
def mesh_repair(mesh_index: int) -> None:
    """Repair a mesh."""
    sess = get_session()
    sess.snapshot(f"Repair mesh #{mesh_index}")
    proj = sess.get_project()
    result = mesh_mod.repair_mesh(proj, mesh_index)
    output_fn(result, "Repaired mesh")


@mesh_group.command("fill-holes")
@click.argument("mesh_index", type=int)
@click.option("--max-hole-size", default=10, type=int, help="Max hole size (edges).")
@handle_error
def mesh_fill_holes(mesh_index: int, max_hole_size: int) -> None:
    """Fill holes in a mesh."""
    sess = get_session()
    sess.snapshot(f"Fill holes mesh #{mesh_index}")
    proj = sess.get_project()
    result = mesh_mod.fill_holes(proj, mesh_index, max_hole_size=max_hole_size)
    output_fn(result, "Filled holes")


@mesh_group.command("flip-normals")
@click.argument("mesh_index", type=int)
@handle_error
def mesh_flip_normals(mesh_index: int) -> None:
    """Flip all face normals."""
    sess = get_session()
    sess.snapshot(f"Flip normals mesh #{mesh_index}")
    proj = sess.get_project()
    result = mesh_mod.flip_normals(proj, mesh_index)
    output_fn(result, "Flipped normals")


@mesh_group.command("merge")
@click.argument("indices", type=str)
@click.option("--name", "-n", help="Name for merged mesh.")
@handle_error
def mesh_merge(indices: str, name: Optional[str]) -> None:
    """Merge multiple meshes (comma-separated indices)."""
    sess = get_session()
    sess.snapshot("Merge meshes")
    proj = sess.get_project()
    idx_list = _parse_indices(indices)
    result = mesh_mod.merge_meshes(proj, idx_list, name=name)
    output_fn(result, f"Merged mesh: {result.get('name', '')}")


@mesh_group.command("split")
@click.argument("mesh_index", type=int)
@handle_error
def mesh_split(mesh_index: int) -> None:
    """Split a mesh into disconnected components."""
    sess = get_session()
    sess.snapshot(f"Split mesh #{mesh_index}")
    proj = sess.get_project()
    result = mesh_mod.split_mesh(proj, mesh_index)
    output_fn(result, "Split mesh")


@mesh_group.command("to-shape")
@click.argument("mesh_index", type=int)
@click.option("--name", "-n", help="Name for resulting part.")
@handle_error
def mesh_to_shape(mesh_index: int, name: Optional[str]) -> None:
    """Convert a mesh to a solid shape."""
    sess = get_session()
    sess.snapshot(f"Mesh to shape #{mesh_index}")
    proj = sess.get_project()
    result = mesh_mod.mesh_to_shape(proj, mesh_index, name=name)
    output_fn(result, f"Converted: {result.get('name', '')}")


# ── Draft commands ───────────────────────────────────────────────────

@cli.group("draft")
def draft_group():
    """2D drafting commands."""
    pass


@draft_group.command("wire")
@click.argument("points_str", type=str)
@click.option("--closed", is_flag=True, help="Close the wire.")
@click.option("--name", "-n", help="Object name.")
@handle_error
def draft_wire(points_str: str, closed: bool, name: Optional[str]) -> None:
    """Create a wire from semicolon-separated x,y,z points."""
    sess = get_session()
    sess.snapshot("Draft wire")
    proj = sess.get_project()
    pts = _parse_points(points_str)
    result = draft_mod.draft_wire(proj, points=pts, closed=closed, name=name)
    output_fn(result, f"Created wire: {result.get('name', '')}")


@draft_group.command("rectangle")
@click.option("--length", "-l", default=10.0, type=float)
@click.option("--height", "-h", default=10.0, type=float)
@click.option("--name", "-n", help="Object name.")
@click.option("--position", "-pos", help="Position x,y,z.")
@handle_error
def draft_rectangle(length: float, height: float, name: Optional[str],
                    position: Optional[str]) -> None:
    """Create a 2D rectangle."""
    sess = get_session()
    sess.snapshot("Draft rectangle")
    proj = sess.get_project()
    pos = _parse_vec3(position) if position else None
    result = draft_mod.draft_rectangle(proj, length=length, height=height,
                                       name=name, position=pos)
    output_fn(result, f"Created rectangle: {result.get('name', '')}")


@draft_group.command("circle")
@click.option("--radius", "-r", default=5.0, type=float)
@click.option("--name", "-n", help="Object name.")
@click.option("--position", "-pos", help="Position x,y,z.")
@handle_error
def draft_circle(radius: float, name: Optional[str],
                 position: Optional[str]) -> None:
    """Create a 2D circle."""
    sess = get_session()
    sess.snapshot("Draft circle")
    proj = sess.get_project()
    pos = _parse_vec3(position) if position else None
    result = draft_mod.draft_circle(proj, radius=radius, name=name, position=pos)
    output_fn(result, f"Created circle: {result.get('name', '')}")


@draft_group.command("ellipse")
@click.option("--major-radius", default=10.0, type=float)
@click.option("--minor-radius", default=5.0, type=float)
@click.option("--name", "-n", help="Object name.")
@click.option("--position", "-pos", help="Position x,y,z.")
@handle_error
def draft_ellipse(major_radius: float, minor_radius: float,
                  name: Optional[str], position: Optional[str]) -> None:
    """Create a 2D ellipse."""
    sess = get_session()
    sess.snapshot("Draft ellipse")
    proj = sess.get_project()
    pos = _parse_vec3(position) if position else None
    result = draft_mod.draft_ellipse(proj, major_radius=major_radius,
                                     minor_radius=minor_radius, name=name,
                                     position=pos)
    output_fn(result, f"Created ellipse: {result.get('name', '')}")


@draft_group.command("polygon")
@click.option("--sides", default=6, type=int)
@click.option("--radius", "-r", default=5.0, type=float)
@click.option("--name", "-n", help="Object name.")
@click.option("--position", "-pos", help="Position x,y,z.")
@handle_error
def draft_polygon(sides: int, radius: float, name: Optional[str],
                  position: Optional[str]) -> None:
    """Create a regular polygon."""
    sess = get_session()
    sess.snapshot("Draft polygon")
    proj = sess.get_project()
    pos = _parse_vec3(position) if position else None
    result = draft_mod.draft_polygon(proj, sides=sides, radius=radius,
                                     name=name, position=pos)
    output_fn(result, f"Created polygon: {result.get('name', '')}")


@draft_group.command("bspline")
@click.argument("points_str", type=str)
@click.option("--closed", is_flag=True, help="Close the spline.")
@click.option("--name", "-n", help="Object name.")
@handle_error
def draft_bspline(points_str: str, closed: bool, name: Optional[str]) -> None:
    """Create a B-spline from semicolon-separated x,y,z points."""
    sess = get_session()
    sess.snapshot("Draft bspline")
    proj = sess.get_project()
    pts = _parse_points(points_str)
    result = draft_mod.draft_bspline(proj, points=pts, closed=closed, name=name)
    output_fn(result, f"Created B-spline: {result.get('name', '')}")


@draft_group.command("bezier")
@click.argument("points_str", type=str)
@click.option("--name", "-n", help="Object name.")
@handle_error
def draft_bezier(points_str: str, name: Optional[str]) -> None:
    """Create a Bezier curve from semicolon-separated x,y,z control points."""
    sess = get_session()
    sess.snapshot("Draft bezier")
    proj = sess.get_project()
    pts = _parse_points(points_str)
    result = draft_mod.draft_bezier(proj, points=pts, name=name)
    output_fn(result, f"Created Bezier: {result.get('name', '')}")


@draft_group.command("point")
@click.option("--point", "-p", default="0,0,0", help="Point x,y,z.")
@click.option("--name", "-n", help="Object name.")
@handle_error
def draft_point(point: str, name: Optional[str]) -> None:
    """Create a draft point."""
    sess = get_session()
    sess.snapshot("Draft point")
    proj = sess.get_project()
    pt = _parse_vec3(point)
    result = draft_mod.draft_point(proj, point=pt, name=name)
    output_fn(result, f"Created point: {result.get('name', '')}")


@draft_group.command("text")
@click.argument("text_content", type=str)
@click.option("--name", "-n", help="Object name.")
@click.option("--position", "-pos", help="Position x,y,z.")
@handle_error
def draft_text(text_content: str, name: Optional[str],
               position: Optional[str]) -> None:
    """Create a text annotation."""
    sess = get_session()
    sess.snapshot("Draft text")
    proj = sess.get_project()
    pos = _parse_vec3(position) if position else None
    result = draft_mod.draft_text(proj, text=text_content, name=name, position=pos)
    output_fn(result, f"Created text: {result.get('name', '')}")


@draft_group.command("shapestring")
@click.argument("text_content", type=str)
@click.argument("font_file", type=str)
@click.option("--size", default=10.0, type=float, help="Font size.")
@click.option("--name", "-n", help="Object name.")
@click.option("--relative-font-path", is_flag=True, help="Use relative font path.")
@handle_error
def draft_shapestring(text_content: str, font_file: str, size: float,
                      name: Optional[str], relative_font_path: bool) -> None:
    """Create a ShapeString."""
    sess = get_session()
    sess.snapshot("Draft shapestring")
    proj = sess.get_project()
    result = draft_mod.draft_shapestring(proj, text=text_content,
                                         font_file=font_file, size=size, name=name,
                                         font_path_relative=relative_font_path)
    output_fn(result, f"Created shapestring: {result.get('name', '')}")


@draft_group.command("dimension")
@click.option("--start", "-s", required=True, help="Start point x,y,z.")
@click.option("--end", "-e", required=True, help="End point x,y,z.")
@click.option("--dim-line", help="Dimension line point x,y,z.")
@click.option("--name", "-n", help="Object name.")
@handle_error
def draft_dimension(start: str, end: str, dim_line: Optional[str],
                    name: Optional[str]) -> None:
    """Create a linear dimension annotation."""
    sess = get_session()
    sess.snapshot("Draft dimension")
    proj = sess.get_project()
    s = _parse_vec3(start)
    e = _parse_vec3(end)
    dl = _parse_vec3(dim_line) if dim_line else None
    result = draft_mod.draft_dimension(proj, start=s, end=e, dim_line=dl, name=name)
    output_fn(result, f"Created dimension: {result.get('name', '')}")


@draft_group.command("label")
@click.argument("target_point", type=str)
@click.option("--text", "-t", default="", help="Label text.")
@click.option("--name", "-n", help="Object name.")
@handle_error
def draft_label(target_point: str, text: str, name: Optional[str]) -> None:
    """Create a label pointing to a target point (x,y,z)."""
    sess = get_session()
    sess.snapshot("Draft label")
    proj = sess.get_project()
    tp = _parse_vec3(target_point)
    result = draft_mod.draft_label(proj, target_point=tp, text=text, name=name)
    output_fn(result, f"Created label: {result.get('name', '')}")


@draft_group.command("hatch")
@click.argument("target_index", type=int)
@click.option("--pattern", default="ANSI31", help="Hatch pattern.")
@click.option("--scale", default=1.0, type=float, help="Pattern scale.")
@click.option("--name", "-n", help="Object name.")
@handle_error
def draft_hatch(target_index: int, pattern: str, scale: float,
                name: Optional[str]) -> None:
    """Apply a hatch pattern to a draft object."""
    sess = get_session()
    sess.snapshot("Draft hatch")
    proj = sess.get_project()
    result = draft_mod.draft_hatch(proj, target_index=target_index, pattern=pattern,
                                   scale=scale, name=name)
    output_fn(result, f"Created hatch: {result.get('name', '')}")


@draft_group.command("move")
@click.argument("index", type=int)
@click.argument("vector", type=str)
@click.option("--copy", is_flag=True, help="Create a moved copy.")
@handle_error
def draft_move(index: int, vector: str, copy: bool) -> None:
    """Move a draft object by a vector (x,y,z)."""
    sess = get_session()
    sess.snapshot(f"Draft move #{index}")
    proj = sess.get_project()
    vec = _parse_vec3(vector)
    result = draft_mod.draft_move(proj, index, vector=vec, copy=copy)
    output_fn(result, f"Moved: {result.get('name', '')}")


@draft_group.command("rotate")
@click.argument("index", type=int)
@click.argument("angle", type=float)
@click.option("--axis", help="Rotation axis x,y,z.")
@click.option("--center", help="Center of rotation x,y,z.")
@click.option("--copy", is_flag=True, help="Create a rotated copy.")
@handle_error
def draft_rotate(index: int, angle: float, axis: Optional[str],
                 center: Optional[str], copy: bool) -> None:
    """Rotate a draft object by angle degrees."""
    sess = get_session()
    sess.snapshot(f"Draft rotate #{index}")
    proj = sess.get_project()
    ax = _parse_vec3(axis) if axis else None
    ctr = _parse_vec3(center) if center else None
    result = draft_mod.draft_rotate(proj, index, angle=angle, axis=ax,
                                    center=ctr, copy=copy)
    output_fn(result, f"Rotated: {result.get('name', '')}")


@draft_group.command("scale")
@click.argument("index", type=int)
@click.argument("scale_factor", type=str)
@click.option("--center", help="Center of scaling x,y,z.")
@click.option("--copy", is_flag=True, help="Create a scaled copy.")
@handle_error
def draft_scale(index: int, scale_factor: str, center: Optional[str],
                copy: bool) -> None:
    """Scale a draft object."""
    sess = get_session()
    sess.snapshot(f"Draft scale #{index}")
    proj = sess.get_project()
    if "," in scale_factor:
        sf = _parse_vec3(scale_factor)
    else:
        sf = float(scale_factor)
    ctr = _parse_vec3(center) if center else None
    result = draft_mod.draft_scale(proj, index, scale=sf, center=ctr, copy=copy)
    output_fn(result, f"Scaled: {result.get('name', '')}")


@draft_group.command("mirror")
@click.argument("index", type=int)
@click.option("--point", help="Mirror reference point x,y,z.")
@click.option("--name", "-n", help="Name for mirrored copy.")
@handle_error
def draft_mirror(index: int, point: Optional[str], name: Optional[str]) -> None:
    """Create a mirrored copy of a draft object."""
    sess = get_session()
    sess.snapshot(f"Draft mirror #{index}")
    proj = sess.get_project()
    pt = _parse_vec3(point) if point else None
    result = draft_mod.draft_mirror(proj, index, point=pt, name=name)
    output_fn(result, f"Mirrored: {result.get('name', '')}")


@draft_group.command("offset")
@click.argument("index", type=int)
@click.option("--distance", "-d", default=1.0, type=float, help="Offset distance.")
@click.option("--copy/--no-copy", default=True, help="Create offset copy.")
@click.option("--name", "-n", help="Name for offset copy.")
@handle_error
def draft_offset(index: int, distance: float, copy: bool,
                 name: Optional[str]) -> None:
    """Offset a draft object."""
    sess = get_session()
    sess.snapshot(f"Draft offset #{index}")
    proj = sess.get_project()
    result = draft_mod.draft_offset(proj, index, distance=distance, copy=copy,
                                    name=name)
    output_fn(result, f"Offset: {result.get('name', '')}")


@draft_group.command("array-linear")
@click.argument("index", type=int)
@click.option("--x-count", default=2, type=int)
@click.option("--y-count", default=1, type=int)
@click.option("--x-interval", default=20.0, type=float)
@click.option("--y-interval", default=20.0, type=float)
@click.option("--name", "-n", help="Array name.")
@handle_error
def draft_array_linear(index: int, x_count: int, y_count: int,
                       x_interval: float, y_interval: float,
                       name: Optional[str]) -> None:
    """Create a linear array of a draft object."""
    sess = get_session()
    sess.snapshot(f"Draft linear array #{index}")
    proj = sess.get_project()
    result = draft_mod.draft_array_linear(proj, index, x_count=x_count,
                                          y_count=y_count, x_interval=x_interval,
                                          y_interval=y_interval, name=name)
    output_fn(result, f"Linear array: {result.get('name', '')}")


@draft_group.command("array-polar")
@click.argument("index", type=int)
@click.option("--count", default=6, type=int)
@click.option("--angle", default=360.0, type=float)
@click.option("--center", help="Center x,y,z.")
@click.option("--name", "-n", help="Array name.")
@handle_error
def draft_array_polar(index: int, count: int, angle: float,
                      center: Optional[str], name: Optional[str]) -> None:
    """Create a polar array of a draft object."""
    sess = get_session()
    sess.snapshot(f"Draft polar array #{index}")
    proj = sess.get_project()
    ctr = _parse_vec3(center) if center else None
    result = draft_mod.draft_array_polar(proj, index, count=count, angle=angle,
                                         center=ctr, name=name)
    output_fn(result, f"Polar array: {result.get('name', '')}")


@draft_group.command("array-path")
@click.argument("index", type=int)
@click.argument("path_index", type=int)
@click.option("--count", default=4, type=int)
@click.option("--name", "-n", help="Array name.")
@handle_error
def draft_array_path(index: int, path_index: int, count: int,
                     name: Optional[str]) -> None:
    """Create a path array of a draft object."""
    sess = get_session()
    sess.snapshot(f"Draft path array #{index}")
    proj = sess.get_project()
    result = draft_mod.draft_array_path(proj, index, path_index=path_index,
                                        count=count, name=name)
    output_fn(result, f"Path array: {result.get('name', '')}")


@draft_group.command("copy")
@click.argument("index", type=int)
@click.option("--name", "-n", help="Name for copy.")
@handle_error
def draft_copy(index: int, name: Optional[str]) -> None:
    """Copy a draft object."""
    sess = get_session()
    sess.snapshot(f"Draft copy #{index}")
    proj = sess.get_project()
    result = draft_mod.draft_copy(proj, index, name=name)
    output_fn(result, f"Copied: {result.get('name', '')}")


@draft_group.command("clone")
@click.argument("index", type=int)
@click.option("--name", "-n", help="Name for clone.")
@handle_error
def draft_clone(index: int, name: Optional[str]) -> None:
    """Create a clone (linked copy) of a draft object."""
    sess = get_session()
    sess.snapshot(f"Draft clone #{index}")
    proj = sess.get_project()
    result = draft_mod.draft_clone(proj, index, name=name)
    output_fn(result, f"Cloned: {result.get('name', '')}")


@draft_group.command("upgrade")
@click.argument("index", type=int)
@handle_error
def draft_upgrade(index: int) -> None:
    """Upgrade a draft object (e.g. wires -> face)."""
    sess = get_session()
    sess.snapshot(f"Draft upgrade #{index}")
    proj = sess.get_project()
    result = draft_mod.draft_upgrade(proj, index)
    output_fn(result, f"Upgraded: {result.get('name', '')}")


@draft_group.command("downgrade")
@click.argument("index", type=int)
@handle_error
def draft_downgrade(index: int) -> None:
    """Downgrade a draft object (e.g. face -> wires)."""
    sess = get_session()
    sess.snapshot(f"Draft downgrade #{index}")
    proj = sess.get_project()
    result = draft_mod.draft_downgrade(proj, index)
    output_fn(result, f"Downgraded: {result.get('name', '')}")


@draft_group.command("trim")
@click.argument("index", type=int)
@click.argument("point", type=str)
@handle_error
def draft_trim(index: int, point: str) -> None:
    """Trim a draft object at a point (x,y,z)."""
    sess = get_session()
    sess.snapshot(f"Draft trim #{index}")
    proj = sess.get_project()
    pt = _parse_vec3(point)
    result = draft_mod.draft_trim(proj, index, point=pt)
    output_fn(result, f"Trimmed: {result.get('name', '')}")


@draft_group.command("join")
@click.argument("indices", type=str)
@click.option("--name", "-n", help="Name for joined result.")
@handle_error
def draft_join(indices: str, name: Optional[str]) -> None:
    """Join multiple draft wires (comma-separated indices)."""
    sess = get_session()
    sess.snapshot("Draft join")
    proj = sess.get_project()
    idx_list = _parse_indices(indices)
    result = draft_mod.draft_join(proj, indices=idx_list, name=name)
    output_fn(result, f"Joined: {result.get('name', '')}")


@draft_group.command("extrude")
@click.argument("index", type=int)
@click.option("--vector", "-v", help="Extrusion vector x,y,z.")
@click.option("--name", "-n", help="Name for result.")
@handle_error
def draft_extrude(index: int, vector: Optional[str], name: Optional[str]) -> None:
    """Extrude a 2D draft object into 3D."""
    sess = get_session()
    sess.snapshot(f"Draft extrude #{index}")
    proj = sess.get_project()
    vec = _parse_vec3(vector) if vector else None
    result = draft_mod.draft_extrude(proj, index, vector=vec, name=name)
    output_fn(result, f"Extruded: {result.get('name', '')}")


@draft_group.command("fillet-2d")
@click.argument("index", type=int)
@click.option("--radius", "-r", default=1.0, type=float, help="Fillet radius.")
@click.option("--edges", default=None, type=str, help="Comma-separated edge indices to fillet.")
@handle_error
def draft_fillet_2d(index: int, radius: float, edges: Optional[str]) -> None:
    """Apply a 2D fillet to a draft object."""
    sess = get_session()
    sess.snapshot(f"Draft fillet-2d #{index}")
    proj = sess.get_project()
    edge_list = [int(e) for e in edges.split(",")] if edges else None
    result = draft_mod.draft_fillet_2d(proj, index, radius=radius, edges=edge_list)
    output_fn(result, f"Fillet-2D: {result.get('name', '')}")


@draft_group.command("to-sketch")
@click.argument("index", type=int)
@click.option("--name", "-n", help="Name for resulting sketch.")
@handle_error
def draft_to_sketch(index: int, name: Optional[str]) -> None:
    """Convert a draft object to a sketch."""
    sess = get_session()
    sess.snapshot(f"Draft to sketch #{index}")
    proj = sess.get_project()
    result = draft_mod.draft_to_sketch(proj, index, name=name)
    output_fn(result, f"Converted to sketch: {result.get('name', '')}")


@draft_group.command("list")
@handle_error
def draft_list() -> None:
    """List all draft objects."""
    sess = get_session()
    proj = sess.get_project()
    result = draft_mod.list_draft_objects(proj)
    output_fn(result, f"{len(result)} draft object(s):")


@draft_group.command("get")
@click.argument("index", type=int)
@handle_error
def draft_get(index: int) -> None:
    """Get draft object details."""
    sess = get_session()
    proj = sess.get_project()
    result = draft_mod.get_draft_object(proj, index)
    output_fn(result, f"Draft object #{index}:")


@draft_group.command("remove")
@click.argument("index", type=int)
@handle_error
def draft_remove(index: int) -> None:
    """Remove a draft object."""
    sess = get_session()
    sess.snapshot(f"Remove draft #{index}")
    proj = sess.get_project()
    result = draft_mod.remove_draft_object(proj, index)
    output_fn(result, f"Removed: {result.get('name', f'#{index}')}")


# ── Surface commands ─────────────────────────────────────────────────

@cli.group("surface")
def surface_group():
    """Surface workbench commands."""
    pass


@surface_group.command("filling")
@click.argument("edge_indices", type=str)
@click.option("--name", "-n", help="Surface name.")
@handle_error
def surface_filling(edge_indices: str, name: Optional[str]) -> None:
    """Create a filling surface from edge indices (comma-separated)."""
    sess = get_session()
    sess.snapshot("Surface filling")
    proj = sess.get_project()
    idx_list = _parse_indices(edge_indices)
    result = surface_mod.surface_filling(proj, edge_indices=idx_list, name=name)
    output_fn(result, f"Created filling: {result.get('name', '')}")


@surface_group.command("sections")
@click.argument("section_indices", type=str)
@click.option("--name", "-n", help="Surface name.")
@handle_error
def surface_sections(section_indices: str, name: Optional[str]) -> None:
    """Create a loft surface through sections (comma-separated indices)."""
    sess = get_session()
    sess.snapshot("Surface sections")
    proj = sess.get_project()
    idx_list = _parse_indices(section_indices)
    result = surface_mod.surface_sections(proj, section_indices=idx_list, name=name)
    output_fn(result, f"Created sections: {result.get('name', '')}")


@surface_group.command("extend")
@click.argument("surface_index", type=int)
@click.option("--length", "-l", default=10.0, type=float, help="Extension length.")
@click.option("--direction", default="normal",
              type=click.Choice(["normal", "u", "v"]))
@click.option("--name", "-n", help="Surface name.")
@handle_error
def surface_extend(surface_index: int, length: float, direction: str,
                   name: Optional[str]) -> None:
    """Extend a surface."""
    sess = get_session()
    sess.snapshot(f"Extend surface #{surface_index}")
    proj = sess.get_project()
    result = surface_mod.surface_extend(proj, surface_index, length=length,
                                        direction=direction, name=name)
    output_fn(result, f"Extended: {result.get('name', '')}")


@surface_group.command("blend-curve")
@click.argument("edge_index1", type=int)
@click.argument("edge_index2", type=int)
@click.option("--name", "-n", help="Surface name.")
@handle_error
def surface_blend_curve(edge_index1: int, edge_index2: int,
                        name: Optional[str]) -> None:
    """Create a blend surface between two edges."""
    sess = get_session()
    sess.snapshot("Surface blend curve")
    proj = sess.get_project()
    result = surface_mod.surface_blend_curve(proj, edge_index1, edge_index2,
                                             name=name)
    output_fn(result, f"Created blend: {result.get('name', '')}")


@surface_group.command("sew")
@click.argument("surface_indices", type=str)
@click.option("--tolerance", default=0.01, type=float, help="Sewing tolerance.")
@click.option("--name", "-n", help="Surface name.")
@handle_error
def surface_sew(surface_indices: str, tolerance: float,
                name: Optional[str]) -> None:
    """Sew surfaces together (comma-separated indices)."""
    sess = get_session()
    sess.snapshot("Surface sew")
    proj = sess.get_project()
    idx_list = _parse_indices(surface_indices)
    result = surface_mod.surface_sew(proj, surface_indices=idx_list,
                                     tolerance=tolerance, name=name)
    output_fn(result, f"Sewn: {result.get('name', '')}")


@surface_group.command("cut")
@click.argument("surface_index", type=int)
@click.argument("cutting_index", type=int)
@click.option("--name", "-n", help="Surface name.")
@handle_error
def surface_cut(surface_index: int, cutting_index: int,
                name: Optional[str]) -> None:
    """Cut a surface with another surface."""
    sess = get_session()
    sess.snapshot(f"Surface cut #{surface_index}")
    proj = sess.get_project()
    result = surface_mod.surface_cut(proj, surface_index, cutting_index, name=name)
    output_fn(result, f"Cut: {result.get('name', '')}")


# ── Import commands ──────────────────────────────────────────────────

@cli.group("import")
def import_group():
    """File import commands."""
    pass


@import_group.command("auto")
@click.argument("path", type=click.Path())
@click.option("--format", "fmt", help="Explicit format override.")
@click.option("--name", "-n", help="Object name.")
@handle_error
def import_auto(path: str, fmt: Optional[str], name: Optional[str]) -> None:
    """Auto-detect and import a file."""
    sess = get_session()
    sess.snapshot("Import file")
    proj = sess.get_project()
    result = import_mod.import_file(proj, path, format=fmt, name=name)
    output_fn(result, f"Imported: {result.get('name', '')}")


@import_group.command("step")
@click.argument("path", type=click.Path())
@click.option("--name", "-n", help="Part name.")
@handle_error
def import_step(path: str, name: Optional[str]) -> None:
    """Import a STEP file."""
    sess = get_session()
    sess.snapshot("Import STEP")
    proj = sess.get_project()
    result = import_mod.import_step(proj, path, name=name)
    output_fn(result, f"Imported STEP: {result.get('name', '')}")


@import_group.command("iges")
@click.argument("path", type=click.Path())
@click.option("--name", "-n", help="Part name.")
@handle_error
def import_iges(path: str, name: Optional[str]) -> None:
    """Import an IGES file."""
    sess = get_session()
    sess.snapshot("Import IGES")
    proj = sess.get_project()
    result = import_mod.import_iges(proj, path, name=name)
    output_fn(result, f"Imported IGES: {result.get('name', '')}")


@import_group.command("stl")
@click.argument("path", type=click.Path())
@click.option("--name", "-n", help="Mesh name.")
@handle_error
def import_stl(path: str, name: Optional[str]) -> None:
    """Import an STL file."""
    sess = get_session()
    sess.snapshot("Import STL")
    proj = sess.get_project()
    result = import_mod.import_stl(proj, path, name=name)
    output_fn(result, f"Imported STL: {result.get('name', '')}")


@import_group.command("obj")
@click.argument("path", type=click.Path())
@click.option("--name", "-n", help="Mesh name.")
@handle_error
def import_obj(path: str, name: Optional[str]) -> None:
    """Import an OBJ file."""
    sess = get_session()
    sess.snapshot("Import OBJ")
    proj = sess.get_project()
    result = import_mod.import_obj(proj, path, name=name)
    output_fn(result, f"Imported OBJ: {result.get('name', '')}")


@import_group.command("dxf")
@click.argument("path", type=click.Path())
@click.option("--name", "-n", help="Object name.")
@handle_error
def import_dxf(path: str, name: Optional[str]) -> None:
    """Import a DXF file."""
    sess = get_session()
    sess.snapshot("Import DXF")
    proj = sess.get_project()
    result = import_mod.import_dxf(proj, path, name=name)
    output_fn(result, f"Imported DXF: {result.get('name', '')}")


@import_group.command("svg")
@click.argument("path", type=click.Path())
@click.option("--name", "-n", help="Object name.")
@handle_error
def import_svg(path: str, name: Optional[str]) -> None:
    """Import an SVG file."""
    sess = get_session()
    sess.snapshot("Import SVG")
    proj = sess.get_project()
    result = import_mod.import_svg(proj, path, name=name)
    output_fn(result, f"Imported SVG: {result.get('name', '')}")


@import_group.command("brep")
@click.argument("path", type=click.Path())
@click.option("--name", "-n", help="Part name.")
@handle_error
def import_brep(path: str, name: Optional[str]) -> None:
    """Import a BREP file."""
    sess = get_session()
    sess.snapshot("Import BREP")
    proj = sess.get_project()
    result = import_mod.import_brep(proj, path, name=name)
    output_fn(result, f"Imported BREP: {result.get('name', '')}")


@import_group.command("3mf")
@click.argument("path", type=click.Path())
@click.option("--name", "-n", help="Mesh name.")
@handle_error
def import_3mf(path: str, name: Optional[str]) -> None:
    """Import a 3MF file."""
    sess = get_session()
    sess.snapshot("Import 3MF")
    proj = sess.get_project()
    result = import_mod.import_3mf(proj, path, name=name)
    output_fn(result, f"Imported 3MF: {result.get('name', '')}")


@import_group.command("ply")
@click.argument("path", type=click.Path())
@click.option("--name", "-n", help="Mesh name.")
@handle_error
def import_ply(path: str, name: Optional[str]) -> None:
    """Import a PLY file."""
    sess = get_session()
    sess.snapshot("Import PLY")
    proj = sess.get_project()
    result = import_mod.import_ply(proj, path, name=name)
    output_fn(result, f"Imported PLY: {result.get('name', '')}")


@import_group.command("off")
@click.argument("path", type=click.Path())
@click.option("--name", "-n", help="Mesh name.")
@handle_error
def import_off(path: str, name: Optional[str]) -> None:
    """Import an OFF file."""
    sess = get_session()
    sess.snapshot("Import OFF")
    proj = sess.get_project()
    result = import_mod.import_off(proj, path, name=name)
    output_fn(result, f"Imported OFF: {result.get('name', '')}")


@import_group.command("gltf")
@click.argument("path", type=click.Path())
@click.option("--name", "-n", help="Mesh name.")
@handle_error
def import_gltf(path: str, name: Optional[str]) -> None:
    """Import a glTF/GLB file."""
    sess = get_session()
    sess.snapshot("Import glTF")
    proj = sess.get_project()
    result = import_mod.import_gltf(proj, path, name=name)
    output_fn(result, f"Imported glTF: {result.get('name', '')}")


@import_group.command("info")
@click.argument("path", type=click.Path())
@handle_error
def import_info(path: str) -> None:
    """Preview file metadata without importing."""
    result = import_mod.import_info(path)
    output_fn(result, "Import info:")


# ── Assembly commands ────────────────────────────────────────────────

@cli.group("assembly")
def assembly_group():
    """Assembly management commands."""
    pass


@assembly_group.command("new")
@click.option("--name", "-n", help="Assembly name.")
@handle_error
def assembly_new(name: Optional[str]) -> None:
    """Create a new assembly."""
    sess = get_session()
    sess.snapshot("New assembly")
    proj = sess.get_project()
    result = asm_mod.create_assembly(proj, name=name)
    output_fn(result, f"Created assembly: {result.get('name', '')}")


@assembly_group.command("add-part")
@click.argument("asm_index", type=int)
@click.argument("part_index", type=int)
@click.option("--transform", help="Placement offset x,y,z.")
@handle_error
def assembly_add_part(asm_index: int, part_index: int,
                      transform: Optional[str]) -> None:
    """Add a part to an assembly."""
    sess = get_session()
    sess.snapshot(f"Add part #{part_index} to assembly #{asm_index}")
    proj = sess.get_project()
    t = _parse_vec3(transform) if transform else None
    result = asm_mod.add_part_to_assembly(proj, asm_index, part_index, transform=t)
    output_fn(result, f"Added: {result.get('name', '')}")


@assembly_group.command("remove-part")
@click.argument("asm_index", type=int)
@click.argument("component_index", type=int)
@handle_error
def assembly_remove_part(asm_index: int, component_index: int) -> None:
    """Remove a component from an assembly."""
    sess = get_session()
    sess.snapshot(f"Remove component #{component_index} from assembly #{asm_index}")
    proj = sess.get_project()
    result = asm_mod.remove_part_from_assembly(proj, asm_index, component_index)
    output_fn(result, f"Removed component #{component_index}")


@assembly_group.command("list")
@handle_error
def assembly_list() -> None:
    """List all assemblies."""
    sess = get_session()
    proj = sess.get_project()
    result = asm_mod.list_assemblies(proj)
    output_fn(result, f"{len(result)} assembly/assemblies:")


@assembly_group.command("get")
@click.argument("index", type=int)
@handle_error
def assembly_get(index: int) -> None:
    """Get assembly details."""
    sess = get_session()
    proj = sess.get_project()
    result = asm_mod.get_assembly(proj, index)
    output_fn(result, f"Assembly #{index}:")


@assembly_group.command("constrain")
@click.argument("asm_index", type=int)
@click.argument("constraint_type", type=str)
@click.option("--components", "-c", required=True,
              help="Component indices (comma-sep).")
@click.option("--param", "-P", multiple=True, help="Param as key=value.")
@handle_error
def assembly_constrain(asm_index: int, constraint_type: str,
                       components: str, param: tuple) -> None:
    """Add a constraint between assembly components."""
    sess = get_session()
    sess.snapshot(f"Constrain assembly #{asm_index}")
    proj = sess.get_project()
    comp_indices = _parse_indices(components)
    params = {}
    for p in param:
        if "=" not in p:
            raise ValueError(f"Param must be key=value, got: {p}")
        k, v = p.split("=", 1)
        try:
            params[k.strip()] = float(v.strip())
        except ValueError:
            params[k.strip()] = v.strip()
    result = asm_mod.add_assembly_constraint(proj, asm_index, constraint_type,
                                             comp_indices, **params)
    output_fn(result, f"Added constraint: {constraint_type}")


@assembly_group.command("solve")
@click.argument("asm_index", type=int)
@handle_error
def assembly_solve(asm_index: int) -> None:
    """Solve assembly constraints."""
    sess = get_session()
    sess.snapshot(f"Solve assembly #{asm_index}")
    proj = sess.get_project()
    result = asm_mod.solve_assembly(proj, asm_index)
    output_fn(result, "Assembly solved")


@assembly_group.command("dof")
@click.argument("asm_index", type=int)
@handle_error
def assembly_dof(asm_index: int) -> None:
    """Estimate degrees of freedom for an assembly."""
    sess = get_session()
    proj = sess.get_project()
    result = asm_mod.degrees_of_freedom(proj, asm_index)
    output_fn(result, f"DOF: {result.get('dof', 'N/A')}")


@assembly_group.command("bom")
@click.argument("asm_index", type=int)
@handle_error
def assembly_bom(asm_index: int) -> None:
    """Generate bill of materials for an assembly."""
    sess = get_session()
    proj = sess.get_project()
    result = asm_mod.generate_bom(proj, asm_index)
    output_fn(result, "Bill of Materials:")


@assembly_group.command("explode")
@click.argument("asm_index", type=int)
@click.option("--factor", default=2.0, type=float, help="Explode factor.")
@handle_error
def assembly_explode(asm_index: int, factor: float) -> None:
    """Explode assembly for visualization."""
    sess = get_session()
    sess.snapshot(f"Explode assembly #{asm_index}")
    proj = sess.get_project()
    result = asm_mod.explode_assembly(proj, asm_index, factor=factor)
    output_fn(result, "Assembly exploded")


@assembly_group.command("collapse")
@click.argument("asm_index", type=int)
@handle_error
def assembly_collapse(asm_index: int) -> None:
    """Collapse (reset) assembly transforms."""
    sess = get_session()
    sess.snapshot(f"Collapse assembly #{asm_index}")
    proj = sess.get_project()
    result = asm_mod.collapse_assembly(proj, asm_index)
    output_fn(result, "Assembly collapsed")


@assembly_group.command("insert-part")
@click.argument("asm_index", type=int)
@click.option("--type", "part_type", default="box", help="Part type to insert")
@click.option("--name", default=None, help="Part name")
@click.option("-P", "--param", multiple=True, help="Parameters as key=value")
@click.option("--transform", default=None, help="Transform as x,y,z")
@handle_error
def assembly_insert_part(asm_index, part_type, name, param, transform):
    """Insert a new inline part into an assembly (FreeCAD 1.1)."""
    sess = get_session()
    proj = sess.get_project()
    params = _parse_params(param) if param else None
    t = _parse_vec3(transform) if transform else None
    result = asm_mod.insert_new_part(proj, asm_index, part_type, name, params, t)
    output_fn(result, "Part inserted into assembly.")


@assembly_group.command("create-simulation")
@click.argument("asm_index", type=int)
@click.option("--name", default=None, help="Simulation name")
@click.option("--duration", type=float, default=5.0, help="Duration in seconds")
@click.option("--fps", type=int, default=24, help="Frames per second")
@handle_error
def assembly_create_simulation(asm_index, name, duration, fps):
    """Create a joint motion simulation (FreeCAD 1.1)."""
    sess = get_session()
    proj = sess.get_project()
    result = asm_mod.create_simulation(proj, asm_index, name, duration, fps)
    output_fn(result, "Simulation created.")


@assembly_group.command("add-sim-step")
@click.argument("asm_index", type=int)
@click.argument("sim_index", type=int)
@click.option("--joint", type=int, required=True, help="Joint index")
@click.option("--start", type=float, default=0.0, help="Start value")
@click.option("--end", type=float, default=1.0, help="End value")
@handle_error
def assembly_add_sim_step(asm_index, sim_index, joint, start, end):
    """Add a motion step to a simulation (FreeCAD 1.1)."""
    sess = get_session()
    proj = sess.get_project()
    result = asm_mod.add_simulation_step(proj, asm_index, sim_index, joint, start, end)
    output_fn(result, "Simulation step added.")


# ── TechDraw commands ────────────────────────────────────────────────

@cli.group("techdraw")
def techdraw_group():
    """Technical drawing commands."""
    pass


@techdraw_group.command("new-page")
@click.option("--name", "-n", help="Page name.")
@click.option("--template", default="A4_LandscapeTD", help="Drawing template.")
@handle_error
def techdraw_new_page(name: Optional[str], template: str) -> None:
    """Create a new TechDraw page."""
    sess = get_session()
    sess.snapshot("New TechDraw page")
    proj = sess.get_project()
    result = td_mod.new_page(proj, name=name, template=template)
    output_fn(result, f"Created page: {result.get('name', '')}")


@techdraw_group.command("set-template")
@click.argument("page_index", type=int)
@click.argument("template", type=str)
@handle_error
def techdraw_set_template(page_index: int, template: str) -> None:
    """Change the template of a page."""
    sess = get_session()
    sess.snapshot(f"Set template on page #{page_index}")
    proj = sess.get_project()
    result = td_mod.set_template(proj, page_index, template)
    output_fn(result, f"Template set to: {template}")


@techdraw_group.command("add-view")
@click.argument("page_index", type=int)
@click.argument("source_index", type=int)
@click.option("--direction", help="View direction x,y,z.")
@click.option("--scale", default=1.0, type=float, help="View scale.")
@click.option("--position", help="Page position x,y.")
@handle_error
def techdraw_add_view(page_index: int, source_index: int,
                      direction: Optional[str], scale: float,
                      position: Optional[str]) -> None:
    """Add a standard view to a page."""
    sess = get_session()
    sess.snapshot(f"Add view to page #{page_index}")
    proj = sess.get_project()
    d = _parse_vec3(direction) if direction else None
    p = _parse_vec2(position) if position else None
    result = td_mod.add_view(proj, page_index, source_index, direction=d,
                             scale=scale, position=p)
    output_fn(result, "Added view")


@techdraw_group.command("add-projection-group")
@click.argument("page_index", type=int)
@click.argument("source_index", type=int)
@click.option("--directions", help="Projections (comma-sep, e.g. front,right,top).")
@handle_error
def techdraw_add_projection_group(page_index: int, source_index: int,
                                  directions: Optional[str]) -> None:
    """Add a projection group to a page."""
    sess = get_session()
    sess.snapshot(f"Add projection group to page #{page_index}")
    proj = sess.get_project()
    dirs = [d.strip() for d in directions.split(",")] if directions else None
    result = td_mod.add_projection_group(proj, page_index, source_index,
                                         directions=dirs)
    output_fn(result, "Added projection group")


@techdraw_group.command("add-section-view")
@click.argument("page_index", type=int)
@click.argument("view_index", type=int)
@click.option("--section-normal", help="Section normal x,y,z.")
@click.option("--section-origin", help="Section origin x,y,z.")
@handle_error
def techdraw_add_section_view(page_index: int, view_index: int,
                              section_normal: Optional[str],
                              section_origin: Optional[str]) -> None:
    """Add a section view."""
    sess = get_session()
    sess.snapshot(f"Add section view to page #{page_index}")
    proj = sess.get_project()
    sn = _parse_vec3(section_normal) if section_normal else None
    so = _parse_vec3(section_origin) if section_origin else None
    result = td_mod.add_section_view(proj, page_index, view_index,
                                     section_normal=sn, section_origin=so)
    output_fn(result, "Added section view")


@techdraw_group.command("add-detail-view")
@click.argument("page_index", type=int)
@click.argument("view_index", type=int)
@click.option("--center", help="Detail center x,y.")
@click.option("--radius", default=20.0, type=float, help="Detail radius.")
@handle_error
def techdraw_add_detail_view(page_index: int, view_index: int,
                             center: Optional[str], radius: float) -> None:
    """Add a detail (magnified) view."""
    sess = get_session()
    sess.snapshot(f"Add detail view to page #{page_index}")
    proj = sess.get_project()
    c = _parse_vec2(center) if center else None
    result = td_mod.add_detail_view(proj, page_index, view_index,
                                    center=c, radius=radius)
    output_fn(result, "Added detail view")


@techdraw_group.command("add-dimension")
@click.argument("page_index", type=int)
@click.argument("view_index", type=int)
@click.argument("dim_type", type=click.Choice(["length", "distance", "radius",
                                                "diameter", "angle"]))
@click.option("--references", "-r", required=True, help="Geometry references (comma-sep).")
@click.option("--value", "-v", type=float, help="Override value.")
@handle_error
def techdraw_add_dimension(page_index: int, view_index: int, dim_type: str,
                           references: str, value: Optional[float]) -> None:
    """Add a dimension to a page."""
    sess = get_session()
    sess.snapshot(f"Add dimension to page #{page_index}")
    proj = sess.get_project()
    refs = _parse_references(references)
    result = td_mod.add_dimension(proj, page_index, view_index, dim_type,
                                  refs, value=value)
    output_fn(result, f"Added {dim_type} dimension")


@techdraw_group.command("add-annotation")
@click.argument("page_index", type=int)
@click.argument("text_content", type=str)
@click.option("--position", help="Position x,y.")
@click.option("--area", is_flag=True, help="Compute area accounting for face holes.")
@click.option("--validate-shape", is_flag=True, default=False, help="Enable shape validation.")
@handle_error
def techdraw_add_annotation(page_index: int, text_content: str,
                            position: Optional[str], area: bool,
                            validate_shape: bool) -> None:
    """Add a text annotation to a page."""
    sess = get_session()
    sess.snapshot(f"Add annotation to page #{page_index}")
    proj = sess.get_project()
    p = _parse_vec2(position) if position else None
    result = td_mod.add_annotation(proj, page_index, text_content, position=p,
                                   area_mode=area, shape_validation=validate_shape)
    output_fn(result, "Added annotation")


@techdraw_group.command("add-leader")
@click.argument("page_index", type=int)
@click.argument("points_str", type=str)
@click.option("--text", "-t", default="", help="Leader text.")
@handle_error
def techdraw_add_leader(page_index: int, points_str: str, text: str) -> None:
    """Add a leader line (semicolon-separated x,y points)."""
    sess = get_session()
    sess.snapshot(f"Add leader to page #{page_index}")
    proj = sess.get_project()
    pts = _parse_points_2d(points_str)
    result = td_mod.add_leader(proj, page_index, points=pts, text=text)
    output_fn(result, "Added leader")


@techdraw_group.command("add-centerline")
@click.argument("page_index", type=int)
@click.argument("view_index", type=int)
@click.option("--references", "-r", required=True, help="References (comma-sep).")
@handle_error
def techdraw_add_centerline(page_index: int, view_index: int,
                            references: str) -> None:
    """Add a centerline to a view."""
    sess = get_session()
    sess.snapshot(f"Add centerline to page #{page_index}")
    proj = sess.get_project()
    refs = _parse_references(references)
    result = td_mod.add_centerline(proj, page_index, view_index, references=refs)
    output_fn(result, "Added centerline")


@techdraw_group.command("add-hatch")
@click.argument("page_index", type=int)
@click.argument("view_index", type=int)
@click.option("--pattern", default="steel", help="Hatch pattern.")
@click.option("--scale", default=1.0, type=float, help="Pattern scale.")
@handle_error
def techdraw_add_hatch(page_index: int, view_index: int, pattern: str,
                       scale: float) -> None:
    """Add a hatch pattern to a view."""
    sess = get_session()
    sess.snapshot(f"Add hatch to page #{page_index}")
    proj = sess.get_project()
    result = td_mod.add_hatch(proj, page_index, view_index, pattern=pattern,
                              scale=scale)
    output_fn(result, "Added hatch")


@techdraw_group.command("export-pdf")
@click.argument("page_index", type=int)
@click.argument("path", type=click.Path())
@handle_error
def techdraw_export_pdf(page_index: int, path: str) -> None:
    """Export a page to PDF."""
    sess = get_session()
    proj = sess.get_project()
    result = td_mod.export_page_pdf(proj, page_index, path)
    output_fn(result, f"Exported PDF: {path}")


@techdraw_group.command("export-svg")
@click.argument("page_index", type=int)
@click.argument("path", type=click.Path())
@handle_error
def techdraw_export_svg(page_index: int, path: str) -> None:
    """Export a page to SVG."""
    sess = get_session()
    proj = sess.get_project()
    result = td_mod.export_page_svg(proj, page_index, path)
    output_fn(result, f"Exported SVG: {path}")


@techdraw_group.command("list-views")
@click.argument("page_index", type=int)
@handle_error
def techdraw_list_views(page_index: int) -> None:
    """List all views on a page."""
    sess = get_session()
    proj = sess.get_project()
    result = td_mod.list_views(proj, page_index)
    output_fn(result, f"{len(result)} view(s):")


@techdraw_group.command("get-view")
@click.argument("page_index", type=int)
@click.argument("view_index", type=int)
@handle_error
def techdraw_get_view(page_index: int, view_index: int) -> None:
    """Get details of a specific view."""
    sess = get_session()
    proj = sess.get_project()
    result = td_mod.get_view(proj, page_index, view_index)
    output_fn(result, f"View #{view_index}:")


# ── FEM commands ─────────────────────────────────────────────────────

@cli.group("fem")
def fem_group():
    """FEM analysis commands."""
    pass


@fem_group.command("new-analysis")
@click.option("--name", "-n", help="Analysis name.")
@handle_error
def fem_new_analysis(name: Optional[str]) -> None:
    """Create a new FEM analysis."""
    sess = get_session()
    sess.snapshot("New FEM analysis")
    proj = sess.get_project()
    result = fem_mod.new_analysis(proj, name=name)
    output_fn(result, f"Created analysis: {result.get('name', '')}")


@fem_group.command("add-fixed")
@click.argument("ai", type=int)
@click.option("--references", "-r", required=True, help="Geometry refs (comma-sep).")
@handle_error
def fem_add_fixed(ai: int, references: str) -> None:
    """Add a fixed boundary constraint."""
    sess = get_session()
    sess.snapshot(f"Add fixed constraint to analysis #{ai}")
    proj = sess.get_project()
    refs = _parse_references(references)
    result = fem_mod.add_fixed_constraint(proj, ai, refs)
    output_fn(result, "Added fixed constraint")


@fem_group.command("add-force")
@click.argument("ai", type=int)
@click.option("--references", "-r", required=True, help="Geometry refs (comma-sep).")
@click.option("--magnitude", "-m", required=True, type=float, help="Force in Newtons.")
@click.option("--direction", "-d", help="Direction x,y,z.")
@handle_error
def fem_add_force(ai: int, references: str, magnitude: float,
                  direction: Optional[str]) -> None:
    """Add a force constraint."""
    sess = get_session()
    sess.snapshot(f"Add force constraint to analysis #{ai}")
    proj = sess.get_project()
    refs = _parse_references(references)
    d = _parse_vec3(direction) if direction else None
    result = fem_mod.add_force_constraint(proj, ai, refs, magnitude, direction=d)
    output_fn(result, "Added force constraint")


@fem_group.command("add-pressure")
@click.argument("ai", type=int)
@click.option("--references", "-r", required=True, help="Geometry refs (comma-sep).")
@click.option("--pressure", "-p", required=True, type=float, help="Pressure in MPa.")
@handle_error
def fem_add_pressure(ai: int, references: str, pressure: float) -> None:
    """Add a pressure constraint."""
    sess = get_session()
    sess.snapshot(f"Add pressure constraint to analysis #{ai}")
    proj = sess.get_project()
    refs = _parse_references(references)
    result = fem_mod.add_pressure_constraint(proj, ai, refs, pressure)
    output_fn(result, "Added pressure constraint")


@fem_group.command("add-displacement")
@click.argument("ai", type=int)
@click.option("--references", "-r", required=True, help="Geometry refs (comma-sep).")
@click.option("--displacement", "-d", help="Displacement dx,dy,dz.")
@handle_error
def fem_add_displacement(ai: int, references: str,
                         displacement: Optional[str]) -> None:
    """Add a displacement constraint."""
    sess = get_session()
    sess.snapshot(f"Add displacement constraint to analysis #{ai}")
    proj = sess.get_project()
    refs = _parse_references(references)
    disp = _parse_vec3(displacement) if displacement else None
    result = fem_mod.add_displacement_constraint(proj, ai, refs, displacement=disp)
    output_fn(result, "Added displacement constraint")


@fem_group.command("add-temperature")
@click.argument("ai", type=int)
@click.option("--references", "-r", required=True, help="Geometry refs (comma-sep).")
@click.option("--temperature", "-t", required=True, type=float,
              help="Temperature in Kelvin.")
@handle_error
def fem_add_temperature(ai: int, references: str, temperature: float) -> None:
    """Add a temperature constraint."""
    sess = get_session()
    sess.snapshot(f"Add temperature constraint to analysis #{ai}")
    proj = sess.get_project()
    refs = _parse_references(references)
    result = fem_mod.add_temperature_constraint(proj, ai, refs, temperature)
    output_fn(result, "Added temperature constraint")


@fem_group.command("add-heatflux")
@click.argument("ai", type=int)
@click.option("--references", "-r", required=True, help="Geometry refs (comma-sep).")
@click.option("--flux", "-f", required=True, type=float, help="Heat flux in W/m^2.")
@handle_error
def fem_add_heatflux(ai: int, references: str, flux: float) -> None:
    """Add a heat flux constraint."""
    sess = get_session()
    sess.snapshot(f"Add heatflux constraint to analysis #{ai}")
    proj = sess.get_project()
    refs = _parse_references(references)
    result = fem_mod.add_heatflux_constraint(proj, ai, refs, flux)
    output_fn(result, "Added heat flux constraint")


@fem_group.command("set-material")
@click.argument("ai", type=int)
@click.argument("material_index", type=int)
@handle_error
def fem_set_material(ai: int, material_index: int) -> None:
    """Assign a material to an analysis."""
    sess = get_session()
    sess.snapshot(f"Set material on analysis #{ai}")
    proj = sess.get_project()
    result = fem_mod.set_fem_material(proj, ai, material_index)
    output_fn(result, "Material assigned to analysis")


@fem_group.command("mesh-generate")
@click.argument("ai", type=int)
@click.option("--max-size", type=float, help="Max element size.")
@click.option("--min-size", type=float, help="Min element size.")
@click.option("--element-type", default="Tet10", help="Element type.")
@click.option("--mesher", type=click.Choice(["gmsh", "netgen"]), default="gmsh",
              help="Mesher backend (FreeCAD 1.1).")
@click.option("--gmsh-verbosity", type=int, default=1,
              help="Gmsh verbosity level (FreeCAD 1.1).")
@click.option("--second-order-linear", is_flag=True,
              help="Second order linear elements (FreeCAD 1.1).")
@click.option("--local-refinement", type=str, default=None,
              help="Local refinement as JSON string (FreeCAD 1.1).")
@handle_error
def fem_mesh_generate(ai: int, max_size: Optional[float],
                      min_size: Optional[float], element_type: str,
                      mesher: str, gmsh_verbosity: int,
                      second_order_linear: bool,
                      local_refinement: Optional[str]) -> None:
    """Configure mesh generation for an analysis."""
    sess = get_session()
    sess.snapshot(f"Generate FEM mesh for analysis #{ai}")
    proj = sess.get_project()
    lr = json.loads(local_refinement) if local_refinement else None
    result = fem_mod.generate_fem_mesh(proj, ai, max_size=max_size,
                                       min_size=min_size,
                                       element_type=element_type,
                                       mesher=mesher,
                                       gmsh_verbosity=gmsh_verbosity,
                                       second_order_linear=second_order_linear,
                                       local_refinement=lr)
    output_fn(result, "Mesh parameters set")


@fem_group.command("solve")
@click.argument("ai", type=int)
@click.option("--solver", default="calculix",
              type=click.Choice(["calculix", "elmer", "z88"]))
@click.option("--output-format", type=click.Choice(["vtu", "vtk", "result"]),
              default=None, help="Output format (FreeCAD 1.1).")
@click.option("--buckling-accuracy", type=float, default=None,
              help="Buckling accuracy (FreeCAD 1.1).")
@handle_error
def fem_solve(ai: int, solver: str, output_format: Optional[str],
              buckling_accuracy: Optional[float]) -> None:
    """Solve a FEM analysis."""
    sess = get_session()
    sess.snapshot(f"Solve analysis #{ai}")
    proj = sess.get_project()
    result = fem_mod.solve_fem(proj, ai, solver=solver,
                               output_format=output_format,
                               buckling_accuracy=buckling_accuracy)
    output_fn(result, "Analysis solver configured")


@fem_group.command("results")
@click.argument("ai", type=int)
@handle_error
def fem_results(ai: int) -> None:
    """Get FEM analysis results."""
    sess = get_session()
    proj = sess.get_project()
    result = fem_mod.get_fem_results(proj, ai)
    output_fn(result, "FEM results:")


@fem_group.command("export-results")
@click.argument("ai", type=int)
@click.argument("path", type=click.Path())
@click.option("--format", "fmt", default="vtk",
              type=click.Choice(["vtk", "csv", "json"]))
@handle_error
def fem_export_results(ai: int, path: str, fmt: str) -> None:
    """Export FEM results."""
    sess = get_session()
    proj = sess.get_project()
    result = fem_mod.export_fem_results(proj, ai, path, format=fmt)
    output_fn(result, f"Exported results: {path}")


@fem_group.command("add-beam-section")
@click.argument("analysis_index", type=int)
@click.option("--section-type", type=click.Choice(["rectangular", "circular",
              "box_beam", "elliptical", "pipe"]), default="rectangular")
@click.option("--references", default=None, help="Comma-separated geometry refs")
@click.option("--width", type=float, default=None)
@click.option("--height", type=float, default=None)
@click.option("--radius", type=float, default=None)
@handle_error
def fem_add_beam_section(analysis_index, section_type, references, width, height, radius):
    """Add an ElementGeometry1D beam section (FreeCAD 1.1)."""
    sess = get_session()
    proj = sess.get_project()
    refs = references.split(",") if references else None
    result = fem_mod.add_beam_section(proj, analysis_index, section_type, refs,
                                      width, height, radius)
    output_fn(result, "Beam section added.")


@fem_group.command("add-tie")
@click.argument("analysis_index", type=int)
@click.option("--master-refs", required=True, help="Comma-separated master refs")
@click.option("--slave-refs", required=True, help="Comma-separated slave refs")
@handle_error
def fem_add_tie(analysis_index, master_refs, slave_refs):
    """Add a tie constraint between shell faces (FreeCAD 1.1)."""
    sess = get_session()
    proj = sess.get_project()
    result = fem_mod.add_tie_constraint(proj, analysis_index,
                                        master_refs.split(","),
                                        slave_refs.split(","))
    output_fn(result, "Tie constraint added.")


@fem_group.command("purge-results")
@click.argument("analysis_index", type=int)
@handle_error
def fem_purge_results(analysis_index):
    """Delete all result objects from an analysis (FreeCAD 1.1)."""
    sess = get_session()
    proj = sess.get_project()
    result = fem_mod.purge_results(proj, analysis_index)
    output_fn(result, "Results purged.")


@fem_group.command("suppress")
@click.argument("analysis_index", type=int)
@click.argument("constraint_index", type=int)
@handle_error
def fem_suppress(analysis_index, constraint_index):
    """Toggle suppressed state on a constraint (FreeCAD 1.1)."""
    sess = get_session()
    proj = sess.get_project()
    result = fem_mod.suppress_object(proj, analysis_index, constraint_index)
    state = "suppressed" if result.get("suppressed") else "active"
    output_fn(result, f"Constraint is now {state}.")


# ── CAM commands ─────────────────────────────────────────────────────

@cli.group("cam")
def cam_group():
    """CAM/CNC machining commands."""
    pass


@cam_group.command("new-job")
@click.argument("part_index", type=int)
@click.option("--name", "-n", help="Job name.")
@handle_error
def cam_new_job(part_index: int, name: Optional[str]) -> None:
    """Create a new CAM job for a part."""
    sess = get_session()
    sess.snapshot("New CAM job")
    proj = sess.get_project()
    result = cam_mod.new_job(proj, part_index, name=name)
    output_fn(result, f"Created job: {result.get('name', '')}")


@cam_group.command("set-stock")
@click.argument("job_index", type=int)
@click.option("--stock-type", default="box",
              type=click.Choice(["box", "cylinder", "from_part"]))
@click.option("--extra-x", default=2.0, type=float)
@click.option("--extra-y", default=2.0, type=float)
@click.option("--extra-z", default=2.0, type=float)
@handle_error
def cam_set_stock(job_index: int, stock_type: str, extra_x: float,
                  extra_y: float, extra_z: float) -> None:
    """Define raw stock for a CAM job."""
    sess = get_session()
    sess.snapshot(f"Set stock on job #{job_index}")
    proj = sess.get_project()
    result = cam_mod.set_stock(proj, job_index, stock_type=stock_type,
                               extra_x=extra_x, extra_y=extra_y, extra_z=extra_z)
    output_fn(result, "Stock defined")


@cam_group.command("add-profile")
@click.argument("job_index", type=int)
@click.option("--faces", default="all", help="Face selection.")
@click.option("--depth", type=float, help="Cut depth.")
@click.option("--step-down", default=1.0, type=float, help="Step-down per pass.")
@click.option("--passes", type=int, default=None, help="Number of passes (FreeCAD 1.1).")
@click.option("--finishing-pass", is_flag=True, help="Add finishing pass (FreeCAD 1.1).")
@handle_error
def cam_add_profile(job_index: int, faces: str, depth: Optional[float],
                    step_down: float, passes: Optional[int],
                    finishing_pass: bool) -> None:
    """Add a profile (contour) operation."""
    sess = get_session()
    sess.snapshot(f"Add profile to job #{job_index}")
    proj = sess.get_project()
    result = cam_mod.add_profile_op(proj, job_index, faces=faces, depth=depth,
                                    step_down=step_down, passes=passes,
                                    finishing_pass=finishing_pass)
    output_fn(result, "Added profile operation")


@cam_group.command("add-pocket")
@click.argument("job_index", type=int)
@click.option("--faces", default="all", help="Face selection.")
@click.option("--depth", type=float, help="Pocket depth.")
@click.option("--step-down", default=1.0, type=float, help="Step-down per pass.")
@click.option("--step-over", default=0.5, type=float, help="Step-over fraction.")
@handle_error
def cam_add_pocket(job_index: int, faces: str, depth: Optional[float],
                   step_down: float, step_over: float) -> None:
    """Add a pocket operation."""
    sess = get_session()
    sess.snapshot(f"Add pocket to job #{job_index}")
    proj = sess.get_project()
    result = cam_mod.add_pocket_op(proj, job_index, faces=faces, depth=depth,
                                   step_down=step_down, step_over=step_over)
    output_fn(result, "Added pocket operation")


@cam_group.command("add-drilling")
@click.argument("job_index", type=int)
@click.option("--holes", default="all", help="Hole selection.")
@click.option("--depth", type=float, help="Drill depth.")
@click.option("--peck-depth", type=float, help="Peck increment.")
@handle_error
def cam_add_drilling(job_index: int, holes: str, depth: Optional[float],
                     peck_depth: Optional[float]) -> None:
    """Add a drilling operation."""
    sess = get_session()
    sess.snapshot(f"Add drilling to job #{job_index}")
    proj = sess.get_project()
    result = cam_mod.add_drilling_op(proj, job_index, holes=holes, depth=depth,
                                     peck_depth=peck_depth)
    output_fn(result, "Added drilling operation")


@cam_group.command("add-facing")
@click.argument("job_index", type=int)
@click.option("--depth", default=1.0, type=float, help="Facing depth.")
@click.option("--step-over", default=0.5, type=float, help="Step-over fraction.")
@handle_error
def cam_add_facing(job_index: int, depth: float, step_over: float) -> None:
    """Add a facing operation."""
    sess = get_session()
    sess.snapshot(f"Add facing to job #{job_index}")
    proj = sess.get_project()
    result = cam_mod.add_facing_op(proj, job_index, depth=depth,
                                   step_over=step_over)
    output_fn(result, "Added facing operation")


@cam_group.command("set-tool")
@click.argument("job_index", type=int)
@click.option("--tool-number", default=1, type=int, help="Tool number.")
@click.option("--diameter", default=6.0, type=float, help="Tool diameter.")
@click.option("--flutes", default=2, type=int, help="Number of flutes.")
@click.option("--type", "tool_type", default="endmill",
              type=click.Choice(["endmill", "ballnose", "drill", "chamfer",
                                 "vbit", "facemill"]))
@click.option("--material", type=str, default=None, help="Tool material (FreeCAD 1.1).")
@click.option("--coating", type=str, default=None, help="Tool coating (FreeCAD 1.1).")
@handle_error
def cam_set_tool(job_index: int, tool_number: int, diameter: float,
                 flutes: int, tool_type: str, material: Optional[str],
                 coating: Optional[str]) -> None:
    """Define a cutting tool."""
    sess = get_session()
    sess.snapshot(f"Set tool on job #{job_index}")
    proj = sess.get_project()
    result = cam_mod.set_tool(proj, job_index, tool_number=tool_number,
                              diameter=diameter, flutes=flutes, type=tool_type,
                              material=material, coating=coating)
    output_fn(result, f"Tool T{tool_number} defined")


@cam_group.command("generate-gcode")
@click.argument("job_index", type=int)
@handle_error
def cam_generate_gcode(job_index: int) -> None:
    """Generate G-code for a job."""
    sess = get_session()
    sess.snapshot(f"Generate G-code for job #{job_index}")
    proj = sess.get_project()
    result = cam_mod.generate_gcode(proj, job_index)
    output_fn(result, "G-code generation configured")


@cam_group.command("simulate")
@click.argument("job_index", type=int)
@handle_error
def cam_simulate(job_index: int) -> None:
    """Simulate a CAM job."""
    sess = get_session()
    proj = sess.get_project()
    result = cam_mod.simulate_job(proj, job_index)
    output_fn(result, "Simulation:")


@cam_group.command("export-gcode")
@click.argument("job_index", type=int)
@click.argument("path", type=click.Path())
@handle_error
def cam_export_gcode(job_index: int, path: str) -> None:
    """Export G-code to a file."""
    sess = get_session()
    proj = sess.get_project()
    result = cam_mod.export_gcode(proj, job_index, path)
    output_fn(result, f"Exported G-code: {path}")


@cam_group.command("add-tapping")
@click.argument("job_index", type=int)
@click.option("--holes", default="all", help="Hole selection")
@click.option("--depth", type=float, default=None, help="Tapping depth")
@click.option("--thread-pitch", type=float, default=1.5, help="Thread pitch")
@click.option("--left-hand", is_flag=True, help="Use G74 left-hand tapping")
@handle_error
def cam_add_tapping(job_index, holes, depth, thread_pitch, left_hand):
    """Add a tapping operation G84/G74 (FreeCAD 1.1)."""
    sess = get_session()
    proj = sess.get_project()
    result = cam_mod.add_tapping_op(proj, job_index, holes, depth, thread_pitch, not left_hand)
    output_fn(result, "Tapping operation added.")


@cam_group.command("import-tool-library")
@click.argument("job_index", type=int)
@click.argument("path", type=click.Path())
@handle_error
def cam_import_tool_library(job_index, path):
    """Import a FreeCAD 1.1 tool library file."""
    sess = get_session()
    proj = sess.get_project()
    result = cam_mod.import_tool_library(proj, job_index, path)
    output_fn(result, "Tool library imported.")


@cam_group.command("export-tool-library")
@click.argument("job_index", type=int)
@click.argument("path", type=click.Path())
@handle_error
def cam_export_tool_library(job_index, path):
    """Export CAM job tool library."""
    sess = get_session()
    proj = sess.get_project()
    result = cam_mod.export_tool_library(proj, job_index, path)
    output_fn(result, "Tool library exported.")


# ── REPL ─────────────────────────────────────────────────────────────

@cli.command("repl")
@click.argument("project_path", required=False, type=click.Path())
@handle_error
def repl(project_path: Optional[str]) -> None:
    """Start interactive REPL session."""
    global _repl_mode
    _repl_mode = True

    from cli_anything.freecad.utils.repl_skin import ReplSkin

    skin = ReplSkin("freecad", version="1.0.0")
    skin.print_banner()

    sess = get_session()
    if project_path and sess.project is None:
        proj = doc_mod.open_document(project_path)
        sess.set_project(proj, path=project_path)

    _repl_commands = {
        "document": "new|open|save|info|profiles",
        "part": "add|remove|list|get|transform|boolean|copy|mirror|scale|offset|thickness|compound|explode|fillet-3d|chamfer-3d|loft|sweep|revolve|extrude|section|slice|line-3d|wire|polygon-3d|info",
        "sketch": "new|add-line|add-circle|add-rect|add-arc|constrain|close|list|get|add-point|add-ellipse|add-polygon|add-bspline|add-slot|edit-element|remove-element|remove-constraint|edit-constraint|mirror|offset|trim|extend|validate|solve-status|set-construction|project-external|intersection|add-external-face",
        "body": "new|pad|pocket|fillet|chamfer|revolution|list|get|groove|additive-loft|additive-pipe|additive-helix|subtractive-loft|subtractive-pipe|subtractive-helix|additive-box|additive-cylinder|additive-sphere|additive-cone|additive-torus|additive-wedge|subtractive-box|subtractive-cylinder|subtractive-sphere|subtractive-cone|subtractive-torus|subtractive-wedge|draft-feature|thickness-feature|hole|linear-pattern|polar-pattern|mirrored|multi-transform|datum-plane|datum-line|datum-point|shape-binder|local-coordinate-system|toggle-freeze",
        "material": "create|assign|list|get|set|presets|import-material|export-material",
        "export": "render|info|presets",
        "session": "undo|redo|status|history",
        "measure": "distance|length|angle|area|volume|radius|diameter|position|center-of-mass|bounding-box|inertia|check-geometry",
        "spreadsheet": "new|set-cell|get-cell|set-alias|import-csv|export-csv|list",
        "mesh": "import|from-shape|export|info|analyze|check|boolean|decimate|remesh|smooth|repair|fill-holes|flip-normals|merge|split|to-shape",
        "draft": "wire|rectangle|circle|ellipse|polygon|bspline|bezier|point|text|shapestring|dimension|label|hatch|move|rotate|scale|mirror|offset|array-linear|array-polar|array-path|copy|clone|upgrade|downgrade|trim|join|extrude|fillet-2d|to-sketch|list|get|remove",
        "surface": "filling|sections|extend|blend-curve|sew|cut",
        "import": "auto|step|iges|stl|obj|dxf|svg|brep|3mf|ply|off|gltf|info",
        "assembly": "new|add-part|remove-part|list|get|constrain|solve|dof|bom|explode|collapse|insert-part|create-simulation|add-sim-step",
        "techdraw": "new-page|set-template|add-view|add-projection-group|add-section-view|add-detail-view|add-dimension|add-annotation|add-leader|add-centerline|add-hatch|export-pdf|export-svg|list-views|get-view",
        "fem": "new-analysis|add-fixed|add-force|add-pressure|add-displacement|add-temperature|add-heatflux|set-material|mesh-generate|solve|results|export-results|add-beam-section|add-tie|purge-results|suppress",
        "cam": "new-job|set-stock|add-profile|add-pocket|add-drilling|add-facing|set-tool|generate-gcode|simulate|export-gcode|add-tapping|import-tool-library|export-tool-library",
    }

    pt_session = skin.create_prompt_session()

    while True:
        try:
            proj_name = ""
            modified = False
            if sess.project:
                proj_name = sess.project.get("name", "untitled")
                modified = sess._modified

            line = skin.get_input(pt_session, project_name=proj_name,
                                  modified=modified)

            if not line:
                continue

            if line.lower() in ("quit", "exit", "q"):
                if sess._modified:
                    skin.warning("Unsaved changes! Use 'document save' first, "
                                 "or type 'quit' again.")
                    sess._modified = False  # Allow second quit
                else:
                    skin.print_goodbye()
                    break

            if line.lower() == "help":
                skin.help(_repl_commands)
                continue

            args = line.split()
            try:
                cli.main(args, standalone_mode=False)
            except SystemExit:
                pass
            except click.exceptions.UsageError as e:
                skin.error(str(e))

        except (KeyboardInterrupt, EOFError):
            skin.print_goodbye()
            break


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
