#!/usr/bin/env python3
"""Openscreen CLI — Screen recording editor for AI agents and power users.

A stateful CLI for editing screen recordings: add zoom, speed ramps,
trim, crop, annotations, backgrounds, and export polished demo videos.
Built on the Openscreen JSON project format with ffmpeg as the rendering backend.
"""

import functools
import json
import os
import sys
from typing import Optional

import click

from .core.session import Session
from .core import project as proj_mod
from .core import timeline as tl_mod
from .core import export as export_mod
from .core import media as media_mod
from .core import preview as preview_mod

# ── Global state ──────────────────────────────────────────────────────────

_session: Optional[Session] = None
_json_output = False
_repl_mode = False
_auto_save = False
_dry_run = False


# ── Output helpers ────────────────────────────────────────────────────────

def output(data, message: str = ""):
    """Print output in JSON or human-readable format."""
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


def _print_dict(d: dict, indent: int = 2):
    for k, v in d.items():
        if isinstance(v, dict):
            click.echo(f"{' ' * indent}{k}:")
            _print_dict(v, indent + 2)
        elif isinstance(v, list):
            click.echo(f"{' ' * indent}{k}: [{len(v)} items]")
        else:
            click.echo(f"{' ' * indent}{k}: {v}")


def _print_list(items: list):
    if not items:
        click.echo("  (empty)")
        return
    for i, item in enumerate(items):
        if isinstance(item, dict):
            click.echo(f"  [{i}]")
            _print_dict(item, indent=4)
        else:
            click.echo(f"  [{i}] {item}")


# ── Error handler ─────────────────────────────────────────────────────────

def handle_error(func):
    """Decorator to catch and format errors."""
    @functools.wraps(func)
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
        except (ValueError, IndexError) as e:
            if _json_output:
                click.echo(json.dumps({"error": str(e), "type": "validation"}))
            else:
                click.echo(f"Error: {e}", err=True)
            if not _repl_mode:
                sys.exit(1)
        except RuntimeError as e:
            if _json_output:
                click.echo(json.dumps({"error": str(e), "type": "runtime"}))
            else:
                click.echo(f"Error: {e}", err=True)
            if not _repl_mode:
                sys.exit(1)
        except Exception as e:
            if _json_output:
                click.echo(json.dumps({"error": str(e), "type": "unexpected"}))
            else:
                click.echo(f"Unexpected error: {e}", err=True)
            if not _repl_mode:
                sys.exit(1)
    return wrapper


# ── Main group ────────────────────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.version_option("1.0.0", prog_name="Openscreen CLI")
@click.option("--json", "json_mode", is_flag=True, help="Output in JSON format")
@click.option("--session", "session_id", default=None, help="Session ID to resume")
@click.option("--project", "project_path", default=None, help="Open project on start")
@click.option("-s", "--save", "auto_save", is_flag=True, help="Auto-save after mutations")
@click.option("--dry-run", "dry_run", is_flag=True, default=False,
              help="Run command without saving changes to disk")
@click.pass_context
def cli(ctx, json_mode, session_id, project_path, auto_save, dry_run):
    """Openscreen CLI — Screen recording editor.

    Edit screen recordings via command line: zoom, speed, trim, crop,
    annotate, and export polished demo videos.

    Run without a subcommand to enter REPL mode.
    """
    global _session, _json_output, _auto_save, _dry_run
    _json_output = json_mode
    _auto_save = auto_save
    _dry_run = dry_run
    _session = Session(session_id)

    if project_path:
        _session.open_project(project_path)

    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


# ── Project commands ──────────────────────────────────────────────────────

@cli.group()
def project():
    """Project management — new, open, save, info, settings."""
    pass


@project.command("new")
@click.option("-v", "--video", default=None, help="Source video path")
@click.option("-o", "--output", default=None, help="Save project to this path")
@handle_error
def project_new(video, output):
    """Create a new project."""
    result = proj_mod.new_project(_session, video)
    if output:
        proj_mod.save_project(_session, output)
        result["saved_to"] = output
    output_fn = globals()["output"]
    output_fn(result, "Project created")


