#!/usr/bin/env python3
"""OrcaSlicer CLI — stateful command-line interface to the real OrcaSlicer slicer.

Projects are JSON files (*.orca-cli.json) holding models, ordered transforms, preset choices and
setting overrides. Slicing, 3MF/STL export and preview thumbnails are all produced by the real
OrcaSlicer binary (headless CLI mode).

Usage:
    cli-anything-orcaslicer project new -o part.orca-cli.json --machine "Generic FDM 256"
    cli-anything-orcaslicer --project part.orca-cli.json model add part.stl
    cli-anything-orcaslicer --project part.orca-cli.json config set layer_height 0.12
    cli-anything-orcaslicer --json --project part.orca-cli.json slice run --outdir out
    cli-anything-orcaslicer            # interactive REPL
"""

from __future__ import annotations

import json
import os
import shlex
import sys
from typing import Any, Optional

import click

from cli_anything.orcaslicer import __version__
from cli_anything.orcaslicer.core import config as config_mod
from cli_anything.orcaslicer.core import export as export_mod
from cli_anything.orcaslicer.core import preview as preview_mod
from cli_anything.orcaslicer.core import profiles as prof_mod
from cli_anything.orcaslicer.core import project as proj_mod
from cli_anything.orcaslicer.core import slicer as slicer_mod
from cli_anything.orcaslicer.core import transforms as tf_mod
from cli_anything.orcaslicer.core.session import Session
from cli_anything.orcaslicer.utils import orcaslicer_backend as backend

_session: Optional[Session] = None
_json_output = False
_repl_mode = False


def get_session() -> Session:
    global _session
    if _session is None:
        _session = Session()
    return _session


# ── Output helpers ───────────────────────────────────────────────


def emit(data: Any, message: str = "") -> None:
    if _json_output:
        click.echo(json.dumps(data, indent=2, default=str))
        return
    if message:  # concise human line; full details are available with --json
        click.echo(message)
        return
    if isinstance(data, dict):
        _print_dict(data)
    elif isinstance(data, list):
        _print_list(data)
    elif data is not None:
        click.echo(str(data))


def _print_dict(d: dict, indent: int = 0) -> None:
    pad = "  " * indent
    for k, v in d.items():
        if isinstance(v, dict):
            click.echo(f"{pad}{k}:")
            _print_dict(v, indent + 1)
        elif isinstance(v, list):
            click.echo(f"{pad}{k}:")
            _print_list(v, indent + 1)
        else:
            click.echo(f"{pad}{k}: {v}")


def _print_list(items: list, indent: int = 0) -> None:
    pad = "  " * indent
    for i, item in enumerate(items):
        if isinstance(item, dict):
            click.echo(f"{pad}[{i}]")
            _print_dict(item, indent + 1)
        else:
            click.echo(f"{pad}- {item}")


def _fail(message: str, etype: str, extra: Optional[dict] = None) -> None:
    if _json_output:
        payload = {"error": message, "type": etype}
        payload.update(extra or {})
        click.echo(json.dumps(payload, indent=2, default=str))
    else:
        click.echo(f"Error: {message}", err=True)
    if not _repl_mode:
        sys.exit(1)


def handle_error(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except backend.OrcaSlicerError as e:
            _fail(str(e), "OrcaSlicerError", {"code": e.code, "code_name": e.code_name})
        except FileNotFoundError as e:
            _fail(str(e), "file_not_found")
        except FileExistsError as e:
            _fail(str(e), "file_exists")
        except KeyError as e:
            _fail(str(e.args[0]) if e.args else "key error", "KeyError")
        except (ValueError, IndexError, RuntimeError) as e:
            _fail(str(e), type(e).__name__)
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


def _require() -> tuple:
    sess = get_session()
    return sess, sess.get_project()


def _command_string() -> str:
    return "cli-anything-orcaslicer " + " ".join(shlex.quote(a) for a in sys.argv[1:])


# ── Main group ───────────────────────────────────────────────────


@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, help="Output as JSON")
@click.option("--project", "project_path", type=str, default=None,
              help="Path to a .orca-cli.json project file")
