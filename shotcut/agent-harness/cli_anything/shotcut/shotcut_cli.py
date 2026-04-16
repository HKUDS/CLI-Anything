#!/usr/bin/env python3
"""Shotcut CLI — A stateful command-line interface for video editing.

This CLI manipulates Shotcut/MLT project files directly, providing
full video editing capabilities for AI agents and power users.

Usage:
    # One-shot commands
    shotcut-cli project new --profile hd1080p30 -o my_project.mlt
    shotcut-cli timeline add-track --type video
    shotcut-cli timeline add-clip video.mp4 --track 1

    # Interactive REPL
    shotcut-cli repl
"""

import sys
import os
import json
import click
from typing import Optional

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cli_anything.shotcut.core.session import Session
from cli_anything.shotcut.core import project as proj_mod
from cli_anything.shotcut.core import timeline as tl_mod
from cli_anything.shotcut.core import filters as filt_mod
from cli_anything.shotcut.core import media as media_mod
from cli_anything.shotcut.core import export as export_mod
from cli_anything.shotcut.core import transitions as trans_mod
from cli_anything.shotcut.core import compositing as comp_mod

# Global session state (persists across commands in REPL mode)
_session: Optional[Session] = None
_json_output = False


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
            sys.exit(1) if not _repl_mode else None
        except (ValueError, IndexError, RuntimeError) as e:
            if _json_output:
                click.echo(json.dumps({"error": str(e), "type": type(e).__name__}))
            else:
                click.echo(f"Error: {e}", err=True)
            sys.exit(1) if not _repl_mode else None
        except Exception as e:
            if _json_output:
                click.echo(json.dumps({"error": str(e), "type": "unexpected"}))
            else:
                click.echo(f"Unexpected error: {e}", err=True)
            sys.exit(1) if not _repl_mode else None
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


_repl_mode = False
_auto_save = False


# ============================================================================
# Main CLI group
# ============================================================================

@click.group(invoke_without_command=True)
@click.option("--json", "json_mode", is_flag=True, help="Output in JSON format")
@click.option("--session", "session_id", default=None, help="Session ID to use/resume")
@click.option("--project", "project_path", default=None, help="Open a project file")
@click.option("-s", "--save", "auto_save", is_flag=True, 
              help="Auto-save project after each mutation command (one-shot mode)")
@click.pass_context
def cli(ctx, json_mode, session_id, project_path, auto_save):
    """Shotcut CLI — Video editing from the command line.

    A stateful CLI for manipulating Shotcut/MLT video projects.
    Designed for AI agents and power users.

    Run without a subcommand to enter interactive REPL mode.
    
    Use -s/--save to automatically save changes after each mutation command.
    This is useful in one-shot mode where each command runs in a new process.
    """
    global _json_output, _session, _auto_save
    _json_output = json_mode
    _auto_save = auto_save

    if session_id:
        _session = Session(session_id)
    else:
        _session = Session()

    if project_path:
        _session.open_project(project_path)

    # Register auto-save callback to run after each command
    ctx.call_on_close(_auto_save_callback)

    if ctx.invoked_subcommand is None:
        ctx.invoke(repl, project_path=None)


def _auto_save_callback():
    """Auto-save callback that runs after each command."""
    global _auto_save, _session
    if _auto_save and _session and _session.is_open and _session.is_modified:
        # Don't auto-save if we're in REPL mode (user can explicitly save)
        if not _repl_mode:
            try:
                _session.save_project()
                click.echo(f"Auto-saved to: {_session.project_path}")
            except Exception as e:
                click.echo(f"Auto-save failed: {e}", err=True)


# ============================================================================
# Project commands
# ============================================================================

@cli.group()
def project():
    """Project management: new, open, save, info."""
    pass


@project.command("new")
@click.option("--profile", default="hd1080p30",
              help="Video profile (hd1080p30, hd1080p60, 4k30, etc.)")
@click.option("-o", "--output", "output_path", default=None,
              help="Save the new project to this path")
@handle_error
def project_new(profile, output_path):
    """Create a new blank project."""
    session = get_session()
    result = proj_mod.new_project(session, profile)
    if output_path:
        save_result = proj_mod.save_project(session, output_path)
        result["saved_to"] = save_result["path"]
    output(result, f"Created new {profile} project")


