#!/usr/bin/env python3
"""Universal Image Converter CLI — batch image format conversion.

A CLI harness for converting images between formats using Pillow.
Supports single-file and batch directory conversion with optional
resize, quality settings, and JSON output for AI agent consumption.

Reference: gimp/agent-harness/cli_anything/gimp/gimp_cli.py (CLI pattern)

Usage:
    # Convert a single image
    cli-anything-universal-image-converter convert photo.jpg -o output/ --format png

    # Batch convert a directory
    cli-anything-universal-image-converter convert --input-dir ./photos -o ./output --format webp

    # Interactive REPL
    cli-anything-universal-image-converter repl
"""

import sys
import os
import json
import shlex
import click
from typing import Optional


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cli_anything.universal_image_converter.core.converter import (
    convert_image,
    batch_convert,
    probe_image,
)
from cli_anything.universal_image_converter.core.formats import (
    list_input_formats,
    list_output_formats,
    get_output_format_info,
    list_quality_presets,
    get_quality_preset,
    INPUT_FORMATS,
    OUTPUT_FORMATS,
)

_json_output = False
_repl_mode = False


def _emit(data, message: str = ""):
    """Output data in human or JSON format."""
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
    """Decorator to catch and format errors consistently."""
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
        except FileExistsError as e:
            if _json_output:
                click.echo(json.dumps({"error": str(e), "type": "file_exists"}))
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
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


# ── Main CLI Group ──────────────────────────────────────────────
@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, help="Output as JSON")
@click.pass_context
def cli(ctx, use_json):
    """Universal Image Converter CLI — batch image format conversion.

    Run without a subcommand to enter interactive REPL mode.
    """
    global _json_output
    _json_output = use_json

    if ctx.invoked_subcommand is None:
        if not sys.stdin.isatty():
            click.echo(ctx.get_help())
            return
        ctx.invoke(repl)


# ── Convert Command ─────────────────────────────────────────────
@cli.command()
@click.option("--input", "-i", "input_files", multiple=True, type=str,
              help="One or more input image file paths")
@click.option("--input-dir", "-d", type=str, default=None,
              help="Directory of images to convert")
@click.option("--output", "-o", type=str, required=True,
              help="Output directory (or single file path for single input)")
@click.option("--format", "-f", "output_format", type=str, required=True,
              help="Target output format (png, jpg, webp, tiff, bmp, ico, gif)")
@click.option("--quality", "-q", type=str, default=None,
              help="Quality preset: lossless, high, medium, low")
@click.option("--width", "-w", type=int, default=None,
              help="Target width in pixels")
@click.option("--height", "-h", type=int, default=None,
              help="Target height in pixels")
@click.option("--no-aspect", is_flag=True, default=False,
              help="Don't maintain aspect ratio when resizing")
@click.option("--overwrite", is_flag=True, default=False,
              help="Overwrite existing files")
@click.option("--prefix", type=str, default="",
              help="Prefix for output filenames")
@click.option("--suffix", type=str, default="",
              help="Suffix for output filenames (before extension)")
@handle_error
def convert(input_files, input_dir, output, output_format, quality, width, height,
            no_aspect, overwrite, prefix, suffix):
    """Convert images between formats.

    Supports single files, multiple files, and directory batch conversion.
    """
    # Validate format
    fmt_key = output_format.lower().lstrip(".")
    if fmt_key not in OUTPUT_FORMATS:
        raise ValueError(f"Unsupported output format: {output_format}. "
                         f"Available: {list(OUTPUT_FORMATS.keys())}")

    # Validate quality preset
    if quality:
        get_quality_preset(quality)  # raises if invalid

    # Collect input files
    all_files = []
    if input_dir:
        if not os.path.isdir(input_dir):
            raise FileNotFoundError(f"Input directory not found: {input_dir}")
        supported_exts = set(INPUT_FORMATS.keys())
        for f in sorted(os.listdir(input_dir)):
            ext = os.path.splitext(f)[1].lower().lstrip(".")
            if ext in supported_exts:
                all_files.append(os.path.join(input_dir, f))

    for f in input_files:
        all_files.append(f)

    if not all_files:
        raise ValueError("No input files specified. Use --input or --input-dir.")

    # Single file with explicit output path (not a directory)
    if len(all_files) == 1 and not input_dir and not os.path.isdir(output):
        if not output.endswith(f".{fmt_key}"):
            output = f"{output}.{fmt_key}"
        result = convert_image(
            all_files[0], output, output_format,
            quality=quality, width=width, height=height,
            keep_aspect=not no_aspect, overwrite=overwrite,
        )
        result["status"] = "converted"
        _emit(result, f"Converted: {all_files[0]} -> {output}")
        return

    # Batch mode
    result = batch_convert(
        all_files, output, output_format,
        quality=quality, width=width, height=height,
        keep_aspect=not no_aspect, overwrite=overwrite,
        prefix=prefix, suffix=suffix,
    )
    summary = {k: v for k, v in result.items() if k != "results"}
    if _json_output:
        _emit(result)
    else:
        _emit(summary, f"Batch conversion: {result['succeeded']}/{result['total']} succeeded, "
              f"{result['skipped']} skipped, {result['failed']} failed")
        if result["failed"] > 0:
            for r in result["results"]:
                if r["status"] == "failed":
                    click.echo(f"  FAIL: {r['input']} — {r.get('error', 'unknown')}")


