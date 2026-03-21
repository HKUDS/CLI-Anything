#!/usr/bin/env python3
"""Darktable CLI — RAW photo processing from the command line.

Usage:
    cli-anything-darktable export input.cr2 output.jpg --quality 95
    cli-anything-darktable info photo.nef
    cli-anything-darktable batch *.cr2 --output-dir ./exports
    cli-anything-darktable styles list
    cli-anything-darktable repl
"""

import sys, os, json, shlex, click
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cli_anything.darktable.core.session import Session
from cli_anything.darktable.core import process as proc
from cli_anything.darktable.core import export as exp_mod

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
        except FileNotFoundError as e:
            msg = {"error": str(e), "type": "file_not_found"}
            if _json_output:
                click.echo(json.dumps(msg))
            else:
                click.echo(f"Error: {e}", err=True)
            if not _repl_mode:
                sys.exit(1)
        except (ValueError, RuntimeError, IndexError) as e:
            msg = {"error": str(e), "type": type(e).__name__}
            if _json_output:
                click.echo(json.dumps(msg))
            else:
                click.echo(f"Error: {e}", err=True)
            if not _repl_mode:
                sys.exit(1)

    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, help="Output as JSON")
@click.pass_context
def cli(ctx, use_json):
    """Darktable CLI — RAW photo processing from the command line."""
    global _json_output
    _json_output = use_json
    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


@cli.command()
@click.argument("input_path")
@click.argument("output_path")
@click.option("--width", "-w", type=int, default=None, help="Output width")
@click.option("--height", "-h", type=int, default=None, help="Output height")
@click.option("--quality", "-q", type=int, default=None, help="JPEG quality 1-100")
@click.option("--icc", type=str, default=None, help="Output ICC profile")
@click.option("--style", type=str, default=None, help="Darktable style")
@click.option("--apply-xmp", type=str, default=None, help="Apply XMP sidecar")
@handle_error
def export(input_path, output_path, width, height, quality, icc, style, apply_xmp):
    """Export RAW to JPEG/PNG/TIFF."""
    result = proc.export_raw(
        input_path,
        output_path,
        width=width,
        height=height,
        quality=quality,
        icc=icc,
        style=style,
        xmp=apply_xmp,
    )
    output(result, f"Exported: {output_path}")


@cli.command()
@click.argument("path")
@handle_error
def info(path):
    """Get RAW file info (exif data)."""
    result = proc.get_file_info(path)
    output(result)


@cli.command()
@click.argument("inputs", nargs=-1, required=True)
@click.option("--output-dir", "-d", required=True, help="Output directory")
@click.option("--width", "-w", type=int, default=None)
@click.option("--height", "-h", type=int, default=None)
@click.option("--quality", "-q", type=int, default=None)
@click.option("--format", "fmt", default="jpg", help="Output format")
@handle_error
def batch(inputs, output_dir, width, height, quality, fmt):
    """Batch export RAW files."""
    result = proc.batch_export(
        list(inputs),
        output_dir,
        width=width,
        height=height,
        quality=quality,
        format=fmt,
    )
    output(result, f"Batch exported {len(result)} files")


@cli.group()
def styles():
    """Darktable style commands."""
    pass


@styles.command("list")
@handle_error
def styles_list():
    """List available darktable styles."""
    result = proc.list_styles()
    output(result, "Available styles:")


@styles.command("export")
@click.argument("input_path")
@click.argument("output_path")
@click.option("--style", "-s", required=True, help="Style name")
@click.option("--quality", "-q", type=int, default=None)
@handle_error
def styles_export(input_path, output_path, style, quality):
    """Export with a specific style."""
    result = proc.export_with_style(input_path, output_path, style, quality=quality)
    output(result, f"Exported with style: {style}")


@cli.group()
def xmp():
    """XMP sidecar commands."""
    pass


@xmp.command("create")
@click.argument("input_path")
@handle_error
def xmp_create(input_path):
    """Create XMP sidecar file."""
    result = proc.create_xmp(input_path)
    output({"xmp_file": result}, f"Created: {result}")


@xmp.command("apply")
@click.argument("xmp_path")
@click.argument("input_path")
@click.argument("output_path")
@click.option("--quality", "-q", type=int, default=None)
@handle_error
def xmp_apply(xmp_path, input_path, output_path, quality):
    """Apply XMP edits to produce output."""
    result = proc.apply_xmp(xmp_path, input_path, output_path, quality=quality)
    output(result, f"Applied XMP: {output_path}")


@cli.group()
def export_presets():
    """Export preset commands."""
    pass


@export_presets.command("list")
@handle_error
def export_preset_list():
    """List export presets."""
    result = exp_mod.list_presets()
    output(result, "Export presets:")


@cli.command()
@handle_error
def repl():
    """Start interactive REPL session."""
    from cli_anything.darktable.utils.repl_skin import ReplSkin

    global _repl_mode
    _repl_mode = True
    skin = ReplSkin("darktable", version="1.0.0")
    skin.print_banner()
    pt_session = skin.create_prompt_session()
    _repl_commands = {
        "export": "Export RAW to JPEG/PNG/TIFF",
        "info": "Get file info",
        "batch": "Batch export files",
        "styles": "list|export",
        "xmp": "create|apply",
        "help": "Show this help",
        "quit": "Exit REPL",
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


def main():
    cli()


if __name__ == "__main__":
    main()
