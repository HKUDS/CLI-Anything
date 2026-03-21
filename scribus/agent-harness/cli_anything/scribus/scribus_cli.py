#!/usr/bin/env python3
"""Scribus CLI — Desktop publishing from the command line.

Usage:
    cli-anything-scribus create output.sla --width 210 --height 297 --pages 4
    cli-anything-scribus info document.sla
    cli-anything-scribus export input.sla output.pdf --preset print
    cli-anything-scribus repl
"""

import sys, os, json, shlex, click
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cli_anything.scribus.core.session import Session
from cli_anything.scribus.core import document as doc

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
    """Scribus CLI — Desktop publishing from the command line."""
    global _json_output
    _json_output = use_json
    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


@cli.command()
@click.argument("output_path")
@click.option("--width", "-w", type=float, default=210.0, help="Page width")
@click.option("--height", "-h", type=float, default=297.0, help="Page height")
@click.option("--pages", "-p", type=int, default=1, help="Number of pages")
@click.option(
    "--orientation", type=click.Choice(["portrait", "landscape"]), default="portrait"
)
@click.option("--unit", type=click.Choice(["mm", "inches", "points"]), default="mm")
@handle_error
def create(output_path, width, height, pages, orientation, unit):
    """Create new document."""
    result = doc.create_document(
        output_path,
        width=width,
        height=height,
        pages=pages,
        orientation=orientation,
        unit=unit,
    )
    output(result, f"Created: {output_path}")


@cli.command()
@click.argument("path")
@handle_error
def info(path):
    """Get SLA file info (pages, layers, objects)."""
    result = doc.get_file_info(path)
    output(result)


@cli.command()
@click.argument("input_path")
@click.argument("output_path")
@click.option(
    "--preset", type=click.Choice(["print", "web", "screen"]), default="print"
)
@click.option("--quality", "-q", type=int, default=None, help="PDF quality")
@handle_error
def export(input_path, output_path, preset, quality):
    """Export SLA to PDF."""
    result = doc.export_to_pdf(input_path, output_path, preset=preset, quality=quality)
    output(result, f"Exported PDF: {output_path}")


@cli.command()
@click.argument("input_path")
@click.argument("output_path")
@click.option("--preset", default="print")
@click.option("--pages", type=str, default=None, help="Page range (e.g. 1-5)")
@handle_error
def pdf_export(input_path, output_path, preset, pages):
    """Export specific pages to PDF."""
    result = doc.export_to_pdf(input_path, output_path, preset=preset, pages=pages)
    output(result, f"Exported PDF: {output_path}")


@cli.group()
def page():
    """Page commands."""
    pass


@page.command("add")
@click.argument("path")
@click.option("--output", "-o", required=True, help="Output path")
@handle_error
def page_add(path, output):
    """Add page to document."""
    result = doc.add_page(path, output)
    globals()["output"](result, f"Added page. Total: {result['pages']}")


@page.command("list")
@click.argument("path")
@handle_error
def page_list(path):
    """List pages with dimensions."""
    result = doc.list_pages(path)
    output(result, "Pages:")


@cli.command()
@click.argument("path")
@click.option("--page", type=int, required=True, help="Page number")
@click.option("--x", type=float, required=True, help="X position")
@click.option("--y", type=float, required=True, help="Y position")
@click.option("--width", "-w", type=float, required=True, help="Frame width")
@click.option("--height", "-h", type=float, required=True, help="Frame height")
@click.option("--content", "-c", required=True, help="Text content")
@click.option("--output", "-o", required=True, help="Output path")
@handle_error
def text_add(path, page, x, y, width, height, content, output):
    """Add text frame."""
    result = doc.add_text_frame(path, page, x, y, width, height, content, output)
    globals()["output"](result, f"Added text frame on page {page}")


@cli.command()
@click.argument("path")
@click.option("--page", type=int, required=True, help="Page number")
@click.option("--x", type=float, required=True, help="X position")
@click.option("--y", type=float, required=True, help="Y position")
@click.option("--width", "-w", type=float, required=True, help="Frame width")
@click.option("--height", "-h", type=float, required=True, help="Frame height")
@click.option("--image", required=True, help="Image path")
@click.option("--output", "-o", required=True, help="Output path")
@handle_error
def image_add(path, page, x, y, width, height, image, output):
    """Add image frame."""
    result = doc.add_image_frame(path, page, x, y, width, height, image, output)
    globals()["output"](result, f"Added image frame on page {page}")


@cli.group()
def layer():
    """Layer commands."""
    pass


@layer.command("list")
@click.argument("path")
@handle_error
def layer_list(path):
    """List layers."""
    result = doc.list_layers_sla(path)
    output(result, "Layers:")


@layer.command("add")
@click.argument("path")
@click.option("--name", "-n", required=True, help="Layer name")
@click.option("--output", "-o", required=True, help="Output path")
@handle_error
def layer_add(path, name, output):
    """Add layer."""
    result = doc.add_layer_sla(path, name, output)
    globals()["output"](result, f"Added layer: {name}")


@cli.command()
@handle_error
def font_list():
    """List available fonts."""
    result = doc.list_fonts()
    output(result, "Available fonts:")


@cli.command()
@handle_error
def repl():
    """Start interactive REPL session."""
    from cli_anything.scribus.utils.repl_skin import ReplSkin

    global _repl_mode
    _repl_mode = True
    skin = ReplSkin("scribus", version="1.0.0")
    skin.print_banner()
    pt_session = skin.create_prompt_session()
    _repl_commands = {
        "create": "Create new document",
        "info": "Get SLA file info",
        "export": "Export SLA to PDF",
        "page": "add|list",
        "text": "Add text frame",
        "image": "Add image frame",
        "layer": "list|add",
        "font": "list",
        "pdf": "Export pages to PDF",
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