# ── Info Command ─────────────────────────────────────────────────
@cli.command()
@click.argument("path")
@handle_error
def info(path):
    """Show detailed information about an image file."""
    result = probe_image(path)
    _emit(result, f"Image info: {path}")


# ── Formats Command ──────────────────────────────────────────────
@cli.command()
@click.option("--type", "fmt_type", type=click.Choice(["input", "output"]),
              default="output", help="Show input or output formats")
@handle_error
def formats(fmt_type):
    """List supported image formats."""
    if fmt_type == "input":
        fmts = list_input_formats()
        _emit(fmts, "Supported input formats:")
    else:
        fmts = list_output_formats()
        _emit(fmts, "Supported output formats:")


# ── Format Info Command ──────────────────────────────────────────
@cli.command("format-info")
@click.argument("format_name")
@handle_error
def format_info(format_name):
    """Show details about a specific output format."""
    info = get_output_format_info(format_name)
    _emit(info)


# ── Quality Command ──────────────────────────────────────────────
@cli.command("quality-presets")
@handle_error
def quality_presets():
    """List quality presets for conversion."""
    presets = list_quality_presets()
    _emit(presets, "Quality presets:")


# ── Resize Command ───────────────────────────────────────────────
@cli.command()
@click.argument("path")
@click.option("--output", "-o", type=str, required=True, help="Output path")
@click.option("--width", "-w", type=int, default=None, help="Target width")
@click.option("--height", "-h", type=int, default=None, help="Target height")
@click.option("--no-aspect", is_flag=True, default=False,
              help="Don't maintain aspect ratio")
@click.option("--format", "-f", "output_format", type=str, default=None,
              help="Output format (auto-detected from extension if not specified)")
@click.option("--overwrite", is_flag=True, default=False)
@handle_error
def resize(path, output, width, height, no_aspect, output_format, overwrite):
    """Resize an image, optionally converting format."""
    if not width and not height:
        raise ValueError("At least one of --width or --height is required.")

    # Auto-detect format from extension
    if not output_format:
        ext = os.path.splitext(output)[1].lower().lstrip(".")
        if ext in OUTPUT_FORMATS:
            output_format = ext
        else:
            output_format = os.path.splitext(path)[1].lower().lstrip(".") or "png"

    result = convert_image(
        path, output, output_format,
        width=width, height=height,
        keep_aspect=not no_aspect, overwrite=overwrite,
    )
    result["status"] = "resized"
    _emit(result, f"Resized: {path} -> {output}")


# ── REPL Command ─────────────────────────────────────────────────
@cli.command()
@handle_error
def repl():
    """Start interactive REPL session."""
    try:
        from cli_anything.universal_image_converter.utils.repl_skin import ReplSkin
    except ImportError:
        click.echo("Error: REPL requires prompt_toolkit. Install with: pip install prompt-toolkit")
        raise SystemExit(1)

    global _repl_mode
    _repl_mode = True

    skin = ReplSkin("universal-image-converter", version="1.0.0")
    skin.print_banner()

    try:
        pt_session = skin.create_prompt_session()
    except Exception:
        click.echo("Error: REPL requires an interactive terminal.", err=True)
        raise SystemExit(1)

    _repl_commands = {
        "convert":         "-i <files> | -d <dir> -o <output> -f <format> [-q quality] [-w W] [-h H]",
        "info":            "<path> — Show image metadata",
        "formats":         "[--type input|output] — List supported formats",
        "format-info":     "<format> — Show format details",
        "quality-presets": "List quality presets",
        "resize":          "<path> -o <output> -w <W> -h <H> — Resize an image",
        "help":            "Show this help",
        "quit":            "Exit REPL",
    }

    while True:
        try:
            line = skin.get_input(pt_session)
            if not line:
                continue
            if line.lower() in ("quit", "exit", "q"):
                skin.print_goodbye()
                break
            if line.lower() == "help":
                skin.help(_repl_commands)
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
                skin.error(f"{e}")

        except (EOFError, KeyboardInterrupt):
            skin.print_goodbye()
            break

    _repl_mode = False


# ── Entry Point ──────────────────────────────────────────────────
def main():
    cli()


if __name__ == "__main__":
    main()
