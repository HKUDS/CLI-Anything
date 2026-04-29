#!/usr/bin/env python3
"""Blender CLI — A stateful command-line interface for 3D scene editing.

This CLI provides full 3D scene management capabilities using a JSON
scene description format, with direct Blender-backed rendering support.

Usage:
    # One-shot commands
    cli-anything-blender scene new --name "MyScene"
    cli-anything-blender object add cube --name "MyCube"
    cli-anything-blender material create --name "Red" --color 1,0,0,1

    # Interactive REPL
    cli-anything-blender
"""

import copy
import sys
import os
import json
import shlex
import shutil
import subprocess
import click
from typing import Optional

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cli_anything.blender.core.session import Session
from cli_anything.blender.core import scene as scene_mod
from cli_anything.blender.core import objects as obj_mod
from cli_anything.blender.core import materials as mat_mod
from cli_anything.blender.core import modifiers as mod_mod
from cli_anything.blender.core import lighting as light_mod
from cli_anything.blender.core import animation as anim_mod
from cli_anything.blender.core import render as render_mod
from cli_anything.blender.core import preview as preview_mod

# Global session state
_session: Optional[Session] = None
_json_output = False
_repl_mode = False
OBJECT_MESH_TYPES = ["cube", "sphere", "cylinder", "cone", "plane", "torus", "monkey", "empty"]


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


def _spawn_live_viewer(session_dir: str, poll_ms: int) -> dict:
    """Launch cli-hub live preview watcher when available."""
    hub = shutil.which("cli-hub")
    command = [
        hub or "cli-hub",
        "previews",
        "watch",
        session_dir,
        "--open",
        "--poll-ms",
        str(int(poll_ms)),
    ]
    if hub is None:
        return {
            "launched": False,
            "command": command,
            "reason": "cli-hub not found on PATH",
        }
    process = subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return {
        "launched": True,
        "pid": process.pid,
        "command": command,
    }


def _spawn_live_poller(session_dir: str) -> dict:
    """Launch the Blender live preview poller in the background."""
    cli_path = shutil.which("cli-anything-blender")
    if cli_path:
        command = [cli_path, "preview", "live", "monitor", "--session-dir", session_dir]
    else:
        command = [
            sys.executable,
            "-m",
            "cli_anything.blender.blender_cli",
            "preview",
            "live",
            "monitor",
            "--session-dir",
            session_dir,
        ]
    log_path = os.path.join(session_dir, "poller.log")
    log_fh = open(log_path, "ab")
    process = subprocess.Popen(
        command,
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        close_fds=True,
    )
    log_fh.close()
    preview_mod.record_live_poller_spawn(
        session_dir,
        pid=process.pid,
        command=command,
        log_path=log_path,
    )
    return {
        "launched": True,
        "pid": process.pid,
        "command": command,
        "log_path": log_path,
    }


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


def _parse_vector_value(value, option_name: str):
    if value is None:
        return None
    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",") if part.strip()]
    else:
        parts = [str(part).strip() for part in value]
    if len(parts) != 3:
        raise ValueError(f"{option_name} must have exactly 3 components.")
    return [float(part) for part in parts]


def _parse_params(param_values):
    params = {}
    for param_value in param_values:
        if "=" not in param_value:
            raise ValueError(f"Invalid param format: '{param_value}'. Use key=value.")
        key, value = param_value.split("=", 1)
        try:
            value = float(value) if "." in value else int(value)
        except ValueError:
            pass
        params[key] = value
    return params


def _add_object_impl(mesh_type, name, location, rotation, scale, param, collection):
    loc = _parse_vector_value(location, "Location")
    rot = _parse_vector_value(rotation, "Rotation")
    scl = _parse_vector_value(scale, "Scale")
    params = _parse_params(param)

    sess = get_session()
    sess.snapshot(f"Add object: {mesh_type}")
    proj = sess.get_project()
    obj = obj_mod.add_object(
        proj, mesh_type=mesh_type, name=name, location=loc,
        rotation=rot, scale=scl, mesh_params=params if params else None,
        collection=collection,
    )
    output(obj, f"Added {mesh_type}: {obj['name']}")


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
              help="Path to .blend-cli.json project file")
@click.option("--dry-run", "dry_run", is_flag=True, default=False,
              help="Run command without saving changes to disk")
