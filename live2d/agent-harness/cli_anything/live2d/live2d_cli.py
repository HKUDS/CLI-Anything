#!/usr/bin/env python3
"""Live2D Cubism CLI — inspect, validate, and manage Live2D models.

Usage:
    cli-anything-live2d inspect model.model3.json
    cli-anything-live2d validate model.model3.json
    cli-anything-live2d motions model.model3.json
    cli-anything-live2d motion-info motions/idle.motion3.json
    cli-anything-live2d expressions model.model3.json
    cli-anything-live2d expr-info expressions/happy.exp3.json
    cli-anything-live2d textures model.model3.json
    cli-anything-live2d physics model.model3.json
    cli-anything-live2d moc3 model.moc3
    cli-anything-live2d deps model.model3.json
    cli-anything-live2d compare modelA.model3.json modelB.model3.json
    cli-anything-live2d pack model.model3.json -o output.zip
    cli-anything-live2d yoyo-check model.model3.json
    cli-anything-live2d init my-character
    cli-anything-live2d scan ./models/
    cli-anything-live2d export model.model3.json --format json
    cli-anything-live2d params model.model3.json
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional

import click

from cli_anything.live2d.core.parser import load_model, save_model, ModelInfo, MotionRef, ExpressionRef
from cli_anything.live2d.core.backup import auto_backup, snapshot, list_backups, restore
from cli_anything.live2d.core.linter import lint_model
from cli_anything.live2d.core.differ import diff_models
from cli_anything.live2d.core.snapshot import write_snapshot
from cli_anything.live2d.core.validator import validate_model, validate_all
from cli_anything.live2d.core.scanner import scan_directory
from cli_anything.live2d.core.motion_parser import load_motion
from cli_anything.live2d.core.expression_parser import load_expression
from cli_anything.live2d.core.texture_info import get_texture_info
from cli_anything.live2d.core.physics_parser import load_physics
from cli_anything.live2d.core.moc3_parser import load_moc3
from cli_anything.live2d.core.comparer import compare_models
from cli_anything.live2d.core.dependency import build_dependency_graph
from cli_anything.live2d.core.packager import package_model
from cli_anything.live2d.core.template import generate_template
from cli_anything.live2d.core.yoyo_pipeline import check_yoyo_export

# Global state
_json_output = False


def output(data, message: str = ""):
    """Print output in human or JSON format."""
    if _json_output:
        click.echo(json.dumps(data, indent=2, ensure_ascii=False, default=str))
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
    """Decorator for consistent error handling."""
    import functools
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except FileNotFoundError as e:
            if _json_output:
                click.echo(json.dumps({"error": str(e), "type": "file_not_found"}))
            else:
                click.echo(f"Error: {e}", err=True)
            sys.exit(1)
        except (ValueError, IndexError) as e:
            if _json_output:
                click.echo(json.dumps({"error": str(e), "type": type(e).__name__}))
            else:
                click.echo(f"Error: {e}", err=True)
            sys.exit(1)
    return wrapper


# ── Main CLI ────────────────────────────────────────────────────

@click.group()
@click.option("--json", "use_json", is_flag=True, help="Output as JSON")
@click.version_option(version="0.3.0", prog_name="cli-anything-live2d")
def cli(use_json: bool):
    """Live2D Cubism CLI — inspect, validate, and manage Live2D models."""
    global _json_output
    _json_output = use_json


def main():
    cli()


# ── inspect ─────────────────────────────────────────────────────

@cli.command()
@click.argument("model_path", type=click.Path(exists=True))
@handle_error
def inspect(model_path: str):
    """Inspect a Live2D model (.model3.json)."""
    info = load_model(Path(model_path))

    data = {
        "model_file": str(info.path),
        "version": info.version,
        "moc3": info.moc3,
        "textures": info.texture_count,
        "motions_total": info.motion_count,
        "motion_groups": info.motion_group_count,
        "expressions": info.expression_count,
        "physics": bool(info.physics),
        "pose": bool(info.pose),
        "userdata": bool(info.userdata),
    }

    if _json_output:
        output(data)
        return

    click.echo(f"\n  🎭 Live2D Model Inspector\n")
    click.echo(f"  File:        {info.path.name}")
    click.echo(f"  Version:     {info.version or 'N/A'}")
    click.echo(f"  Moc3:        {info.moc3}")
    click.echo(f"  Textures:    {info.texture_count}")
    click.echo(f"  Motions:     {info.motion_count} ({info.motion_group_count} groups)")
    click.echo(f"  Expressions: {info.expression_count}")
    click.echo(f"  Physics:     {'✅' if info.physics else '❌'}")
    click.echo(f"  Pose:        {'✅' if info.pose else '❌'}")
    click.echo(f"  UserData:    {'✅' if info.userdata else '❌'}")
    click.echo()


# ── validate ────────────────────────────────────────────────────

@cli.command()
@click.argument("model_path", type=click.Path(exists=True))
@click.option("--verbose", "-v", is_flag=True, help="Show all checks")
@click.option("--strict", is_flag=True, help="Reject placeholder or incomplete production exports")
@click.option("--min-moc3-size", default=1024, show_default=True, help="Minimum .moc3 size in strict mode")
@handle_error
def validate(model_path: str, verbose: bool, strict: bool, min_moc3_size: int):
    """Validate a Live2D model — check all referenced files exist."""
    info = load_model(Path(model_path))
    result = validate_model(info, strict=strict, min_moc3_size=min_moc3_size)

    if _json_output:
        output(result.to_dict())
        if not result.ok:
            sys.exit(1)
        return

    click.echo(f"\n  🔍 Validation: {info.path.name}\n")
    if strict:
        click.echo(f"  Mode: strict")
    click.echo(f"  Files checked: {result.checked}")

    if result.errors:
        click.echo(f"  Errors: {len(result.errors)}\n")
        for e in result.errors:
            click.echo(f"  ❌ {e}")
        sys.exit(1)
    else:
        click.echo(f"  ✅ All files present!")

    if result.warnings:
        for w in result.warnings:
            click.echo(f"  ⚠️  {w}")
    click.echo()


# ── motions ─────────────────────────────────────────────────────

@cli.command()
@click.argument("model_path", type=click.Path(exists=True))
@click.option("--group", "-g", help="Filter by motion group")
@handle_error
def motions(model_path: str, group: Optional[str]):
    """List all motions in a Live2D model."""
    info = load_model(Path(model_path))

    if _json_output:
        data = {}
        for g, ms in info.motions.items():
            if group and g != group:
                continue
            data[g] = [{"file": m.file, "fade_in": m.fade_in, "fade_out": m.fade_out} for m in ms]
        output(data)
        return

    click.echo(f"\n  🎬 Motions: {info.path.name}\n")
    for group_name, items in info.motions.items():
        if group and group != group_name:
            continue
        click.echo(f"  [{group_name}] ({len(items)} motions)")
        for i, m in enumerate(items):
            click.echo(f"    {i}. {m.file}  (fade: {m.fade_in}s / {m.fade_out}s)")
        click.echo()


# ── motion-info ─────────────────────────────────────────────────

@cli.command(name="motion-info")
@click.argument("motion_path", type=click.Path(exists=True))
@handle_error
def motion_info_cmd(motion_path: str):
    """Detailed analysis of a .motion3.json file."""
    info = load_motion(Path(motion_path))

    if _json_output:
        output(info.to_dict())
        return

    click.echo(f"\n  🎬 Motion Analysis: {info.path.name}\n")
    click.echo(f"  Version:     {info.version}")
    click.echo(f"  Duration:    {info.duration}s")
    click.echo(f"  FPS:         {info.fps}")
    click.echo(f"  Loop:        {'Yes' if info.loop else 'No'}")
    click.echo(f"  Curves:      {info.curve_count}")
    click.echo(f"  Segments:    {info.total_segment_count}")
    click.echo(f"  Points:      {info.total_point_count}")
    click.echo()

    if info.parameter_curves:
        click.echo(f"  Parameters ({len(info.parameter_curves)}):")
        for c in info.parameter_curves:
            click.echo(f"    - {c.id}  ({c.keyframe_count} keyframes)")
        click.echo()

    if info.part_curves:
        click.echo(f"  Parts ({len(info.part_curves)}):")
        for c in info.part_curves:
            click.echo(f"    - {c.id}  ({c.keyframe_count} keyframes)")
        click.echo()


# ── expressions ─────────────────────────────────────────────────

@cli.command()
@click.argument("model_path", type=click.Path(exists=True))
@handle_error
def expressions(model_path: str):
    """List all expressions in a Live2D model."""
    info = load_model(Path(model_path))

    if _json_output:
        output([{"name": e.name, "file": e.file} for e in info.expressions])
        return

    click.echo(f"\n  😊 Expressions: {info.path.name}\n")
    if not info.expressions:
        click.echo("  (none)")
        return
    for i, expr in enumerate(info.expressions):
        click.echo(f"  {i}. {expr.name}  →  {expr.file}")
    click.echo()


# ── expr-info ───────────────────────────────────────────────────

@cli.command(name="expr-info")
@click.argument("expression_path", type=click.Path(exists=True))
@handle_error
def expr_info_cmd(expression_path: str):
    """Detailed analysis of a .exp3.json file."""
    info = load_expression(Path(expression_path))

    if _json_output:
        output(info.to_dict())
        return

    click.echo(f"\n  😊 Expression Analysis: {info.path.name}\n")
    click.echo(f"  Version:  {info.version}")
    click.echo(f"  Fade In:  {info.fade_in}s")
    click.echo(f"  Fade Out: {info.fade_out}s")
    click.echo(f"  Params:   {info.param_count}\n")

    if info.params:
        click.echo(f"  {'Parameter':<30} {'Value':>8}")
        click.echo(f"  {'─' * 30} {'─' * 8}")
        for p in info.params:
            click.echo(f"  {p.id:<30} {p.value:>8.2f}")
    click.echo()


# ── textures ────────────────────────────────────────────────────

@cli.command()
@click.argument("model_path", type=click.Path(exists=True))
@handle_error
def textures(model_path: str):
    """List all textures with dimensions and sizes."""
    info = load_model(Path(model_path))
    model_dir = info.path.parent

    if _json_output:
        data = []
        for tex in info.textures:
            data.append(get_texture_info(model_dir / tex).to_dict())
        output(data)
        return

    click.echo(f"\n  🖼️  Textures: {info.path.name}\n")
    for i, tex in enumerate(info.textures):
        tinfo = get_texture_info(model_dir / tex)
        if tinfo.width > 0:
            click.echo(f"  ✅ {i}. {tex}")
            click.echo(f"     {tinfo.width}×{tinfo.height}  {tinfo.size_display}  ({tinfo.format})")
        else:
            click.echo(f"  ❌ {i}. {tex}  (MISSING)")
    click.echo()


# ── physics ─────────────────────────────────────────────────────

@cli.command()
@click.argument("physics_path", type=click.Path(exists=True))
@handle_error
def physics(physics_path: str):
    """Show physics simulation configuration."""
    info = load_physics(Path(physics_path))

    if _json_output:
        output(info.to_dict())
        return

    click.echo(f"\n  ⚡ Physics: {info.path.name}\n")
    click.echo(f"  Version:  {info.version}")
    click.echo(f"  Settings: {info.setting_count}\n")

    for s in info.settings:
        click.echo(f"  [{s.id}]")
        click.echo(f"    Inputs:  {', '.join(s.input_params)}")
        click.echo(f"    Outputs: {', '.join(s.output_params)}")
        click.echo(f"    Vertices: {len(s.vertices)}")
        if s.normalization:
            click.echo(f"    Normalization:")
            for k, v in s.normalization.items():
                click.echo(f"      {k}: min={v.get('Minimum')}, default={v.get('Default')}, max={v.get('Maximum')}")
        click.echo()

    if info.all_input_params:
        click.echo(f"  All input params:  {', '.join(info.all_input_params)}")
    if info.all_output_params:
        click.echo(f"  All output params: {', '.join(info.all_output_params)}")
    click.echo()


# ── moc3 ────────────────────────────────────────────────────────

@cli.command()
@click.argument("moc3_path", type=click.Path(exists=True))
@handle_error
def moc3(moc3_path: str):
    """Show .moc3 binary file info."""
    info = load_moc3(Path(moc3_path))

    if _json_output:
        output(info.to_dict())
        return

    click.echo(f"\n  🔧 Moc3 Info: {info.path.name}\n")
    click.echo(f"  Valid:     {'✅' if info.valid else '❌'}")
    click.echo(f"  Version:   {info.version}")
    click.echo(f"  Size:      {info._size_display()}")
    click.echo()


# ── params ──────────────────────────────────────────────────────

@cli.command()
@click.argument("model_path", type=click.Path(exists=True))
@handle_error
def params(model_path: str):
    """Show model parameter groups (from model3.json)."""
    info = load_model(Path(model_path))

    if _json_output:
        output(info.groups)
        return

    click.echo(f"\n  ⚙️  Parameters: {info.path.name}\n")
    if info.groups:
        for g in info.groups:
            target = g.get("Target", "")
            name = g.get("Name", "")
            ids = g.get("Ids", "")
            if isinstance(ids, list):
                ids = ", ".join(ids)
            click.echo(f"  Group: {name}  Target: {target}  Ids: {ids}")
    else:
        click.echo("  (no parameter groups defined in model3.json)")
    click.echo()


# ── deps ────────────────────────────────────────────────────────

@cli.command()
@click.argument("model_path", type=click.Path(exists=True))
@handle_error
def deps(model_path: str):
    """Show dependency graph: which motions/expressions use which parameters."""
    info = load_model(Path(model_path))
    graph = build_dependency_graph(info)

    if _json_output:
        output(graph.to_dict())
        return

    click.echo(f"\n  🔗 Dependency Graph: {info.path.name}\n")
    click.echo(f"  Parameters: {graph.param_count}")
    if graph.parse_errors:
        click.echo(f"  Parse errors: {len(graph.parse_errors)}")
    click.echo()

    for pid, usage in sorted(graph.params.items(), key=lambda x: -x[1].total_references):
        click.echo(f"  {pid}  (refs: {usage.total_references})")
        if usage.motions:
            for m in usage.motions[:3]:
                click.echo(f"    📹 {m}")
            if len(usage.motions) > 3:
                click.echo(f"    ... +{len(usage.motions) - 3} more")
        if usage.expressions:
            for e in usage.expressions:
                click.echo(f"    😊 {e}")
        click.echo()

    if graph.parse_errors:
        click.echo(f"  ⚠️  Parse errors:")
        for err in graph.parse_errors:
            click.echo(f"    {err['file']}: {err['error']}")
    click.echo()


# ── compare ─────────────────────────────────────────────────────

@cli.command()
@click.argument("model_a", type=click.Path(exists=True))
@click.argument("model_b", type=click.Path(exists=True))
@handle_error
def compare(model_a: str, model_b: str):
    """Compare two Live2D models."""
    info_a = load_model(Path(model_a))
    info_b = load_model(Path(model_b))
    diff = compare_models(info_a, info_b)

    if _json_output:
        output(diff.to_dict())
        return

    click.echo(f"\n  🔀 Model Comparison\n")
    click.echo(f"  A: {info_a.path.name}")
    click.echo(f"  B: {info_b.path.name}\n")

    if not diff.has_changes:
        click.echo("  ✅ Models are identical!")
        click.echo()
        return

    click.echo(f"  Added:    {len(diff.added)}")
    click.echo(f"  Removed:  {len(diff.removed)}")
    click.echo(f"  Changed:  {len(diff.changed)}")
    click.echo()

    if diff.added:
        click.echo("  ➕ Added:")
        for item in diff.added:
            click.echo(f"    [{item.category}] {item.name}")
        click.echo()

    if diff.removed:
        click.echo("  ➖ Removed:")
        for item in diff.removed:
            click.echo(f"    [{item.category}] {item.name}")
        click.echo()

    if diff.changed:
        click.echo("  🔄 Changed:")
        for item in diff.changed:
            click.echo(f"    [{item.category}] {item.name}: {item.detail}")
    click.echo()


# ── pack ────────────────────────────────────────────────────────

@cli.command()
@click.argument("model_path", type=click.Path(exists=True))
@click.option("--out", "-o", type=click.Path(), default=None, help="Output zip path")
@click.option("--no-motions", is_flag=True, help="Exclude motions")
@click.option("--no-expressions", is_flag=True, help="Exclude expressions")
@handle_error
def pack(model_path: str, out: Optional[str], no_motions: bool, no_expressions: bool):
    """Package a model and all dependencies into a zip."""
    info = load_model(Path(model_path))

    if out is None:
        out = str(info.path.with_suffix(".zip"))

    result = package_model(
        info,
        Path(out),
        include_motions=not no_motions,
        include_expressions=not no_expressions,
    )

    if _json_output:
        output(result.to_dict())
        return

    click.echo(f"\n  📦 Package: {result.output_path.name}\n")
    click.echo(f"  Files:  {result.files_count}")
    click.echo(f"  Size:   {result._size_display()}")

    if result.missing_files:
        click.echo(f"\n  ⚠️  Missing ({len(result.missing_files)}):")
        for f in result.missing_files:
            click.echo(f"    - {f}")
    click.echo()


# ── init ────────────────────────────────────────────────────────

@cli.command(name="yoyo-check")
@click.argument("model_path", type=click.Path(exists=True))
@click.option(
    "--require-motion",
    multiple=True,
    default=("idle",),
    show_default=True,
    help="Motion group required by the Yoyo desktop-pet runtime",
)
@handle_error
def yoyo_check(model_path: str, require_motion: tuple[str, ...]):
    """Check whether a Live2D export is ready for the Yoyo desktop pet."""
    report = check_yoyo_export(Path(model_path), required_motion_groups=require_motion)

    if _json_output:
        output(report.to_dict())
        if not report.ok:
            sys.exit(1)
        return

    click.echo(f"\n  🧪 Yoyo Live2D export check\n")
    click.echo(f"  Model:       {report.summary['model_file']}")
    click.echo(f"  Moc3:        {report.summary['moc3']}")
    click.echo(f"  Textures:    {report.summary['texture_count']}")
    click.echo(f"  Motions:     {report.summary['motion_count']} ({', '.join(report.summary['motion_groups']) or 'none'})")
    click.echo(f"  Expressions: {report.summary['expression_count']}")

    if report.errors:
        click.echo(f"\n  Errors: {len(report.errors)}")
        for error in report.errors:
            click.echo(f"  ❌ {error}")
        sys.exit(1)

    if report.warnings:
        click.echo(f"\n  Warnings: {len(report.warnings)}")
        for warning in report.warnings:
            click.echo(f"  ⚠️  {warning}")

    click.echo(f"\n  ✅ Ready for Yoyo desktop-pet integration\n")


@cli.command()
@click.argument("name")
@click.option("--dir", "-d", type=click.Path(), default=".", help="Output directory")
@handle_error
def init(name: str, dir: str):
    """Generate a Live2D model template/skeleton."""
    output_dir = Path(dir) / name
    model_path = generate_template(name, output_dir)

    if _json_output:
        output({
            "name": name,
            "directory": str(output_dir),
            "model_file": str(model_path),
            "files": [str(f.relative_to(output_dir)) for f in sorted(output_dir.rglob("*")) if f.is_file()],
        })
        return

    click.echo(f"\n  🆕 Template: {name}\n")
    click.echo(f"  Directory: {output_dir}")
    click.echo(f"  Files:")
    for f in sorted(output_dir.rglob("*")):
        if f.is_file():
            click.echo(f"    {f.relative_to(output_dir)}")
    click.echo()
    click.echo(f"  Edit {model_path.name} to start building your model!")
    click.echo()


# ── scan ────────────────────────────────────────────────────────

@cli.command()
@click.argument("directory", type=click.Path(exists=True))
@click.option("--validate", "-v", "do_validate", is_flag=True, help="Also validate each model")
@handle_error
def scan(directory: str, do_validate: bool):
    """Scan a directory for all Live2D models."""
    d = Path(directory)
    models = scan_directory(d)

    if _json_output:
        data = [m.to_dict() for m in models]
        if do_validate:
            results = validate_all(models)
            for i, r in enumerate(results):
                data[i]["validation"] = r.to_dict()
        output(data)
        return

    click.echo(f"\n  🔎 Scanning: {d}\n")
    if not models:
        click.echo("  No .model3.json files found.")
        return

    click.echo(f"  Found {len(models)} model(s):\n")
    for m in models:
        rel = m.path.relative_to(d)
        click.echo(f"  🎭 {rel}")
        click.echo(f"     Textures: {m.texture_count}  Motions: {m.motion_count}  Expressions: {m.expression_count}")

        if do_validate:
            r = validate_model(m)
            if r.errors:
                click.echo(f"     ⚠️  {len(r.errors)} missing files")
            else:
                click.echo(f"     ✅ All files present")
        click.echo()


# ── export ──────────────────────────────────────────────────────

@cli.command(name="export")
@click.argument("model_path", type=click.Path(exists=True))
@click.option("--format", "fmt", type=click.Choice(["json", "csv"]), default="json")
@click.option("--out", "-o", type=click.Path(), help="Output file path")
@handle_error
def export_cmd(model_path: str, fmt: str, out: Optional[str]):
    """Export model summary as JSON or CSV."""
    info = load_model(Path(model_path))

    if fmt == "json":
        text = json.dumps(info.to_dict(), indent=2, ensure_ascii=False)
    elif fmt == "csv":
        lines = ["type,group,name,file"]
        for tex in info.textures:
            lines.append(f"texture,,,{tex}")
        for expr in info.expressions:
            lines.append(f"expression,,{expr.name},{expr.file}")
        for group, motions in info.motions.items():
            for m in motions:
                fname = Path(m.file).stem
                lines.append(f"motion,{group},{fname},{m.file}")
        text = "\n".join(lines)

    if out:
        Path(out).write_text(text, encoding="utf-8")
        click.echo(f"  ✅ Exported to {out}")
    else:
        click.echo(text)


# ── edit-motion ────────────────────────────────────────────────

@cli.command(name="edit-motion")
@click.argument("model_path", type=click.Path(exists=True))
@click.option("--group", "-g", required=True, help="Motion group name")
@click.option("--index", "-i", type=int, required=True, help="Motion index in group (0-based)")
@click.option("--fade-in", type=float, help="New fade-in time (seconds)")
@click.option("--fade-out", type=float, help="New fade-out time (seconds)")
@click.option("--file", "new_file", help="Replace motion file path")
@handle_error
def edit_motion(model_path: str, group: str, index: int, fade_in: Optional[float], fade_out: Optional[float], new_file: Optional[str]):
    """Edit a motion's fade times or file path."""
    p = Path(model_path)
    auto_backup(p)
    info = load_model(p)

    if group not in info.motions:
        raise ValueError(f"Group '{group}' not found. Available: {list(info.motions.keys())}")

    motions = info.motions[group]
    if index < 0 or index >= len(motions):
        raise ValueError(f"Index {index} out of range. Group '{group}' has {len(motions)} motions (0-{len(motions)-1})")

    motion = motions[index]
    changes = []
    if fade_in is not None:
        motion.fade_in = fade_in
        changes.append(f"fade_in={fade_in}")
    if fade_out is not None:
        motion.fade_out = fade_out
        changes.append(f"fade_out={fade_out}")
    if new_file is not None:
        motion.file = new_file
        changes.append(f"file={new_file}")

    if not changes:
        click.echo("  Nothing to change. Use --fade-in, --fade-out, or --file.")
        return

    save_model(info)
    click.echo(f"  ✅ [{group}][{index}] {motion.file}")
    for c in changes:
        click.echo(f"     {c}")
    click.echo()


