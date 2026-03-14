#!/usr/bin/env python3
"""Kdenlive CLI — A stateful command-line interface for video editing.

This CLI provides full video project management capabilities using a JSON
project format, with MLT XML generation for Kdenlive/melt.

Usage:
    # One-shot commands
    python3 -m cli.kdenlive_cli project new --name "MyVideo"
    python3 -m cli.kdenlive_cli bin import /path/to/video.mp4
    python3 -m cli.kdenlive_cli timeline add-track --type video

    # Interactive REPL
    python3 -m cli.kdenlive_cli repl
"""

import sys
import os
import json
import shlex
import click
from typing import Optional

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cli_anything.kdenlive.core.session import Session
from cli_anything.kdenlive.core import project as proj_mod
from cli_anything.kdenlive.core import bin as bin_mod
from cli_anything.kdenlive.core import timeline as tl_mod
from cli_anything.kdenlive.core import filters as filt_mod
from cli_anything.kdenlive.core import transitions as trans_mod
from cli_anything.kdenlive.core import guides as guide_mod
from cli_anything.kdenlive.core import export as export_mod
from cli_anything.kdenlive.utils.mlt_xml import seconds_to_timecode, timecode_to_seconds
from cli_anything.kdenlive.utils.repl_skin import ReplSkin

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


def parse_time(value: str) -> float:
    """Parse a time value that can be seconds or HH:MM:SS.mmm."""
    return timecode_to_seconds(value)


# ── Main CLI Group ──────────────────────────────────────────────
@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, help="Output as JSON")
@click.option("--project", "project_path", type=str, default=None,
              help="Path to .kdenlive-cli.json project file")