@project.command("open")
@click.argument("path")
@handle_error
def project_open(path):
    """Open an existing .mlt project file."""
    session = get_session()
    result = proj_mod.open_project(session, path)
    output(result, f"Opened project: {path}")


@project.command("save")
@click.argument("path", required=False)
@handle_error
def project_save(path):
    """Save the current project. Optionally specify a new path."""
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


@project.command("profiles")
@handle_error
def project_profiles():
    """List available video profiles."""
    result = proj_mod.list_profiles()
    output(result, "Available profiles:")


@project.command("xml")
@handle_error
def project_xml():
    """Print the raw MLT XML of the current project."""
    session = get_session()
    if not session.is_open:
        raise RuntimeError("No project is open")
    from cli_anything.shotcut.utils.mlt_xml import mlt_to_string
    click.echo(mlt_to_string(session.root))


# ============================================================================
# Timeline commands
# ============================================================================

@cli.group()
def timeline():
    """Timeline operations: tracks, clips, trimming."""
    pass


@timeline.command("show")
@handle_error
def timeline_show():
    """Show the timeline overview."""
    session = get_session()
    result = tl_mod.show_timeline(session)
    if _json_output:
        output(result)
    else:
        _print_timeline_visual(result)


def _print_timeline_visual(data: dict):
    """Print a visual ASCII representation of the timeline."""
    tracks = data.get("tracks", [])
    if not tracks:
        click.echo("(empty timeline)")
        return

    click.echo(f"Timeline ({data.get('fps_num', 30000)}/{data.get('fps_den', 1001)} fps)")
    click.echo("=" * 70)

    for track in reversed(tracks):  # Top tracks first (video on top)
        if track.get("type") == "background":
            continue

        idx = track.get("index", "?")
        name = track.get("name") or track.get("type", "?").upper()
        ttype = track.get("type", "?")[0].upper()
        muted = " [MUTED]" if "audio" in track.get("hide", "") else ""
        hidden = " [HIDDEN]" if "video" in track.get("hide", "") else ""

        click.echo(f"\n  {ttype}{idx} {name}{muted}{hidden}")
        click.echo(f"  {'─' * 66}")

        clips = track.get("clips", [])
        if not clips:
            click.echo(f"  │ (empty)")
        else:
            for item in clips:
                if item.get("type") == "blank":
                    length = item.get("length", "?")
                    click.echo(f"  │ ··· gap ({length}) ···")
                else:
                    ci = item.get("clip_index", "?")
                    caption = item.get("caption", "") or item.get("resource", "?")
                    # Truncate long names
                    if len(caption) > 40:
                        caption = caption[:37] + "..."
                    in_tc = item.get("in", "")
                    out_tc = item.get("out", "")
                    click.echo(f"  │ [{ci}] {caption}  ({in_tc} → {out_tc})")

    click.echo(f"\n{'=' * 70}")


@timeline.command("tracks")
@handle_error
def timeline_tracks():
    """List all tracks."""
    session = get_session()
    result = tl_mod.list_tracks(session)
    output(result, "Tracks:")


@timeline.command("add-track")
@click.option("--type", "track_type", default="video",
              type=click.Choice(["video", "audio"]), help="Track type")
@click.option("--name", default="", help="Track name")
@handle_error
def timeline_add_track(track_type, name):
    """Add a new track to the timeline."""
    session = get_session()
    result = tl_mod.add_track(session, track_type, name)
    output(result, f"Added {track_type} track at index {result['track_index']}")


@timeline.command("remove-track")
@click.argument("track_index", type=int)
@handle_error
def timeline_remove_track(track_index):
    """Remove a track by index."""
    session = get_session()
    result = tl_mod.remove_track(session, track_index)
    output(result, f"Removed track {track_index}")


@timeline.command("add-clip")
@click.argument("resource")
@click.option("--track", "track_index", required=True, type=int, help="Track index")
@click.option("--in", "in_point", default=None, help="In point (timecode)")
@click.option("--out", "out_point", default=None, help="Out point (timecode)")
@click.option("--position", default=None, type=int, help="Insert position (clip index)")
@click.option("--caption", default=None, help="Display name")
@handle_error
def timeline_add_clip(resource, track_index, in_point, out_point, position, caption):
    """Add a media clip to a track."""
    session = get_session()
    result = tl_mod.add_clip(session, resource, track_index,
                             in_point, out_point, position, caption)
    output(result, f"Added clip to track {track_index}")