@project.command("open")
@click.argument("path")
@handle_error
def project_open(path):
    """Open an existing .openscreen project."""
    result = proj_mod.open_project(_session, path)
    output(result, f"Opened: {path}")


@project.command("save")
@click.option("-o", "--output", "output_path", default=None, help="Save to path (default: current)")
@handle_error
def project_save(output_path=None):
    """Save the current project."""
    result = proj_mod.save_project(_session, output_path)
    output(result)


@project.command("info")
@handle_error
def project_info():
    """Show project information."""
    result = proj_mod.info(_session)
    output(result)


@project.command("set-video")
@click.argument("path")
@handle_error
def project_set_video(path):
    """Set the source video for the project."""
    result = proj_mod.set_video(_session, path)
    output(result, f"Video set: {path}")


@project.command("set")
@click.argument("key")
@click.argument("value")
@handle_error
def project_set(key, value):
    """Set a project setting (e.g., aspectRatio, wallpaper, padding)."""
    # Auto-convert numeric and boolean values
    if value.lower() in ("true", "false"):
        value = value.lower() == "true"
    else:
        try:
            value = int(value)
        except ValueError:
            try:
                value = float(value)
            except ValueError:
                pass
    result = proj_mod.set_setting(_session, key, value)
    output(result)
    if _auto_save and not _dry_run and _session.project_path:
        _session.save_project()


# ── Zoom commands ─────────────────────────────────────────────────────────

@cli.group()
def zoom():
    """Zoom regions — add, remove, list zoom effects on timeline."""
    pass


@zoom.command("list")
@handle_error
def zoom_list():
    """List all zoom regions."""
    result = tl_mod.list_zoom_regions(_session)
    output(result)


@zoom.command("add")
@click.option("--start", required=True, type=int, help="Start time in milliseconds")
@click.option("--end", required=True, type=int, help="End time in milliseconds")
@click.option("--depth", default=3, type=int, help="Zoom depth 1-6 (default: 3)")
@click.option("--focus-x", default=0.5, type=float, help="Focus X (0-1)")
@click.option("--focus-y", default=0.5, type=float, help="Focus Y (0-1)")
@click.option("--focus-mode", default="manual", help="Focus mode: manual or auto")
@handle_error
def zoom_add(start, end, depth, focus_x, focus_y, focus_mode):
    """Add a zoom region."""
    result = tl_mod.add_zoom_region(
        _session, start, end, depth, focus_x, focus_y, focus_mode
    )
    output(result, "Zoom region added")
    if _auto_save and not _dry_run and _session.project_path:
        _session.save_project()


@zoom.command("remove")
@click.argument("region_id")
@handle_error
def zoom_remove(region_id):
    """Remove a zoom region by ID."""
    result = tl_mod.remove_zoom_region(_session, region_id)
    output(result)
    if _auto_save and not _dry_run and _session.project_path:
        _session.save_project()


# ── Speed commands ────────────────────────────────────────────────────────

@cli.group()
def speed():
    """Speed regions — add, remove, list speed changes."""
    pass


@speed.command("list")
@handle_error
def speed_list():
    """List all speed regions."""
    result = tl_mod.list_speed_regions(_session)
    output(result)


@speed.command("add")
@click.option("--start", required=True, type=int, help="Start time in ms")
@click.option("--end", required=True, type=int, help="End time in ms")
@click.option("--speed", "spd", default=1.5, type=float, help="Speed multiplier")
@handle_error
def speed_add(start, end, spd):
    """Add a speed region."""
    result = tl_mod.add_speed_region(_session, start, end, spd)
    output(result, "Speed region added")
    if _auto_save and not _dry_run and _session.project_path:
        _session.save_project()


@speed.command("remove")
@click.argument("region_id")
@handle_error
def speed_remove(region_id):
    """Remove a speed region by ID."""
    result = tl_mod.remove_speed_region(_session, region_id)
    output(result)
    if _auto_save and not _dry_run and _session.project_path:
        _session.save_project()


# ── Trim commands ─────────────────────────────────────────────────────────

