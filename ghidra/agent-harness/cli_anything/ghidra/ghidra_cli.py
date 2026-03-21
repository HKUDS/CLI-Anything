#!/usr/bin/env python3
"""Ghidra CLI — A stateful command-line interface for binary analysis.

This CLI wraps Ghidra's powerful reverse engineering capabilities into a structured,
agent-friendly interface with JSON output, project state, and REPL mode.

Usage:
    # One-shot commands
    cli-anything-ghidra analyze binary.exe --project /tmp/ghidra_proj
    cli-anything-ghidra decompile binary.exe --function main
    cli-anything-ghidra strings binary.exe
    cli-anything-ghidra functions binary.exe

    # Interactive REPL
    cli-anything-ghidra
"""

import sys
import os
import json
import shlex
import click
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cli_anything.ghidra.core.session import Session
from cli_anything.ghidra.core import analyze as analyze_mod
from cli_anything.ghidra.core import decompile as decomp_mod

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
    """Ghidra CLI — Stateful binary analysis from the command line.

    Run without a subcommand to enter interactive REPL mode.
    """
    global _json_output
    _json_output = use_json

    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


# ── Analysis Commands ──────────────────────────────────────────
@cli.command("analyze")
@click.argument("binary")
@click.option("--project", default=None, help="Ghidra project directory")
@click.option("--script", default=None, help="Post-analysis script path")
@click.option("--timeout", type=int, default=300, help="Analysis timeout (seconds)")
@handle_error
def analyze_cmd(binary, project, script, timeout):
    """Run auto-analysis on a binary."""
    result = analyze_mod.analyze(
        binary, project_dir=project, script=script, timeout=timeout
    )
    output(result)


@cli.command("strings")
@click.argument("binary")
@click.option("--min-length", type=int, default=4, help="Minimum string length")
@handle_error
def strings_cmd(binary, min_length):
    """Extract strings with addresses."""
    result = analyze_mod.strings(binary, min_length=min_length)
    output(result)


@cli.command("imports")
@click.argument("binary")
@handle_error
def imports_cmd(binary):
    """List imported functions."""
    result = analyze_mod.imports(binary)
    output(result)


@cli.command("exports")
@click.argument("binary")
@handle_error
def exports_cmd(binary):
    """List exported functions."""
    result = analyze_mod.exports(binary)
    output(result)


@cli.command("functions")
@click.argument("binary")
@handle_error
def functions_cmd(binary):
    """List all functions with addresses."""
    result = analyze_mod.functions(binary)
    output(result)


@cli.command("xrefs")
@click.argument("binary")
@click.option("--address", required=True, help="Target address (hex)")
@handle_error
def xrefs_cmd(binary, address):
    """Show cross-references to address."""
    result = analyze_mod.xrefs(binary, address)
    output(result)


@cli.command("symbols")
@click.argument("binary")
@handle_error
def symbols_cmd(binary):
    """List symbols."""
    result = analyze_mod.symbols(binary)
    output(result)


@cli.command("headers")
@click.argument("binary")
@handle_error
def headers_cmd(binary):
    """Show PE/ELF header info."""
    result = analyze_mod.headers(binary)
    output(result)


# ── Decompile Commands ──────────────────────────────────────────
@cli.command("decompile")
@click.argument("binary")
@click.option(
    "--function", "func_name", required=True, help="Function name to decompile"
)
@click.option("--output", "-o", default=None, help="Output file path")
@handle_error
def decompile_cmd(binary, func_name, output):
    """Decompile a function to C."""
    result = decomp_mod.decompile(binary, func_name, output=output)
    if output and "c_code" in result:
        output({"status": "success", "output": output}, f"Decompiled to: {output}")
    else:
        output(result)


@cli.command("decompile-all")
@click.argument("binary")
@click.option("--output-dir", "-o", required=True, help="Output directory")
@click.option("--timeout", type=int, default=600, help="Decompilation timeout")
@handle_error
def decompile_all_cmd(binary, output_dir, timeout):
    """Decompile all functions."""
    result = decomp_mod.decompile_all(binary, output_dir, timeout=timeout)
    output(result)


# ── Script Commands ──────────────────────────────────────────────
@cli.group()
def script():
    """Script execution commands."""
    pass


@script.command("run")
@click.argument("script_path")
@click.option("--binary", required=True, help="Target binary")
@click.option("--project", required=True, help="Ghidra project directory")
@handle_error
def script_run(script_path, binary, project):
    """Run a Ghidra script."""
    result = analyze_mod.run_script(binary, project, script_path)
    output(result)


# ── Project Commands ──────────────────────────────────────────────
@cli.group()
def project():
    """Project management commands."""
    pass


@project.command("create")
@click.option("--name", required=True, help="Project name")
@click.option("--project-dir", required=True, help="Project directory")
@handle_error
def project_create(name, project_dir):
    """Create Ghidra project."""
    result = analyze_mod.project_create(name, project_dir)
    output(result)


@project.command("import")
@click.option("--project-dir", required=True, help="Project directory")
@click.option("--binary", required=True, help="Binary to import")
@handle_error
def project_import(project_dir, binary):
    """Import binary into project."""
    result = analyze_mod.project_import(project_dir, binary)
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
    from cli_anything.ghidra.utils.repl_skin import ReplSkin

    global _repl_mode
    _repl_mode = True

    skin = ReplSkin("ghidra", version="1.0.0")
    skin.print_banner()

    pt_session = skin.create_prompt_session()

    _repl_commands = {
        "analyze": "Run auto-analysis on binary",
        "decompile": "Decompile function to C",
        "decompile-all": "Decompile all functions",
        "strings": "Extract strings with addresses",
        "imports": "List imported functions",
        "exports": "List exported functions",
        "functions": "List all functions",
        "xrefs": "Show cross-references",
        "symbols": "List symbols",
        "headers": "Show PE/ELF headers",
        "script": "run — Run Ghidra script",
        "project": "create|import",
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