@timeline.command("remove-clip")
@click.argument("track_index", type=int)
@click.argument("clip_index", type=int)
@click.option("--no-ripple", is_flag=True, help="Leave a gap instead of closing it")
@handle_error
def timeline_remove_clip(track_index, clip_index, no_ripple):
    """Remove a clip from a track."""
    session = get_session()
    result = tl_mod.remove_clip(session, track_index, clip_index, ripple=not no_ripple)
    output(result, f"Removed clip {clip_index} from track {track_index}")


@timeline.command("move-clip")
@click.argument("from_track", type=int)
@click.argument("clip_index", type=int)
@click.option("--to-track", required=True, type=int, help="Destination track")
@click.option("--to-position", default=None, type=int, help="Position on destination track")
@handle_error
def timeline_move_clip(from_track, clip_index, to_track, to_position):
    """Move a clip between tracks or positions."""
    session = get_session()
    result = tl_mod.move_clip(session, from_track, clip_index, to_track, to_position)
    output(result, f"Moved clip from track {from_track} to track {to_track}")


@timeline.command("trim")
@click.argument("track_index", type=int)
@click.argument("clip_index", type=int)
@click.option("--in", "in_point", default=None, help="New in point (timecode)")
@click.option("--out", "out_point", default=None, help="New out point (timecode)")
@handle_error
def timeline_trim(track_index, clip_index, in_point, out_point):
    """Trim a clip's in/out points."""
    session = get_session()
    result = tl_mod.trim_clip(session, track_index, clip_index, in_point, out_point)
    output(result, "Clip trimmed")


@timeline.command("split")
@click.argument("track_index", type=int)
@click.argument("clip_index", type=int)
@click.option("--at", required=True, help="Timecode to split at (within clip source)")
@handle_error
def timeline_split(track_index, clip_index, at):
    """Split a clip into two at the given timecode."""
    session = get_session()
    result = tl_mod.split_clip(session, track_index, clip_index, at)
    output(result, "Clip split")


@timeline.command("clips")
@click.argument("track_index", type=int)
@handle_error
def timeline_clips(track_index):
    """List all clips on a track."""
    session = get_session()
    result = tl_mod.list_clips(session, track_index)
    output(result, f"Clips on track {track_index}:")


@timeline.command("add-blank")
@click.argument("track_index", type=int)
@click.option("--length", required=True, help="Duration (timecode)")
@handle_error
def timeline_add_blank(track_index, length):
    """Add a blank gap to a track."""
    session = get_session()
    result = tl_mod.add_blank(session, track_index, length)
    output(result, f"Added blank to track {track_index}")


@timeline.command("set-name")
@click.argument("track_index", type=int)
@click.argument("name")
@handle_error
def timeline_set_name(track_index, name):
    """Set a track's display name."""
    session = get_session()
    result = tl_mod.set_track_name(session, track_index, name)
    output(result, f"Track {track_index} renamed to '{name}'")


@timeline.command("mute")
@click.argument("track_index", type=int)
@click.option("--unmute", is_flag=True, help="Unmute instead of mute")
@handle_error
def timeline_mute(track_index, unmute):
    """Mute or unmute a track."""
    session = get_session()
    result = tl_mod.set_track_mute(session, track_index, not unmute)
    action = "Unmuted" if unmute else "Muted"
    output(result, f"{action} track {track_index}")


@timeline.command("hide")
@click.argument("track_index", type=int)
@click.option("--unhide", is_flag=True, help="Unhide instead of hide")
@handle_error
def timeline_hide(track_index, unhide):
    """Hide or unhide a video track."""
    session = get_session()
    result = tl_mod.set_track_hidden(session, track_index, not unhide)
    action = "Unhid" if unhide else "Hid"
    output(result, f"{action} track {track_index}")


# ============================================================================
# Filter commands
# ============================================================================