@click.option("--dry-run", "dry_run", is_flag=True, default=False,
              help="Run command without saving changes to disk")
@click.version_option(__version__, prog_name="cli-anything-orcaslicer")
@click.pass_context
def cli(ctx, use_json, project_path, dry_run):
    """OrcaSlicer CLI — slice, export and preview 3D-print jobs with the real OrcaSlicer.

    Run without a subcommand to enter the interactive REPL.
    """
    global _json_output
    _json_output = use_json
    ctx.ensure_object(dict)
    ctx.obj["project_path"] = project_path

    if project_path:
        sess = get_session()
        if os.path.exists(project_path):
            if not sess.has_project() or sess.project_path != project_path:
                try:
                    sess.set_project(proj_mod.open_project(project_path), project_path)
                except (ValueError, FileNotFoundError) as e:
                    _fail(str(e), type(e).__name__)
        elif ctx.invoked_subcommand not in (None, "project", "repl", "backend", "preview"):
            _fail(f"Project file not found: {project_path}. Create it with "
                  f"'project new -o {project_path}'.", "file_not_found")

    if ctx.invoked_subcommand is None:
        ctx.invoke(repl, project_path=None)


@cli.result_callback()
def auto_save_on_exit(result, use_json, project_path, dry_run, **kwargs):
    """Auto-save the project after one-shot commands if state was modified."""
    if _repl_mode or dry_run:
        return
    sess = get_session()
    if sess.has_project() and sess._modified and sess.project_path:
        try:
            sess.save_session()
        except Exception as e:  # pragma: no cover - defensive
            click.echo(f"Warning: Auto-save failed: {e}", err=True)


# ── project ──────────────────────────────────────────────────────


@cli.group()
def project():
    """Project management (new, open, save, info)."""


@project.command("new")
@click.option("--name", "-n", default="untitled", help="Project name")
@click.option("--machine", default=proj_mod.DEFAULT_MACHINE, show_default=True,
              help="Machine preset: built-in name, preset name, or path to .json")
@click.option("--process", default=proj_mod.DEFAULT_PROCESS, show_default=True,
              help="Process (quality) preset")
@click.option("--filament", default=proj_mod.DEFAULT_FILAMENT, show_default=True,
              help="Filament preset")
@click.option("--profiles-dir", "profiles_dirs", multiple=True,
              help="Directory of OrcaSlicer JSON presets to search (repeatable)")
@click.option("--model", "models", multiple=True, help="Model file to add (repeatable)")
@click.option("--output", "-o", type=str, default=None, help="Project file to write")
@click.pass_context
@handle_error
def project_new(ctx, name, machine, process, filament, profiles_dirs, models, output):
    """Create a new project."""
    output = output or ctx.obj.get("project_path")
    dirs = list(profiles_dirs)
    for kind, ref in (("machine", machine), ("process", process), ("filament", filament)):
        prof_mod.validate_ref(kind, ref, dirs)
    proj = proj_mod.create_project(name, machine, process, filament, dirs)
    for m in models:
        proj_mod.add_model(proj, m)
    sess = get_session()
    sess.set_project(proj, output)
    if output:
        proj_mod.save_project(proj, output)
    emit(proj_mod.project_info(proj), f"Created project: {name}")


@project.command("open")
@click.argument("path")
@handle_error
def project_open(path):
    """Open a project file into the session."""
    proj = proj_mod.open_project(path)
    get_session().set_project(proj, path)
    emit(proj_mod.project_info(proj), f"Opened: {path}")


@project.command("save")
@click.argument("path", required=False)
@handle_error
def project_save(path):
    """Save the project (to PATH, or its current file)."""
    sess, proj = _require()
    saved = sess.save_session(path)
    emit({"saved": os.path.abspath(saved)}, f"Saved: {saved}")


@project.command("info")
@handle_error
def project_info():
    """Show project summary."""
    _, proj = _require()
    emit(proj_mod.project_info(proj))


