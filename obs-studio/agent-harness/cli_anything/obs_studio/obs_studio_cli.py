#!/usr/bin/env python3
"""OBS Studio CLI -- A stateful command-line interface for OBS scene collection editing.

This CLI provides full OBS Studio scene management capabilities using a JSON
scene collection format. No OBS installation required for editing.

Usage:
    # One-shot commands
    python3 -m cli.obs_cli project new --name "my_stream"
    python3 -m cli.obs_cli source add video_capture --name "Camera"
    python3 -m cli.obs_cli scene add --name "BRB"

    # Interactive REPL
    python3 -m cli.obs_cli repl
"""

import sys
import os
import json
import shlex
import click
from typing import Optional

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cli_anything.obs_studio.core.session import Session
from cli_anything.obs_studio.core import project as proj_mod
from cli_anything.obs_studio.core import scenes as scene_mod
from cli_anything.obs_studio.core import sources as src_mod
from cli_anything.obs_studio.core import filters as filt_mod
from cli_anything.obs_studio.core import audio as audio_mod
from cli_anything.obs_studio.core import transitions as trans_mod
from cli_anything.obs_studio.core import output as out_mod

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


# -- Main CLI Group ----------------------------------------------------------
@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, help="Output as JSON")
@click.option("--project", "project_path", type=str, default=None,
              help="Path to OBS scene collection JSON file")