@cli.group("filter")
def filter_group():
    """Filter operations: add, remove, configure effects."""
    pass


@filter_group.command("list-available")
@click.option("--category", default=None, type=click.Choice(["video", "audio"]),
              help="Filter by category")
@handle_error
def filter_list_available(category):
    """List all available filters."""
    result = filt_mod.list_available_filters(category)
    output(result, "Available filters:")


@filter_group.command("info")
@click.argument("filter_name")
@handle_error
def filter_info(filter_name):
    """Show detailed info about a filter and its parameters."""
    result = filt_mod.get_filter_info(filter_name)
    output(result, f"Filter: {filter_name}")


@filter_group.command("add")
@click.argument("filter_name")
@click.option("--track", "track_index", default=None, type=int,
              help="Track index (omit for global)")
@click.option("--clip", "clip_index", default=None, type=int,
              help="Clip index on track (omit for track-level)")
@click.option("--param", "params", multiple=True,
              help="Parameter as name=value (repeatable)")
@handle_error
def filter_add(filter_name, track_index, clip_index, params):
    """Add a filter to a clip, track, or globally."""
    session = get_session()
    param_dict = {}
    for p in params:
        if "=" not in p:
            raise ValueError(f"Invalid param format: {p!r}. Use name=value")
        key, val = p.split("=", 1)
        param_dict[key] = val

    result = filt_mod.add_filter(session, filter_name, track_index, clip_index,
                                 param_dict if param_dict else None)
    output(result, f"Added filter '{filter_name}'")


@filter_group.command("remove")
@click.argument("filter_index", type=int)
@click.option("--track", "track_index", default=None, type=int,
              help="Track index (omit for global)")
@click.option("--clip", "clip_index", default=None, type=int,
              help="Clip index (omit for track-level)")
@handle_error
def filter_remove(filter_index, track_index, clip_index):
    """Remove a filter by index."""
    session = get_session()
    result = filt_mod.remove_filter(session, filter_index, track_index, clip_index)
    output(result, f"Removed filter {filter_index}")


@filter_group.command("set")
@click.argument("filter_index", type=int)
@click.argument("param_name")
@click.argument("param_value")
@click.option("--track", "track_index", default=None, type=int)
@click.option("--clip", "clip_index", default=None, type=int)
@handle_error
def filter_set(filter_index, param_name, param_value, track_index, clip_index):
    """Set a parameter on a filter."""
    session = get_session()
    result = filt_mod.set_filter_param(session, filter_index, param_name, param_value,
                                       track_index, clip_index)
    output(result, f"Set {param_name}={param_value}")


@filter_group.command("list")
@click.option("--track", "track_index", default=None, type=int,
              help="Track index (omit for global)")
@click.option("--clip", "clip_index", default=None, type=int,
              help="Clip index (omit for track-level)")
@handle_error
def filter_list(track_index, clip_index):
    """List active filters on a target."""
    session = get_session()
    result = filt_mod.list_filters(session, track_index, clip_index)
    target = "global"
    if track_index is not None and clip_index is not None:
        target = f"track {track_index}, clip {clip_index}"
    elif track_index is not None:
        target = f"track {track_index}"
    output(result, f"Filters on {target}:")


# ============================================================================
# Media commands
# ============================================================================

@cli.group()
def media():
    """Media operations: probe, list, check files."""
    pass


@media.command("probe")
@click.argument("filepath")
@handle_error
def media_probe(filepath):
    """Analyze a media file's properties."""
    result = media_mod.probe_media(filepath)
    output(result, f"Media info: {os.path.basename(filepath)}")


@media.command("list")
@handle_error
def media_list():
    """List all media clips in the current project."""
    session = get_session()
    result = media_mod.list_media(session)
    output(result, "Media in project:")


@media.command("check")
@handle_error
def media_check():
    """Check all media files for existence."""
    session = get_session()
    result = media_mod.check_media_files(session)
    output(result)


@media.command("thumbnail")
@click.argument("filepath")
@click.option("-o", "--output", "output_path", required=True,
              help="Output image path")
@click.option("--time", "at_time", default="00:00:01.000",
              help="Time position for thumbnail")