@click.pass_context
def cli(ctx, use_json, project_path, dry_run):
    """Blender CLI — Stateful 3D scene editing from the command line.

    Run without a subcommand to enter interactive REPL mode.
    """
    global _json_output
    _json_output = use_json

    if project_path:
        sess = get_session()
        if not sess.has_project():
            proj = scene_mod.open_scene(project_path)
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


# ── Scene Commands ──────────────────────────────────────────────
@cli.group()
def scene():
    """Scene management commands."""
    pass


@scene.command("new")
@click.option("--name", "-n", default="untitled", help="Scene name")
@click.option("--profile", "-p", type=str, default=None, help="Scene profile")
@click.option("--resolution-x", "-rx", type=int, default=1920, help="Horizontal resolution")
@click.option("--resolution-y", "-ry", type=int, default=1080, help="Vertical resolution")
@click.option("--engine", type=click.Choice(["CYCLES", "EEVEE", "WORKBENCH"]), default="CYCLES")
@click.option("--samples", type=int, default=128, help="Render samples")
@click.option("--fps", type=int, default=24, help="Frames per second")
@click.option("--output", "-o", type=str, default=None, help="Save path")
@handle_error
def scene_new(name, profile, resolution_x, resolution_y, engine, samples, fps, output):
    """Create a new scene."""
    proj = scene_mod.create_scene(
        name=name, profile=profile, resolution_x=resolution_x,
        resolution_y=resolution_y, engine=engine, samples=samples, fps=fps,
    )
    sess = get_session()
    sess.set_project(proj, output)
    if output:
        scene_mod.save_scene(proj, output)
    output_data = scene_mod.get_scene_info(proj)
    globals()["output"](output_data, f"Created scene: {name}")


@scene.command("open")
@click.argument("path")
@handle_error
def scene_open(path):
    """Open an existing scene."""
    proj = scene_mod.open_scene(path)
    sess = get_session()
    sess.set_project(proj, path)
    info = scene_mod.get_scene_info(proj)
    output(info, f"Opened: {path}")


@scene.command("save")
@click.argument("path", required=False)
@handle_error
def scene_save(path):
    """Save the current scene."""
    sess = get_session()
    saved = sess.save_session(path)
    output({"saved": saved}, f"Saved to: {saved}")


@scene.command("info")
@handle_error
def scene_info():
    """Show scene information."""
    sess = get_session()
    info = scene_mod.get_scene_info(sess.get_project())
    output(info)


@scene.command("profiles")
@handle_error
def scene_profiles():
    """List available scene profiles."""
    profiles = scene_mod.list_profiles()
    output(profiles, "Available profiles:")


@scene.command("json")
@handle_error
def scene_json():
    """Print raw scene JSON."""
    sess = get_session()
    click.echo(json.dumps(sess.get_project(), indent=2, default=str))


# ── Object Commands ─────────────────────────────────────────────
@cli.group("object")
def object_group():
    """3D object management commands."""
    pass


@object_group.command("add")
@click.argument("mesh_type", type=click.Choice(OBJECT_MESH_TYPES))
@click.option("--name", "-n", default=None, help="Object name")
@click.option("--location", "-l", default=None, help="Location x,y,z")
@click.option("--rotation", "-r", default=None, help="Rotation x,y,z (degrees)")
@click.option("--scale", "-s", default=None, help="Scale x,y,z")
@click.option("--param", "-p", multiple=True, help="Mesh parameter: key=value")
@click.option("--collection", "-c", default=None, help="Target collection")
@handle_error
def object_add(mesh_type, name, location, rotation, scale, param, collection):
    """Add a 3D primitive object."""
    _add_object_impl(mesh_type, name, location, rotation, scale, param, collection)


@object_group.command("add-mesh")
@click.option("--type", "mesh_type", type=click.Choice(OBJECT_MESH_TYPES), required=True,
              help="Primitive mesh type")
@click.option("--name", "-n", default=None, help="Object name")
@click.option("--location", "-l", nargs=3, type=float, default=None, help="Location x y z")
@click.option("--rotation", "-r", nargs=3, type=float, default=None, help="Rotation x y z (degrees)")
@click.option("--scale", "-s", nargs=3, type=float, default=None, help="Scale x y z")
@click.option("--param", "-p", multiple=True, help="Mesh parameter: key=value")
@click.option("--collection", "-c", default=None, help="Target collection")
@handle_error
def object_add_mesh(mesh_type, name, location, rotation, scale, param, collection):
    """Compatibility alias for `object add`."""
    _add_object_impl(mesh_type, name, location, rotation, scale, param, collection)