# ── add-motion ─────────────────────────────────────────────────

@cli.command(name="add-motion")
@click.argument("model_path", type=click.Path(exists=True))
@click.option("--group", "-g", required=True, help="Motion group name")
@click.option("--file", "motion_file", required=True, help="Motion file path")
@click.option("--fade-in", type=float, default=0.5, show_default=True)
@click.option("--fade-out", type=float, default=0.5, show_default=True)
@handle_error
def add_motion(model_path: str, group: str, motion_file: str, fade_in: float, fade_out: float):
    """Add a motion to a group (creates group if needed)."""
    p = Path(model_path)
    auto_backup(p)
    info = load_model(p)

    if group not in info.motions:
        info.motions[group] = []

    info.motions[group].append(MotionRef(file=motion_file, fade_in=fade_in, fade_out=fade_out))
    save_model(info)
    click.echo(f"  ✅ Added to [{group}] (now {len(info.motions[group])} motions)")
    click.echo(f"     {motion_file}  (fade: {fade_in}s / {fade_out}s)")
    click.echo()


# ── rm-motion ──────────────────────────────────────────────────

@cli.command(name="rm-motion")
@click.argument("model_path", type=click.Path(exists=True))
@click.option("--group", "-g", required=True, help="Motion group name")
@click.option("--index", "-i", type=int, required=True, help="Motion index to remove")
@click.confirmation_option(prompt="Are you sure?")
@handle_error
def rm_motion(model_path: str, group: str, index: int):
    """Remove a motion from a group."""
    p = Path(model_path)
    auto_backup(p)
    info = load_model(p)

    if group not in info.motions:
        raise ValueError(f"Group '{group}' not found.")

    motions = info.motions[group]
    if index < 0 or index >= len(motions):
        raise ValueError(f"Index {index} out of range (0-{len(motions)-1})")

    removed = motions.pop(index)
    if not motions:
        del info.motions[group]

    save_model(info)
    click.echo(f"  ✅ Removed [{group}][{index}]: {removed.file}")
    click.echo()