@project.command("json")
@handle_error
def project_json():
    """Print the raw project JSON."""
    _, proj = _require()
    click.echo(json.dumps(proj, indent=2, default=str))


# ── model ────────────────────────────────────────────────────────


@cli.group()
def model():
    """Input models (STL / OBJ / 3MF / STEP / AMF)."""


@model.command("add")
@click.argument("path")
@click.option("--name", default=None, help="Display name")
@click.option("--filament", type=int, default=None, help="Filament slot (1-based) for this model")
@handle_error
def model_add(path, name, filament):
    """Add a model to the project."""
    sess, proj = _require()
    sess.snapshot(f"add model {os.path.basename(path)}")
    m = proj_mod.add_model(proj, path, name, filament)
    emit(m, f"Added model #{m['id']}: {m['name']}")


@model.command("remove")
@click.argument("model_id", type=int)
@handle_error
def model_remove(model_id):
    """Remove a model by id."""
    sess, proj = _require()
    sess.snapshot(f"remove model {model_id}")
    m = proj_mod.remove_model(proj, model_id)
    emit(m, f"Removed model #{model_id}")


@model.command("list")
@handle_error
def model_list():
    """List models."""
    _, proj = _require()
    emit(proj_mod.list_models(proj))


@model.command("inspect")
@click.argument("model_id", type=int, required=False)
@handle_error
def model_inspect(model_id):
    """Inspect mesh dimensions/volume/manifold status using OrcaSlicer (--info / --inspect-mesh)."""
    _, proj = _require()
    models = proj["models"]
    if model_id is not None:
        models = [m for m in models if m["id"] == model_id]
        if not models:
            raise IndexError(f"No model with id {model_id}.")
    if not models:
        raise ValueError("Project has no models.")
    result = backend.inspect_models([m["path"] for m in models])
    mesh = result.get("mesh", {}).get("objects", [])
    emit({"info": result["info"],
          "objects": [{"name": o.get("name"), "bbox_object": o.get("bbox_object"),
                       "bbox_world": o.get("bbox_world")} for o in mesh]})


# ── transform ────────────────────────────────────────────────────


@cli.group()
def transform():
    """Ordered model transforms (applied by OrcaSlicer to all objects)."""


def _add_tf(op, value=None, desc=None):
    sess, proj = _require()
    sess.snapshot(desc or f"transform {op}")
    entry = tf_mod.add_transform(proj, op, value)
    emit({"added": proj_mod.describe_transform(entry), "transforms": len(proj["transforms"])},
         f"Added transform: {proj_mod.describe_transform(entry)}")


@transform.command("scale")
@click.argument("factor", type=float)
@handle_error
def transform_scale(factor):
    """Uniformly scale by FACTOR."""
    _add_tf("scale", factor)


@transform.command("rotate")
@click.argument("degrees", type=float)
@click.option("--axis", type=click.Choice(["x", "y", "z"]), default="z", show_default=True)
@handle_error
def transform_rotate(degrees, axis):
    """Rotate by DEGREES around an axis."""
    _add_tf({"x": "rotate_x", "y": "rotate_y", "z": "rotate"}[axis], degrees,
            f"rotate {axis} {degrees:g}")


@transform.command("orient")
@handle_error
def transform_orient():
    """Auto-orient objects (OrcaSlicer's orientation optimiser)."""
    _add_tf("orient", 1)


@transform.command("arrange")
@handle_error
def transform_arrange():
    """Auto-arrange objects on the plate."""
    _add_tf("arrange", 1)


@transform.command("ensure-on-bed")
@handle_error
def transform_ensure():
    """Drop objects onto the bed if partly below it (automatic when scaling/tilting)."""
    _add_tf("ensure_on_bed")


@transform.command("repetitions")
@click.argument("count", type=int)
@handle_error
def transform_reps(count):
    """Repeat the whole model COUNT times."""
    _add_tf("repetitions", count)