@object_group.command("remove")
@click.argument("index", type=int)
@handle_error
def object_remove(index):
    """Remove an object by index."""
    sess = get_session()
    sess.snapshot(f"Remove object {index}")
    removed = obj_mod.remove_object(sess.get_project(), index)
    output(removed, f"Removed object {index}: {removed.get('name', '')}")


@object_group.command("duplicate")
@click.argument("index", type=int)
@handle_error
def object_duplicate(index):
    """Duplicate an object."""
    sess = get_session()
    sess.snapshot(f"Duplicate object {index}")
    dup = obj_mod.duplicate_object(sess.get_project(), index)
    output(dup, f"Duplicated object {index}")


@object_group.command("transform")
@click.argument("index", type=int)
@click.option("--translate", "-t", default=None, help="Translate dx,dy,dz")
@click.option("--rotate", "-r", default=None, help="Rotate rx,ry,rz (degrees)")
@click.option("--scale", "-s", default=None, help="Scale sx,sy,sz (multiplier)")
@handle_error
def object_transform(index, translate, rotate, scale):
    """Transform an object (translate, rotate, scale)."""
    trans = [float(x) for x in translate.split(",")] if translate else None
    rot = [float(x) for x in rotate.split(",")] if rotate else None
    scl = [float(x) for x in scale.split(",")] if scale else None

    sess = get_session()
    sess.snapshot(f"Transform object {index}")
    obj = obj_mod.transform_object(sess.get_project(), index,
                                    translate=trans, rotate=rot, scale=scl)
    output(obj, f"Transformed object {index}: {obj['name']}")


@object_group.command("set")
@click.argument("index", type=int)
@click.argument("prop")
@click.argument("value")
@handle_error
def object_set(index, prop, value):
    """Set an object property (name, visible, location, rotation, scale, parent)."""
    sess = get_session()
    sess.snapshot(f"Set object {index} {prop}={value}")
    # Handle vector properties
    if prop in ("location", "rotation", "scale"):
        value = [float(x) for x in value.split(",")]
    obj_mod.set_object_property(sess.get_project(), index, prop, value)
    output({"object": index, "property": prop, "value": value},
           f"Set object {index} {prop} = {value}")


@object_group.command("list")
@handle_error
def object_list():
    """List all objects."""
    sess = get_session()
    objects = obj_mod.list_objects(sess.get_project())
    output(objects, "Objects:")


@object_group.command("get")
@click.argument("index", type=int)
@handle_error
def object_get(index):
    """Get detailed info about an object."""
    sess = get_session()
    obj = obj_mod.get_object(sess.get_project(), index)
    output(obj)


# ── Material Commands ───────────────────────────────────────────
@cli.group()
def material():
    """Material management commands."""
    pass


@material.command("create")
@click.option("--name", "-n", default="Material", help="Material name")
@click.option("--color", "-c", default=None, help="Base color R,G,B,A (0.0-1.0)")
@click.option("--metallic", type=float, default=0.0, help="Metallic factor")
@click.option("--roughness", type=float, default=0.5, help="Roughness factor")
@click.option("--specular", type=float, default=0.5, help="Specular factor")
@handle_error
def material_create(name, color, metallic, roughness, specular):
    """Create a new material."""
    col = [float(x) for x in color.split(",")] if color else None
    sess = get_session()
    sess.snapshot(f"Create material: {name}")
    mat = mat_mod.create_material(
        sess.get_project(), name=name, color=col,
        metallic=metallic, roughness=roughness, specular=specular,
    )
    output(mat, f"Created material: {mat['name']}")


@material.command("assign")
@click.argument("material_index", type=int)
@click.argument("object_index", type=int)
@handle_error
def material_assign(material_index, object_index):
    """Assign a material to an object."""
    sess = get_session()
    sess.snapshot(f"Assign material {material_index} to object {object_index}")
    result = mat_mod.assign_material(sess.get_project(), material_index, object_index)
    output(result, f"Assigned {result['material']} to {result['object']}")