@cli.group()
def trim():
    """Trim regions — cut out sections of the recording."""
    pass


@trim.command("list")
@handle_error
def trim_list():
    """List all trim regions."""
    result = tl_mod.list_trim_regions(_session)
    output(result)


@trim.command("add")
@click.option("--start", required=True, type=int, help="Start time in ms")
@click.option("--end", required=True, type=int, help="End time in ms")
@handle_error
def trim_add(start, end):
    """Add a trim region (cuts this section out)."""
    result = tl_mod.add_trim_region(_session, start, end)
    output(result, "Trim region added")
    if _auto_save and not _dry_run and _session.project_path:
        _session.save_project()


@trim.command("remove")
@click.argument("region_id")
@handle_error
def trim_remove(region_id):
    """Remove a trim region by ID."""
    result = tl_mod.remove_trim_region(_session, region_id)
    output(result)


# ── Crop commands ─────────────────────────────────────────────────────────

@cli.group()
def crop():
    """Crop — set the visible area of the recording."""
    pass


@crop.command("get")
@handle_error
def crop_get():
    """Show current crop region."""
    result = tl_mod.get_crop(_session)
    output(result)


@crop.command("set")
@click.option("--x", default=0.0, type=float, help="Left edge (0-1)")
@click.option("--y", default=0.0, type=float, help="Top edge (0-1)")
@click.option("--width", "w", default=1.0, type=float, help="Width (0-1)")
@click.option("--height", "h", default=1.0, type=float, help="Height (0-1)")
@handle_error
def crop_set(x, y, w, h):
    """Set crop region (normalized 0-1 coordinates)."""
    result = tl_mod.set_crop(_session, x, y, w, h)
    output(result, "Crop updated")
    if _auto_save and not _dry_run and _session.project_path:
        _session.save_project()


# ── Annotation commands ───────────────────────────────────────────────────

@cli.group()
def annotation():
    """Annotations — add text overlays to the recording."""
    pass


@annotation.command("list")
@handle_error
def annotation_list():
    """List all annotations."""
    result = tl_mod.list_annotations(_session)
    output(result)


@annotation.command("add-text")
@click.option("--start", required=True, type=int, help="Start time in ms")
@click.option("--end", required=True, type=int, help="End time in ms")
@click.option("--text", required=True, help="Text content")
@click.option("--x", default=0.5, type=float, help="X position (0-1)")
@click.option("--y", default=0.5, type=float, help="Y position (0-1)")
@click.option("--font-size", default=32, type=int, help="Font size")
@click.option("--color", default="#ffffff", help="Text color (hex)")
@click.option("--bg-color", default="#000000", help="Background color (hex)")
@handle_error
def annotation_add_text(start, end, text, x, y, font_size, color, bg_color):
    """Add a text annotation."""
    result = tl_mod.add_text_annotation(
        _session, start, end, text, x, y, font_size, color, bg_color
    )
    output(result, "Annotation added")
    if _auto_save and not _dry_run and _session.project_path:
        _session.save_project()


@annotation.command("remove")
@click.argument("region_id")
@handle_error
def annotation_remove(region_id):
    """Remove an annotation by ID."""
    result = tl_mod.remove_annotation(_session, region_id)
    output(result)


# ── Media commands ────────────────────────────────────────────────────────

@cli.group()
def media():
    """Media — probe and inspect video files."""
    pass


@media.command("probe")
@click.argument("path")
@handle_error
def media_probe(path):
    """Probe a video file and show metadata."""
    result = media_mod.probe(path)
    output(result)


@media.command("check")
@click.argument("path")
@handle_error
def media_check(path):
    """Check if a video file is valid."""
    result = media_mod.check_video(path)
    output(result)


@media.command("thumbnail")
@click.argument("input_path")
@click.argument("output_path")
@click.option("-t", "--time", "time_s", default=0.0, help="Time in seconds")
@handle_error
def media_thumbnail(input_path, output_path, time_s):
    """Extract a thumbnail frame from a video."""
    result = media_mod.extract_thumbnail(input_path, output_path, time_s)
    output(result)