@click.option("--width", default=320, type=int, help="Thumbnail width")
@click.option("--height", default=180, type=int, help="Thumbnail height")
@handle_error
def media_thumbnail(filepath, output_path, at_time, width, height):
    """Generate a thumbnail from a video file."""
    result = media_mod.generate_thumbnail(filepath, output_path, at_time, width, height)
    output(result, f"Thumbnail saved to: {output_path}")


# ============================================================================
# Export commands
# ============================================================================

@cli.group()
def export():
    """Export/render operations."""
    pass


@export.command("presets")
@handle_error
def export_presets():
    """List available export presets."""
    result = export_mod.list_presets()
    output(result, "Export presets:")


@export.command("preset-info")
@click.argument("preset_name")
@handle_error
def export_preset_info(preset_name):
    """Show details of an export preset."""
    result = export_mod.get_preset_info(preset_name)
    output(result, f"Preset: {preset_name}")


@export.command("render")
@click.argument("output_path")
@click.option("--preset", default="default", help="Export preset name")
@click.option("--width", default=None, type=int, help="Override output width")
@click.option("--height", default=None, type=int, help="Override output height")
@click.option("--overwrite", is_flag=True, help="Overwrite existing output")
@handle_error
def export_render(output_path, preset, width, height, overwrite):
    """Render the project to a video file."""
    session = get_session()
    result = export_mod.render(session, output_path, preset, width, height, overwrite)
    output(result, f"Render complete: {output_path}")


# ============================================================================
# Transition commands
# ============================================================================

@cli.group("transition")
def transition_group():
    """Transition operations: dissolve, wipe, and other transitions."""
    pass


@transition_group.command("list-available")
@click.option("--category", default=None, type=click.Choice(["video", "audio"]),
              help="Filter by category")
@handle_error
def transition_list_available(category):
    """List all available transition types."""
    result = trans_mod.list_available_transitions(category)
    output(result, "Available transitions:")


@transition_group.command("info")
@click.argument("transition_name")
@handle_error
def transition_info(transition_name):
    """Show detailed info about a transition type."""
    result = trans_mod.get_transition_info(transition_name)
    output(result, f"Transition: {transition_name}")


@transition_group.command("add")
@click.argument("transition_name")
@click.option("--track-a", required=True, type=int, help="Source track (background)")
@click.option("--track-b", required=True, type=int, help="Destination track (foreground)")
@click.option("--in", "in_point", default=None, help="Start timecode")
@click.option("--out", "out_point", default=None, help="End timecode")
@click.option("--param", "params", multiple=True,
              help="Parameter as name=value (repeatable)")
@handle_error
def transition_add(transition_name, track_a, track_b, in_point, out_point, params):
    """Add a transition between two tracks."""
    session = get_session()
    param_dict = {}
    for p in params:
        if "=" not in p:
            raise ValueError(f"Invalid param format: {p!r}. Use name=value")
        key, val = p.split("=", 1)
        param_dict[key] = val

    result = trans_mod.add_transition(session, transition_name, track_a, track_b,
                                      in_point, out_point,
                                      param_dict if param_dict else None)
    output(result, f"Added transition '{transition_name}'")


@transition_group.command("remove")
@click.argument("transition_index", type=int)
@handle_error
def transition_remove(transition_index):
    """Remove a transition by index."""
    session = get_session()
    result = trans_mod.remove_transition(session, transition_index)
    output(result, f"Removed transition {transition_index}")


@transition_group.command("set")
@click.argument("transition_index", type=int)
@click.argument("param_name")
@click.argument("param_value")
@handle_error
def transition_set(transition_index, param_name, param_value):
    """Set a parameter on a transition."""
    session = get_session()
    result = trans_mod.set_transition_param(session, transition_index,
                                            param_name, param_value)
    output(result, f"Set {param_name}={param_value}")


@transition_group.command("list")
@handle_error
def transition_list():
    """List all transitions on the timeline."""
    session = get_session()
    result = trans_mod.list_transitions(session)
    output(result, "Timeline transitions:")


# ============================================================================
# Compositing commands
# ============================================================================

@cli.group("composite")
def composite_group():
    """Compositing: blend modes, PIP, opacity."""
    pass