@material.command("set")
@click.argument("index", type=int)
@click.argument("prop")
@click.argument("value")
@handle_error
def material_set(index, prop, value):
    """Set a material property (color, metallic, roughness, specular, alpha, etc.)."""
    # Handle color properties
    if prop in ("color", "emission_color"):
        value = [float(x) for x in value.split(",")]
    elif prop == "use_backface_culling":
        pass  # handled by set_material_property
    else:
        try:
            value = float(value)
        except ValueError:
            pass
    sess = get_session()
    sess.snapshot(f"Set material {index} {prop}")
    mat_mod.set_material_property(sess.get_project(), index, prop, value)
    output({"material": index, "property": prop, "value": value},
           f"Set material {index} {prop}")


@material.command("list")
@handle_error
def material_list():
    """List all materials."""
    sess = get_session()
    materials = mat_mod.list_materials(sess.get_project())
    output(materials, "Materials:")


@material.command("get")
@click.argument("index", type=int)
@handle_error
def material_get(index):
    """Get detailed info about a material."""
    sess = get_session()
    mat = mat_mod.get_material(sess.get_project(), index)
    output(mat)


# ── Modifier Commands ───────────────────────────────────────────
@cli.group("modifier")
def modifier_group():
    """Modifier management commands."""
    pass


@modifier_group.command("list-available")
@click.option("--category", "-c", type=str, default=None,
              help="Filter by category: generate, deform")
@handle_error
def modifier_list_available(category):
    """List all available modifiers."""
    modifiers = mod_mod.list_available(category)
    output(modifiers, "Available modifiers:")


@modifier_group.command("info")
@click.argument("name")
@handle_error
def modifier_info(name):
    """Show details about a modifier."""
    info = mod_mod.get_modifier_info(name)
    output(info)


@modifier_group.command("add")
@click.argument("modifier_type")
@click.option("--object", "-o", "object_index", type=int, default=0, help="Object index")
@click.option("--name", "-n", default=None, help="Custom modifier name")
@click.option("--param", "-p", multiple=True, help="Parameter: key=value")
@handle_error
def modifier_add(modifier_type, object_index, name, param):
    """Add a modifier to an object."""
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
    sess.snapshot(f"Add modifier {modifier_type} to object {object_index}")
    result = mod_mod.add_modifier(
        sess.get_project(), modifier_type, object_index, name=name, params=params,
    )
    output(result, f"Added modifier: {result['name']}")


@modifier_group.command("remove")
@click.argument("modifier_index", type=int)
@click.option("--object", "-o", "object_index", type=int, default=0)
@handle_error
def modifier_remove(modifier_index, object_index):
    """Remove a modifier by index."""
    sess = get_session()
    sess.snapshot(f"Remove modifier {modifier_index} from object {object_index}")
    result = mod_mod.remove_modifier(sess.get_project(), modifier_index, object_index)
    output(result, f"Removed modifier {modifier_index}")


@modifier_group.command("set")
@click.argument("modifier_index", type=int)
@click.argument("param")
@click.argument("value")
@click.option("--object", "-o", "object_index", type=int, default=0)
@handle_error
def modifier_set(modifier_index, param, value, object_index):
    """Set a modifier parameter."""
    try:
        value = float(value) if "." in str(value) else int(value)
    except ValueError:
        pass
    sess = get_session()
    sess.snapshot(f"Set modifier {modifier_index} {param}={value}")
    mod_mod.set_modifier_param(sess.get_project(), modifier_index, param, value, object_index)
    output({"modifier": modifier_index, "param": param, "value": value},
           f"Set modifier {modifier_index} {param} = {value}")


@modifier_group.command("list")
@click.option("--object", "-o", "object_index", type=int, default=0)
@handle_error
def modifier_list(object_index):
    """List modifiers on an object."""
    sess = get_session()
    modifiers = mod_mod.list_modifiers(sess.get_project(), object_index)
    output(modifiers, f"Modifiers on object {object_index}:")


# ── Camera Commands ─────────────────────────────────────────────
@cli.group()
def camera():
    """Camera management commands."""
    pass


@camera.command("add")
@click.option("--name", "-n", default=None, help="Camera name")
@click.option("--location", "-l", default=None, help="Location x,y,z")
@click.option("--rotation", "-r", default=None, help="Rotation x,y,z (degrees)")
@click.option("--type", "camera_type", type=click.Choice(["PERSP", "ORTHO", "PANO"]),
              default="PERSP")
