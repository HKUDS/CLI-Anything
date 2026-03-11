#!/usr/bin/env python3
"""Audacity CLI — A stateful command-line interface for audio editing.

This CLI provides full audio editing capabilities using Python stdlib
(wave, struct, math) as the backend engine, with a JSON project format
that tracks tracks, clips, effects, labels, and history.

Usage:
    # One-shot commands
    python3 -m cli.audacity_cli project new --name "My Podcast"
    python3 -m cli.audacity_cli track add --name "Voice"
    python3 -m cli.audacity_cli clip add 0 recording.wav
    python3 -m cli.audacity_cli effect add normalize --track 0

    # Interactive REPL
    python3 -m cli.audacity_cli repl
"""

import sys
import os
import json
import shlex
import click
from typing import Optional

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cli_anything.audacity.core.session import Session
from cli_anything.audacity.core import project as proj_mod
from cli_anything.audacity.core import tracks as track_mod
from cli_anything.audacity.core import clips as clip_mod
from cli_anything.audacity.core import effects as fx_mod
from cli_anything.audacity.core import labels as label_mod
from cli_anything.audacity.core import selection as sel_mod
from cli_anything.audacity.core import media as media_mod
from cli_anything.audacity.core import export as export_mod

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


# -- Main CLI Group --------------------------------------------------------
@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, help="Output as JSON")
@click.option("--project", "project_path", type=str, default=None,
              help="Path to .audacity-cli.json project file")