@click.pass_context
def cli(ctx, use_json, project_path):
    """Kdenlive CLI — Stateful video editing from the command line.

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


# ── Project Commands ────────────────────────────────────────────
@cli.group()
def project():
    """Project management commands."""
    pass


@project.command("new")
@click.option("--name", "-n", default="untitled", help="Project name")
@click.option("--profile", "-p", type=str, default=None, help="Video profile")
@click.option("--width", type=int, default=1920)
@click.option("--height", type=int, default=1080)
@click.option("--fps-num", type=int, default=30)
@click.option("--fps-den", type=int, default=1)
@click.option("--output", "-o", type=str, default=None, help="Save path")
@handle_error
def project_new(name, profile, width, height, fps_num, fps_den, output):
    """Create a new project."""
    proj = proj_mod.create_project(
        name=name, profile=profile, width=width, height=height,
        fps_num=fps_num, fps_den=fps_den,
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
    output(info, f"Opened: {path}")


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


@project.command("profiles")
@handle_error
def project_profiles():
    """List available video profiles."""
    profiles = proj_mod.list_profiles()
    output(profiles, "Available profiles:")


@project.command("json")
@handle_error
def project_json():
    """Print raw project JSON."""
    sess = get_session()
    click.echo(json.dumps(sess.get_project(), indent=2, default=str))


# ── Bin Commands ────────────────────────────────────────────────
@cli.group("bin")
def bin_group():
    """Media bin management commands."""
    pass


@bin_group.command("import")
@click.argument("source")
@click.option("--name", "-n", default=None, help="Clip name")
@click.option("--duration", "-d", type=float, default=0.0, help="Duration in seconds")
@click.option("--type", "clip_type", type=click.Choice(["video", "audio", "image", "color", "title"]),
              default="video")
@handle_error
def bin_import(source, name, duration, clip_type):
    """Import a clip into the media bin."""
    sess = get_session()
    sess.snapshot("Import clip")
    clip = bin_mod.import_clip(sess.get_project(), source, name=name,
                               duration=duration, clip_type=clip_type)
    output(clip, f"Imported: {clip['name']}")


@bin_group.command("remove")
@click.argument("clip_id")
@handle_error
def bin_remove(clip_id):
    """Remove a clip from the bin."""
    sess = get_session()
    sess.snapshot(f"Remove clip {clip_id}")
    removed = bin_mod.remove_clip(sess.get_project(), clip_id)
    output(removed, f"Removed clip: {removed['name']}")


@bin_group.command("list")
@handle_error
def bin_list():
    """List all clips in the bin."""
    sess = get_session()
    clips = bin_mod.list_clips(sess.get_project())
    output(clips, "Bin clips:")


@bin_group.command("get")
@click.argument("clip_id")
@handle_error
def bin_get(clip_id):
    """Get detailed clip info."""
    sess = get_session()
    clip = bin_mod.get_clip(sess.get_project(), clip_id)
    output(clip)


# ── Timeline Commands ───────────────────────────────────────────
@cli.group()
def timeline():
    """Timeline management commands."""
    pass


@timeline.command("add-track")
@click.option("--name", "-n", default=None, help="Track name")
@click.option("--type", "track_type", type=click.Choice(["video", "audio"]), default="video")
@click.option("--mute", is_flag=True)
@click.option("--hide", is_flag=True)
@click.option("--locked", is_flag=True)
@handle_error
def timeline_add_track(name, track_type, mute, hide, locked):
    """Add a track to the timeline."""
    sess = get_session()
    sess.snapshot("Add track")
    track = tl_mod.add_track(sess.get_project(), name=name, track_type=track_type,
                              mute=mute, hide=hide, locked=locked)
    output(track, f"Added track: {track['name']}")


@timeline.command("remove-track")
@click.argument("track_id", type=int)
@handle_error
def timeline_remove_track(track_id):
    """Remove a track."""
    sess = get_session()
    sess.snapshot(f"Remove track {track_id}")
    removed = tl_mod.remove_track(sess.get_project(), track_id)
    output(removed, f"Removed track: {removed['name']}")


@timeline.command("add-clip")
@click.argument("track_id", type=int)
@click.argument("clip_id")
@click.option("--position", "-p", type=float, default=0.0, help="Position in seconds")
@click.option("--in", "in_point", type=float, default=0.0, help="In point in seconds")
@click.option("--out", "out_point", type=float, default=None, help="Out point in seconds")
@handle_error
def timeline_add_clip(track_id, clip_id, position, in_point, out_point):
    """Add a clip to a track."""
    sess = get_session()
    sess.snapshot("Add clip to track")
    entry = tl_mod.add_clip_to_track(sess.get_project(), track_id, clip_id,
                                      position=position, in_point=in_point,
                                      out_point=out_point)
    output(entry, "Added clip to track")


@timeline.command("remove-clip")
@click.argument("track_id", type=int)
@click.argument("clip_index", type=int)
@handle_error
def timeline_remove_clip(track_id, clip_index):
    """Remove a clip from a track."""
    sess = get_session()
    sess.snapshot("Remove clip from track")
    removed = tl_mod.remove_clip_from_track(sess.get_project(), track_id, clip_index)
    output(removed, "Removed clip from track")


@timeline.command("trim")
@click.argument("track_id", type=int)
@click.argument("clip_index", type=int)
@click.option("--in", "new_in", type=float, default=None, help="New in point")
@click.option("--out", "new_out", type=float, default=None, help="New out point")
@handle_error
def timeline_trim(track_id, clip_index, new_in, new_out):
    """Trim a clip's in/out points."""
    sess = get_session()
    sess.snapshot("Trim clip")
    result = tl_mod.trim_clip(sess.get_project(), track_id, clip_index,
                               new_in=new_in, new_out=new_out)
    output(result, "Trimmed clip")


@timeline.command("split")
@click.argument("track_id", type=int)
@click.argument("clip_index", type=int)
@click.argument("split_at", type=float)
@handle_error
def timeline_split(track_id, clip_index, split_at):
    """Split a clip at a time offset."""
    sess = get_session()
    sess.snapshot("Split clip")
    parts = tl_mod.split_clip(sess.get_project(), track_id, clip_index, split_at)
    output(parts, "Split clip into two parts")


@timeline.command("move")
@click.argument("track_id", type=int)
@click.argument("clip_index", type=int)
@click.argument("new_position", type=float)
@handle_error
def timeline_move(track_id, clip_index, new_position):
    """Move a clip to a new position."""
    sess = get_session()
    sess.snapshot("Move clip")
    result = tl_mod.move_clip(sess.get_project(), track_id, clip_index, new_position)
    output(result, f"Moved clip to {new_position}")