@click.option("--focal-length", "-f", type=float, default=50.0, help="Focal length (mm)")
@click.option("--active", is_flag=True, help="Set as active camera")
@handle_error
def camera_add(name, location, rotation, camera_type, focal_length, active):
    """Add a camera to the scene."""
    loc = [float(x) for x in location.split(",")] if location else None
    rot = [float(x) for x in rotation.split(",")] if rotation else None

    sess = get_session()
    sess.snapshot("Add camera")
    cam = light_mod.add_camera(
        sess.get_project(), name=name, location=loc, rotation=rot,
        camera_type=camera_type, focal_length=focal_length, set_active=active,
    )
    output(cam, f"Added camera: {cam['name']}")


@camera.command("set")
@click.argument("index", type=int)
@click.argument("prop")
@click.argument("value")
@handle_error
def camera_set(index, prop, value):
    """Set a camera property."""
    # Handle vector properties
    if prop in ("location", "rotation"):
        value = [float(x) for x in value.split(",")]
    sess = get_session()
    sess.snapshot(f"Set camera {index} {prop}")
    light_mod.set_camera(sess.get_project(), index, prop, value)
    output({"camera": index, "property": prop, "value": value},
           f"Set camera {index} {prop}")


@camera.command("set-active")
@click.argument("index", type=int)
@handle_error
def camera_set_active(index):
    """Set the active camera."""
    sess = get_session()
    sess.snapshot(f"Set active camera {index}")
    result = light_mod.set_active_camera(sess.get_project(), index)
    output(result, f"Active camera: {result['active_camera']}")


@camera.command("list")
@handle_error
def camera_list():
    """List all cameras."""
    sess = get_session()
    cameras = light_mod.list_cameras(sess.get_project())
    output(cameras, "Cameras:")


# ── Light Commands ──────────────────────────────────────────────
@cli.group()
def light():
    """Light management commands."""
    pass


@light.command("add")
@click.argument("light_type", type=click.Choice(["point", "sun", "spot", "area"]))
@click.option("--name", "-n", default=None, help="Light name")
@click.option("--location", "-l", default=None, help="Location x,y,z")
@click.option("--rotation", "-r", default=None, help="Rotation x,y,z (degrees)")
@click.option("--color", "-c", default=None, help="Color R,G,B (0.0-1.0)")
@click.option("--power", "-w", type=float, default=None, help="Power/energy")
@handle_error
def light_add(light_type, name, location, rotation, color, power):
    """Add a light to the scene."""
    loc = [float(x) for x in location.split(",")] if location else None
    rot = [float(x) for x in rotation.split(",")] if rotation else None
    col = [float(x) for x in color.split(",")] if color else None

    sess = get_session()
    sess.snapshot(f"Add light: {light_type}")
    lt = light_mod.add_light(
        sess.get_project(), light_type=light_type.upper(), name=name,
        location=loc, rotation=rot, color=col, power=power,
    )
    output(lt, f"Added {light_type} light: {lt['name']}")


@light.command("set")
@click.argument("index", type=int)
@click.argument("prop")
@click.argument("value")
@handle_error
def light_set(index, prop, value):
    """Set a light property."""
    # Handle vector/color properties
    if prop in ("location", "rotation", "color"):
        value = [float(x) for x in value.split(",")]
    sess = get_session()
    sess.snapshot(f"Set light {index} {prop}")
    light_mod.set_light(sess.get_project(), index, prop, value)
    output({"light": index, "property": prop, "value": value},
           f"Set light {index} {prop}")


@light.command("list")
@handle_error
def light_list():
    """List all lights."""
    sess = get_session()
    lights = light_mod.list_lights(sess.get_project())
    output(lights, "Lights:")


# ── Animation Commands ──────────────────────────────────────────
@cli.group()
def animation():
    """Animation and keyframe commands."""
    pass


@animation.command("keyframe")
@click.argument("object_index", type=int)
@click.argument("frame", type=int)
@click.argument("prop")
@click.argument("value")
@click.option("--interpolation", "-i", type=click.Choice(["CONSTANT", "LINEAR", "BEZIER"]),
              default="BEZIER")
