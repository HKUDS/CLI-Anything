#!/usr/bin/env python3
"""3MF CLI — Mesh geometry editor for 3D printing files.

Detect and resize cylindrical holes, repair meshes, compare 3MF files.

Usage:
    # One-shot commands
    cli-anything-3mf info model.3mf
    cli-anything-3mf inspect model.3mf
    cli-anything-3mf resize model.3mf --hole 0 --hole 1 --diameter 4.2 -o output.3mf
    cli-anything-3mf --json inspect model.3mf

    # Interactive REPL
    cli-anything-3mf
"""

import sys
import os
import json
import shlex
import click
from typing import Optional

from cli_anything.threemf.core import parser
from cli_anything.threemf.core import inspector
from cli_anything.threemf.core import modifier
from cli_anything.threemf.core import repair as repair_mod
from cli_anything.threemf.utils import threemf_backend as backend

# ── Global state ────────────────────────────────────────────────
_json_output = False
_repl_mode = False


def output(data, message: str = ""):
    """Print data as JSON or human-readable text."""
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
    """Decorator: catch errors and format output."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (RuntimeError, FileNotFoundError, FileExistsError) as e:
            if _json_output:
                click.echo(json.dumps({"error": str(e), "type": type(e).__name__}))
            else:
                click.echo(f"Error: {e}", err=True)
            if not _repl_mode:
                sys.exit(1)
        except (ValueError, IndexError) as e:
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
    """3MF CLI — Mesh geometry editor for 3D printing files.

    Run without a subcommand to enter interactive REPL mode.
    """
    global _json_output
    _json_output = use_json

    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


# ── info command ────────────────────────────────────────────────
@cli.command()
@click.argument("file", type=click.Path(exists=True))
@handle_error
def info(file):
    """Show mesh info (vertices, faces, bounds, watertight, volume)."""
    data = parser.parse_3mf(file)
    objects = []
    for mesh in data.meshes:
        stats = backend.compute_mesh_stats(mesh)
        stats["id"] = mesh.object_id
        stats["name"] = mesh.name
        objects.append(stats)
    result = {
        "file": os.path.basename(file),
        "unit": data.unit,
        "objects": objects,
    }
    if not _json_output:
        click.echo(f"File: {os.path.basename(file)}  Unit: {data.unit}")
        click.echo()
        for obj in objects:
            click.echo(f"  Object {obj['id']}: {obj['name']}")
            click.echo(f"    Vertices:     {obj['vertex_count']}")
            click.echo(f"    Faces:        {obj['face_count']}")
            bb = obj["bounding_box"]
            click.echo(f"    Bounding box: [{bb['min'][0]:.2f}, {bb['min'][1]:.2f}, {bb['min'][2]:.2f}]"
                        f" to [{bb['max'][0]:.2f}, {bb['max'][1]:.2f}, {bb['max'][2]:.2f}]")
            dims = bb["size"]
            click.echo(f"    Dimensions:   {dims[0]:.2f} x {dims[1]:.2f} x {dims[2]:.2f} mm")
            click.echo(f"    Watertight:   {obj['watertight']}")
            vol = obj['volume_mm3']
            click.echo(f"    Volume:       {vol:.2f} mm3" if vol is not None else "    Volume:       N/A (not watertight)")
            click.echo(f"    Surface area: {obj['surface_area_mm2']:.2f} mm2")
    else:
        output(result)


# ── inspect command ─────────────────────────────────────────────
@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--planes", "-n", type=int, default=20, help="Number of cross-section planes")
@click.option("--min-diameter", type=float, default=0.5, help="Minimum hole diameter (mm)")
@click.option("--min-confidence", type=float, default=0.7, help="Minimum detection confidence")
@click.option("--axis", "-a", type=int, default=0, help="Hole axis: 0=X, 1=Y, 2=Z")
@click.option("--mesh", "-m", type=int, default=0, help="Mesh object index")
@handle_error
def inspect(file, planes, min_diameter, min_confidence, axis, mesh):
    """Detect and list all cylindrical holes."""
    data = parser.parse_3mf(file)
    if mesh >= len(data.meshes):
        raise ValueError(f"Mesh index {mesh} out of range (0..{len(data.meshes)-1})")

    mesh_data = data.meshes[mesh]
    params = inspector.InspectParams(
        num_planes=planes,
        min_hole_diameter=min_diameter,
        min_confidence=min_confidence,
        axis=axis,
    )
    holes = inspector.inspect_mesh(mesh_data, params)

    from dataclasses import asdict
    holes_data = [asdict(h) for h in holes]
    result = {
        "file": os.path.basename(file),
        "object": mesh_data.name,
        "hole_count": len(holes),
        "holes": holes_data,
    }

    if not _json_output:
        click.echo(f"File: {os.path.basename(file)}  Object: {mesh_data.name}")
        click.echo(f"Detected {len(holes)} hole(s):")
        click.echo()
        axis_labels = {0: "X", 1: "Y", 2: "Z"}
        for h in holes:
            click.echo(f"  Hole {h.hole_id}:")
            click.echo(f"    Diameter:   {h.diameter:.3f} mm")
            click.echo(f"    Center:     ({h.center[0]:.3f}, {h.center[1]:.3f})")
            click.echo(f"    Axis:       {axis_labels.get(h.axis, '?')}"
                        f" [{h.axis_min:.2f} .. {h.axis_max:.2f}]")
            click.echo(f"    Confidence: {h.confidence:.2f}")
            click.echo(f"    Vertices:   {h.vertex_count}")
    else:
        output(result)


# ── resize command ──────────────────────────────────────────────
@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--hole", "-h", "hole_ids", multiple=True, type=int, required=True,
              help="Hole ID(s) to resize (from inspect output)")
@click.option("--diameter", "-d", type=float, required=True, help="Target diameter (mm)")
@click.option("--output", "-o", "output_path", type=str, required=True, help="Output file path")
@click.option("--mesh", "-m", type=int, default=0, help="Mesh object index")
@click.option("--overwrite", is_flag=True, help="Overwrite output if exists")
@handle_error
def resize(file, hole_ids, diameter, output_path, mesh, overwrite):
    """Resize cylindrical holes to specified diameter."""
    if os.path.exists(output_path) and not overwrite:
        raise FileExistsError(f"Output file exists: {output_path}. Use --overwrite to replace.")
    if diameter <= 0:
        raise ValueError("Diameter must be positive")

    data = parser.parse_3mf(file)
    new_data, changes = modifier.resize_holes(data, list(hole_ids), diameter, mesh_index=mesh)

    # Auto-repair after resize
    target_mesh = new_data.meshes[mesh]
    repaired, report = repair_mod.repair_mesh(target_mesh)
    total_fixes = report["vertices_merged"] + report["degenerate_faces_removed"] + report["unreferenced_vertices_removed"]
    if total_fixes > 0:
        meshes_list = list(new_data.meshes)
        meshes_list[mesh] = repaired
        new_data = parser.ThreeMFData(
            meshes=tuple(meshes_list),
            unit=new_data.unit,
            model_path=new_data.model_path,
            metadata=new_data.metadata,
            raw_entries=new_data.raw_entries,
            source_path=new_data.source_path,
        )

    parser.write_3mf(new_data, output_path)

    result = {
        "input": os.path.basename(file),
        "output": os.path.basename(output_path),
        "target_diameter": diameter,
        "holes_resized": list(hole_ids),
        "changes": changes,
        "repairs": report,
    }

    if not _json_output:
        click.echo(f"Resized {len(hole_ids)} hole(s) to {diameter}mm")
        for c in changes:
            click.echo(f"  Hole {c['hole_id']}: {c['old_diameter']:.3f}mm -> {c['new_diameter']:.3f}mm"
                        f" ({c['vertices_moved']} vertices)")
        if total_fixes > 0:
            click.echo(f"  Auto-repair: {total_fixes} fixes applied")
        click.echo(f"Saved: {output_path}")
    else:
        output(result)


# ── repair command ──────────────────────────────────────────────
@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_path", type=str, required=True, help="Output file path")
@click.option("--mesh", "-m", type=int, default=0, help="Mesh object index")
@click.option("--overwrite", is_flag=True, help="Overwrite output if exists")
@handle_error
def repair(file, output_path, mesh, overwrite):
    """Fix mesh issues (degenerate faces, duplicate vertices, normals)."""
    if os.path.exists(output_path) and not overwrite:
        raise FileExistsError(f"Output file exists: {output_path}. Use --overwrite to replace.")

    data = parser.parse_3mf(file)
    if mesh >= len(data.meshes):
        raise ValueError(f"Mesh index {mesh} out of range (0..{len(data.meshes)-1})")

    mesh_data = data.meshes[mesh]
    repaired, report = repair_mod.repair_mesh(mesh_data)

    meshes_list = list(data.meshes)
    meshes_list[mesh] = repaired
    new_data = parser.ThreeMFData(
        meshes=tuple(meshes_list),
        unit=data.unit,
        model_path=data.model_path,
        metadata=data.metadata,
        raw_entries=data.raw_entries,
        source_path=data.source_path,
    )
    parser.write_3mf(new_data, output_path)

    result = {
        "input": os.path.basename(file),
        "output": os.path.basename(output_path),
        "repairs": report,
    }

    if not _json_output:
        total = report['vertices_merged'] + report['degenerate_faces_removed'] + report['unreferenced_vertices_removed']
        click.echo(f"Repaired: {os.path.basename(file)}")
        click.echo(f"  Duplicates merged:    {report['vertices_merged']}")
        click.echo(f"  Degenerates removed:  {report['degenerate_faces_removed']}")
        click.echo(f"  Unreferenced removed: {report['unreferenced_vertices_removed']}")
        click.echo(f"  Total fixes:          {total}")
        click.echo(f"Saved: {output_path}")
    else:
        output(result)


# ── compare command ─────────────────────────────────────────────
@cli.command()
@click.argument("file1", type=click.Path(exists=True))
@click.argument("file2", type=click.Path(exists=True))
@click.option("--mesh", "-m", type=int, default=0, help="Mesh object index")
@handle_error
def compare(file1, file2, mesh):
    """Compare two 3MF files."""
    data1 = parser.parse_3mf(file1)
    data2 = parser.parse_3mf(file2)

    if mesh >= len(data1.meshes) or mesh >= len(data2.meshes):
        raise ValueError(f"Mesh index {mesh} out of range for one or both files")

    result = inspector.compare_meshes(data1.meshes[mesh], data2.meshes[mesh])
    result["file1"] = os.path.basename(file1)
    result["file2"] = os.path.basename(file2)

    if not _json_output:
        click.echo(f"Comparing: {os.path.basename(file1)} vs {os.path.basename(file2)}")
        click.echo()
        click.echo(f"  {'':20s} {'File 1':>10s} {'File 2':>10s} {'Diff':>10s}")
        click.echo(f"  {'─' * 52}")
        click.echo(f"  {'Vertices':20s} {result['vertices']['file1']:>10d}"
                    f" {result['vertices']['file2']:>10d}"
                    f" {result['vertices']['diff']:>+10d}")
        click.echo(f"  {'Faces':20s} {result['faces']['file1']:>10d}"
                    f" {result['faces']['file2']:>10d}"
                    f" {result['faces']['diff']:>+10d}")
        click.echo(f"  {'Volume (mm3)':20s} {result['volume']['file1']:>10.1f}"
                    f" {result['volume']['file2']:>10.1f}"
                    f" {result['volume']['diff']:>+10.1f}")
        click.echo(f"  {'Watertight':20s} {str(result['watertight']['file1']):>10s}"
                    f" {str(result['watertight']['file2']):>10s}")
    else:
        output(result)


# ── REPL ────────────────────────────────────────────────────────
@cli.command(hidden=True)
@handle_error
def repl():
    """Start interactive REPL session."""
    global _repl_mode
    _repl_mode = True

    from cli_anything.threemf.utils.repl_skin import ReplSkin
    skin = ReplSkin("3mf", version="1.0.0")
    skin.print_banner()

    pt_session = skin.create_prompt_session()

    skin.help({
        "info <file>": "Show mesh statistics",
        "inspect <file>": "Detect cylindrical holes",
        "resize <file> -h <id> -d <mm> -o <out>": "Resize holes",
        "repair <file> -o <out>": "Fix mesh issues",
        "compare <f1> <f2>": "Compare two files",
        "help": "Show this help",
        "quit": "Exit REPL",
    })

    while True:
        try:
            user_input = skin.get_input(pt_session)
            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "q"):
                skin.print_goodbye()
                break
            if user_input.lower() == "help":
                skin.help({
                    "info <file>": "Show mesh statistics",
                    "inspect <file>": "Detect cylindrical holes",
                    "resize <file> -h <id> -d <mm> -o <out>": "Resize holes",
                    "repair <file> -o <out>": "Fix mesh issues",
                    "compare <f1> <f2>": "Compare two files",
                    "help": "Show this help",
                    "quit": "Exit REPL",
                })
                continue

            try:
                args = shlex.split(user_input)
            except ValueError as e:
                skin.error(f"Parse error: {e}")
                continue

            try:
                cli(args, standalone_mode=False)
            except SystemExit:
                pass
            except click.exceptions.UsageError as e:
                skin.error(str(e))
            except Exception as e:
                skin.error(str(e))

        except (KeyboardInterrupt, EOFError):
            skin.print_goodbye()
            break


def main():
    cli()


if __name__ == "__main__":
    main()