@click.pass_context
def cli(ctx, use_json, project_path):
    """OBS Studio CLI -- Stateful scene collection editing from the command line.

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


# -- Project Commands --------------------------------------------------------
@cli.group()
def project():
    """Project management commands."""
    pass


@project.command("new")
@click.option("--name", "-n", default="untitled", help="Project name")
@click.option("--width", "-w", type=int, default=1920, help="Output width")
@click.option("--height", "-h", type=int, default=1080, help="Output height")
@click.option("--fps", type=int, default=30, help="Frames per second")
@click.option("--encoder", type=str, default="x264", help="Video encoder")
@click.option("--output", "-o", type=str, default=None, help="Save path")
@handle_error
def project_new(name, width, height, fps, encoder, output):
    """Create a new OBS scene collection."""
    proj = proj_mod.create_project(
        name=name, output_width=width, output_height=height,
        fps=fps, encoder=encoder,
    )
    sess = get_session()
    sess.set_project(proj, output)
    if output:
        proj_mod.save_project(proj, output)
    info = proj_mod.get_project_info(proj)
    globals()["output"](info, f"Created project: {name}")


@project.command("open")
@click.argument("path")
@handle_error
def project_open(path):
    """Open an existing project."""
    proj = proj_mod.open_project(path)
    sess = get_session()
    sess.set_project(proj, path)
    info = proj_mod.get_project_info(proj)
    globals()["output"](info, f"Opened: {path}")


@project.command("save")
@click.argument("path", required=False)
@handle_error
def project_save(path):
    """Save the current project."""
    sess = get_session()
    saved = sess.save_session(path)
    globals()["output"]({"saved": saved}, f"Saved to: {saved}")


@project.command("info")
@handle_error
def project_info():
    """Show project information."""
    sess = get_session()
    info = proj_mod.get_project_info(sess.get_project())
    globals()["output"](info)


@project.command("json")
@handle_error
def project_json():
    """Print raw project JSON."""
    sess = get_session()
    click.echo(json.dumps(sess.get_project(), indent=2, default=str))


# -- Scene Commands ----------------------------------------------------------
@cli.group("scene")
def scene_group():
    """Scene management commands."""
    pass


@scene_group.command("add")
@click.option("--name", "-n", default="Scene", help="Scene name")
@handle_error
def scene_add(name):
    """Add a new scene."""
    sess = get_session()
    sess.snapshot(f"Add scene: {name}")
    scene = scene_mod.add_scene(sess.get_project(), name=name)
    output(scene, f"Added scene: {scene['name']}")


@scene_group.command("remove")
@click.argument("index", type=int)
@handle_error
def scene_remove(index):
    """Remove a scene by index."""
    sess = get_session()
    sess.snapshot(f"Remove scene {index}")
    removed = scene_mod.remove_scene(sess.get_project(), index)
    output(removed, f"Removed scene: {removed['name']}")


@scene_group.command("duplicate")
@click.argument("index", type=int)
@handle_error
def scene_duplicate(index):
    """Duplicate a scene."""
    sess = get_session()
    sess.snapshot(f"Duplicate scene {index}")
    dup = scene_mod.duplicate_scene(sess.get_project(), index)
    output(dup, f"Duplicated scene: {dup['name']}")


@scene_group.command("set-active")
@click.argument("index", type=int)
@handle_error
def scene_set_active(index):
    """Set the active scene."""
    sess = get_session()
    sess.snapshot(f"Set active scene {index}")
    result = scene_mod.set_active_scene(sess.get_project(), index)
    output(result, f"Active scene: {result['active_scene']}")


@scene_group.command("list")
@handle_error
def scene_list():
    """List all scenes."""
    sess = get_session()
    scenes = scene_mod.list_scenes(sess.get_project())
    output(scenes, "Scenes:")


# -- Source Commands ---------------------------------------------------------
@cli.group("source")
def source_group():
    """Source management commands."""
    pass


@source_group.command("add")
@click.argument("source_type", type=click.Choice(sorted(src_mod.SOURCE_TYPES.keys())))
@click.option("--name", "-n", default=None, help="Source name")
@click.option("--scene", "-s", "scene_index", type=int, default=0, help="Scene index")
@click.option("--position", "-p", default=None, help="Position x,y")
@click.option("--size", default=None, help="Size widthxheight")
@click.option("--setting", "-S", multiple=True, help="Setting: key=value")
@handle_error
def source_add(source_type, name, scene_index, position, size, setting):
    """Add a source to a scene."""
    pos = None
    if position:
        parts = position.split(",")
        pos = {"x": float(parts[0]), "y": float(parts[1])}
    sz = None
    if size:
        parts = size.split("x")
        sz = {"width": int(parts[0]), "height": int(parts[1])}
    settings = {}
    for s in setting:
        if "=" not in s:
            raise ValueError(f"Invalid setting format: '{s}'. Use key=value.")
        k, v = s.split("=", 1)
        try:
            v = float(v) if "." in v else int(v)
        except ValueError:
            pass
        settings[k] = v

    sess = get_session()
    sess.snapshot(f"Add source: {source_type}")
    src = src_mod.add_source(
        sess.get_project(), source_type, scene_index=scene_index,
        name=name, position=pos, size=sz, settings=settings if settings else None,
    )
    output(src, f"Added {source_type}: {src['name']}")


@source_group.command("remove")
@click.argument("index", type=int)
@click.option("--scene", "-s", "scene_index", type=int, default=0)
@handle_error
def source_remove(index, scene_index):
    """Remove a source by index."""
    sess = get_session()
    sess.snapshot(f"Remove source {index}")
    removed = src_mod.remove_source(sess.get_project(), index, scene_index)
    output(removed, f"Removed source: {removed['name']}")


@source_group.command("duplicate")
@click.argument("index", type=int)
@click.option("--scene", "-s", "scene_index", type=int, default=0)
@handle_error
def source_duplicate(index, scene_index):
    """Duplicate a source."""
    sess = get_session()
    sess.snapshot(f"Duplicate source {index}")
    dup = src_mod.duplicate_source(sess.get_project(), index, scene_index)
    output(dup, f"Duplicated source: {dup['name']}")


@source_group.command("set")
@click.argument("index", type=int)
@click.argument("prop")
@click.argument("value")
@click.option("--scene", "-s", "scene_index", type=int, default=0)
@handle_error
def source_set(index, prop, value, scene_index):
    """Set a source property (name, visible, locked, opacity, rotation)."""
    sess = get_session()
    sess.snapshot(f"Set source {index} {prop}={value}")
    src = src_mod.set_source_property(sess.get_project(), index, prop, value, scene_index)
    output({"source": index, "property": prop, "value": value},
           f"Set source {index} {prop} = {value}")


@source_group.command("transform")
@click.argument("index", type=int)
@click.option("--position", "-p", default=None, help="Position x,y")
@click.option("--size", default=None, help="Size widthxheight")
@click.option("--crop", default=None, help="Crop top,bottom,left,right")
@click.option("--rotation", "-r", type=float, default=None)
@click.option("--scene", "-s", "scene_index", type=int, default=0)
@handle_error
def source_transform(index, position, size, crop, rotation, scene_index):
    """Transform a source (position, size, crop, rotation)."""
    pos = None
    if position:
        parts = position.split(",")
        pos = {"x": float(parts[0]), "y": float(parts[1])}
    sz = None
    if size:
        parts = size.split("x")
        sz = {"width": int(parts[0]), "height": int(parts[1])}
    cr = None
    if crop:
        parts = crop.split(",")
        cr = {"top": int(parts[0]), "bottom": int(parts[1]),
              "left": int(parts[2]), "right": int(parts[3])}

    sess = get_session()
    sess.snapshot(f"Transform source {index}")
    src = src_mod.transform_source(
        sess.get_project(), index, scene_index,
        position=pos, size=sz, crop=cr, rotation=rotation,
    )
    output(src, f"Transformed source {index}: {src['name']}")


@source_group.command("list")
@click.option("--scene", "-s", "scene_index", type=int, default=0)
@handle_error
def source_list(scene_index):
    """List all sources in a scene."""
    sess = get_session()
    sources = src_mod.list_sources(sess.get_project(), scene_index)
    output(sources, "Sources:")


# -- Filter Commands ---------------------------------------------------------
@cli.group("filter")
def filter_group():
    """Filter management commands."""
    pass


@filter_group.command("add")
@click.argument("filter_type", type=click.Choice(sorted(filt_mod.FILTER_TYPES.keys())))
@click.option("--source", "-S", "source_index", type=int, default=0, help="Source index")
@click.option("--scene", "-s", "scene_index", type=int, default=0, help="Scene index")
@click.option("--name", "-n", default=None, help="Filter name")
@click.option("--param", "-p", multiple=True, help="Parameter: key=value")
@handle_error
def filter_add(filter_type, source_index, scene_index, name, param):
    """Add a filter to a source."""
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
    sess.snapshot(f"Add filter: {filter_type}")
    filt = filt_mod.add_filter(
        sess.get_project(), filter_type, source_index, scene_index,
        name=name, params=params if params else None,
    )
    output(filt, f"Added filter: {filt['name']}")


@filter_group.command("remove")
@click.argument("filter_index", type=int)
@click.option("--source", "-S", "source_index", type=int, default=0)
@click.option("--scene", "-s", "scene_index", type=int, default=0)
@handle_error
def filter_remove(filter_index, source_index, scene_index):
    """Remove a filter from a source."""
    sess = get_session()
    sess.snapshot(f"Remove filter {filter_index}")
    removed = filt_mod.remove_filter(sess.get_project(), filter_index, source_index, scene_index)
    output(removed, f"Removed filter: {removed['name']}")


@filter_group.command("set")
@click.argument("filter_index", type=int)
@click.argument("param")
@click.argument("value")
@click.option("--source", "-S", "source_index", type=int, default=0)
@click.option("--scene", "-s", "scene_index", type=int, default=0)
@handle_error
def filter_set(filter_index, param, value, source_index, scene_index):
    """Set a filter parameter."""
    try:
        value = float(value) if "." in str(value) else int(value)
    except ValueError:
        pass
    sess = get_session()
    sess.snapshot(f"Set filter {filter_index} {param}={value}")
    filt_mod.set_filter_param(
        sess.get_project(), filter_index, param, value, source_index, scene_index,
    )
    output({"filter": filter_index, "param": param, "value": value},
           f"Set filter {filter_index} {param} = {value}")


@filter_group.command("list")
@click.option("--source", "-S", "source_index", type=int, default=0)
@click.option("--scene", "-s", "scene_index", type=int, default=0)
@handle_error
def filter_list(source_index, scene_index):
    """List all filters on a source."""
    sess = get_session()
    filters = filt_mod.list_filters(sess.get_project(), source_index, scene_index)
    output(filters, "Filters:")


@filter_group.command("list-available")
@click.option("--category", "-c", type=str, default=None, help="Filter by category: video, audio")
@handle_error
def filter_list_available(category):
    """List all available filter types."""
    filters = filt_mod.list_available_filters(category)
    output(filters, "Available filters:")


# -- Audio Commands ----------------------------------------------------------
@cli.group("audio")
def audio_group():
    """Audio management commands."""
    pass


@audio_group.command("add")
@click.option("--name", "-n", default="Audio", help="Audio source name")
@click.option("--type", "audio_type", type=click.Choice(["input", "output"]), default="input")
@click.option("--device", "-d", default="", help="Device identifier")
@click.option("--volume", "-v", type=float, default=1.0, help="Volume (0.0-3.0)")
@handle_error
def audio_add(name, audio_type, device, volume):
    """Add a global audio source."""
    sess = get_session()
    sess.snapshot(f"Add audio: {name}")
    src = audio_mod.add_audio_source(
        sess.get_project(), name=name, audio_type=audio_type,
        device=device, volume=volume,
    )
    output(src, f"Added audio source: {src['name']}")


@audio_group.command("remove")
@click.argument("index", type=int)
@handle_error
def audio_remove(index):
    """Remove a global audio source."""
    sess = get_session()
    sess.snapshot(f"Remove audio {index}")
    removed = audio_mod.remove_audio_source(sess.get_project(), index)
    output(removed, f"Removed audio: {removed['name']}")


@audio_group.command("volume")
@click.argument("index", type=int)
@click.argument("level", type=float)
@handle_error
def audio_volume(index, level):
    """Set volume for an audio source (0.0-3.0)."""
    sess = get_session()
    sess.snapshot(f"Set audio {index} volume={level}")
    src = audio_mod.set_volume(sess.get_project(), index, level)
    output({"audio": index, "volume": level}, f"Volume set to {level}")


@audio_group.command("mute")
@click.argument("index", type=int)
@handle_error
def audio_mute(index):
    """Mute an audio source."""
    sess = get_session()
    sess.snapshot(f"Mute audio {index}")
    src = audio_mod.mute(sess.get_project(), index)
    output({"audio": index, "muted": True}, f"Muted audio {index}")


@audio_group.command("unmute")
@click.argument("index", type=int)
@handle_error
def audio_unmute(index):
    """Unmute an audio source."""
    sess = get_session()
    sess.snapshot(f"Unmute audio {index}")
    src = audio_mod.unmute(sess.get_project(), index)
    output({"audio": index, "muted": False}, f"Unmuted audio {index}")


@audio_group.command("monitor")
@click.argument("index", type=int)
@click.argument("monitor_type", type=click.Choice(["none", "monitor_only", "monitor_and_output"]))
@handle_error
def audio_monitor(index, monitor_type):
    """Set audio monitoring type."""
    sess = get_session()
    sess.snapshot(f"Set audio {index} monitor={monitor_type}")
    src = audio_mod.set_monitor(sess.get_project(), index, monitor_type)
    output({"audio": index, "monitor": monitor_type}, f"Monitor set to {monitor_type}")


@audio_group.command("list")
@handle_error
def audio_list():
    """List all audio sources."""
    sess = get_session()
    sources = audio_mod.list_audio(sess.get_project())
    output(sources, "Audio sources:")


# -- Transition Commands -----------------------------------------------------
@cli.group("transition")
def transition_group():
    """Transition management commands."""
    pass


@transition_group.command("add")
@click.argument("transition_type", type=click.Choice(sorted(trans_mod.TRANSITION_TYPES.keys())))
@click.option("--name", "-n", default=None, help="Transition name")
@click.option("--duration", "-d", type=int, default=None, help="Duration in ms")
@handle_error
def transition_add(transition_type, name, duration):
    """Add a transition."""
    sess = get_session()
    sess.snapshot(f"Add transition: {transition_type}")
    trans = trans_mod.add_transition(
        sess.get_project(), transition_type, name=name, duration=duration,
    )
    output(trans, f"Added transition: {trans['name']}")


@transition_group.command("remove")
@click.argument("index", type=int)
@handle_error
def transition_remove(index):
    """Remove a transition."""
    sess = get_session()
    sess.snapshot(f"Remove transition {index}")
    removed = trans_mod.remove_transition(sess.get_project(), index)
    output(removed, f"Removed transition: {removed['name']}")


@transition_group.command("set-active")
@click.argument("index", type=int)
@handle_error
def transition_set_active(index):
    """Set the active transition."""
    sess = get_session()
    sess.snapshot(f"Set active transition {index}")
    result = trans_mod.set_active_transition(sess.get_project(), index)
    output(result, f"Active transition: {result['active_transition']}")


@transition_group.command("duration")
@click.argument("index", type=int)
@click.argument("duration", type=int)
@handle_error
def transition_duration(index, duration):
    """Set transition duration in milliseconds."""
    sess = get_session()
    sess.snapshot(f"Set transition {index} duration={duration}")
    trans = trans_mod.set_duration(sess.get_project(), index, duration)
    output(trans, f"Duration set to {duration}ms")


@transition_group.command("list")
@handle_error
def transition_list():
    """List all transitions."""
    sess = get_session()
    transitions = trans_mod.list_transitions(sess.get_project())
    output(transitions, "Transitions:")


# -- Output Commands ---------------------------------------------------------
@cli.group("output")
def output_group():
    """Output/streaming/recording configuration."""
    pass


@output_group.command("streaming")
@click.option("--service", type=click.Choice(["twitch", "youtube", "facebook", "custom"]), default=None)
@click.option("--server", type=str, default=None)
@click.option("--key", type=str, default=None)
@handle_error
def output_streaming(service, server, key):
    """Configure streaming settings."""
    sess = get_session()
    sess.snapshot("Update streaming settings")
    result = out_mod.set_streaming(sess.get_project(), service=service, server=server, key=key)
    globals()["output"](result, "Streaming settings updated")


@output_group.command("recording")
@click.option("--path", type=str, default=None)
@click.option("--format", "fmt", type=click.Choice(["mkv", "mp4", "mov", "flv", "ts"]), default=None)
@click.option("--quality", type=click.Choice(["low", "medium", "high", "lossless"]), default=None)
@handle_error
def output_recording(path, fmt, quality):
    """Configure recording settings."""
    sess = get_session()
    sess.snapshot("Update recording settings")
    result = out_mod.set_recording(sess.get_project(), path=path, fmt=fmt, quality=quality)
    globals()["output"](result, "Recording settings updated")


@output_group.command("settings")
@click.option("--width", type=int, default=None)
@click.option("--height", type=int, default=None)
@click.option("--fps", type=int, default=None)
@click.option("--video-bitrate", type=int, default=None)
@click.option("--audio-bitrate", type=int, default=None)
@click.option("--encoder", type=str, default=None)
@click.option("--preset", type=str, default=None, help="Apply encoding preset")
@handle_error
def output_settings(width, height, fps, video_bitrate, audio_bitrate, encoder, preset):
    """Configure output settings."""
    sess = get_session()
    sess.snapshot("Update output settings")
    result = out_mod.set_output_settings(
        sess.get_project(),
        output_width=width, output_height=height, fps=fps,
        video_bitrate=video_bitrate, audio_bitrate=audio_bitrate,
        encoder=encoder, preset=preset,
    )
    globals()["output"](result, "Output settings updated")


@output_group.command("info")
@handle_error
def output_info():
    """Show current output configuration."""
    sess = get_session()
    info = out_mod.get_output_info(sess.get_project())
    globals()["output"](info)


@output_group.command("presets")
@handle_error
def output_presets():
    """List available encoding presets."""
    presets = out_mod.list_encoding_presets()
    globals()["output"](presets, "Encoding presets:")


# -- Session Commands --------------------------------------------------------
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


# -- REPL --------------------------------------------------------------------
@cli.command()
@click.option("--project", "project_path", type=str, default=None)
@handle_error
def repl(project_path):
    """Start interactive REPL session."""
    from cli_anything.obs_studio.utils.repl_skin import ReplSkin

    global _repl_mode
    _repl_mode = True

    skin = ReplSkin("obs_studio", version="1.0.0")

    if project_path:
        sess = get_session()
        proj = proj_mod.open_project(project_path)
        sess.set_project(proj, project_path)

    skin.print_banner()

    pt_session = skin.create_prompt_session()

    def _get_project_name():
        """Get current project name for prompt display."""
        try:
            sess = get_session()
            if sess.has_project():
                info = proj_mod.get_project_info(sess.get_project())
                return info.get("name", "")
        except Exception:
            pass
        return ""

    while True:
        try:
            line = skin.get_input(
                pt_session,
                project_name=_get_project_name(),
                modified=False,
            ).strip()
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
                skin.error(str(e))

        except (EOFError, KeyboardInterrupt):
            skin.print_goodbye()
            break

    _repl_mode = False


def _repl_help(skin=None):
    commands = {
        "project new|open|save|info|json": "Project management",
        "scene add|remove|duplicate|set-active|list": "Scene management",
        "source add|remove|duplicate|set|transform|list": "Source management",
        "filter add|remove|set|list|list-available": "Filter management",
        "audio add|remove|volume|mute|unmute|monitor|list": "Audio management",
        "transition add|remove|set-active|duration|list": "Transition management",
        "output streaming|recording|settings|info|presets": "Output configuration",
        "session status|undo|redo|history": "Session management",
        "help": "Show this help",
        "quit": "Exit REPL",
    }
    if skin is not None:
        skin.help(commands)
    else:
        click.echo("\nCommands:")
        for cmd, desc in commands.items():
            click.echo(f"  {cmd:55s} {desc}")
        click.echo()


# -- Entry Point -------------------------------------------------------------
def main():
    cli()


if __name__ == "__main__":
    main()