# ── add-expr ───────────────────────────────────────────────────

@cli.command(name="add-expr")
@click.argument("model_path", type=click.Path(exists=True))
@click.option("--name", "-n", required=True, help="Expression name")
@click.option("--file", "-f", required=True, help="Expression file path (.exp3.json)")
@handle_error
def add_expr(model_path: str, name: str, file: str):
    """Add an expression to the model."""
    p = Path(model_path)
    auto_backup(p)
    info = load_model(p)

    for e in info.expressions:
        if e.name == name:
            raise ValueError(f"Expression '{name}' already exists (→ {e.file})")

    info.expressions.append(ExpressionRef(name=name, file=file))
    save_model(info)
    click.echo(f"  ✅ Added expression: {name} → {file}")
    click.echo()


# ── rm-expr ────────────────────────────────────────────────────

@cli.command(name="rm-expr")
@click.argument("model_path", type=click.Path(exists=True))
@click.option("--name", "-n", required=True, help="Expression name to remove")
@click.confirmation_option(prompt="Are you sure?")
@handle_error
def rm_expr(model_path: str, name: str):
    """Remove an expression from the model."""
    p = Path(model_path)
    auto_backup(p)
    info = load_model(p)

    found = None
    for e in info.expressions:
        if e.name == name:
            found = e
            break

    if not found:
        raise ValueError(f"Expression '{name}' not found.")

    info.expressions.remove(found)
    save_model(info)
    click.echo(f"  ✅ Removed expression: {name} (was → {found.file})")
    click.echo()