@transform.command("ground")
@click.option("--largest", is_flag=True, help="Lay on the largest convex-hull face")
@click.option("--normal", default=None, help="Lay on the face with outward normal closest to NX,NY,NZ")
@click.option("--point", default=None, help="Lay on the face containing X,Y,Z")
@handle_error
def transform_ground(largest, normal, point):
    """Lay objects flat on a chosen face."""
    chosen = [bool(largest), normal is not None, point is not None]
    if sum(chosen) != 1:
        raise ValueError("Choose exactly one of --largest, --normal, --point.")
    if largest:
        _add_tf("ground_largest_face")
    elif normal is not None:
        _add_tf("ground_face_normal", normal)
    else:
        _add_tf("ground_face_point", point)


@transform.command("repair")
@handle_error
def transform_repair():
    """Repair meshes (close holes, fix normals)."""
    _add_tf("repair")


@transform.command("list")
@handle_error
def transform_list():
    """List transforms in application order."""
    _, proj = _require()
    emit([{"index": i, "op": t["op"], "value": t["value"]} for i, t in enumerate(proj["transforms"])])


@transform.command("remove")
@click.argument("index", type=int)
@handle_error
def transform_remove(index):
    """Remove the transform at INDEX."""
    sess, proj = _require()
    if not 0 <= index < len(proj["transforms"]):
        raise IndexError(f"No transform at index {index} (have {len(proj['transforms'])}).")
    sess.snapshot(f"remove transform {index}")
    t = proj["transforms"].pop(index)
    emit(t, f"Removed transform: {proj_mod.describe_transform(t)}")


@transform.command("clear")
@handle_error
def transform_clear():
    """Remove all transforms."""
    sess, proj = _require()
    sess.snapshot("clear transforms")
    n = tf_mod.clear_transforms(proj)
    emit({"removed": n}, f"Cleared {n} transform(s)")


# ── profile ──────────────────────────────────────────────────────


@cli.group()
def profile():
    """Printer / process / filament presets."""


@profile.command("list")
@click.option("--kind", type=click.Choice(list(prof_mod.KINDS)), default=None)
@click.option("--source", type=click.Choice(["all", "builtin", "system"]), default="all")
@click.option("--limit", type=int, default=200, show_default=True)
@handle_error
def profile_list(kind, source, limit):
    """List available presets (built-in and any found in preset directories)."""
    sess = get_session()
    dirs = sess.project["profiles"]["dirs"] if sess.has_project() else None
    items = prof_mod.list_presets(kind, dirs, include_system=source != "builtin")
    if source == "system":
        items = [i for i in items if i["source"] == "system"]
    emit(items[:limit])


@profile.command("show")
@click.argument("kind", type=click.Choice(list(prof_mod.KINDS)))
@click.argument("ref")
@click.option("--all", "show_all", is_flag=True, help="Print every key (default: summary)")
@handle_error
def profile_show(kind, ref, show_all):
    """Show a resolved (flattened) preset."""
    sess = get_session()
    dirs = sess.project["profiles"]["dirs"] if sess.has_project() else None
    flat = prof_mod.resolve(kind, ref, dirs)
    emit(flat if show_all else {"name": flat.get("name"), "type": flat.get("type"),
                                "keys": len(flat), "sample": {k: flat[k] for k in list(flat)[:12]}})


@profile.command("use")
@click.argument("kind", type=click.Choice(list(prof_mod.KINDS)))
@click.argument("ref")
@click.option("--slot", type=int, default=1, show_default=True, help="Filament slot (filament only)")
@handle_error
def profile_use(kind, ref, slot):
    """Select the machine / process / filament preset for this project."""
    sess, proj = _require()
    refs = proj["profiles"]
    check_ref = os.path.abspath(os.path.expanduser(ref)) if ref.lower().endswith(".json") else ref
    prof_mod.validate_ref(kind, check_ref, refs["dirs"])
    sess.snapshot(f"use {kind} {ref}")
    if kind == "filament":
        if not 1 <= slot <= len(refs["filaments"]):
            raise IndexError(f"Filament slot {slot} out of range (1-{len(refs['filaments'])}).")
        refs["filaments"][slot - 1] = check_ref
    else:
        refs[kind] = check_ref
    emit({"kind": kind, "ref": check_ref}, f"Using {kind} preset: {check_ref}")