@composite_group.command("blend-modes")
@handle_error
def composite_blend_modes():
    """List all available blend modes."""
    result = comp_mod.list_blend_modes()
    output(result, "Available blend modes:")


@composite_group.command("set-blend")
@click.argument("track_index", type=int)
@click.argument("blend_mode")
@handle_error
def composite_set_blend(track_index, blend_mode):
    """Set the blend mode for a track."""
    session = get_session()
    result = comp_mod.set_track_blend_mode(session, track_index, blend_mode)
    output(result, f"Set blend mode '{blend_mode}' on track {track_index}")


@composite_group.command("get-blend")
@click.argument("track_index", type=int)
@handle_error
def composite_get_blend(track_index):
    """Get the current blend mode for a track."""
    session = get_session()
    result = comp_mod.get_track_blend_mode(session, track_index)
    output(result, f"Track {track_index} blend mode:")


@composite_group.command("set-opacity")
@click.argument("track_index", type=int)
@click.argument("opacity", type=float)
@handle_error
def composite_set_opacity(track_index, opacity):
    """Set the opacity of a track (0.0-1.0)."""
    session = get_session()
    result = comp_mod.set_track_opacity(session, track_index, opacity)
    output(result, f"Set track {track_index} opacity to {opacity}")


@composite_group.command("pip")
@click.argument("track_index", type=int)
@click.argument("clip_index", type=int)
@click.option("--x", default="0", help="X position (pixels or percentage)")
@click.option("--y", default="0", help="Y position (pixels or percentage)")
@click.option("--width", default="100%", help="Width (pixels or percentage)")
@click.option("--height", default="100%", help="Height (pixels or percentage)")
@click.option("--opacity", default=1.0, type=float, help="Opacity (0.0-1.0)")
@handle_error
def composite_pip(track_index, clip_index, x, y, width, height, opacity):
    """Set picture-in-picture position for a clip."""
    session = get_session()
    result = comp_mod.pip_position(session, track_index, clip_index,
                                    x, y, width, height, opacity)
    output(result, f"PIP set on track {track_index}, clip {clip_index}")


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
        output({"action": "undo", "success": True, "undo_remaining": len(s._undo_stack)},
               "Undone")
    else:
        output({"action": "undo", "success": False}, "Nothing to undo")


@session.command("redo")
@handle_error
def session_redo():
    """Redo the last undone operation."""
    s = get_session()
    if s.redo():
        output({"action": "redo", "success": True, "redo_remaining": len(s._redo_stack)},
               "Redone")
    else:
        output({"action": "redo", "success": False}, "Nothing to redo")


@session.command("save")
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
    result = Session.list_sessions()
    output(result, "Saved sessions:")


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

    from cli_anything.shotcut.utils.repl_skin import ReplSkin
    skin = ReplSkin("shotcut", version="1.0.0")
    skin.print_banner()

    if project_path:
        skin.info(f"Opened: {project_path}")
        print()

    try:
        _run_repl(s, skin)
    except (KeyboardInterrupt, EOFError):
        skin.print_goodbye()

    _repl_mode = False