# ── edit-texture ───────────────────────────────────────────────

@cli.command(name="edit-texture")
@click.argument("model_path", type=click.Path(exists=True))
@click.option("--index", "-i", type=int, required=True, help="Texture index (0-based)")
@click.option("--path", "new_path", required=True, help="New texture path")
@handle_error
def edit_texture(model_path: str, index: int, new_path: str):
    """Replace a texture file path."""
    p = Path(model_path)
    auto_backup(p)
    info = load_model(p)

    if index < 0 or index >= len(info.textures):
        raise ValueError(f"Index {index} out of range. Model has {len(info.textures)} textures (0-{len(info.textures)-1})")

    old = info.textures[index]
    info.textures[index] = new_path
    save_model(info)
    click.echo(f"  ✅ Texture [{index}]: {old} → {new_path}")
    click.echo()


# ── edit-model ─────────────────────────────────────────────────

@cli.command(name="edit-model")
@click.argument("model_path", type=click.Path(exists=True))
@click.option("--moc3", help="Replace moc3 file path")
@click.option("--physics", help="Replace physics file path")
@click.option("--pose", help="Replace pose file path")
@click.option("--userdata", help="Replace userdata file path")
@handle_error
def edit_model(model_path: str, moc3: Optional[str], physics: Optional[str], pose: Optional[str], userdata: Optional[str]):
    """Edit model-level file references (moc3, physics, pose, userdata)."""
    p = Path(model_path)
    auto_backup(p)
    info = load_model(p)

    changes = []
    if moc3 is not None:
        info.moc3 = moc3
        changes.append(f"moc3={moc3}")
    if physics is not None:
        info.physics = physics
        changes.append(f"physics={physics}")
    if pose is not None:
        info.pose = pose
        changes.append(f"pose={pose}")
    if userdata is not None:
        info.userdata = userdata
        changes.append(f"userdata={userdata}")

    if not changes:
        click.echo("  Nothing to change. Use --moc3, --physics, --pose, or --userdata.")
        return

    save_model(info)
    click.echo(f"  ✅ Updated {info.path.name}")
    for c in changes:
        click.echo(f"     {c}")
    click.echo()


# ── undo ───────────────────────────────────────────────────────

@cli.command()
@click.argument("model_path", type=click.Path(exists=True))
@click.option("--list", "do_list", is_flag=True, help="List available backups")
@click.option("--backup", "backup_name", default=None, help="Specific backup file to restore")
@handle_error
def undo(model_path: str, do_list: bool, backup_name: Optional[str]):
    """Undo last edit by restoring from auto-backup."""
    p = Path(model_path)

    if do_list:
        backups = list_backups(p)
        if not backups:
            click.echo("  No backups found.")
            return
        click.echo(f"\n  📋 Backups for {p.name}\n")
        for b in backups:
            click.echo(f"  {b['file']}  ({b['size']} bytes)")
        click.echo()
        return

    src = restore(p, backup_name)
    click.echo(f"  ✅ Restored from: {src.name}")
    click.echo()


# ── batch ──────────────────────────────────────────────────────

@cli.command()
@click.argument("directory", type=click.Path(exists=True))
@click.option("--set-fade-in", type=float, help="Set fade_in for all motions")
@click.option("--set-fade-out", type=float, help="Set fade_out for all motions")
@click.option("--add-motion-group", help="Add motion group name")
@click.option("--add-motion-file", help="Motion file path for --add-motion-group")
@click.option("--add-expr-name", help="Add expression name")
@click.option("--add-expr-file", help="Expression file path")
@click.option("--set-moc3", help="Set moc3 path for all models")
@click.option("--dry-run", is_flag=True, help="Show what would change without saving")
@handle_error
def batch(directory: str, set_fade_in: Optional[float], set_fade_out: Optional[float],
          add_motion_group: Optional[str], add_motion_file: Optional[str],
          add_expr_name: Optional[str], add_expr_file: Optional[str],
          set_moc3: Optional[str], dry_run: bool):
    """Batch-edit multiple models in a directory."""
    from cli_anything.live2d.core.scanner import scan_directory
    d = Path(directory)
    models = scan_directory(d)

    if not models:
        click.echo("  No models found.")
        return

    actions = []
    if set_fade_in is not None:
        actions.append(f"fade_in={set_fade_in}")
    if set_fade_out is not None:
        actions.append(f"fade_out={set_fade_out}")
    if add_motion_group and add_motion_file:
        actions.append(f"add motion [{add_motion_group}] → {add_motion_file}")
    if add_expr_name and add_expr_file:
        actions.append(f"add expression {add_expr_name} → {add_expr_file}")
    if set_moc3:
        actions.append(f"moc3={set_moc3}")

    if not actions:
        click.echo("  Nothing to do. Use --set-fade-in, --set-fade-out, --add-motion-*, --add-expr-*, --set-moc3.")
        return

    click.echo(f"\n  🔧 Batch: {len(models)} model(s)\n")
    for a in actions:
        click.echo(f"     {a}")
    click.echo()

    for m in models:
        info = load_model(m.path)
        changed = False

        if not dry_run:
            auto_backup(m.path)

        if set_fade_in is not None:
            for group in info.motions.values():
                for mot in group:
                    mot.fade_in = set_fade_in
                    changed = True

        if set_fade_out is not None:
            for group in info.motions.values():
                for mot in group:
                    mot.fade_out = set_fade_out
                    changed = True

        if add_motion_group and add_motion_file:
            if add_motion_group not in info.motions:
                info.motions[add_motion_group] = []
            info.motions[add_motion_group].append(MotionRef(file=add_motion_file))
            changed = True

        if add_expr_name and add_expr_file:
            existing_names = {e.name for e in info.expressions}
            if add_expr_name not in existing_names:
                info.expressions.append(ExpressionRef(name=add_expr_name, file=add_expr_file))
                changed = True

        if set_moc3:
            info.moc3 = set_moc3
            changed = True

        status = "would change" if dry_run else ("✅ updated" if changed else "no change")
        click.echo(f"  {m.path.relative_to(d)}  → {status}")

        if changed and not dry_run:
            save_model(info)

    click.echo()


# ── lint ───────────────────────────────────────────────────────

