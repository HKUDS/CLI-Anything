#!/usr/bin/env python3
"""FFprobe CLI — Structured media file analysis via ffprobe."""

import sys
import os
import json
import shlex
import click
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cli_anything.ffprobe.core.session import Session
from cli_anything.ffprobe.core import analyze

_session = None
_json_output = False
_repl_mode = False


def get_session():
    global _session
    if _session is None:
        _session = Session()
    return _session


def output(data, message=""):
    if _json_output:
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        if message:
            click.echo(message)
        if isinstance(data, dict):
            for k, v in data.items():
                click.echo(f"  {k}: {v}")
        elif isinstance(data, list):
            for i, item in enumerate(data):
                if isinstance(item, dict):
                    click.echo(f"  [{i}]")
                    for k, v in item.items():
                        click.echo(f"    {k}: {v}")
                else:
                    click.echo(f"  - {item}")
        else:
            click.echo(str(data))


def handle_error(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if _json_output:
                click.echo(json.dumps({"error": str(e), "type": type(e).__name__}))
            else:
                click.echo(f"Error: {e}", err=True)
            if not _repl_mode:
                sys.exit(1)

    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True)
@click.pass_context
def cli(ctx, use_json):
    global _json_output
    _json_output = use_json
    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


# ── Analyze group ─────────────────────────────────────────────────────


@cli.group(name="analyze")
def analyze_cmd():
    """Analyze media files."""
    pass


@analyze_cmd.command("info")
@click.argument("file")
@handle_error
def analyze_info(file):
    """Full probe with JSON output."""
    result = analyze.analyze_info(file)
    output(result, f"Analysis of {file}:")


@analyze_cmd.command("streams")
@click.argument("file")
@handle_error
def analyze_streams(file):
    """List streams only."""
    result = analyze.analyze_streams(file)
    output(result, f"Streams in {file}:")


@analyze_cmd.command("format")
@click.argument("file")
@handle_error
def analyze_format(file):
    """Show container format info."""
    result = analyze.analyze_format(file)
    output(result, f"Format info for {file}:")


@analyze_cmd.command("codec")
@click.argument("file")
@handle_error
def analyze_codec(file):
    """Show codec details for all streams."""
    result = analyze.analyze_codec(file)
    output(result, f"Codec details for {file}:")


@analyze_cmd.command("chapters")
@click.argument("file")
@handle_error
def analyze_chapters(file):
    """List chapters."""
    result = analyze.analyze_chapters(file)
    output(result, f"Chapters in {file}:")


@analyze_cmd.command("packets")
@click.argument("file")
@click.option("--count", default=50, help="Number of packets to show")
@handle_error
def analyze_packets(file, count):
    """Show packet info."""
    result = analyze.analyze_packets(file, count=count)
    output(result, f"Packets in {file} (limit {count}):")


@analyze_cmd.command("frames")
@click.argument("file")
@click.option("--count", default=50, help="Number of frames to show")
@handle_error
def analyze_frames(file, count):
    """Show frame info."""
    result = analyze.analyze_frames(file, count=count)
    output(result, f"Frames in {file} (limit {count}):")


@analyze_cmd.command("thumbnails")
@click.argument("file")
@handle_error
def analyze_thumbnails(file):
    """Extract thumbnail timestamps."""
    result = analyze.analyze_thumbnails(file)
    output(result, f"Thumbnail keyframes in {file}:")


# ── Batch group ───────────────────────────────────────────────────────


@cli.group()
def batch():
    """Batch analysis operations."""
    pass


@batch.command("analyze")
@click.argument("files", nargs=-1, required=True)
@handle_error
def batch_analyze(files):
    """Analyze multiple files."""
    result = analyze.batch_analyze(list(files))
    output(result, f"Batch analysis of {len(files)} files:")


# ── Compare ───────────────────────────────────────────────────────────


@cli.command()
@click.argument("file1")
@click.argument("file2")
@handle_error
def compare(file1, file2):
    """Compare two media files."""
    result = analyze.compare(file1, file2)
    output(result, f"Comparing {file1} vs {file2}:")


# ── Session commands ──────────────────────────────────────────────────


@cli.command()
@handle_error
def status():
    """Show session status."""
    s = get_session()
    output(s.status())


# ── REPL ──────────────────────────────────────────────────────────────


@cli.command()
@handle_error
def repl():
    """Start interactive REPL."""
    from cli_anything.ffprobe.utils.repl_skin import ReplSkin

    global _repl_mode
    _repl_mode = True
    skin = ReplSkin("ffprobe", version="1.0.0")
    skin.print_banner()

    commands = {
        "analyze info <file>": "Full probe with JSON output",
        "analyze streams <file>": "List streams only",
        "analyze format <file>": "Show container format info",
        "analyze codec <file>": "Show codec details for all streams",
        "analyze chapters <file>": "List chapters",
        "analyze packets <file>": "Show packet info (--count)",
        "analyze frames <file>": "Show frame info (--count)",
        "analyze thumbnails <file>": "Extract thumbnail timestamps",
        "batch analyze <files...>": "Analyze multiple files",
        "compare <file1> <file2>": "Compare two media files",
        "status": "Show session status",
        "help": "Show this help",
        "quit": "Exit the REPL",
    }

    pt_session = skin.create_prompt_session()
    while True:
        try:
            line = skin.get_input(pt_session)
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
            except Exception:
                args = line.split()
            try:
                cli.main(args, standalone_mode=False)
            except SystemExit:
                pass
            except click.exceptions.UsageError as e:
                skin.warning(f"Usage error: {e}")
            except Exception as e:
                skin.error(f"{e}")
        except (EOFError, KeyboardInterrupt):
            skin.print_goodbye()
            break
    _repl_mode = False


def main():
    cli()


if __name__ == "__main__":
    main()