@timeline.command("list")
@handle_error
def timeline_list():
    """List all tracks."""
    sess = get_session()
    tracks = tl_mod.list_tracks(sess.get_project())
    output(tracks, "Tracks:")


# ── Filter Commands ─────────────────────────────────────────────
@cli.group("filter")
def filter_group():
    """Filter/effect management commands."""
    pass


@filter_group.command("add")
@click.argument("track_id", type=int)
@click.argument("clip_index", type=int)
@click.argument("filter_name")
@click.option("--param", "-p", multiple=True, help="Parameter: key=value")
@handle_error
def filter_add(track_id, clip_index, filter_name, param):
    """Add a filter to a clip."""
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
    sess.snapshot(f"Add filter {filter_name}")
    result = filt_mod.add_filter(sess.get_project(), track_id, clip_index,
                                  filter_name, params=params if params else None)
    output(result, f"Added filter: {filter_name}")


@filter_group.command("remove")
@click.argument("track_id", type=int)
@click.argument("clip_index", type=int)
@click.argument("filter_index", type=int)
@handle_error
def filter_remove(track_id, clip_index, filter_index):
    """Remove a filter from a clip."""
    sess = get_session()
    sess.snapshot("Remove filter")
    removed = filt_mod.remove_filter(sess.get_project(), track_id, clip_index, filter_index)
    output(removed, f"Removed filter: {removed['name']}")


@filter_group.command("set")
@click.argument("track_id", type=int)
@click.argument("clip_index", type=int)
@click.argument("filter_index", type=int)
@click.argument("param_name")
@click.argument("value")
@handle_error
def filter_set(track_id, clip_index, filter_index, param_name, value):
    """Set a filter parameter."""
    try:
        value = float(value) if "." in str(value) else int(value)
    except ValueError:
        pass
    sess = get_session()
    sess.snapshot("Set filter param")
    result = filt_mod.set_filter_param(sess.get_project(), track_id, clip_index,
                                        filter_index, param_name, value)
    output(result, f"Set {param_name} = {value}")


@filter_group.command("list")
@click.argument("track_id", type=int)
@click.argument("clip_index", type=int)
@handle_error
def filter_list(track_id, clip_index):
    """List filters on a clip."""
    sess = get_session()
    filters = filt_mod.list_filters(sess.get_project(), track_id, clip_index)
    output(filters, "Filters:")


@filter_group.command("available")
@click.option("--category", "-c", default=None, help="Filter by category")
@handle_error
def filter_available(category):
    """List all available filters."""
    filters = filt_mod.list_available(category)
    output(filters, "Available filters:")


# ── Transition Commands ─────────────────────────────────────────
@cli.group()
def transition():
    """Transition management commands."""
    pass


@transition.command("add")
@click.argument("transition_type")
@click.argument("track_a", type=int)
@click.argument("track_b", type=int)
@click.option("--position", "-p", type=float, default=0.0)
@click.option("--duration", "-d", type=float, default=1.0)
@click.option("--param", multiple=True, help="Parameter: key=value")
@handle_error
def transition_add(transition_type, track_a, track_b, position, duration, param):
    """Add a transition between tracks."""
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
    sess.snapshot(f"Add transition {transition_type}")
    result = trans_mod.add_transition(sess.get_project(), transition_type,
                                      track_a, track_b, position=position,
                                      duration=duration, params=params if params else None)
    output(result, f"Added transition: {transition_type}")


@transition.command("remove")
@click.argument("transition_id", type=int)
@handle_error
def transition_remove(transition_id):
    """Remove a transition."""
    sess = get_session()
    sess.snapshot(f"Remove transition {transition_id}")
    removed = trans_mod.remove_transition(sess.get_project(), transition_id)
    output(removed, f"Removed transition {transition_id}")