@cli.command()
@click.argument("model_path", type=click.Path(exists=True))
@click.option("--level", type=click.Choice(["error", "warning", "info"]), default="warning", help="Min level to show")
@handle_error
def lint(model_path: str, level: str):
    """Lint a model for best practices (naming, textures, structure)."""
    report = lint_model(Path(model_path))

    if _json_output:
        output(report.to_dict())
        if not report.ok:
            sys.exit(1)
        return

    level_order = {"error": 0, "warning": 1, "info": 2}
    min_level = level_order.get(level, 1)

    filtered = [i for i in report.issues if level_order.get(i.level, 0) <= min_level]

    click.echo(f"\n  🔎 Lint: {report.model_path.name}\n")
    if not filtered:
        click.echo("  ✅ No issues found!")
    else:
        icons = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}
        for i in filtered:
            icon = icons.get(i.level, "?")
            click.echo(f"  {icon} [{i.category}] {i.message}")
            if i.fix_hint:
                click.echo(f"     💡 {i.fix_hint}")
        click.echo(f"\n  Summary: {len(report.errors)} errors, {len(report.warnings)} warnings, {len(report.infos)} info")

    click.echo()
    if not report.ok:
        sys.exit(1)


# ── diff (enhanced) ────────────────────────────────────────────

@cli.command(name="diff")
@click.argument("model_a", type=click.Path(exists=True))
@click.argument("model_b", type=click.Path(exists=True))
@handle_error
def diff_cmd(model_a: str, model_b: str):
    """Detailed diff between two models (field, motion, expression, texture level)."""
    info_a = load_model(Path(model_a))
    info_b = load_model(Path(model_b))
    d = diff_models(info_a, info_b)

    if _json_output:
        output(d.to_dict())
        return

    click.echo(f"\n  🔀 Diff: {info_a.path.name} vs {info_b.path.name}\n")
    if not d.has_changes:
        click.echo("  ✅ No differences!")
        click.echo()
        return

    icons = {"texture": "🖼️", "motion": "🎬", "expression": "😊", "field": "📝", "param": "⚙️"}
    for item in d.items:
        icon = icons.get(item.category, "•")
        click.echo(f"  {icon} [{item.category}] {item.name}")
        click.echo(f"     {item.detail}")

    click.echo(f"\n  Total: {len(d.items)} difference(s)")
    click.echo()


# ── param-edit ─────────────────────────────────────────────────

@cli.command(name="param-edit")
@click.argument("expression_path", type=click.Path(exists=True))
@click.option("--param-id", "-p", required=True, help="Parameter ID (e.g. ParamEyeLOpen)")
@click.option("--value", "-v", type=float, required=True, help="New value")
@click.option("--fade-in", type=float, help="Override fade-in for this param")
@click.option("--fade-out", type=float, help="Override fade-out for this param")
@handle_error
def param_edit(expression_path: str, param_id: str, value: float, fade_in: Optional[float], fade_out: Optional[float]):
    """Edit a parameter value inside an expression file (.exp3.json)."""
    p = Path(expression_path)
    if not p.exists():
        raise FileNotFoundError(f"Expression file not found: {p}")

    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)

    params = data.get("Parameters", [])
    found = False
    for param in params:
        if param.get("Id") == param_id:
            param["Value"] = value
            if fade_in is not None:
                param["FadeInTime"] = fade_in
            if fade_out is not None:
                param["FadeOutTime"] = fade_out
            found = True
            break

    if not found:
        # Add new param
        new_param = {"Id": param_id, "Value": value}
        if fade_in is not None:
            new_param["FadeInTime"] = fade_in
        if fade_out is not None:
            new_param["FadeOutTime"] = fade_out
        params.append(new_param)
        data["Parameters"] = params
        click.echo(f"  ✅ Added {param_id}={value}")
    else:
        click.echo(f"  ✅ Updated {param_id}={value}")

    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    click.echo()


# ── snapshot ───────────────────────────────────────────────────

@cli.command()
@click.argument("model_path", type=click.Path(exists=True))
@click.option("--out", "-o", type=click.Path(), default=None, help="Output HTML path")
@click.option("--embed", is_flag=True, help="Embed textures as base64 (self-contained)")
@handle_error
def snapshot_cmd(model_path: str, out: Optional[str], embed: bool):
    """Generate an HTML preview of the model."""
    info = load_model(Path(model_path))

    if out is None:
        name = info.path.name.replace(".model3.json", "").replace(".json", "")
        out = str(info.path.parent / f"{name}.html")

    result = write_snapshot(info, Path(out), embed_textures=embed)
    click.echo(f"  ✅ Preview: {result}")
    click.echo()


# ── watch ──────────────────────────────────────────────────────

@cli.command()
@click.argument("directory", type=click.Path(exists=True))
@click.option("--interval", type=float, default=2.0, show_default=True, help="Check interval in seconds")
@handle_error
def watch(directory: str, interval: float):
    """Watch directory for changes and auto-validate Live2D models."""
    import time
    from cli_anything.live2d.core.scanner import scan_directory

    d = Path(directory)
    click.echo(f"\n  👁️  Watching: {d}")
    click.echo(f"  Interval: {interval}s  (Ctrl+C to stop)\n")

    last_mtimes: dict[str, float] = {}

    try:
        while True:
            models = scan_directory(d)
            current_files = {}

            for m in models:
                # Collect all related files
                related = [m.path]
                model_dir = m.path.parent
                for tex in m.textures:
                    related.append(model_dir / tex)
                for motions in m.motions.values():
                    for mot in motions:
                        related.append(model_dir / mot.file)
                for expr in m.expressions:
                    related.append(model_dir / expr.file)

                for f in related:
                    if f.exists():
                        key = str(f)
                        mtime = f.stat().st_mtime
                        current_files[key] = mtime

                        if key in last_mtimes and mtime != last_mtimes[key]:
                            click.echo(f"  🔄 Changed: {f.relative_to(d)}  ({time.strftime('%H:%M:%S')})")
                            # Auto-validate the parent model
                            result = validate_model(m)
                            if result.errors:
                                for e in result.errors:
                                    click.echo(f"     ❌ {e}")
                            else:
                                click.echo(f"     ✅ Valid")

            last_mtimes = current_files
            time.sleep(interval)

    except KeyboardInterrupt:
        click.echo("\n  Stopped watching.")


# ── atlas ──────────────────────────────────────────────────────

@cli.command()
@click.argument("model_path", type=click.Path(exists=True))
@click.option("--merge", is_flag=True, help="Suggest texture merge (analyze sizes)")
@click.option("--split", is_flag=True, help="Suggest texture split (oversized textures)")
@click.option("--max-size", type=int, default=2048, show_default=True, help="Max texture dimension")
@handle_error
def atlas(model_path: str, merge: bool, split: bool, max_size: int):
    """Analyze and manage texture atlases."""
    info = load_model(Path(model_path))
    model_dir = info.path.parent

    click.echo(f"\n  🗺️  Texture Atlas: {info.path.name}\n")

    textures_info = []
    for i, tex in enumerate(info.textures):
        tinfo = get_texture_info(model_dir / tex)
        textures_info.append((i, tex, tinfo))
        exists = "✅" if tinfo.width > 0 else "❌"
        size_str = f"{tinfo.width}×{tinfo.height}" if tinfo.width > 0 else "MISSING"
        click.echo(f"  {exists} [{i}] {tex}  {size_str}  {tinfo.size_display}")

    if merge:
        click.echo(f"\n  📦 Merge suggestions:")
        small = [(i, tex, t) for i, tex, t in textures_info if t.width > 0 and t.width <= 512 and t.height <= 512]
        if len(small) >= 2:
            click.echo(f"     {len(small)} small textures could be merged into a single atlas")
            for i, tex, t in small:
                click.echo(f"       [{i}] {tex} ({t.width}×{t.height})")
        else:
            click.echo(f"     No small textures to merge.")

    if split:
        click.echo(f"\n  ✂️  Split suggestions:")
        oversized = [(i, tex, t) for i, tex, t in textures_info if t.width > max_size or t.height > max_size]
        if oversized:
            for i, tex, t in oversized:
                click.echo(f"     [{i}] {tex} ({t.width}×{t.height}) exceeds {max_size}px")
        else:
            click.echo(f"     All textures within {max_size}px limit.")

    click.echo()


# ── migrate ────────────────────────────────────────────────────