@handle_error
def animation_keyframe(object_index, frame, prop, value, interpolation):
    """Set a keyframe on an object."""
    # Handle vector values
    if prop in ("location", "rotation", "scale"):
        value = [float(x) for x in value.split(",")]
    sess = get_session()
    sess.snapshot(f"Add keyframe at frame {frame}")
    result = anim_mod.add_keyframe(
        sess.get_project(), object_index, frame, prop, value, interpolation,
    )
    output(result, f"Keyframe set at frame {frame}")


@animation.command("remove-keyframe")
@click.argument("object_index", type=int)
@click.argument("frame", type=int)
@click.option("--prop", "-p", default=None, help="Property (remove all at frame if not specified)")
@handle_error
def animation_remove_keyframe(object_index, frame, prop):
    """Remove a keyframe from an object."""
    sess = get_session()
    sess.snapshot(f"Remove keyframe at frame {frame}")
    removed = anim_mod.remove_keyframe(sess.get_project(), object_index, frame, prop)
    output(removed, f"Removed {len(removed)} keyframe(s) at frame {frame}")


@animation.command("frame-range")
@click.argument("start", type=int)
@click.argument("end", type=int)
@handle_error
def animation_frame_range(start, end):
    """Set the animation frame range."""
    sess = get_session()
    sess.snapshot("Set frame range")
    result = anim_mod.set_frame_range(sess.get_project(), start, end)
    output(result, f"Frame range: {start}-{end}")


@animation.command("fps")
@click.argument("fps", type=int)
@handle_error
def animation_fps(fps):
    """Set the animation FPS."""
    sess = get_session()
    result = anim_mod.set_fps(sess.get_project(), fps)
    output(result, f"FPS set to {fps}")


@animation.command("list-keyframes")
@click.argument("object_index", type=int)
@click.option("--prop", "-p", default=None, help="Filter by property")
@handle_error
def animation_list_keyframes(object_index, prop):
    """List keyframes for an object."""
    sess = get_session()
    keyframes = anim_mod.list_keyframes(sess.get_project(), object_index, prop)
    output(keyframes, f"Keyframes for object {object_index}:")


# ── Render Commands ─────────────────────────────────────────────
@cli.group("render")
def render_group():
    """Render settings and output commands."""
    pass


@render_group.command("settings")
@click.option("--engine", type=click.Choice(["CYCLES", "EEVEE", "WORKBENCH"]), default=None)
@click.option("--resolution-x", "-rx", type=int, default=None)
@click.option("--resolution-y", "-ry", type=int, default=None)
@click.option("--resolution-percentage", type=int, default=None)
@click.option("--samples", type=int, default=None)
@click.option("--denoising/--no-denoising", default=None)
@click.option("--transparent/--no-transparent", default=None)
@click.option("--format", "output_format", default=None)
@click.option("--output-path", default=None)
@click.option("--preset", default=None, help="Apply render preset")
@handle_error
def render_settings(engine, resolution_x, resolution_y, resolution_percentage,
                    samples, denoising, transparent, output_format, output_path, preset):
    """Configure render settings."""
    sess = get_session()
    sess.snapshot("Update render settings")
    result = render_mod.set_render_settings(
        sess.get_project(),
        engine=engine,
        resolution_x=resolution_x,
        resolution_y=resolution_y,
        resolution_percentage=resolution_percentage,
        samples=samples,
        use_denoising=denoising,
        film_transparent=transparent,
        output_format=output_format,
        output_path=output_path,
        preset=preset,
    )
    output(result, "Render settings updated")


@render_group.command("info")
@handle_error
def render_info():
    """Show current render settings."""
    sess = get_session()
    info = render_mod.get_render_settings(sess.get_project())
    output(info)


@render_group.command("presets")
@handle_error
def render_presets():
    """List available render presets."""
    presets = render_mod.list_render_presets()
    output(presets, "Render presets:")


@render_group.command("execute")
@click.argument("output_path", required=False)
@click.option("--output", "output_option", type=str, default=None,
              help="Render output path (alternative to positional OUTPUT_PATH)")
@click.option("--engine", type=click.Choice(["CYCLES", "EEVEE", "WORKBENCH"]), default=None,
              help="Override render engine for this render")