@click.pass_context
def cli(ctx, use_json, project_path):
    """Audacity CLI — Stateful audio editing from the command line.

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


# -- Project Commands ------------------------------------------------------
@cli.group()
def project():
    """Project management commands."""
    pass


@project.command("new")
@click.option("--name", "-n", default="untitled", help="Project name")
@click.option("--sample-rate", "-sr", type=int, default=44100, help="Sample rate")
@click.option("--bit-depth", "-bd", type=int, default=16, help="Bit depth")
@click.option("--channels", "-ch", type=int, default=2, help="Channels (1=mono, 2=stereo)")
@click.option("--output", "-o", type=str, default=None, help="Save path")
@handle_error
def project_new(name, sample_rate, bit_depth, channels, output):
    """Create a new project."""
    proj = proj_mod.create_project(
        name=name, sample_rate=sample_rate,
        bit_depth=bit_depth, channels=channels,
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
    output({"saved": saved}, f"Saved to: {saved}")


@project.command("info")
@handle_error
def project_info():
    """Show project information."""
    sess = get_session()
    info = proj_mod.get_project_info(sess.get_project())
    output(info)


@project.command("settings")
@click.option("--sample-rate", "-sr", type=int, default=None)
@click.option("--bit-depth", "-bd", type=int, default=None)
@click.option("--channels", "-ch", type=int, default=None)
@handle_error
def project_settings(sample_rate, bit_depth, channels):
    """View or update project settings."""
    sess = get_session()
    proj = sess.get_project()
    if sample_rate or bit_depth or channels:
        sess.snapshot("Change settings")
        result = proj_mod.set_settings(proj, sample_rate, bit_depth, channels)
        output(result, "Settings updated:")
    else:
        output(proj.get("settings", {}), "Project settings:")


@project.command("json")
@handle_error
def project_json():
    """Print raw project JSON."""
    sess = get_session()
    click.echo(json.dumps(sess.get_project(), indent=2, default=str))


# -- Track Commands --------------------------------------------------------
@cli.group()
def track():
    """Track management commands."""
    pass


@track.command("add")
@click.option("--name", "-n", default=None, help="Track name")
@click.option("--type", "track_type", type=click.Choice(["audio", "label"]),
              default="audio", help="Track type")
@click.option("--volume", "-v", type=float, default=1.0, help="Volume (0.0-2.0)")
@click.option("--pan", "-p", type=float, default=0.0, help="Pan (-1.0 to 1.0)")
@handle_error
def track_add(name, track_type, volume, pan):
    """Add a new track."""
    sess = get_session()
    sess.snapshot(f"Add track: {name or 'new'}")
    result = track_mod.add_track(
        sess.get_project(), name=name, track_type=track_type,
        volume=volume, pan=pan,
    )
    output(result, f"Added track: {result['name']}")


@track.command("remove")
@click.argument("index", type=int)
@handle_error
def track_remove(index):
    """Remove a track by index."""
    sess = get_session()
    sess.snapshot(f"Remove track {index}")
    removed = track_mod.remove_track(sess.get_project(), index)
    output(removed, f"Removed track: {removed.get('name', '')}")


@track.command("list")
@handle_error
def track_list():
    """List all tracks."""
    sess = get_session()
    tracks = track_mod.list_tracks(sess.get_project())
    output(tracks, "Tracks:")


@track.command("set")
@click.argument("index", type=int)
@click.argument("prop")
@click.argument("value")
@handle_error
def track_set(index, prop, value):
    """Set a track property (name, mute, solo, volume, pan)."""
    sess = get_session()
    sess.snapshot(f"Set track {index} {prop}={value}")
    result = track_mod.set_track_property(sess.get_project(), index, prop, value)
    output({"track": index, "property": prop, "value": value},
           f"Set track {index} {prop} = {value}")


# -- Clip Commands ---------------------------------------------------------
@cli.group()
def clip():
    """Clip management commands."""
    pass


@clip.command("import")
@click.argument("path")
@handle_error
def clip_import(path):
    """Probe/import an audio file (show metadata)."""
    info = clip_mod.import_audio(path)
    output(info, f"Audio file: {path}")


@clip.command("add")
@click.argument("track_index", type=int)
@click.argument("source")
@click.option("--name", "-n", default=None, help="Clip name")
@click.option("--start", "-s", type=float, default=0.0, help="Start time on timeline")
@click.option("--end", "-e", type=float, default=None, help="End time on timeline")
@click.option("--trim-start", type=float, default=0.0, help="Trim start within source")
@click.option("--trim-end", type=float, default=None, help="Trim end within source")
@click.option("--volume", "-v", type=float, default=1.0, help="Clip volume")
@handle_error
def clip_add(track_index, source, name, start, end, trim_start, trim_end, volume):
    """Add an audio clip to a track."""
    sess = get_session()
    sess.snapshot(f"Add clip to track {track_index}")
    result = clip_mod.add_clip(
        sess.get_project(), track_index, source,
        name=name, start_time=start, end_time=end,
        trim_start=trim_start, trim_end=trim_end, volume=volume,
    )
    output(result, f"Added clip: {result['name']}")


@clip.command("remove")
@click.argument("track_index", type=int)
@click.argument("clip_index", type=int)
@handle_error
def clip_remove(track_index, clip_index):
    """Remove a clip from a track."""
    sess = get_session()
    sess.snapshot(f"Remove clip {clip_index} from track {track_index}")
    removed = clip_mod.remove_clip(sess.get_project(), track_index, clip_index)
    output(removed, f"Removed clip: {removed.get('name', '')}")


@clip.command("trim")
@click.argument("track_index", type=int)
@click.argument("clip_index", type=int)
@click.option("--trim-start", type=float, default=None, help="New trim start")
@click.option("--trim-end", type=float, default=None, help="New trim end")
@handle_error
def clip_trim(track_index, clip_index, trim_start, trim_end):
    """Trim a clip's start and/or end."""
    sess = get_session()
    sess.snapshot(f"Trim clip {clip_index} on track {track_index}")
    result = clip_mod.trim_clip(
        sess.get_project(), track_index, clip_index,
        trim_start=trim_start, trim_end=trim_end,
    )
    output(result, "Clip trimmed")


@clip.command("split")
@click.argument("track_index", type=int)
@click.argument("clip_index", type=int)
@click.argument("split_time", type=float)
@handle_error
def clip_split(track_index, clip_index, split_time):
    """Split a clip at a given time position."""
    sess = get_session()
    sess.snapshot(f"Split clip {clip_index} at {split_time}")
    result = clip_mod.split_clip(
        sess.get_project(), track_index, clip_index, split_time,
    )
    output(result, f"Split clip into 2 parts at {split_time}s")


@clip.command("move")
@click.argument("track_index", type=int)
@click.argument("clip_index", type=int)
@click.argument("new_start", type=float)
@handle_error
def clip_move(track_index, clip_index, new_start):
    """Move a clip to a new start time."""
    sess = get_session()
    sess.snapshot(f"Move clip {clip_index} to {new_start}")
    result = clip_mod.move_clip(
        sess.get_project(), track_index, clip_index, new_start,
    )
    output(result, f"Moved clip to {new_start}s")