@cli.command()
@click.argument("model_path", type=click.Path(exists=True))
@click.option("--target-version", type=int, default=3, show_default=True, help="Target model version")
@click.option("--dry-run", is_flag=True, help="Show changes without saving")
@handle_error
def migrate(model_path: str, target_version: int, dry_run: bool):
    """Migrate a model to a newer format version."""
    p = Path(model_path)
    info = load_model(p)

    click.echo(f"\n  🔄 Migrate: {info.path.name}\n")
    click.echo(f"  Current version: {info.version}")
    click.echo(f"  Target version:  {target_version}")

    current = int(info.version) if info.version else 0
    if current >= target_version:
        click.echo(f"\n  ✅ Already at version {current}, no migration needed.")
        click.echo()
        return

    changes = []

    # Read raw JSON for structural changes
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)

    refs = data.get("FileReferences", {})

    # Version 1 → 2: ensure Motions dict exists
    if current < 2 and "Motions" not in refs:
        refs["Motions"] = {}
        changes.append("Added Motions structure")

    # Version 2 → 3: ensure Groups array exists
    if current < 3 and "Groups" not in data:
        data["Groups"] = []
        changes.append("Added Groups array")

    data["Version"] = target_version
    changes.append(f"Version {current} → {target_version}")

    if not changes:
        click.echo("  No structural changes needed.")
    else:
        for c in changes:
            click.echo(f"  • {c}")

    if dry_run:
        click.echo(f"\n  (dry run — not saved)")
    else:
        if not dry_run:
            auto_backup(p)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        click.echo(f"\n  ✅ Saved.")

    click.echo()


# ── find-replace ───────────────────────────────────────────────

@cli.command(name="find-replace")
@click.argument("model_path", type=click.Path(exists=True))
@click.option("--find", "-f", required=True, help="Text to find in file paths")
@click.option("--replace", "-r", required=True, help="Replacement text")
@click.option("--dry-run", is_flag=True, help="Show changes without saving")
@handle_error
def find_replace(model_path: str, find: str, replace: str, dry_run: bool):
    """Batch rename file references (textures, motions, expressions)."""
    p = Path(model_path)
    info = load_model(p)
    changes = []

    # Textures
    for i, tex in enumerate(info.textures):
        if find in tex:
            new_tex = tex.replace(find, replace)
            changes.append(f"texture [{i}]: {tex} → {new_tex}")
            if not dry_run:
                info.textures[i] = new_tex

    # Motions
    for group, motions in info.motions.items():
        for i, m in enumerate(motions):
            if find in m.file:
                new_file = m.file.replace(find, replace)
                changes.append(f"motion [{group}][{i}]: {m.file} → {new_file}")
                if not dry_run:
                    m.file = new_file

    # Expressions
    for expr in info.expressions:
        if find in expr.file:
            new_file = expr.file.replace(find, replace)
            changes.append(f"expression {expr.name}: {expr.file} → {new_file}")
            if not dry_run:
                expr.file = new_file
        if find in expr.name:
            new_name = expr.name.replace(find, replace)
            changes.append(f"expression name: {expr.name} → {new_name}")
            if not dry_run:
                expr.name = new_name

    # Top-level
    for field_name in ("moc3", "physics", "pose", "userdata"):
        val = getattr(info, field_name)
        if val and find in val:
            new_val = val.replace(find, replace)
            changes.append(f"{field_name}: {val} → {new_val}")
            if not dry_run:
                setattr(info, field_name, new_val)

    if not changes:
        click.echo(f"  No occurrences of '{find}' found.")
        return

    click.echo(f"\n  🔍 Find & Replace: '{find}' → '{replace}'\n")
    for c in changes:
        click.echo(f"  {'📝' if not dry_run else '👀'} {c}")

    if not dry_run:
        auto_backup(p)
        save_model(info)
        click.echo(f"\n  ✅ Saved ({len(changes)} change(s))")
    else:
        click.echo(f"\n  (dry run — {len(changes)} change(s) would be made)")
    click.echo()


# ── orphan ─────────────────────────────────────────────────────

@cli.command()
@click.argument("model_path", type=click.Path(exists=True))
@handle_error
def orphan(model_path: str):
    """Find files in the model directory that aren't referenced by the model."""
    info = load_model(Path(model_path))
    model_dir = info.path.parent

    # Collect all referenced files
    referenced = set()
    referenced.add(info.moc3)
    referenced.add(info.physics)
    referenced.add(info.pose)
    referenced.add(info.userdata)
    referenced.add(info.display_info)
    referenced.update(info.textures)
    for motions in info.motions.values():
        for m in motions:
            referenced.add(m.file)
    for e in info.expressions:
        referenced.add(e.file)
    # Remove empty strings
    referenced.discard("")

    # Scan all files in model directory
    all_files = set()
    for f in model_dir.rglob("*"):
        if f.is_file() and f.name != info.path.name:
            rel = str(f.relative_to(model_dir))
            # Skip backup dirs and hidden files
            if ".live2d-backups" in rel or rel.startswith("."):
                continue
            all_files.add(rel)

    orphans = sorted(all_files - referenced)

    if _json_output:
        output({"model": str(info.path), "referenced": len(referenced), "total_files": len(all_files), "orphans": orphans})
        return

    click.echo(f"\n  👻 Orphan Files: {info.path.name}\n")
    click.echo(f"  Referenced: {len(referenced)} files")
    click.echo(f"  Total:      {len(all_files)} files")
    click.echo()

    if not orphans:
        click.echo("  ✅ No orphan files!")
    else:
        click.echo(f"  {len(orphans)} orphan file(s):\n")
        for o in orphans:
            click.echo(f"  🗑️  {o}")
    click.echo()


# ── restore-file ───────────────────────────────────────────────

@cli.command(name="restore-file")
@click.argument("model_path", type=click.Path(exists=True))
@click.option("--file", "target_file", required=True, help="File to restore (relative path from model dir)")
@click.option("--backup", "backup_name", default=None, help="Specific backup to restore from")
@handle_error
def restore_file(model_path: str, target_file: str, backup_name: Optional[str]):
    """Restore a specific file from backup."""
    from cli_anything.live2d.core.backup import _backup_dir_for
    p = Path(model_path)
    bdir = _backup_dir_for(p)

    if not bdir.exists():
        raise FileNotFoundError(f"No backups found for {p.name}")

    # Find the backup
    if backup_name:
        backup_path = bdir / backup_name
    else:
        backups = sorted(bdir.glob("*.model3.json"), reverse=True)
        if not backups:
            raise FileNotFoundError("No backups found")
        backup_path = backups[0]

    if not backup_path.exists():
        raise FileNotFoundError(f"Backup not found: {backup_path}")

    # The backup is the model JSON itself
    model_dir = p.parent
    if target_file == p.name:
        # Restoring the model file itself
        import shutil
        shutil.copy2(backup_path, p)
        click.echo(f"  ✅ Restored {p.name} from {backup_path.name}")
    else:
        click.echo(f"  ℹ️  Backups only store the .model3.json file.")
        click.echo(f"     To restore other files, use your version control (git).")
    click.echo()


# ── backup-clean ───────────────────────────────────────────────

@cli.command(name="backup-clean")
@click.argument("model_path", type=click.Path(exists=True))
@click.option("--keep", "-k", type=int, default=10, show_default=True, help="Number of recent backups to keep")
@click.option("--dry-run", is_flag=True, help="Show what would be deleted")
@handle_error
def backup_clean(model_path: str, keep: int, dry_run: bool):
    """Clean old backups, keep only the N most recent."""
    from cli_anything.live2d.core.backup import _backup_dir_for
    p = Path(model_path)
    bdir = _backup_dir_for(p)

    if not bdir.exists():
        click.echo("  No backups found.")
        return

    backups = sorted(bdir.glob("*.model3.json"), reverse=True)
    to_delete = backups[keep:]

    if _json_output:
        deleted = []
        if not dry_run:
            for f in to_delete:
                f.unlink()
                deleted.append(f.name)
        output({
            "total": len(backups),
            "keep": keep,
            "delete": len(to_delete),
            "deleted": deleted,
            "dry_run": dry_run,
            "files": [f.name for f in to_delete],
        })
        return

    click.echo(f"\n  🧹 Backup Cleanup\n")
    click.echo(f"  Total backups: {len(backups)}")
    click.echo(f"  Keeping:       {min(keep, len(backups))}")
    click.echo(f"  Deleting:      {len(to_delete)}")
    click.echo()

    for f in to_delete:
        if dry_run:
            click.echo(f"  👀 would delete: {f.name}")
        else:
            f.unlink()
            click.echo(f"  🗑️  deleted: {f.name}")

    if not dry_run and to_delete:
        click.echo(f"\n  ✅ Cleaned {len(to_delete)} backup(s)")
    elif not to_delete:
        click.echo("  Nothing to clean.")
    click.echo()