# ── Export commands ────────────────────────────────────────────────────────

@cli.group()
def export():
    """Export — render the final video."""
    pass


@cli.group()
def preview():
    """Preview bundle capture and inspection."""
    pass


@export.command("presets")
@handle_error
def export_presets():
    """List available export presets."""
    result = export_mod.list_presets()
    output(result)


@export.command("render")
@click.argument("output_path")
@handle_error
def export_render(output_path):
    """Render the project to a video file."""
    def on_progress(stage, msg):
        if not _json_output:
            click.echo(f"  [{stage}] {msg}")

    result = export_mod.render(_session, output_path, on_progress)
    output(result, f"Exported to: {output_path}")


@preview.command("recipes")
@handle_error
def preview_recipes():
    """List available preview recipes."""
    output(preview_mod.list_recipes(), "Preview recipes")


@preview.command("capture")
@click.option("--recipe", default="quick", help="Preview recipe name")
@click.option("--force", is_flag=True, help="Bypass preview cache")
@click.option("--root-dir", default=None, help="Override preview bundle root directory")
@handle_error
def preview_capture(recipe, force, root_dir):
    """Capture a preview bundle for the active project."""
    result = preview_mod.capture(
        _session,
        recipe=recipe,
        force=force,
        root_dir=root_dir,
        command=f"cli-anything-openscreen --project {_session.project_path or ''} preview capture --recipe {recipe}".strip(),
    )
    bundle_dir = result.get("_bundle_dir", result.get("bundle_dir", ""))
    status = "Reused preview bundle" if result.get("cached") else "Created preview bundle"
    output(result, f"{status}: {bundle_dir}")


@preview.command("latest")
@click.option("--recipe", default=None, help="Filter by recipe name")
@click.option("--root-dir", default=None, help="Override preview bundle root directory")
@handle_error
def preview_latest(recipe, root_dir):
    """Show the latest preview bundle manifest."""
    result = preview_mod.latest(project_path=_session.project_path, recipe=recipe, root_dir=root_dir)
    output(result, f"Latest preview bundle: {result.get('_bundle_dir', '')}")


# ── Session commands ──────────────────────────────────────────────────────

@cli.group("session")
def session_group():
    """Session — undo, redo, status, save/list sessions."""
    pass


@session_group.command("status")
@handle_error
def session_status():
    """Show current session status."""
    result = _session.status()
    output(result)


@session_group.command("undo")
@handle_error
def session_undo():
    """Undo the last operation."""
    if _session.undo():
        output({"status": "undone", "undo_remaining": len(_session._undo_stack)})
    else:
        output({"status": "nothing_to_undo"})


@session_group.command("redo")
@handle_error
def session_redo():
    """Redo the last undone operation."""
    if _session.redo():
        output({"status": "redone", "redo_remaining": len(_session._redo_stack)})
    else:
        output({"status": "nothing_to_redo"})


@session_group.command("save")
@handle_error
def session_save_state():
    """Save session state to disk."""
    path = _session.save_session_state()
    output({"status": "saved", "path": path})


@session_group.command("list")
@handle_error
def session_list():
    """List all saved sessions."""
    result = Session.list_sessions()
    output(result)


# ── REPL command ──────────────────────────────────────────────────────────