@clip.command("list")
@click.argument("track_index", type=int)
@handle_error
def clip_list(track_index):
    """List clips on a track."""
    sess = get_session()
    clips = clip_mod.list_clips(sess.get_project(), track_index)
    output(clips, f"Clips on track {track_index}:")


# -- Effect Commands -------------------------------------------------------
@cli.group("effect")
def effect_group():
    """Effect management commands."""
    pass


@effect_group.command("list-available")
@click.option("--category", "-c", type=str, default=None,
              help="Filter by category: volume, fade, transform, delay, eq, dynamics, generate, restoration")
@handle_error
def effect_list_available(category):
    """List all available effects."""
    effects = fx_mod.list_available(category)
    output(effects, "Available effects:")


@effect_group.command("info")
@click.argument("name")
@handle_error
def effect_info(name):
    """Show details about an effect."""
    info = fx_mod.get_effect_info(name)
    output(info)


@effect_group.command("add")
@click.argument("name")
@click.option("--track", "-t", "track_index", type=int, default=0, help="Track index")
@click.option("--param", "-p", multiple=True, help="Parameter: key=value")
@handle_error
def effect_add(name, track_index, param):
    """Add an effect to a track."""
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
    sess.snapshot(f"Add effect {name} to track {track_index}")
    result = fx_mod.add_effect(sess.get_project(), name, track_index, params)
    output(result, f"Added effect: {name}")


@effect_group.command("remove")
@click.argument("effect_index", type=int)
@click.option("--track", "-t", "track_index", type=int, default=0)
@handle_error
def effect_remove(effect_index, track_index):
    """Remove an effect by index."""
    sess = get_session()
    sess.snapshot(f"Remove effect {effect_index} from track {track_index}")
    result = fx_mod.remove_effect(sess.get_project(), effect_index, track_index)
    output(result, f"Removed effect {effect_index}")


@effect_group.command("set")
@click.argument("effect_index", type=int)
@click.argument("param")
@click.argument("value")
@click.option("--track", "-t", "track_index", type=int, default=0)
@handle_error
def effect_set(effect_index, param, value, track_index):
    """Set an effect parameter."""
    try:
        value = float(value) if "." in str(value) else int(value)
    except ValueError:
        pass
    sess = get_session()
    sess.snapshot(f"Set effect {effect_index} {param}={value}")
    fx_mod.set_effect_param(sess.get_project(), effect_index, param, value, track_index)
    output({"effect": effect_index, "param": param, "value": value},
           f"Set effect {effect_index} {param} = {value}")


@effect_group.command("list")
@click.option("--track", "-t", "track_index", type=int, default=0)
@handle_error
def effect_list(track_index):
    """List effects on a track."""
    sess = get_session()
    effects = fx_mod.list_effects(sess.get_project(), track_index)
    output(effects, f"Effects on track {track_index}:")


# -- Selection Commands ----------------------------------------------------
@cli.group()
def selection():
    """Selection management commands."""
    pass


@selection.command("set")
@click.argument("start", type=float)
@click.argument("end", type=float)
@handle_error
def selection_set(start, end):
    """Set selection range."""
    sess = get_session()
    result = sel_mod.set_selection(sess.get_project(), start, end)
    output(result, f"Selection: {start}s - {end}s")


@selection.command("all")
@handle_error
def selection_all():
    """Select all (entire project duration)."""
    sess = get_session()
    result = sel_mod.select_all(sess.get_project())
    output(result, "Selected all")


@selection.command("none")
@handle_error
def selection_none():
    """Clear selection."""
    sess = get_session()
    result = sel_mod.select_none(sess.get_project())
    output(result, "Selection cleared")


@selection.command("info")
@handle_error
def selection_info():
    """Show current selection."""
    sess = get_session()
    result = sel_mod.get_selection(sess.get_project())
    output(result)


# -- Label Commands --------------------------------------------------------
@cli.group()
def label():
    """Label/marker management commands."""
    pass


@label.command("add")
@click.argument("start", type=float)
@click.option("--end", "-e", type=float, default=None, help="End time (for range labels)")
@click.option("--text", "-t", default="", help="Label text")
@handle_error
def label_add(start, end, text):
    """Add a label at a time position."""
    sess = get_session()
    sess.snapshot(f"Add label at {start}")
    result = label_mod.add_label(sess.get_project(), start, end, text)
    output(result, f"Added label: {text or f'at {start}s'}")