@profile.command("dirs")
@handle_error
def profile_dirs():
    """Show preset search directories (project-specific first)."""
    sess = get_session()
    extra = sess.project["profiles"]["dirs"] if sess.has_project() else []
    emit({"project_dirs": extra, "search_dirs": prof_mod.search_dirs(extra)})


@profile.command("add-dir")
@click.argument("directory")
@handle_error
def profile_add_dir(directory):
    """Add a directory of OrcaSlicer JSON presets to the project's search path."""
    sess, proj = _require()
    d = os.path.abspath(os.path.expanduser(directory))
    if not os.path.isdir(d):
        raise FileNotFoundError(f"Directory not found: {d}")
    sess.snapshot("add profile dir")
    if d not in proj["profiles"]["dirs"]:
        proj["profiles"]["dirs"].append(d)
    prof_mod.clear_index_cache()
    emit({"dirs": proj["profiles"]["dirs"]}, f"Added preset directory: {d}")


# ── filament (multi-slot) ────────────────────────────────────────


@cli.group()
def filament():
    """Filament slots (multi-material projects)."""


@filament.command("add")
@click.argument("ref")
@handle_error
def filament_add(ref):
    """Append a filament preset as a new slot."""
    sess, proj = _require()
    check_ref = os.path.abspath(os.path.expanduser(ref)) if ref.lower().endswith(".json") else ref
    prof_mod.validate_ref("filament", check_ref, proj["profiles"]["dirs"])
    sess.snapshot(f"add filament {ref}")
    proj["profiles"]["filaments"].append(check_ref)
    emit({"slot": len(proj["profiles"]["filaments"]), "ref": check_ref},
         f"Added filament slot {len(proj['profiles']['filaments'])}: {check_ref}")


@filament.command("remove")
@click.argument("slot", type=int)
@handle_error
def filament_remove(slot):
    """Remove filament slot SLOT (1-based)."""
    sess, proj = _require()
    fl = proj["profiles"]["filaments"]
    if not 1 <= slot <= len(fl):
        raise IndexError(f"Filament slot {slot} out of range (1-{len(fl)}).")
    if len(fl) == 1:
        raise ValueError("A project needs at least one filament.")
    if any(m.get("filament") == slot for m in proj["models"]):
        raise ValueError(f"Slot {slot} is assigned to a model; reassign or remove the model first.")
    sess.snapshot(f"remove filament {slot}")
    removed = fl.pop(slot - 1)
    for m in proj["models"]:
        if m.get("filament") and m["filament"] > slot:
            m["filament"] -= 1
    emit({"removed": removed}, f"Removed filament slot {slot}")


@filament.command("list")
@handle_error
def filament_list():
    """List filament slots."""
    _, proj = _require()
    emit([{"slot": i, "ref": r} for i, r in enumerate(proj["profiles"]["filaments"], start=1)])


# ── config ───────────────────────────────────────────────────────


@cli.group("config")
def config_group():
    """Setting overrides (validated against the real OrcaSlicer schema)."""


@config_group.command("keys")
@click.option("--search", "-s", default="", help="Substring filter")
@click.option("--kind", type=click.Choice(list(prof_mod.KINDS)), default=None)
@click.option("--limit", type=int, default=50, show_default=True)
@handle_error
def config_keys(search, kind, limit):
    """Search valid setting keys and their defaults."""
    emit(config_mod.search_keys(search, kind, limit))


@config_group.command("get")
@click.argument("key")
@click.option("--kind", type=click.Choice(list(prof_mod.KINDS)), default=None)
@handle_error
def config_get(key, kind):
    """Show a setting's effective value and its source."""
    _, proj = _require()
    emit(config_mod.get_effective(proj, key, kind))


@config_group.command("set")
@click.argument("key")
@click.argument("value")
@click.option("--kind", type=click.Choice(list(prof_mod.KINDS)), default=None,
              help="Preset kind (auto-detected for known keys)")
