#!/usr/bin/env python3
"""Krita CLI — Digital art and painting from the command line.

Usage:
    cli-anything-krita info artwork.kra
    cli-anything-krita export artwork.kra output.png
    cli-anything-krita layer list artwork.kra
    cli-anything-krita create --width 1920 --height 1080 --output canvas.png
    cli-anything-krita repl
"""

import sys, os, json, shlex, click
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cli_anything.krita.core.session import Session
from cli_anything.krita.core import canvas as cv
from cli_anything.krita.core import export as exp_mod

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
    """Krita CLI — Digital art and painting from the command line."""
    global _json_output
    _json_output = use_json
    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


@cli.command()
@click.argument("path")
@handle_error
def info(path):
    """Get KRA file info (layers, dimensions, color space)."""
    result = cv.get_file_info(path)
    output(result)


@cli.command()
@click.argument("input_path")
@click.argument("output_path")
@click.option("--flatten", is_flag=True, help="Flatten layers")
@click.option("--width", "-w", type=int, default=None)
@click.option("--height", "-h", type=int, default=None)
@handle_error
def export(input_path, output_path, flatten, width, height):
    """Export KRA to PNG/JPEG/TIFF/PSD/PDF."""
    result = cv.export_file(
        input_path, output_path, flatten=flatten, width=width, height=height
    )
    output(result, f"Exported: {output_path}")


@cli.command()
@click.argument("inputs", nargs=-1, required=True)
@click.option("--output-dir", "-d", required=True, help="Output directory")
@click.option("--format", "fmt", default="png", help="Output format")
@click.option("--flatten", is_flag=True)
@handle_error
def batch(inputs, output_dir, fmt, flatten):
    """Batch export KRA files."""
    result = cv.batch_export(list(inputs), output_dir, fmt=fmt, flatten=flatten)
    output(result, f"Batch exported {len(result)} files")


@cli.group()
def layer():
    """Layer commands."""
    pass


@layer.command("list")
@click.argument("path")
@handle_error
def layer_list(path):
    """List layers in a .kra file."""
    result = cv.list_layers(path)
    output(result, "Layers:")


@layer.command("export")
@click.argument("path")
@click.option("--index", "-i", type=int, required=True, help="Layer index")
@click.option("--output", "-o", required=True, help="Output path")
@handle_error
def layer_export(path, index, output):
    """Export specific layer."""
    result = cv.export_layer(path, index, output)
    globals()["output"](result, f"Exported layer: {result.get('layer', '')}")


@cli.command()
@click.argument("input_path")
@click.argument("output_path")
@handle_error
def flatten(input_path, output_path):
    """Flatten and export."""
    result = cv.export_file(input_path, output_path, flatten=True)
    output(result, f"Flattened: {output_path}")


@cli.command()
@click.argument("input_path")
@click.argument("output_path")
@click.option("--width", "-w", type=int, required=True)
@click.option("--height", "-h", type=int, required=True)
@handle_error
def resize(input_path, output_path, width, height):
    """Resize canvas."""
    result = cv.resize_canvas(input_path, output_path, width, height)
    output(result, f"Resized to {width}x{height}")


@cli.command()
@click.argument("input_path")
@click.argument("output_path")
@click.option(
    "--filter",
    "-f",
    "filter_name",
    required=True,
    help="Filter: blur,sharpen,emboss,edges,grayscale,invert,brightness,contrast",
)
@handle_error
def filter_apply(input_path, output_path, filter_name):
    """Apply a filter."""
    result = cv.apply_filter(input_path, output_path, filter_name)
    output(result, f"Applied filter: {filter_name}")


@cli.command()
@click.argument("input_path")
@click.argument("output_path")
@click.option(
    "--space", "-s", required=True, help="Colorspace: SRGB, RGB, RGBA, CMYK, GRAYSCALE"
)
@handle_error
def colorspace_convert(input_path, output_path, space):
    """Convert color space."""
    result = cv.convert_colorspace(input_path, output_path, space)
    output(result, f"Converted to {space}")


@cli.command()
@click.option("--width", "-w", type=int, required=True, help="Canvas width")
@click.option("--height", "-h", type=int, required=True, help="Canvas height")
@click.option("--output", "-o", "output_path", required=True, help="Output file")
@click.option("--background", "-bg", default="#ffffff", help="Background color")
@handle_error
def create(width, height, output_path, background):
    """Create new canvas."""
    result = cv.create_canvas(width, height, output_path, background=background)
    globals()["output"](result, f"Created {width}x{height} canvas")


@cli.command()
@handle_error
def repl():
    """Start interactive REPL session."""
    from cli_anything.krita.utils.repl_skin import ReplSkin

    global _repl_mode
    _repl_mode = True
    skin = ReplSkin("krita", version="1.0.0")
    skin.print_banner()
    pt_session = skin.create_prompt_session()
    _repl_commands = {
        "info": "Get KRA file info",
        "export": "Export KRA to image",
        "batch": "Batch export",
        "layer": "list|export",
        "flatten": "Flatten and export",
        "resize": "Resize canvas",
        "filter": "Apply filter (blur/sharpen/etc)",
        "colorspace": "Convert color space",
        "create": "Create new canvas",
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