@label.command("remove")
@click.argument("index", type=int)
@handle_error
def label_remove(index):
    """Remove a label by index."""
    sess = get_session()
    sess.snapshot(f"Remove label {index}")
    removed = label_mod.remove_label(sess.get_project(), index)
    output(removed, f"Removed label: {removed.get('text', '')}")


@label.command("list")
@handle_error
def label_list():
    """List all labels."""
    sess = get_session()
    labels = label_mod.list_labels(sess.get_project())
    output(labels, "Labels:")


# -- Media Commands --------------------------------------------------------
@cli.group()
def media():
    """Media file operations."""
    pass


@media.command("probe")
@click.argument("path")
@handle_error
def media_probe(path):
    """Analyze an audio file."""
    info = media_mod.probe_audio(path)
    output(info)


@media.command("check")
@handle_error
def media_check():
    """Check that all referenced audio files exist."""
    sess = get_session()
    result = media_mod.check_media(sess.get_project())
    output(result)


# -- Export Commands -------------------------------------------------------
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
@click.option("--preset", "-p", default="wav", help="Export preset")
@click.option("--overwrite", is_flag=True, help="Overwrite existing file")
@click.option("--channels", "-ch", type=int, default=None, help="Channel override (1 or 2)")
@handle_error
def export_render(output_path, preset, overwrite, channels):
    """Render the project to an audio file."""
    sess = get_session()
    result = export_mod.render_mix(
        sess.get_project(), output_path,
        preset=preset, overwrite=overwrite,
        channels_override=channels,
    )
    output(result, f"Rendered to: {output_path}")


# -- Session Commands ------------------------------------------------------
@cli.group("session")
def session_group():
    """Session management commands."""
    pass


@session_group.command("status")
@handle_error
def session_status():
    """Show session status."""
    sess = get_session()
    output(sess.status())


@session_group.command("undo")
@handle_error
def session_undo():
    """Undo the last operation."""
    sess = get_session()
    desc = sess.undo()
    output({"undone": desc}, f"Undone: {desc}")


@session_group.command("redo")
@handle_error
def session_redo():
    """Redo the last undone operation."""
    sess = get_session()
    desc = sess.redo()
    output({"redone": desc}, f"Redone: {desc}")


@session_group.command("history")
@handle_error
def session_history():
    """Show undo history."""
    sess = get_session()
    history = sess.list_history()
    output(history, "Undo history:")


# -- REPL ------------------------------------------------------------------
@cli.command()
@click.option("--project", "project_path", type=str, default=None)
@handle_error
def repl(project_path):
    """Start interactive REPL session."""
    global _repl_mode
    _repl_mode = True

    from cli_anything.audacity.utils.repl_skin import ReplSkin
    skin = ReplSkin("audacity", version="1.0.0")

    if project_path:
        sess = get_session()
        proj = proj_mod.open_project(project_path)
        sess.set_project(proj, project_path)

    skin.print_banner()

    pt_session = skin.create_prompt_session()

    while True:
        try:
            sess = get_session()
            proj_name = ""
            modified = False
            if sess.has_project():
                proj = sess.get_project()
                proj_name = proj.get("name", "")
                modified = sess.is_modified() if hasattr(sess, 'is_modified') else False

            line = skin.get_input(pt_session, project_name=proj_name, modified=modified)
            if not line:
                continue
            if line.lower() in ("quit", "exit", "q"):
                skin.print_goodbye()
                break
            if line.lower() == "help":
                _repl_help(skin)
                continue

            args = shlex.split(line)
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
        "project new|open|save|info|settings|json": "Project management",
        "track add|remove|list|set": "Track management",
        "clip import|add|remove|trim|split|move|list": "Clip management",
        "effect list-available|info|add|remove|set|list": "Effect management",
        "selection set|all|none|info": "Selection management",
        "label add|remove|list": "Label/marker management",
        "media probe|check": "Media file operations",
        "export presets|preset-info|render": "Export/render commands",
        "session status|undo|redo|history": "Session management",
        "help": "Show this help",
        "quit": "Exit REPL",
    }
    if skin is not None:
        skin.help(commands)
    else:
        click.echo("\nCommands:")
        for cmd, desc in commands.items():
            click.echo(f"  {cmd:50s} {desc}")
        click.echo()


# -- Entry Point -----------------------------------------------------------
def main():
    cli()


if __name__ == "__main__":
    main()