# ── manifest ───────────────────────────────────────────────────

@cli.command()
@click.argument("model_path", type=click.Path(exists=True))
@click.option("--out", "-o", type=click.Path(), help="Output file path")
@handle_error
def manifest(model_path: str, out: Optional[str]):
    """Generate a manifest of all model files with checksums and sizes."""
    import hashlib
    info = load_model(Path(model_path))
    model_dir = info.path.parent

    files = []

    # Model file itself
    files.append(_manifest_entry(info.path, model_dir))

    # Moc3
    if info.moc3:
        p = model_dir / info.moc3
        if p.exists():
            files.append(_manifest_entry(p, model_dir))

    # Textures
    for tex in info.textures:
        p = model_dir / tex
        if p.exists():
            files.append(_manifest_entry(p, model_dir))

    # Motions
    for motions in info.motions.values():
        for m in motions:
            p = model_dir / m.file
            if p.exists():
                files.append(_manifest_entry(p, model_dir))

    # Expressions
    for e in info.expressions:
        p = model_dir / e.file
        if p.exists():
            files.append(_manifest_entry(p, model_dir))

    # Physics, pose, userdata
    for ref in (info.physics, info.pose, info.userdata, info.display_info):
        if ref:
            p = model_dir / ref
            if p.exists():
                files.append(_manifest_entry(p, model_dir))

    total_size = sum(f["size"] for f in files)

    if _json_output:
        output({"model": str(info.path), "files": len(files), "total_size": total_size, "entries": files})
        return

    click.echo(f"\n  📋 Manifest: {info.path.name}\n")
    click.echo(f"  {'File':<45} {'Size':>10}  SHA256 (short)")
    click.echo(f"  {'─' * 45} {'─' * 10}  {'─' * 16}")
    for f in files:
        size_str = _format_size(f["size"])
        click.echo(f"  {f['path']:<45} {size_str:>10}  {f['sha256'][:12]}")
    click.echo(f"\n  Total: {len(files)} files, {_format_size(total_size)}")
    click.echo()

    if out:
        import json as _json
        Path(out).write_text(_json.dumps({"files": files, "total": len(files), "total_size": total_size}, indent=2))
        click.echo(f"  ✅ Written to {out}")
        click.echo()


