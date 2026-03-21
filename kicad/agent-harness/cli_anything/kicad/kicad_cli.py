#!/usr/bin/env python3
"""KiCad CLI — A stateful command-line interface for electronics design.

This CLI wraps KiCad's powerful PCB/schematic capabilities into a structured,
agent-friendly interface with JSON output, project state, and REPL mode.

Usage:
    # One-shot commands
    cli-anything-kicad sch export schematic.kicad_sch --output schematic.pdf
    cli-anything-kicad pcb drc board.kicad_pcb
    cli-anything-kicad pcb gerber board.kicad_pcb --output gerbers/

    # Interactive REPL
    cli-anything-kicad
"""

import sys
import os
import json
import shlex
import click
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cli_anything.kicad.core.session import Session
from cli_anything.kicad.core import schematic as sch_mod
from cli_anything.kicad.core import pcb as pcb_mod
from cli_anything.kicad.core import library as lib_mod

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

    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


# ── Main CLI Group ──────────────────────────────────────────────
@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, help="Output as JSON")
@click.pass_context
def cli(ctx, use_json):
    """KiCad CLI — Stateful electronics design from the command line.

    Run without a subcommand to enter interactive REPL mode.
    """
    global _json_output
    _json_output = use_json

    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


# ── Schematic Commands ──────────────────────────────────────────
@cli.group()
def sch():
    """Schematic operations."""
    pass


@sch.command("export")
@click.argument("file")
@click.option("--output", "-o", required=True, help="Output file path")
@click.option("--page-size", default=None, help="Page size (A4, A3, Letter)")
@click.option("--no-background", is_flag=True, help="Transparent background")
@handle_error
def sch_export(file, output, page_size, no_background):
    """Export schematic to PDF/SVG/PNG."""
    result = sch_mod.export(
        file, output, page_size=page_size, no_background=no_background
    )
    output(result, f"Exported to: {output}")


@sch.command("bom")
@click.argument("file")
@click.option("--output", "-o", required=True, help="Output BOM file")
@click.option("--format", "fmt", default="csv", type=click.Choice(["csv", "xml"]))
@handle_error
def sch_bom(file, output, fmt):
    """Generate Bill of Materials (BOM)."""
    result = sch_mod.bom(file, output, format=fmt)
    output(result, f"BOM generated: {output}")


@sch.command("netlist")
@click.argument("file")
@click.option("--output", "-o", required=True, help="Output netlist file")
@click.option(
    "--format",
    "fmt",
    default="kicad",
    type=click.Choice(["kicad", "allegro", "pads", "spice"]),
)
@handle_error
def sch_netlist(file, output, fmt):
    """Export netlist from schematic."""
    result = sch_mod.netlist(file, output, fmt=fmt)
    output(result, f"Netlist exported: {output}")


@sch.group()
def symbols():
    """Symbol operations."""
    pass


@symbols.command("list")
@click.argument("file")
@handle_error
def symbols_list(file):
    """List symbols in schematic."""
    syms = sch_mod.symbols_list(file)
    output(syms, f"Symbols in {file}:")


# ── PCB Commands ──────────────────────────────────────────────────
@cli.group()
def pcb():
    """PCB operations."""
    pass


@pcb.command("export")
@click.argument("file")
@click.option("--output", "-o", required=True, help="Output file path")
@click.option("--layers", default=None, help="Comma-separated layers (F.Cu,B.Cu)")
@click.option(
    "--format", "fmt", default="svg", type=click.Choice(["svg", "pdf", "gerber"])
)
@handle_error
def pcb_export(file, output, layers, fmt):
    """Export PCB to SVG/Gerber/PDF."""
    result = pcb_mod.export(file, output, layers=layers, fmt=fmt)
    output(result, f"Exported to: {output}")


@pcb.command("drc")
@click.argument("file")
@handle_error
def pcb_drc(file):
    """Run Design Rule Check."""
    result = pcb_mod.drc(file)
    output(result)


@pcb.command("drill")
@click.argument("file")
@click.option("--output-dir", "-o", required=True, help="Output directory")
@handle_error
def pcb_drill(file, output_dir):
    """Generate drill files."""
    result = pcb_mod.drill(file, output_dir)
    output(result)


@pcb.command("gerber")
@click.argument("file")
@click.option("--output-dir", "-o", required=True, help="Output directory")
@handle_error
def pcb_gerber(file, output_dir):
    """Generate Gerber files (all layers)."""
    result = pcb_mod.gerber(file, output_dir)
    output(result)


@pcb.command("3d")
@click.argument("file")
@click.option("--output", "-o", required=True, help="Output file (.step/.wrl)")
@handle_error
def pcb_3d(file, output):
    """Export 3D model (STEP/VRML)."""
    result = pcb_mod.export_3d(file, output)
    output(result)


@pcb.command("stats")
@click.argument("file")
@handle_error
def pcb_stats(file):
    """PCB statistics (tracks, vias, components)."""
    result = pcb_mod.stats(file)
    output(result)


# ── Library Commands ──────────────────────────────────────────────
@cli.group()
def lib():
    """Library operations."""
    pass


@lib.command("list")
@click.argument("dir")
@handle_error
def lib_list(dir):
    """List symbols/footprints in a library."""
    if os.path.isdir(dir):
        symbols = lib_mod.list_symbols(dir)
        footprints = lib_mod.list_footprints(dir)
        result = {"symbols": symbols, "footprints": footprints}
    else:
        symbols = lib_mod.list_symbols(dir)
        result = {"symbols": symbols}
    output(result)


@lib.command("export")
@click.argument("lib_path")
@click.option("--output-dir", "-o", required=True, help="Output directory")
@click.option("--symbol", default=None, help="Specific symbol name")
@handle_error
def lib_export(lib_path, output_dir, symbol):
    """Export library symbols to SVG."""
    result = lib_mod.export_symbol(lib_path, output_dir, symbol_name=symbol)
    output(result)


# ── Session Commands ──────────────────────────────────────────────
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


# ── REPL ─────────────────────────────────────────────────────────
@cli.command()
@handle_error
def repl():
    """Start interactive REPL session."""
    from cli_anything.kicad.utils.repl_skin import ReplSkin

    global _repl_mode
    _repl_mode = True

    skin = ReplSkin("kicad", version="1.0.0")
    skin.print_banner()

    pt_session = skin.create_prompt_session()

    _repl_commands = {
        "sch": "export|bom|netlist|symbols list",
        "pcb": "export|drc|drill|gerber|3d|stats",
        "lib": "list|export",
        "session": "status|undo|redo|history",
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


# ── Entry Point ──────────────────────────────────────────────────
def main():
    cli()


if __name__ == "__main__":
    main()