@cli.command()
def repl():
    """Start interactive REPL mode."""
    global _repl_mode
    _repl_mode = True

    from .utils.repl_skin import ReplSkin
    skin = ReplSkin("openscreen", version="1.0.0")
    skin.print_banner()

    pt_session = skin.create_prompt_session()

    COMMANDS = {
        "help":           "Show this help",
        "quit":           "Exit REPL",
        "status":         "Show session status",
        "undo":           "Undo last operation",
        "redo":           "Redo last operation",
        "new [video]":    "Create new project (optional video path)",
        "open <path>":    "Open .openscreen project file",
        "save [path]":    "Save project",
        "info":           "Show project info",
        "set-video <p>":  "Set source video",
        "set <k> <v>":    "Set editor setting",
        "zoom list":      "List zoom regions",
        "zoom add":       "Add zoom (prompts for params)",
        "zoom rm <id>":   "Remove zoom region",
        "speed list":     "List speed regions",
        "speed add":      "Add speed region (prompts)",
        "speed rm <id>":  "Remove speed region",
        "trim list":      "List trim regions",
        "trim add":       "Add trim region (prompts)",
        "trim rm <id>":   "Remove trim region",
        "crop":           "Show crop region",
        "crop set":       "Set crop (prompts)",
        "probe <path>":   "Probe a video file",
        "export <path>":  "Render and export video",
        "preview [recipe]": "Capture a preview bundle",
        "preview-latest [recipe]": "Show the latest preview bundle",
    }

    while True:
        try:
            proj_name = ""
            modified = False
            if _session.is_open:
                proj_name = os.path.basename(_session.project_path or "untitled")
                modified = _session.is_modified

            line = skin.get_input(pt_session, project_name=proj_name, modified=modified)
            if not line:
                continue

            parts = line.split()
            cmd = parts[0].lower()

            if cmd in ("quit", "exit", "q"):
                if _session.is_modified:
                    skin.warning("Unsaved changes! Use 'save' first or 'quit' again.")
                    _session._modified = False  # Allow next quit
                    continue
                break

            elif cmd == "help":
                skin.help(COMMANDS)

            elif cmd == "status":
                result = _session.status()
                output(result)

            elif cmd == "undo":
                if _session.undo():
                    skin.success("Undone")
                else:
                    skin.warning("Nothing to undo")

            elif cmd == "redo":
                if _session.redo():
                    skin.success("Redone")
                else:
                    skin.warning("Nothing to redo")

            elif cmd == "new":
                video = parts[1] if len(parts) > 1 else None
                proj_mod.new_project(_session, video)
                skin.success("New project created")

            elif cmd == "open":
                if len(parts) < 2:
                    skin.error("Usage: open <path>")
                    continue
                proj_mod.open_project(_session, parts[1])
                skin.success(f"Opened: {parts[1]}")

            elif cmd == "save":
                path = parts[1] if len(parts) > 1 else None
                result = proj_mod.save_project(_session, path)
                skin.success(f"Saved: {result['path']}")

            elif cmd == "info":
                result = proj_mod.info(_session)
                output(result)

            elif cmd == "set-video":
                if len(parts) < 2:
                    skin.error("Usage: set-video <path>")
                    continue
                proj_mod.set_video(_session, parts[1])
                skin.success(f"Video set: {parts[1]}")

            elif cmd == "set":
                if len(parts) < 3:
                    skin.error("Usage: set <key> <value>")
                    continue
                val = parts[2]
                if val.lower() in ("true", "false"):
                    val = val.lower() == "true"
                else:
                    try:
                        val = int(val)
                    except ValueError:
                        try:
                            val = float(val)
                        except ValueError:
                            pass
                proj_mod.set_setting(_session, parts[1], val)
                skin.success(f"{parts[1]} = {val}")

            elif cmd == "zoom":
                _repl_zoom(parts[1:], skin, pt_session)

            elif cmd == "speed":
                _repl_speed(parts[1:], skin, pt_session)

            elif cmd == "trim":
                _repl_trim(parts[1:], skin, pt_session)

            elif cmd == "crop":
                if len(parts) > 1 and parts[1] == "set":
                    skin.info("Enter crop (normalized 0-1):")
                    x = float(skin.sub_input("  x: ", pt_session) or "0")
                    y = float(skin.sub_input("  y: ", pt_session) or "0")
                    w = float(skin.sub_input("  width: ", pt_session) or "1")
                    h = float(skin.sub_input("  height: ", pt_session) or "1")
                    tl_mod.set_crop(_session, x, y, w, h)
                    skin.success("Crop updated")
                else:
                    result = tl_mod.get_crop(_session)
                    output(result)

            elif cmd == "probe":
                if len(parts) < 2:
                    skin.error("Usage: probe <path>")
                    continue
                result = media_mod.probe(parts[1])
                output(result)

            elif cmd == "export":
                if len(parts) < 2:
                    skin.error("Usage: export <output_path>")
                    continue
                def on_prog(stage, msg):
                    skin.info(f"[{stage}] {msg}")
                result = export_mod.render(_session, parts[1], on_prog)
                skin.success(f"Exported: {result['output']} ({result['file_size']} bytes)")

            elif cmd == "preview":
                recipe = parts[1] if len(parts) > 1 else "quick"
                result = preview_mod.capture(_session, recipe=recipe)
                output(result, f"Preview bundle: {result.get('_bundle_dir', '')}")

            elif cmd == "preview-latest":
                recipe = parts[1] if len(parts) > 1 else None
                result = preview_mod.latest(project_path=_session.project_path, recipe=recipe)
                output(result, f"Latest preview bundle: {result.get('_bundle_dir', '')}")

            else:
                skin.warning(f"Unknown command: {cmd}. Type 'help' for commands.")

        except KeyboardInterrupt:
            print()
            continue
        except EOFError:
            break
        except Exception as e:
            skin.error(str(e))

    skin.print_goodbye()


