#!/usr/bin/env python3
"""MuseScore CLI — A stateful command-line interface for music notation.

This CLI wraps MuseScore 4's mscore backend, providing transposition,
export (PDF/audio/MIDI), part extraction, instrument management, and
score analysis from the command line.

Usage:
    cli-anything-musescore --json project info -i score.mscz
    cli-anything-musescore --json transpose by-key -i score.mscz -o out.mscz --target-key "C major"
    cli-anything-musescore --json export pdf -i score.mscz -o score.pdf
    cli-anything-musescore   # Enter interactive REPL
"""

import functools
import sys
import os
import json
import click
from typing import Optional

from cli_anything.musescore.core.session import Session, get_session
from cli_anything.musescore.core import project as proj_mod
from cli_anything.musescore.core import transpose as trans_mod
from cli_anything.musescore.core import parts as parts_mod
from cli_anything.musescore.core import export as export_mod
from cli_anything.musescore.core import instruments as inst_mod
from cli_anything.musescore.core import media as media_mod

_json_output = False
_repl_mode = False


def output(data, message: str = ""):
    """Output data as JSON or human-readable."""
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
    """Decorator for consistent error handling across commands."""
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
        except (ValueError, IndexError, RuntimeError) as e:
            if _json_output:
                click.echo(json.dumps({"error": str(e), "type": type(e).__name__}))
            else:
                click.echo(f"Error: {e}", err=True)
            if not _repl_mode:
                sys.exit(1)
    return wrapper


# ── Main CLI Group ────────────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, help="Output as JSON")
@click.option("--project", "project_path", type=str, default=None,
              help="Path to score file to open")