@click.option("--samples", type=int, default=None, help="Override render samples for this render")
@click.option("--format", "output_format", default=None, help="Override output format for this render")
@click.option("--preset", default=None, help="Apply a render preset for this render")
@click.option("--frame", "-f", type=int, default=None, help="Specific frame to render")
@click.option("--animation", "-a", is_flag=True, help="Render full animation")
@click.option("--overwrite", is_flag=True, help="Overwrite existing file")
@handle_error
def render_execute(output_path, output_option, engine, samples, output_format, preset,
                   frame, animation, overwrite):
    """Render the scene via Blender headless."""
    if output_path and output_option:
        raise ValueError("Specify the output path either positionally or with --output, not both.")

    target_output = output_option or output_path
    if not target_output:
        raise ValueError("Output path is required. Pass OUTPUT_PATH or --output.")

    sess = get_session()
    project = sess.get_project()
    if any(value is not None for value in (engine, samples, output_format, preset)):
        project = copy.deepcopy(project)
        render_mod.set_render_settings(
            project,
            engine=engine,
            samples=samples,
            output_format=output_format,
            preset=preset,
        )

    result = render_mod.render_scene(
        project,
        target_output,
        frame=frame,
        animation=animation,
        overwrite=overwrite,
        execute=True,
    )
    if animation:
        message = (
            f"Rendered animation: {result['output_count']} output(s) via {result['method']}"
        )
    else:
        message = f"Rendered: {result['output']} ({result['file_size']:,} bytes) via {result['method']}"
    output(result, message)


@render_group.command("script")
@click.argument("output_path")
@click.option("--frame", "-f", type=int, default=None)
@click.option("--animation", "-a", is_flag=True)
@handle_error
def render_script(output_path, frame, animation):
    """Generate bpy script without rendering."""
    sess = get_session()
    script = render_mod.generate_bpy_script(
        sess.get_project(), output_path, frame=frame, animation=animation,
    )
    click.echo(script)


@cli.group("preview")
def preview_group():
    """Preview bundle capture and inspection."""
    pass


@preview_group.group("live")
def preview_live_group():
    """Live preview session management."""
    pass


@preview_group.command("recipes")
@handle_error
def preview_recipes():
    """List available preview recipes."""
    output(preview_mod.list_recipes(), "Preview recipes:")


@preview_group.command("capture")
@click.option("--recipe", default="quick", help="Preview recipe name")
@click.option("--force", is_flag=True, help="Bypass preview cache")
@click.option("--root-dir", default=None, help="Override preview bundle root directory")
@handle_error
def preview_capture(recipe, force, root_dir):
    """Capture a preview bundle for the active scene."""
    sess = get_session()
    result = preview_mod.capture(
        sess,
        recipe=recipe,
        force=force,
        root_dir=root_dir,
        command=f"cli-anything-blender --project {sess.project_path or ''} preview capture --recipe {recipe}".strip(),
    )
    bundle_dir = result.get("_bundle_dir", result.get("bundle_dir", ""))
    status = "Reused preview bundle" if result.get("cached") else "Created preview bundle"
    output(result, f"{status}: {bundle_dir}")


@preview_group.command("latest")
@click.option("--recipe", default=None, help="Filter by recipe name")
@click.option("--root-dir", default=None, help="Override preview bundle root directory")
@handle_error
def preview_latest(recipe, root_dir):
    """Show the latest preview bundle manifest."""
    sess = get_session()
    result = preview_mod.latest(project_path=sess.project_path, recipe=recipe, root_dir=root_dir)
    output(result, f"Latest preview bundle: {result.get('_bundle_dir', '')}")


@preview_live_group.command("start")
@click.option("--recipe", default="quick", help="Preview recipe name")
@click.option("--force", is_flag=True, help="Bypass preview cache")
@click.option("--root-dir", default=None, help="Override preview root directory")
@click.option("--poll-ms", default=1500, show_default=True, help="Suggested viewer polling interval")
@click.option("--mode", type=click.Choice(["poll", "manual"]), default="poll", show_default=True,
              help="Live preview mode. Poll mode auto-captures when the project file changes.")
@click.option("--source-poll-ms", default=500, show_default=True,
              help="Polling interval for source project changes in poll mode.")