@handle_error
def config_set(key, value, kind):
    """Override a setting. Lists: pass a JSON array, e.g. '["200","205"]'."""
    sess, proj = _require()
    sess.snapshot(f"set {key}")
    r = config_mod.set_override(proj, key, value, kind)
    emit(r, f"Set {r['kind']}.{key} = {r['value']}")


@config_group.command("apply")
@click.argument("assignments", nargs=-1, required=True)
@handle_error
def config_apply(assignments):
    """Set several overrides at once: KEY=VALUE [KEY=VALUE ...]."""
    sess, proj = _require()
    parsed = []
    for a in assignments:
        if "=" not in a:
            raise ValueError(f"Expected KEY=VALUE, got '{a}'.")
        parsed.append(tuple(a.split("=", 1)))
    sess.snapshot(f"apply {len(parsed)} settings")
    results = [config_mod.set_override(proj, k, v) for k, v in parsed]
    emit(results, f"Applied {len(results)} setting(s)")


@config_group.command("unset")
@click.argument("key")
@click.option("--kind", type=click.Choice(list(prof_mod.KINDS)), default=None)
@handle_error
def config_unset(key, kind):
    """Remove an override."""
    sess, proj = _require()
    sess.snapshot(f"unset {key}")
    emit(config_mod.unset_override(proj, key, kind), f"Removed override {key}")


@config_group.command("list")
@handle_error
def config_list():
    """List current overrides."""
    _, proj = _require()
    emit(config_mod.list_overrides(proj))


# ── slice ────────────────────────────────────────────────────────


@cli.group("slice")
def slice_group():
    """Slice with the real OrcaSlicer and inspect results."""


@slice_group.command("options")
@click.option("--plate", type=int, default=None, help="0 = all plates, N = plate N")
@click.option("--strict/--no-strict", default=None, help="Fail on non-critical warnings")
@click.option("--no-check/--check", "no_check", default=None, help="Skip validity checks")
@click.option("--outdir", default=None, help="Default output directory")
@click.option("--auto-ensure-on-bed/--no-auto-ensure-on-bed", "auto_eob", default=None,
              help="Auto-add --ensure-on-bed when scaling/tilting (default on)")
@handle_error
def slice_options(plate, strict, no_check, outdir, auto_eob):
    """Show or persist default slice options."""
    sess, proj = _require()
    opts = proj["slice"]
    changes = {"plate": plate, "strict": strict, "no_check": no_check,
               "outdir": os.path.abspath(outdir) if outdir else None, "auto_ensure_on_bed": auto_eob}
    changes = {k: v for k, v in changes.items() if v is not None}
    if changes:
        merged = {**opts, **changes}
        if merged.get("strict") and merged.get("no_check"):
            raise ValueError("--strict cannot be combined with --no-check.")
        sess.snapshot("slice options")
        opts.update(changes)
    emit(dict(opts))


@slice_group.command("run")
@click.option("--plate", type=int, default=None, help="0 = all plates (default), N = plate N")
@click.option("--outdir", "-o", default=None, help="Output directory (default <project>_output)")
@click.option("--export-3mf", "export_3mf", default=None, help="Also save a sliced 3MF project")
@click.option("--strict/--no-strict", default=None)
@click.option("--no-check/--check", "no_check", default=None)
@click.option("--timeout", type=int, default=900, show_default=True, help="Seconds")
@click.pass_context
@handle_error
def slice_run(ctx, plate, outdir, export_3mf, strict, no_check, timeout):
    """Slice the project and write verified G-code."""
    sess, proj = _require()
    sess.snapshot("slice run")  # the slice result is recorded in project history -> modified
    result = slicer_mod.slice_project(
        proj, project_path=sess.project_path, outdir=outdir, plate=plate, export_3mf=export_3mf,
        strict=strict, no_check=no_check, timeout=timeout)
    if _json_output:
        emit(result)
        return
    for p in result["plates"]:
        click.echo(f"Plate {p['plate']}: {p['layers']} layers, {p.get('print_time')}, "
                   f"{p.get('filament_g')} g filament, {p['bytes']:,} bytes")
        click.echo(f"  G-code: {p['path']}")
    if result["export_3mf"]:
        click.echo(f"3MF: {result['export_3mf']}")
    if result["auto_ensure_on_bed"]:
        click.echo("note: --ensure-on-bed was added automatically (scale/tilt transform present)")
    for w in result["warnings"]:
        click.echo(f"warning: {w}")