def _repl_zoom(args, skin, pt_session=None):
    """Handle zoom subcommands in REPL."""
    if not args:
        skin.error("Usage: zoom list|add|rm <id>")
        return
    sub = args[0]
    if sub == "list":
        result = tl_mod.list_zoom_regions(_session)
        output(result)
    elif sub == "add":
        skin.info("Add zoom region:")
        start = int(skin.sub_input("  start_ms: ", pt_session))
        end = int(skin.sub_input("  end_ms: ", pt_session))
        depth = int(skin.sub_input("  depth (1-6, default 3): ", pt_session) or "3")
        fx = float(skin.sub_input("  focus_x (0-1, default 0.5): ", pt_session) or "0.5")
        fy = float(skin.sub_input("  focus_y (0-1, default 0.5): ", pt_session) or "0.5")
        result = tl_mod.add_zoom_region(_session, start, end, depth, fx, fy)
        skin.success(f"Added zoom: {result['id']}")
    elif sub == "rm" and len(args) > 1:
        tl_mod.remove_zoom_region(_session, args[1])
        skin.success(f"Removed: {args[1]}")
    else:
        skin.error("Usage: zoom list|add|rm <id>")


def _repl_speed(args, skin, pt_session=None):
    """Handle speed subcommands in REPL."""
    if not args:
        skin.error("Usage: speed list|add|rm <id>")
        return
    sub = args[0]
    if sub == "list":
        result = tl_mod.list_speed_regions(_session)
        output(result)
    elif sub == "add":
        skin.info("Add speed region:")
        start = int(skin.sub_input("  start_ms: ", pt_session))
        end = int(skin.sub_input("  end_ms: ", pt_session))
        spd = float(skin.sub_input("  speed (0.25-2.0, default 1.5): ", pt_session) or "1.5")
        result = tl_mod.add_speed_region(_session, start, end, spd)
        skin.success(f"Added speed: {result['id']}")
    elif sub == "rm" and len(args) > 1:
        tl_mod.remove_speed_region(_session, args[1])
        skin.success(f"Removed: {args[1]}")
    else:
        skin.error("Usage: speed list|add|rm <id>")


def _repl_trim(args, skin, pt_session=None):
    """Handle trim subcommands in REPL."""
    if not args:
        skin.error("Usage: trim list|add|rm <id>")
        return
    sub = args[0]
    if sub == "list":
        result = tl_mod.list_trim_regions(_session)
        output(result)
    elif sub == "add":
        skin.info("Add trim region:")
        start = int(skin.sub_input("  start_ms: ", pt_session))
        end = int(skin.sub_input("  end_ms: ", pt_session))
        result = tl_mod.add_trim_region(_session, start, end)
        skin.success(f"Added trim: {result['id']}")
    elif sub == "rm" and len(args) > 1:
        tl_mod.remove_trim_region(_session, args[1])
        skin.success(f"Removed: {args[1]}")
    else:
        skin.error("Usage: trim list|add|rm <id>")


if __name__ == "__main__":
    cli()
