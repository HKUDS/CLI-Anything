#!/usr/bin/env python3
import sys, os, json, shlex, click
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cli_anything.imagemagick.core.session import Session
from cli_anything.imagemagick.core import convert as im_convert

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


@cli.command()
@click.argument("input_path")
@click.argument("output_path")
@click.option("--width", type=int, default=None)
@click.option("--height", type=int, default=None)
@click.option("--quality", type=int, default=None)
@click.option("--format", "fmt", default=None)
@click.option("--blur", type=float, default=None)
@click.option("--sharpen", type=float, default=None)
@click.option("--brightness", type=int, default=None)
@click.option("--contrast", type=int, default=None)
@click.option("--grayscale", is_flag=True, default=False)
@click.option("--flip", is_flag=True, default=False)
@click.option("--flop", is_flag=True, default=False)
@click.option("--rotate", type=float, default=None)
@click.option("--crop", default=None)
@handle_error
def convert(
    input_path,
    output_path,
    width,
    height,
    quality,
    fmt,
    blur,
    sharpen,
    brightness,
    contrast,
    grayscale,
    flip,
    flop,
    rotate,
    crop,
):
    """Convert an image with various options."""
    result = im_convert.convert(
        input_path,
        output_path,
        width=width,
        height=height,
        quality=quality,
        format=fmt,
        blur=blur,
        sharpen=sharpen,
        brightness=brightness,
        contrast=contrast,
        grayscale=grayscale,
        flip=flip,
        flop=flop,
        rotate=rotate,
        crop=crop,
    )
    output(result)


@cli.command()
@click.argument("file_path")
@handle_error
def info(file_path):
    """Get image info."""
    result = im_convert.info(file_path)
    output(result)


@cli.command()
@click.argument("input_path")
@click.argument("output_path")
@click.option("--width", type=int, required=True)
@click.option("--height", type=int, required=True)
@click.option("--mode", type=click.Choice(["fit", "fill"]), default="fit")
@handle_error
def resize(input_path, output_path, width, height, mode):
    """Resize an image (fit/fill modes)."""
    result = im_convert.resize(
        input_path, output_path, width=width, height=height, mode=mode
    )
    output(result)


@cli.command()
@click.argument("input_path")
@click.argument("output_path")
@click.option("--width", type=int, required=True)
@click.option("--height", type=int, required=True)
@click.option("--x", "x_pos", type=int, required=True)
@click.option("--y", "y_pos", type=int, required=True)
@handle_error
def crop(input_path, output_path, width, height, x_pos, y_pos):
    """Crop an image (WxH+X+Y)."""
    result = im_convert.crop_image(
        input_path, output_path, width=width, height=height, x=x_pos, y=y_pos
    )
    output(result)


@cli.command()
@click.argument("input_path")
@click.argument("output_path")
@click.option("--size", type=int, default=128)
@handle_error
def thumbnail(input_path, output_path, size):
    """Create a thumbnail (fit within SxS)."""
    result = im_convert.thumbnail(input_path, output_path, size=size)
    output(result)


@cli.command()
@click.argument("input_path")
@click.argument("output_path")
@click.option("--text", required=True)
@click.option("--gravity", default="southeast")
@handle_error
def watermark(input_path, output_path, text, gravity):
    """Add text watermark."""
    result = im_convert.watermark(input_path, output_path, text=text, gravity=gravity)
    output(result)


@cli.command()
@click.argument("input_path")
@click.argument("output_path")
@click.option("--width", type=int, default=5)
@click.option("--color", default="black")
@handle_error
def border(input_path, output_path, width, color):
    """Add border to an image."""
    result = im_convert.border(input_path, output_path, width=width, color=color)
    output(result)


@cli.command()
@click.argument("inputs", nargs=-1, required=True)
@click.option("--output", "output_path", required=True)
@click.option("--tile", default="3x3")
@click.option("--geometry", default="200x200+5+5")
@handle_error
def montage(inputs, output_path, tile, geometry):
    """Create montage from images."""
    result = im_convert.montage(list(inputs), output_path, tile=tile, geometry=geometry)
    output(result)


@cli.group()
def animate():
    """GIF animation commands."""
    pass


@animate.command("info")
@click.argument("file_path")
@handle_error
def animate_info(file_path):
    """GIF animation info."""
    result = im_convert.animate_info(file_path)
    output(result)


@cli.command()
@click.argument("file1")
@click.argument("file2")
@handle_error
def compare(file1, file2):
    """Compare two images (RMSE metric)."""
    result = im_convert.compare(file1, file2)
    output(result)


@cli.command()
@click.argument("inputs", nargs=-1, required=True)
@click.option("--output-dir", required=True)
@click.option(
    "--operation",
    type=click.Choice(["thumbnail", "resize", "grayscale"]),
    default="thumbnail",
)
@click.option("--size", type=int, default=128)
@click.option("--width", type=int, default=None)
@click.option("--height", type=int, default=None)
@handle_error
def batch(inputs, output_dir, operation, size, width, height):
    """Batch process multiple images."""
    kwargs = {}
    if operation == "thumbnail":
        kwargs["size"] = size
    if operation == "resize":
        kwargs.update({"width": width, "height": height})
    result = im_convert.batch(list(inputs), output_dir, operation=operation, **kwargs)
    output(result)


@cli.command()
@handle_error
def repl():
    """Start interactive REPL."""
    from cli_anything.imagemagick.utils.repl_skin import ReplSkin

    global _repl_mode
    _repl_mode = True
    skin = ReplSkin("imagemagick", version="1.0.0")
    skin.print_banner()
    pt_session = skin.create_prompt_session()
    commands = {
        "convert": "Convert image with options",
        "info": "Image metadata",
        "resize": "Resize image (fit/fill)",
        "crop": "Crop image",
        "thumbnail": "Create thumbnail",
        "watermark": "Add text watermark",
        "border": "Add border",
        "montage": "Create montage",
        "animate info": "GIF animation info",
        "compare": "Compare two images",
        "batch": "Batch process images",
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
                skin.help(commands)
                continue
            try:
                args = shlex.split(line)
            except:
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