@slice_group.command("stats")
@click.option("--plate", type=int, default=1, show_default=True)
@handle_error
def slice_stats(plate):
    """Per-feature / per-object statistics from the last slice (OrcaSlicer's own numbers)."""
    _, proj = _require()
    emit(slicer_mod.feature_stats(proj, plate))


@slice_group.command("last")
@handle_error
def slice_last():
    """Show a summary of the most recent slice."""
    _, proj = _require()
    emit(slicer_mod.last_slice(proj))


@slice_group.command("gcode-info")
@click.argument("path")
@handle_error
def slice_gcode_info(path):
    """Verify and summarise any OrcaSlicer G-code file."""
    emit(slicer_mod.gcode_info(path))


# ── export ───────────────────────────────────────────────────────


@cli.group("export")
def export_group():
    """Export 3MF / settings / STL / G-code."""


@export_group.command("3mf")
@click.argument("path")
@click.option("--no-slice", is_flag=True, help="Export the unsliced project only")
@click.option("--overwrite", is_flag=True)
@handle_error
def export_3mf_cmd(path, no_slice, overwrite):
    """Export an OrcaSlicer 3MF project (sliced by default; embeds G-code + thumbnails)."""
    sess, proj = _require()
    r = export_mod.export_3mf(proj, path, sess.project_path, with_slice=not no_slice, overwrite=overwrite)
    emit(r, f"Exported 3MF: {r['path']}")


@export_group.command("settings")
@click.argument("path")
@click.option("--overwrite", is_flag=True)
@handle_error
def export_settings_cmd(path, overwrite):
    """Dump the full effective configuration resolved by OrcaSlicer."""
    _, proj = _require()
    r = export_mod.export_settings(proj, path, overwrite)
    emit(r, f"Exported settings: {r['path']}")


@export_group.command("stl")
@click.argument("dest_dir")
@click.option("--overwrite", is_flag=True)
@handle_error
def export_stl_cmd(dest_dir, overwrite):
    """Export the transformed objects as STL files into DEST_DIR."""
    _, proj = _require()
    r = export_mod.export_stl(proj, dest_dir, overwrite)
    emit(r, f"Exported {len(r['files'])} STL file(s) to {r['dest']}")


@export_group.command("gcode")
@click.argument("path")
@click.option("--plate", type=int, default=1, show_default=True)
@click.option("--overwrite", is_flag=True)
@handle_error
def export_gcode_cmd(path, plate, overwrite):
    """Copy the last slice's G-code to PATH (run 'slice run' first)."""
    _, proj = _require()
    r = export_mod.export_gcode(proj, path, plate, overwrite)
    emit(r, f"Exported G-code: {r['path']}")


# ── preview ──────────────────────────────────────────────────────


@cli.group()
def preview():
    """Preview bundles (producer). Inspect with: cli-hub previews inspect <bundle_dir>."""


@preview.command("recipes")
@handle_error
def preview_recipes():
    """List preview recipes."""
    emit(preview_mod.list_recipes())


def _strip(m: dict) -> dict:
    return {k: v for k, v in m.items() if k != "cache_key"}


@preview.command("capture")
@click.option("--recipe", default="quick", show_default=True)
@click.option("--plate", type=int, default=1, show_default=True)
@click.option("--force", is_flag=True, help="Ignore the cache and slice again")
@click.option("--root-dir", default=None, help="Bundle root (default <project_dir>/.cli-anything/previews)")
@handle_error
def preview_capture(recipe, plate, force, root_dir):
    """Slice with OrcaSlicer and publish a preview bundle (cached by project fingerprint)."""
    sess, proj = _require()
    m = preview_mod.capture(proj, sess.project_path, recipe, force, root_dir, plate, _command_string())
    emit(_strip(m), f"Preview bundle ({'cached' if m.get('cached') else 'new'}): {m['_bundle_dir']}")