@click.pass_context
def cli(ctx, use_json, project_path):
    """MuseScore CLI — Music notation from the command line.

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
        ctx.invoke(repl)


# ── Project Commands ──────────────────────────────────────────────────

@cli.group()
def project():
    """Project management commands."""
    pass


@project.command("open")
@click.option("-i", "--input", "path", required=True, help="Score file path")
@handle_error
def project_open(path):
    """Open a score file."""
    proj = proj_mod.open_project(path)
    sess = get_session()
    sess.set_project(proj, path)
    output(proj, f"Opened: {path}")


@project.command("info")
@click.option("-i", "--input", "path", required=True, help="Score file path")
@handle_error
def project_info(path):
    """Show score information."""
    info = proj_mod.project_info(path)
    output(info)


@project.command("save")
@click.option("-i", "--input", "input_path", required=True, help="Input score file")
@click.option("-o", "--output", "output_path", required=True, help="Output score file")
@handle_error
def project_save(input_path, output_path):
    """Save/convert a score to .mscz format via mscore export."""
    from cli_anything.musescore.core import export as export_mod_local
    result = export_mod_local.export_score(input_path, output_path, fmt="mscz")
    output(result, f"Saved to: {output_path}")


# ── Transpose Commands ────────────────────────────────────────────────

@cli.group()
def transpose():
    """Transposition commands."""
    pass


@transpose.command("by-key")
@click.option("-i", "--input", "input_path", required=True, help="Input score")
@click.option("-o", "--output", "output_path", required=True, help="Output score")
@click.option("--target-key", required=True, help="Target key (e.g., 'C major', 'Db', 'Am')")
@click.option("--direction", type=click.Choice(["up", "down", "closest"]),
              default="closest", help="Transpose direction")
@click.option("--no-key-sig", is_flag=True, help="Don't transpose key signatures")
@click.option("--no-chord-names", is_flag=True, help="Don't transpose chord names")
@handle_error
def transpose_by_key(input_path, output_path, target_key, direction,
                     no_key_sig, no_chord_names):
    """Transpose to a target key."""
    sess = get_session()
    if sess.has_project():
        sess.snapshot(f"Transpose to {target_key}")

    result = trans_mod.transpose_by_key(
        input_path, output_path,
        target_key=target_key,
        direction=direction,
        transpose_key_signatures=not no_key_sig,
        transpose_chord_names=not no_chord_names,
    )

    # Update session state from output file
    if sess.has_project() and sess.project_path == input_path:
        updated = proj_mod.open_project(output_path)
        sess.project_data.update(updated)
        sess.project_path = output_path

    output(result, f"Transposed to {target_key}")


@transpose.command("by-interval")
@click.option("-i", "--input", "input_path", required=True, help="Input score")
@click.option("-o", "--output", "output_path", required=True, help="Output score")
@click.option("--semitones", type=int, default=None, help="Semitones (negative = down)")
@click.option("--interval", "interval_index", type=int, default=None,
              help="MuseScore interval index (0-25)")
@click.option("--direction", type=click.Choice(["up", "down"]),
              default="up", help="Transpose direction")
@click.option("--no-key-sig", is_flag=True, help="Don't transpose key signatures")
@click.option("--no-chord-names", is_flag=True, help="Don't transpose chord names")
@handle_error
def transpose_by_interval(input_path, output_path, semitones, interval_index,
                          direction, no_key_sig, no_chord_names):
    """Transpose by a chromatic interval."""
    sess = get_session()
    if sess.has_project():
        sess.snapshot(f"Transpose by interval")

    result = trans_mod.transpose_by_interval(
        input_path, output_path,
        semitones=semitones,
        interval_index=interval_index,
        direction=direction,
        transpose_key_signatures=not no_key_sig,
        transpose_chord_names=not no_chord_names,
    )

    # Update session state from output file
    if sess.has_project() and sess.project_path == input_path:
        updated = proj_mod.open_project(output_path)
        sess.project_data.update(updated)
        sess.project_path = output_path

    output(result, "Transposed by interval")


@transpose.command("diatonic")
@click.option("-i", "--input", "input_path", required=True, help="Input score")
@click.option("-o", "--output", "output_path", required=True, help="Output score")
@click.option("--steps", type=int, required=True, help="Diatonic steps (negative = down)")
@click.option("--direction", type=click.Choice(["up", "down"]),
              default="up", help="Transpose direction")
@click.option("--no-key-sig", is_flag=True, help="Don't transpose key signatures")
@click.option("--no-chord-names", is_flag=True, help="Don't transpose chord names")
@handle_error
def transpose_diatonic(input_path, output_path, steps, direction,
                       no_key_sig, no_chord_names):
    """Transpose diatonically."""
    sess = get_session()
    if sess.has_project():
        sess.snapshot(f"Diatonic transpose by {steps}")

    result = trans_mod.transpose_diatonic(
        input_path, output_path,
        steps=steps,
        direction=direction,
        transpose_key_signatures=not no_key_sig,
        transpose_chord_names=not no_chord_names,
    )

    # Update session state from output file
    if sess.has_project() and sess.project_path == input_path:
        updated = proj_mod.open_project(output_path)
        sess.project_data.update(updated)
        sess.project_path = output_path

    output(result, f"Diatonic transpose by {steps} steps")


# ── Parts Commands ────────────────────────────────────────────────────

@cli.group()
def parts():
    """Part extraction and management."""
    pass


@parts.command("list")
@click.option("-i", "--input", "path", required=True, help="Score file path")
@handle_error
def parts_list(path):
    """List all parts in a score."""
    result = parts_mod.list_parts(path)
    output(result, "Parts:")


@parts.command("extract")
@click.option("-i", "--input", "path", required=True, help="Score file path")
@click.option("-o", "--output", "output_path", required=True, help="Output file path")
@click.option("--part", "part_name", required=True, help="Part name to extract")
@handle_error
def parts_extract(path, output_path, part_name):
    """Extract a single part from a score."""
    result = parts_mod.extract_part(path, part_name, output_path)
    output(result, f"Extracted part: {part_name}")


@parts.command("generate")
@click.option("-i", "--input", "path", required=True, help="Score file path")
@click.option("-d", "--output-dir", required=True, help="Output directory")
@handle_error
def parts_generate(path, output_dir):
    """Generate all parts as separate files."""
    result = parts_mod.generate_all_parts(path, output_dir)
    output(result, f"Generated {len(result)} parts")


# ── Export Commands ───────────────────────────────────────────────────

@cli.group("export")
def export_group():
    """Export/render commands."""
    pass


def _make_export_cmd(fmt_name, description):
    """Factory for format-specific export commands."""
    @export_group.command(fmt_name, help=description)
    @click.option("-i", "--input", "input_path", required=True, help="Input score")
    @click.option("-o", "--output", "output_path", required=True, help="Output file")
    @click.option("--dpi", type=int, default=None, help="DPI for PNG export")
    @click.option("--bitrate", type=int, default=None, help="Bitrate for MP3 (kbps)")
    @click.option("--trim", type=int, default=None, help="Trim margin for PNG/SVG")
    @click.option("--style", type=str, default=None, help="Style file (.mss)")
    @click.option("--sound-profile", type=str, default=None,
                  help="Audio profile (MuseScore Basic or Muse Sounds)")
    @handle_error
    def export_cmd(input_path, output_path, dpi, bitrate, trim, style, sound_profile):
        result = export_mod.export_score(
            input_path, output_path, fmt=fmt_name,
            dpi=dpi, bitrate=bitrate, trim=trim,
            style=style, sound_profile=sound_profile,
        )
        output(result, f"Exported {fmt_name}: {output_path}")

    return export_cmd


# Create format-specific commands
_make_export_cmd("pdf", "Export as PDF document")
_make_export_cmd("png", "Export as PNG images (one per page)")
_make_export_cmd("svg", "Export as SVG vector graphics")
_make_export_cmd("mp3", "Export as MP3 audio")
_make_export_cmd("flac", "Export as FLAC audio")
_make_export_cmd("wav", "Export as WAV audio")
_make_export_cmd("midi", "Export as MIDI file")
_make_export_cmd("musicxml", "Export as MusicXML")
_make_export_cmd("braille", "Export as Braille music notation")


@export_group.command("batch")
@click.option("-i", "--input", "input_path", required=True, help="Input score")
@click.option("-o", "--output", "outputs", multiple=True, required=True,
              help="Output files (specify multiple)")
@handle_error
def export_batch(input_path, outputs):
    """Export to multiple formats at once."""
    result = export_mod.batch_export(input_path, list(outputs))
    output(result, f"Batch exported {len(result)} files")


@export_group.command("verify")
@click.argument("path")
@click.option("--format", "fmt", default=None, help="Expected format")
@handle_error
def export_verify(path, fmt):
    """Verify an exported file using magic bytes."""
    result = export_mod.verify_output(path, fmt)
    output(result)


# ── Instruments Commands ──────────────────────────────────────────────

@cli.group()
def instruments():
    """Instrument management commands."""
    pass


@instruments.command("list")
@click.option("-i", "--input", "path", required=True, help="Score file path")
@handle_error
def instruments_list(path):
    """List instruments in a score."""
    result = inst_mod.list_instruments(path)
    output(result, "Instruments:")


@instruments.command("add")
@click.option("-i", "--input", "path", required=True, help="Input .mscz file")
@click.option("-o", "--output", "output_path", required=True, help="Output .mscz file")
@click.option("--id", "instrument_id", required=True, help="Instrument ID")
@click.option("--name", required=True, help="Display name")
@handle_error
def instruments_add(path, output_path, instrument_id, name):
    """Add an instrument to a score."""
    sess = get_session()
    if sess.has_project():
        sess.snapshot(f"Add instrument: {name}")
    result = inst_mod.add_instrument(path, output_path, instrument_id, name)

    # Update session state from output file
    if sess.has_project() and sess.project_path == path:
        updated = proj_mod.open_project(output_path)
        sess.project_data.update(updated)
        sess.project_path = output_path

    output(result, f"Added instrument: {name}")


@instruments.command("remove")
@click.option("-i", "--input", "path", required=True, help="Input .mscz file")
@click.option("-o", "--output", "output_path", required=True, help="Output .mscz file")
@click.option("--name", required=True, help="Instrument name to remove")
@handle_error
def instruments_remove(path, output_path, name):
    """Remove an instrument from a score."""
    sess = get_session()
    if sess.has_project():
        sess.snapshot(f"Remove instrument: {name}")
    result = inst_mod.remove_instrument(path, output_path, name)

    # Update session state from output file
    if sess.has_project() and sess.project_path == path:
        updated = proj_mod.open_project(output_path)
        sess.project_data.update(updated)
        sess.project_path = output_path

    output(result, f"Removed instrument: {name}")


@instruments.command("reorder")
@click.option("-i", "--input", "path", required=True, help="Input .mscz file")
@click.option("-o", "--output", "output_path", required=True, help="Output .mscz file")
@click.option("--order", required=True, help="Comma-separated instrument names")
@handle_error
def instruments_reorder(path, output_path, order):
    """Reorder instruments in a score."""
    new_order = [n.strip() for n in order.split(",")]
    sess = get_session()
    if sess.has_project():
        sess.snapshot("Reorder instruments")
    result = inst_mod.reorder_instruments(path, output_path, new_order)

    # Update session state from output file
    if sess.has_project() and sess.project_path == path:
        updated = proj_mod.open_project(output_path)
        sess.project_data.update(updated)
        sess.project_path = output_path

    output(result, "Reordered instruments")


# ── Media Commands ────────────────────────────────────────────────────

@cli.group()
def media():
    """Media analysis commands."""
    pass


@media.command("probe")
@click.option("-i", "--input", "path", required=True, help="Score file path")
@handle_error
def media_probe(path):
    """Probe score metadata."""
    result = media_mod.probe_score(path)
    output(result)


@media.command("diff")
@click.option("--reference", required=True, help="Reference score")
@click.option("--compare", required=True, help="Comparison score")
@click.option("--raw", is_flag=True, help="Use raw diff format")
@handle_error
def media_diff(reference, compare, raw):
    """Diff two scores."""
    result = media_mod.diff_scores(reference, compare, raw=raw)
    output(result)


@media.command("stats")
@click.option("-i", "--input", "path", required=True, help="Score file path")
@handle_error
def media_stats(path):
    """Show score statistics."""
    result = media_mod.score_stats(path)
    output(result)


# ── Session Commands ──────────────────────────────────────────────────

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
    output(history, "History:")


# ── REPL ──────────────────────────────────────────────────────────────

@cli.command(hidden=True)
@handle_error
def repl():
    """Start interactive REPL session."""
    global _repl_mode
    _repl_mode = True

    from cli_anything.musescore.utils.repl_skin import ReplSkin
    skin = ReplSkin("musescore", version="1.0.0")
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
                modified = sess.is_modified()

            line = skin.get_input(pt_session, project_name=proj_name,
                                  modified=modified)
            if not line:
                continue
            if line.lower() in ("quit", "exit", "q"):
                skin.print_goodbye()
                break
            if line.lower() == "help":
                _repl_help(skin)
                continue

            import shlex
            args = shlex.split(line)
            # Preserve --json flag across REPL commands
            if _json_output and "--json" not in args:
                args = ["--json"] + args
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
        "project open|info|save": "Project management",
        "transpose by-key|by-interval|diatonic": "Transposition",
        "parts list|extract|generate": "Part extraction",
        "export pdf|png|svg|mp3|wav|midi|...": "Export/render",
        "instruments list|add|remove|reorder": "Instrument management",
        "media probe|diff|stats": "Score analysis",
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


# ── Entry Point ───────────────────────────────────────────────────────

def main():
    cli()


if __name__ == "__main__":
    main()