def _manifest_entry(path: Path, base: Path) -> dict:
    import hashlib
    data = path.read_bytes()
    return {
        "path": str(path.relative_to(base)),
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _format_size(n: int) -> str:
    if n < 1024:
        return f"{n}B"
    elif n < 1024 * 1024:
        return f"{n / 1024:.1f}KB"
    else:
        return f"{n / (1024*1024):.1f}MB"


# ── stats ──────────────────────────────────────────────────────

@cli.command()
@click.argument("directory", type=click.Path(exists=True))
@handle_error
def stats(directory: str):
    """Project overview: model count, motions, expressions, textures, disk usage."""
    from cli_anything.live2d.core.scanner import scan_directory
    d = Path(directory)
    models = scan_directory(d)

    total_motions = 0
    total_expressions = 0
    total_textures = 0
    total_groups = set()
    total_size = 0

    for m in models:
        info = load_model(m.path)
        total_motions += info.motion_count
        total_expressions += info.expression_count
        total_textures += info.texture_count
        total_groups.update(info.motions.keys())
        total_size += info.path.stat().st_size
        model_dir = info.path.parent
        for tex in info.textures:
            p = model_dir / tex
            if p.exists():
                total_size += p.stat().st_size
        for motions in info.motions.values():
            for mot in motions:
                p = model_dir / mot.file
                if p.exists():
                    total_size += p.stat().st_size
        for e in info.expressions:
            p = model_dir / e.file
            if p.exists():
                total_size += p.stat().st_size

    if _json_output:
        output({
            "directory": str(d),
            "models": len(models),
            "motions": total_motions,
            "expressions": total_expressions,
            "textures": total_textures,
            "groups": sorted(total_groups),
            "total_size": total_size,
        })
        return

    click.echo(f"\n  📊 Project Stats: {d}\n")
    click.echo(f"  Models:      {len(models)}")
    click.echo(f"  Motions:     {total_motions}")
    click.echo(f"  Expressions: {total_expressions}")
    click.echo(f"  Textures:    {total_textures}")
    click.echo(f"  Groups:      {len(total_groups)} ({', '.join(sorted(total_groups))})")
    click.echo(f"  Disk:        {_format_size(total_size)}")
    click.echo()


# ── gen-motion ─────────────────────────────────────────────────

@cli.command(name="gen-motion")
@click.argument("name")
@click.option("--duration", "-d", type=float, default=2.0, show_default=True, help="Duration in seconds")
@click.option("--fps", type=float, default=30, show_default=True, help="Frames per second")
@click.option("--loop", "do_loop", is_flag=True, default=True, help="Loop animation")
@click.option("--out", "-o", type=click.Path(), default=None, help="Output path")
@handle_error
def gen_motion(name: str, duration: float, fps: float, do_loop: bool, out: Optional[str]):
    """Generate a skeleton .motion3.json file."""
    if out is None:
        out = f"{name}.motion3.json"

    data = {
        "Version": 1,
        "Meta": {
            "Duration": duration,
            "Fps": fps,
            "Loop": do_loop,
            "CurveCount": 0,
            "TotalSegmentCount": 0,
            "TotalPointCount": 0,
        },
        "Curves": [],
    }

    Path(out).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    click.echo(f"  ✅ Generated: {out}")
    click.echo(f"     Duration: {duration}s  FPS: {fps}  Loop: {do_loop}")
    click.echo()


# ── gen-expr ───────────────────────────────────────────────────

@cli.command(name="gen-expr")
@click.argument("name")
@click.option("--fade-in", type=float, default=0.5, show_default=True)
@click.option("--fade-out", type=float, default=0.5, show_default=True)
@click.option("--out", "-o", type=click.Path(), default=None, help="Output path")
@handle_error
def gen_expr(name: str, fade_in: float, fade_out: float, out: Optional[str]):
    """Generate a skeleton .exp3.json file."""
    if out is None:
        out = f"{name}.exp3.json"

    data = {
        "Version": 1,
        "FadeInTime": fade_in,
        "FadeOutTime": fade_out,
        "Parameters": [],
    }

    Path(out).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    click.echo(f"  ✅ Generated: {out}")
    click.echo(f"     Fade: {fade_in}s / {fade_out}s")
    click.echo(f"     Edit with: cli-anything-live2d param-edit {out} -p ParamId -v 1.0")
    click.echo()


# ── rename-group ───────────────────────────────────────────────

@cli.command(name="rename-group")
@click.argument("model_path", type=click.Path(exists=True))
@click.option("--old", required=True, help="Current group name")
@click.option("--new", "new_name", required=True, help="New group name")
@handle_error
def rename_group(model_path: str, old: str, new_name: str):
    """Rename a motion group."""
    p = Path(model_path)
    auto_backup(p)
    info = load_model(p)

    if old not in info.motions:
        raise ValueError(f"Group '{old}' not found. Available: {list(info.motions.keys())}")
    if new_name in info.motions:
        raise ValueError(f"Group '{new_name}' already exists.")

    info.motions[new_name] = info.motions.pop(old)
    save_model(info)
    click.echo(f"  ✅ Renamed group: {old} → {new_name} ({len(info.motions[new_name])} motions)")
    click.echo()


# ── param-list ─────────────────────────────────────────────────

@cli.command(name="param-list")
@click.argument("model_path", type=click.Path(exists=True))
@handle_error
def param_list(model_path: str):
    """List all unique parameters used across motions and expressions."""
    info = load_model(Path(model_path))
    model_dir = info.path.parent

    params: dict[str, dict] = {}  # id -> {motions: [], expressions: []}

    # Scan motions
    for group, motions in info.motions.items():
        for m in motions:
            mp = model_dir / m.file
            if not mp.exists():
                continue
            try:
                from cli_anything.live2d.core.motion_parser import load_motion
                minfo = load_motion(mp)
                for c in minfo.parameter_curves:
                    if c.id not in params:
                        params[c.id] = {"motions": [], "expressions": []}
                    params[c.id]["motions"].append(f"[{group}] {Path(m.file).stem}")
            except Exception:
                pass

    # Scan expressions
    for expr in info.expressions:
        ep = model_dir / expr.file
        if not ep.exists():
            continue
        try:
            from cli_anything.live2d.core.expression_parser import load_expression
            einfo = load_expression(ep)
            for p in einfo.params:
                if p.id not in params:
                    params[p.id] = {"motions": [], "expressions": []}
                params[p.id]["expressions"].append(expr.name)
        except Exception:
            pass

    if _json_output:
        output({"model": str(info.path), "parameter_count": len(params), "parameters": params})
        return

    click.echo(f"\n  ⚙️  Parameter Usage: {info.path.name}\n")
    if not params:
        click.echo("  (no parameters found in motions/expressions)")
        click.echo()
        return

    for pid in sorted(params):
        usage = params[pid]
        total = len(usage["motions"]) + len(usage["expressions"])
        click.echo(f"  {pid}  ({total} reference(s))")
        for m in usage["motions"][:3]:
            click.echo(f"    📹 {m}")
        if len(usage["motions"]) > 3:
            click.echo(f"    ... +{len(usage['motions']) - 3} more motions")
        for e in usage["expressions"]:
            click.echo(f"    😊 {e}")
    click.echo()


# ── flatten ────────────────────────────────────────────────────

@cli.command()
@click.argument("model_path", type=click.Path(exists=True))
@click.option("--out-dir", "-o", required=True, help="Output directory for flattened model")
@click.option("--dry-run", is_flag=True, help="Show what would be copied")
@handle_error
def flatten(model_path: str, out_dir: str, dry_run: bool):
    """Flatten model directory structure (all files in one dir) for deployment."""
    import shutil
    info = load_model(Path(model_path))
    model_dir = info.path.parent
    out = Path(out_dir)

    # Collect all files
    files = []
    files.append((info.path, info.path.name))
    if info.moc3:
        files.append((model_dir / info.moc3, Path(info.moc3).name))
    for tex in info.textures:
        files.append((model_dir / tex, Path(tex).name))
    for motions in info.motions.values():
        for m in motions:
            files.append((model_dir / m.file, Path(m.file).name))
            sound = m.extra.get("Sound")
            if isinstance(sound, str) and sound:
                files.append((model_dir / sound, Path(sound).name))
    for e in info.expressions:
        files.append((model_dir / e.file, Path(e.file).name))
    for ref in (info.physics, info.pose, info.userdata, info.display_info):
        if ref:
            p = model_dir / ref
            if p.exists():
                files.append((p, Path(ref).name))

    # Deduplicate and detect collisions
    seen = {}  # name -> original source path
    unique_files = []
    collisions = []
    for src, name in files:
        if not src.exists():
            continue
        if name in seen:
            if seen[name] != src:
                collisions.append((name, seen[name], src))
        else:
            seen[name] = src
            unique_files.append((src, name))

    if collisions:
        click.echo(f"\n  ❌ Basename collisions detected:\n")
        for name, a, b in collisions:
            click.echo(f"     {name}:")
            click.echo(f"       {a.relative_to(model_dir)}")
            click.echo(f"       {b.relative_to(model_dir)}")
        click.echo(f"\n  Cannot flatten — rename files to avoid collisions first.")
        click.echo()
        sys.exit(1)

    click.echo(f"\n  📦 Flatten: {info.path.name} → {out}\n")

    if dry_run:
        for src, name in unique_files:
            click.echo(f"  👀 {src.relative_to(model_dir)} → {name}")
        click.echo(f"\n  (dry run — {len(unique_files)} files would be copied)")
        click.echo()
        return

    out.mkdir(parents=True, exist_ok=True)
    for src, name in unique_files:
        shutil.copy2(src, out / name)
        click.echo(f"  ✅ {name}")

    # Update model JSON to use flat paths
    flat_info = load_model(info.path)
    flat_info.moc3 = Path(flat_info.moc3).name if flat_info.moc3 else ""
    flat_info.textures = [Path(t).name for t in flat_info.textures]
    flat_info.physics = Path(flat_info.physics).name if flat_info.physics else ""
    flat_info.pose = Path(flat_info.pose).name if flat_info.pose else ""
    flat_info.userdata = Path(flat_info.userdata).name if flat_info.userdata else ""
    flat_info.display_info = Path(flat_info.display_info).name if flat_info.display_info else ""
    for motions in flat_info.motions.values():
        for m in motions:
            m.file = Path(m.file).name
            sound = m.extra.get("Sound")
            if isinstance(sound, str) and sound:
                m.extra["Sound"] = Path(sound).name
    for e in flat_info.expressions:
        e.file = Path(e.file).name

    flat_info.path = out / info.path.name
    save_model(flat_info)

    if _json_output:
        output({"files": len(unique_files), "out_dir": str(out), "entries": [n for _, n in unique_files]})
    else:
        click.echo(f"\n  ✅ Flattened {len(unique_files)} files to {out}")
        click.echo()


# ── runtime-check ──────────────────────────────────────────────

@cli.command(name="runtime-check")
@click.argument("model_path", type=click.Path(exists=True))
@click.option("--target", type=click.Choice(["cubism-viewer", "web-sdk", "yoyo", "all"]), default="all", show_default=True)
@handle_error
def runtime_check(model_path: str, target: str):
    """Check model compatibility with specific Live2D runtimes."""
    info = load_model(Path(model_path))
    model_dir = info.path.parent
    issues = []

    # Common checks
    if not info.moc3:
        issues.append(("error", "common", "No moc3 file referenced"))
    else:
        moc3_path = model_dir / info.moc3
        if not moc3_path.exists():
            issues.append(("error", "common", f"Moc3 file not found: {info.moc3}"))
        else:
            size = moc3_path.stat().st_size
            if size < 1024:
                issues.append(("error", "common", f"Moc3 file too small ({size} bytes)"))

    if not info.textures:
        issues.append(("error", "common", "No textures defined"))
    else:
        for i, tex in enumerate(info.textures):
            tp = model_dir / tex
            if not tp.exists():
                issues.append(("error", "common", f"Texture [{i}] missing: {tex}"))
            else:
                from cli_anything.live2d.core.texture_info import get_texture_info
                tinfo = get_texture_info(tp)
                if tinfo.width > 4096 or tinfo.height > 4096:
                    issues.append(("warning", "common", f"Texture [{i}] very large ({tinfo.width}×{tinfo.height})"))

    if not info.motions:
        issues.append(("warning", "common", "No motions defined"))

    # Web SDK checks
    if target in ("web-sdk", "all"):
        if not info.physics:
            issues.append(("warning", "web-sdk", "No physics file (recommended for web)"))
        for group, motions in info.motions.items():
            for i, m in enumerate(motions):
                if m.fade_in > 1.0 or m.fade_out > 1.0:
                    issues.append(("info", "web-sdk", f"[{group}][{i}] has long fade times ({m.fade_in}/{m.fade_out}s) — may feel sluggish on web"))

    # Cubism Viewer checks
    if target in ("cubism-viewer", "all"):
        if not info.expressions:
            issues.append(("info", "cubism-viewer", "No expressions (Cubism Viewer supports them well)"))
        if "Idle" not in info.motions and "idle" not in info.motions:
            issues.append(("warning", "cubism-viewer", "No Idle motion group (expected by most viewers)"))

    # Yoyo checks
    if target in ("yoyo", "all"):
        # Normalize: accept both "Idle" and "idle"
        yoyo_idle = info.motions.get("Idle") or info.motions.get("idle")
        if not yoyo_idle:
            issues.append(("error", "yoyo", "No Idle group (required for Yoyo)"))
        else:
            if not any(m.fade_in <= 0.5 for m in yoyo_idle):
                issues.append(("warning", "yoyo", "Idle motions should have fast fade-in (≤0.5s)"))

    if _json_output:
        output({"model": str(info.path), "target": target, "issues": [{"level": l, "scope": s, "msg": m} for l, s, m in issues]})
        if any(l == "error" for l, _, _ in issues):
            sys.exit(1)
        return

    click.echo(f"\n  🔧 Runtime Check: {info.path.name}  (target: {target})\n")
    if not issues:
        click.echo("  ✅ No issues found!")
    else:
        icons = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}
        for level, scope, msg in issues:
            click.echo(f"  {icons[level]} [{scope}] {msg}")

        errors = sum(1 for l, _, _ in issues if l == "error")
        warns = sum(1 for l, _, _ in issues if l == "warning")
        click.echo(f"\n  {errors} error(s), {warns} warning(s)")
        if errors:
            sys.exit(1)
    click.echo()


if __name__ == "__main__":
    main()