@preview.command("latest")
@click.option("--recipe", default=None)
@click.option("--root-dir", default=None)
@handle_error
def preview_latest(recipe, root_dir):
    """Return the newest existing bundle (never renders)."""
    sess = get_session()
    m = preview_mod.latest(sess.project_path, recipe, root_dir)
    emit(_strip(m), f"Latest bundle: {m['_bundle_dir']}")


@preview.command("diff")
@click.option("--recipe", default="quick", show_default=True)
@click.option("--base", "base_dir", default=None, help="Baseline bundle dir (default: latest capture)")
@click.option("--root-dir", default=None)
@handle_error
def preview_diff(recipe, base_dir, root_dir):
    """Capture now and publish a before/after comparison bundle against a baseline."""
    sess, proj = _require()
    m = preview_mod.diff(proj, sess.project_path, recipe, base_dir, root_dir, _command_string())
    emit(_strip(m), f"Diff bundle: {m['_bundle_dir']}")


# ── backend / session ────────────────────────────────────────────


@cli.group("backend")
def backend_group():
    """The OrcaSlicer binary used by this harness."""


@backend_group.command("info")
@handle_error
def backend_info():
    """Show OrcaSlicer executable, version and supported CLI flags."""
    emit(backend.backend_info())


@cli.group("session")
def session_group():
    """Session state, undo / redo."""


@session_group.command("status")
@handle_error
def session_status():
    """Show session status."""
    emit(get_session().status())


@session_group.command("undo")
@handle_error
def session_undo():
    """Undo the last project edit."""
    desc = get_session().undo()
    emit({"undone": desc}, f"Undone: {desc}")


@session_group.command("redo")
@handle_error
def session_redo():
    """Redo the last undone edit."""
    desc = get_session().redo()
    emit({"redone": desc}, f"Redone: {desc}")


@session_group.command("history")
@handle_error
def session_history():
    """List the undo history."""
    emit(get_session().list_history())


# ── REPL ─────────────────────────────────────────────────────────


@cli.command()
@click.option("--project", "project_path", type=str, default=None, help="Project to open")
@handle_error
def repl(project_path):
    """Start the interactive REPL."""
    from cli_anything.orcaslicer.utils.repl_skin import ReplSkin

    global _repl_mode
    _repl_mode = True
    skin = ReplSkin("orcaslicer", version=__version__)
    if project_path:
        get_session().set_project(proj_mod.open_project(project_path), project_path)
    skin.print_banner()
    pt_session = skin.create_prompt_session()

    commands = {
        "project": "new|open|save|info|json",
        "model": "add|remove|list|inspect",
        "transform": "scale|rotate|orient|arrange|ensure-on-bed|repetitions|ground|repair|list|remove|clear",
        "profile": "list|show|use|dirs|add-dir",
        "filament": "add|remove|list",
        "config": "keys|get|set|apply|unset|list",
        "slice": "options|run|stats|last|gcode-info",
        "export": "3mf|settings|stl|gcode",
        "preview": "recipes|capture|latest|diff",
        "backend": "info",
        "session": "status|undo|redo|history",
        "help": "show this help",
        "quit": "exit REPL",
    }
    try:
        while True:
            try:
                sess = get_session()
                name, modified = "", False
                if sess.has_project():
                    name = os.path.basename(sess.project_path) if sess.project_path else sess.project.get("name", "")
                    modified = sess._modified
                line = skin.get_input(pt_session, project_name=name, modified=modified).strip()
                if not line:
                    continue
                if line.lower() in ("quit", "exit", "q"):
                    skin.print_goodbye()
                    break
                if line.lower() == "help":
                    skin.help(commands)
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
                    skin.error(str(e))
            except (EOFError, KeyboardInterrupt):
                skin.print_goodbye()
                break
    finally:
        _repl_mode = False


# ── Entry point ──────────────────────────────────────────────────


def main():
    cli()


if __name__ == "__main__":
    main()