@click.option("--open", "open_window", is_flag=True, help="Launch cli-hub live viewer in a separate window.")
@handle_error
def preview_live_start(recipe, force, root_dir, poll_ms, mode, source_poll_ms, open_window):
    """Start a live preview session and publish the latest bundle."""
    sess = get_session()
    result = preview_mod.live_start(
        sess,
        recipe=recipe,
        force=force,
        root_dir=root_dir,
        refresh_hint_ms=poll_ms,
        live_mode=mode,
        source_poll_ms=source_poll_ms,
        command=(
            f"cli-anything-blender --project {sess.project_path or ''} "
            f"preview live start --recipe {recipe}"
        ).strip(),
    )
    if result.get("live_mode") == "poll" and not result.get("poller", {}).get("running"):
        result["poller"] = _spawn_live_poller(result["_session_dir"])
    if open_window:
        result["viewer"] = _spawn_live_viewer(result["_session_dir"], poll_ms)
    output(result, f"Started live preview session: {result.get('_session_dir', '')}")


@preview_live_group.command("push")
@click.option("--recipe", default="quick", help="Preview recipe name")
@click.option("--force", is_flag=True, help="Bypass preview cache")
@click.option("--root-dir", default=None, help="Override preview root directory")
@click.option("--poll-ms", default=1500, show_default=True, help="Suggested viewer polling interval")
@handle_error
def preview_live_push(recipe, force, root_dir, poll_ms):
    """Publish a fresh bundle into the live preview session."""
    sess = get_session()
    result = preview_mod.live_push(
        sess,
        recipe=recipe,
        force=force,
        root_dir=root_dir,
        refresh_hint_ms=poll_ms,
        command=(
            f"cli-anything-blender --project {sess.project_path or ''} "
            f"preview live push --recipe {recipe}"
        ).strip(),
    )
    output(result, f"Updated live preview session: {result.get('_session_dir', '')}")


@preview_live_group.command("status")
@click.option("--recipe", default="quick", help="Preview recipe name")
@click.option("--root-dir", default=None, help="Override preview root directory")
@handle_error
def preview_live_status(recipe, root_dir):
    """Show live preview session metadata."""
    sess = get_session()
    result = preview_mod.live_status(sess, recipe=recipe, root_dir=root_dir)
    output(result, f"Live preview session: {result.get('_session_dir', '')}")


@preview_live_group.command("stop")
@click.option("--recipe", default="quick", help="Preview recipe name")
@click.option("--root-dir", default=None, help="Override preview root directory")
@handle_error
def preview_live_stop(recipe, root_dir):
    """Stop the live preview session without deleting artifacts."""
    sess = get_session()
    result = preview_mod.live_stop(sess, recipe=recipe, root_dir=root_dir)
    output(result, f"Stopped live preview session: {result.get('_session_dir', '')}")


@preview_live_group.command("monitor", hidden=True)
@click.option("--session-dir", required=True, help="Live session directory to monitor.")
@handle_error
def preview_live_monitor(session_dir):
    """Internal background poller for live preview sessions."""
    result = preview_mod.run_live_poller(session_dir)
    output(result, "")


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
    from cli_anything.blender.utils.repl_skin import ReplSkin

    global _repl_mode
    _repl_mode = True

    skin = ReplSkin("blender", version="1.0.0")

    if project_path:
        sess = get_session()
        proj = scene_mod.open_scene(project_path)
        sess.set_project(proj, project_path)

    skin.print_banner()

    pt_session = skin.create_prompt_session()

    _repl_commands = {
        "scene":     "new|open|save|info|profiles|json",
        "object":    "add|remove|duplicate|transform|set|list|get",
        "material":  "create|assign|set|list|get",
        "modifier":  "list-available|info|add|remove|set|list",
        "camera":    "add|set|set-active|list",
        "light":     "add|set|list",
        "animation": "keyframe|remove-keyframe|frame-range|fps|list-keyframes",
        "render":    "settings|info|presets|execute|script",
        "preview":   "recipes|capture|latest|live start|push|status|stop",
        "session":   "status|undo|redo|history",
        "help":      "show this help",
        "quit":      "exit REPL",
    }

    while True:
        try:
            sess = get_session()
            project_name = ""
            modified = False
            if sess.has_project():
                if sess.project_path:
                    project_name = os.path.basename(sess.project_path)
                else:
                    info = sess.get_project()
                    project_name = info.get("scene", {}).get("name", info.get("name", ""))
                modified = sess._modified

            line = skin.get_input(pt_session, project_name=project_name, modified=modified).strip()
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
                skin.error(str(e))

        except (EOFError, KeyboardInterrupt):
            skin.print_goodbye()
            break

    _repl_mode = False


# ── Entry Point ─────────────────────────────────────────────────
def main():
    cli()


if __name__ == "__main__":
    main()