def _run_repl(s: Session, skin):
    """Run the interactive REPL loop with skin styling."""
    pt_session = skin.create_prompt_session()

    REPL_COMMANDS = {
        "help": "Show this help",
        "status": "Show session status",
        "quit": "Exit the REPL",
        "exit": "Exit the REPL",
        "new [profile]": "Create new project",
        "open <path>": "Open a project file",
        "save [path]": "Save the project",
        "info": "Show project info",
        "xml": "Print raw MLT XML",
        "tracks": "List timeline tracks",
        "show": "Show timeline overview",
        "add-track <video|audio> [name]": "Add a track",
        "add-clip <file> <track> [in] [out]": "Add clip to track",
        "clips <track>": "List clips on a track",
        "remove-clip <track> <clip>": "Remove a clip",
        "trim <track> <clip> [--in tc] [--out tc]": "Trim a clip",
        "split <track> <clip> <at>": "Split a clip",
        "add-filter <name> [--track n] [--clip n] [p=v ...]": "Add a filter",
        "filters [--track n] [--clip n]": "List filters on target",
        "remove-filter <idx> [--track n] [--clip n]": "Remove a filter",
        "set-filter <idx> <param> <value> [--track n] [--clip n]": "Set filter param",
        "filter-info <name>": "Show filter details",
        "list-filters [video|audio]": "List available filters",
        "media": "List media in project",
        "probe <file>": "Probe a media file",
        "check": "Check media files exist",
        "presets": "List export presets",
        "render <output> [--preset name]": "Render project",
        "undo": "Undo last operation",
        "redo": "Redo last undone operation",
    }

    while True:
        # Build prompt context
        proj_name = ""
        if s.project_path:
            proj_name = os.path.basename(s.project_path)
        elif s.is_open:
            proj_name = "(unsaved)"
        modified = s.is_modified if hasattr(s, 'is_modified') else False

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
            if cmd in ("quit", "exit"):
                if s.is_modified:
                    skin.warning("Unsaved changes. Use 'save' first or type 'quit' again.")
                    s._modified = False
                skin.print_goodbye()
                break

            elif cmd == "help":
                skin.help(REPL_COMMANDS)

            elif cmd == "status":
                output(s.status())

            elif cmd == "new":
                profile = args[0] if args else "hd1080p30"
                result = proj_mod.new_project(s, profile)
                output(result, f"Created new {profile} project")

            elif cmd == "open":
                if not args:
                    click.echo("Usage: open <path>")
                    continue
                result = proj_mod.open_project(s, args[0])
                output(result, f"Opened: {args[0]}")

            elif cmd == "save":
                path = args[0] if args else None
                result = proj_mod.save_project(s, path)
                output(result, f"Saved: {result['path']}")

            elif cmd == "info":
                result = proj_mod.project_info(s)
                output(result)

            elif cmd == "xml":
                if not s.is_open:
                    click.echo("No project is open")
                    continue
                from cli_anything.shotcut.utils.mlt_xml import mlt_to_string
                click.echo(mlt_to_string(s.root))

            elif cmd == "tracks":
                result = tl_mod.list_tracks(s)
                output(result)

            elif cmd == "show":
                result = tl_mod.show_timeline(s)
                _print_timeline_visual(result)

            elif cmd == "add-track":
                ttype = args[0] if args else "video"
                name = " ".join(args[1:]) if len(args) > 1 else ""
                result = tl_mod.add_track(s, ttype, name)
                output(result, f"Added {ttype} track")

            elif cmd == "add-clip":
                if len(args) < 2:
                    click.echo("Usage: add-clip <file> <track> [in] [out]")
                    continue
                resource = args[0]
                track = int(args[1])
                in_pt = args[2] if len(args) > 2 else None
                out_pt = args[3] if len(args) > 3 else None
                result = tl_mod.add_clip(s, resource, track, in_pt, out_pt)
                output(result, f"Added clip to track {track}")

            elif cmd == "clips":
                if not args:
                    click.echo("Usage: clips <track>")
                    continue
                result = tl_mod.list_clips(s, int(args[0]))
                output(result)

            elif cmd == "remove-clip":
                if len(args) < 2:
                    click.echo("Usage: remove-clip <track> <clip>")
                    continue
                result = tl_mod.remove_clip(s, int(args[0]), int(args[1]))
                output(result)

            elif cmd == "trim":
                if len(args) < 2:
                    click.echo("Usage: trim <track> <clip> [--in tc] [--out tc]")
                    continue
                track = int(args[0])
                clip = int(args[1])
                in_pt = None
                out_pt = None
                i = 2
                while i < len(args):
                    if args[i] == "--in" and i + 1 < len(args):
                        in_pt = args[i + 1]
                        i += 2
                    elif args[i] == "--out" and i + 1 < len(args):
                        out_pt = args[i + 1]
                        i += 2
                    else:
                        i += 1
                result = tl_mod.trim_clip(s, track, clip, in_pt, out_pt)
                output(result, "Trimmed")

            elif cmd == "split":
                if len(args) < 3:
                    click.echo("Usage: split <track> <clip> <at>")
                    continue
                result = tl_mod.split_clip(s, int(args[0]), int(args[1]), args[2])
                output(result, "Split")

            elif cmd == "add-filter":
                if not args:
                    click.echo("Usage: add-filter <name> [--track n] [--clip n] [p=v ...]")
                    continue
                fname = args[0]
                track_idx = None
                clip_idx = None
                params = {}
                i = 1
                while i < len(args):
                    if args[i] == "--track" and i + 1 < len(args):
                        track_idx = int(args[i + 1])
                        i += 2
                    elif args[i] == "--clip" and i + 1 < len(args):
                        clip_idx = int(args[i + 1])
                        i += 2
                    elif "=" in args[i]:
                        k, v = args[i].split("=", 1)
                        params[k] = v
                        i += 1
                    else:
                        i += 1
                result = filt_mod.add_filter(s, fname, track_idx, clip_idx,
                                             params if params else None)
                output(result, f"Added filter '{fname}'")

            elif cmd == "filters":
                track_idx = None
                clip_idx = None
                i = 0
                while i < len(args):
                    if args[i] == "--track" and i + 1 < len(args):
                        track_idx = int(args[i + 1])
                        i += 2
                    elif args[i] == "--clip" and i + 1 < len(args):
                        clip_idx = int(args[i + 1])
                        i += 2
                    else:
                        i += 1
                result = filt_mod.list_filters(s, track_idx, clip_idx)
                output(result)

            elif cmd == "remove-filter":
                if not args:
                    click.echo("Usage: remove-filter <idx> [--track n] [--clip n]")
                    continue
                fidx = int(args[0])
                track_idx = None
                clip_idx = None
                i = 1
                while i < len(args):
                    if args[i] == "--track" and i + 1 < len(args):
                        track_idx = int(args[i + 1])
                        i += 2
                    elif args[i] == "--clip" and i + 1 < len(args):
                        clip_idx = int(args[i + 1])
                        i += 2
                    else:
                        i += 1
                result = filt_mod.remove_filter(s, fidx, track_idx, clip_idx)
                output(result)

            elif cmd == "set-filter":
                if len(args) < 3:
                    click.echo("Usage: set-filter <idx> <param> <value> [--track n] [--clip n]")
                    continue
                fidx = int(args[0])
                pname = args[1]
                pval = args[2]
                track_idx = None
                clip_idx = None
                i = 3
                while i < len(args):
                    if args[i] == "--track" and i + 1 < len(args):
                        track_idx = int(args[i + 1])
                        i += 2
                    elif args[i] == "--clip" and i + 1 < len(args):
                        clip_idx = int(args[i + 1])
                        i += 2
                    else:
                        i += 1
                result = filt_mod.set_filter_param(s, fidx, pname, pval,
                                                    track_idx, clip_idx)
                output(result)

            elif cmd == "filter-info":
                if not args:
                    click.echo("Usage: filter-info <name>")
                    continue
                result = filt_mod.get_filter_info(args[0])
                output(result)

            elif cmd == "list-filters":
                cat = args[0] if args else None
                result = filt_mod.list_available_filters(cat)
                output(result)

            elif cmd == "media":
                result = media_mod.list_media(s)
                output(result)

            elif cmd == "probe":
                if not args:
                    click.echo("Usage: probe <file>")
                    continue
                result = media_mod.probe_media(args[0])
                output(result)

            elif cmd == "check":
                result = media_mod.check_media_files(s)
                output(result)

            elif cmd == "presets":
                result = export_mod.list_presets()
                output(result)

            elif cmd == "render":
                if not args:
                    click.echo("Usage: render <output> [--preset name]")
                    continue
                out_path = args[0]
                preset = "default"
                i = 1
                while i < len(args):
                    if args[i] == "--preset" and i + 1 < len(args):
                        preset = args[i + 1]
                        i += 2
                    else:
                        i += 1
                result = export_mod.render(s, out_path, preset)
                output(result)

            elif cmd == "undo":
                if s.undo():
                    click.echo("Undone")
                else:
                    click.echo("Nothing to undo")

            elif cmd == "redo":
                if s.redo():
                    click.echo("Redone")
                else:
                    click.echo("Nothing to redo")

            else:
                skin.warning(f"Unknown command: {cmd}. Type 'help' for available commands.")

        except Exception as e:
            skin.error(str(e))


# ============================================================================
# Entry point
# ============================================================================

if __name__ == "__main__":
    cli()