@transition.command("set")
@click.argument("transition_id", type=int)
@click.argument("param_name")
@click.argument("value")
@handle_error
def transition_set(transition_id, param_name, value):
    """Set a transition parameter."""
    try:
        value = float(value) if "." in str(value) else int(value)
    except ValueError:
        pass
    sess = get_session()
    sess.snapshot("Set transition param")
    result = trans_mod.set_transition(sess.get_project(), transition_id, param_name, value)
    output(result, f"Set {param_name} = {value}")


@transition.command("list")
@handle_error
def transition_list():
    """List all transitions."""
    sess = get_session()
    transitions = trans_mod.list_transitions(sess.get_project())
    output(transitions, "Transitions:")


# ── Guide Commands ──────────────────────────────────────────────
@cli.group()
def guide():
    """Guide/marker management commands."""
    pass


@guide.command("add")
@click.argument("position", type=float)
@click.option("--label", "-l", default="", help="Guide label")
@click.option("--type", "guide_type", type=click.Choice(["default", "chapter", "segment"]),
              default="default")
@click.option("--comment", "-c", default="", help="Comment")
@handle_error
def guide_add(position, label, guide_type, comment):
    """Add a guide at a position (seconds)."""
    sess = get_session()
    sess.snapshot("Add guide")
    g = guide_mod.add_guide(sess.get_project(), position, label=label,
                             guide_type=guide_type, comment=comment)
    output(g, f"Added guide at {position}s")


@guide.command("remove")
@click.argument("guide_id", type=int)
@handle_error
def guide_remove(guide_id):
    """Remove a guide."""
    sess = get_session()
    sess.snapshot(f"Remove guide {guide_id}")
    removed = guide_mod.remove_guide(sess.get_project(), guide_id)
    output(removed, f"Removed guide {guide_id}")


@guide.command("list")
@handle_error
def guide_list():
    """List all guides."""
    sess = get_session()
    guides = guide_mod.list_guides(sess.get_project())
    output(guides, "Guides:")


# ── Export Commands ─────────────────────────────────────────────
@cli.group()
def export():
    """Export and render commands."""
    pass


@export.command("xml")
@click.option("--output", "-o", type=str, default=None, help="Output file path")
@handle_error
def export_xml(output):
    """Generate Kdenlive/MLT XML."""
    sess = get_session()
    xml = export_mod.generate_kdenlive_xml(sess.get_project())
    if output:
        with open(output, "w") as f:
            f.write(xml)
        globals()["output"]({"path": output, "size": len(xml)}, f"XML written to: {output}")
    else:
        click.echo(xml)


@export.command("presets")
@handle_error
def export_presets():
    """List available render presets."""
    presets = export_mod.list_render_presets()
    output(presets, "Render presets:")


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
    global _repl_mode
    _repl_mode = True

    if project_path:
        sess = get_session()
        proj = proj_mod.open_project(project_path)
        sess.set_project(proj, project_path)

    skin = ReplSkin("kdenlive", version="1.0.0")
    skin.print_banner()

    pt_session = skin.create_prompt_session()

    commands_dict = {
        "project new|open|save|info|profiles|json": "Project management",
        "bin import|remove|list|get": "Media bin management",
        "timeline add-track|remove-track|add-clip|remove-clip|trim|split|move|list": "Timeline management",
        "filter add|remove|set|list|available": "Filter/effect management",
        "transition add|remove|set|list": "Transition management",
        "guide add|remove|list": "Guide/marker management",
        "export xml|presets": "Export and render",
        "session status|undo|redo|history": "Session management",
        "help": "Show this help",
        "quit": "Exit REPL",
    }

    while True:
        try:
            sess = get_session()
            project_name = ""
            modified = False
            if sess.has_project():
                proj = sess.get_project()
                project_name = proj.get("name", "")
                modified = sess.is_modified() if hasattr(sess, 'is_modified') else False

            line = skin.get_input(pt_session, project_name=project_name, modified=modified)
            if not line:
                continue
            if line.lower() in ("quit", "exit", "q"):
                skin.print_goodbye()
                break
            if line.lower() == "help":
                skin.help(commands_dict)
                continue

            args = shlex.split(line)
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


# ── Entry Point ─────────────────────────────────────────────────
def main():
    cli()


if __name__ == "__main__":
    main()
