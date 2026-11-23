"""cli-anything-ghidra - CLI harness for Ghidra (headless reverse engineering)."""

import json
import shlex
import sys

import click

from cli_anything.ghidra.core import analysis as analysis_core
from cli_anything.ghidra.core import queries as queries_core
from cli_anything.ghidra.utils.ghidra_backend import GhidraBackend
from cli_anything.ghidra.utils.repl_skin import ReplSkin

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}
VERSION = "1.0.0"


def make_backend(ctx: click.Context) -> GhidraBackend:
    return GhidraBackend()


def output(data, as_json: bool) -> None:
    if as_json:
        click.echo(json.dumps(data, indent=2, default=str))
    elif isinstance(data, dict):
        for k, v in data.items():
            click.echo(f"{k}: {v}")
    elif isinstance(data, list):
        for item in data:
            click.echo(json.dumps(item, default=str) if isinstance(item, dict) else str(item))
    else:
        click.echo(str(data))


# ---------------------------------------------------------------------------
# Root group
# ---------------------------------------------------------------------------

@click.group(context_settings=CONTEXT_SETTINGS, invoke_without_command=True)
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON")
@click.pass_context
def cli(ctx: click.Context, as_json: bool):
    """cli-anything-ghidra - analyze binaries with Ghidra from the command line.

    Needs Ghidra 12.x (set GHIDRA_INSTALL_DIR) and a JDK 25+ (GHIDRA_JAVA_HOME).
    The target binary is read and copied, never executed.
    """
    ctx.ensure_object(dict)
    ctx.obj["as_json"] = as_json
    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


def main():
    try:
        cli(obj={})
    except RuntimeError as exc:
        # Backend failures arrive as exceptions; surface them as parsable JSON with --json.
        # sys.argv is used because the Click context is already unwound here.
        if "--json" in sys.argv:
            click.echo(json.dumps({"error": str(exc)}, default=str))
        else:
            click.echo(str(exc), err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# REPL
# ---------------------------------------------------------------------------

@cli.command(hidden=True)
@click.pass_context
def repl(ctx: click.Context):
    """Interactive REPL mode."""
    skin = ReplSkin("ghidra", version=VERSION)
    skin.print_banner()
    pt_session = skin.create_prompt_session()

    while True:
        try:
            line = skin.get_input(pt_session, project_name="ghidra")
        except (EOFError, KeyboardInterrupt):
            break

        line = line.strip()
        if not line:
            continue
        if line in ("exit", "quit"):
            break
        if line == "help":
            skin.help({
                "analyze BINARY": "Import and analyze (run once per binary)",
                "info BINARY": "Format, language, function count",
                "functions BINARY": "List functions",
                "decompile BINARY TARGET": "Decompile a function (name or address)",
                "strings BINARY": "Defined strings",
                "imports BINARY": "External symbols",
                "xrefs BINARY TARGET": "References to an address or symbol",
            })
            continue

        try:
            cli.main(args=shlex.split(line), obj=dict(ctx.obj), standalone_mode=False)
        except click.exceptions.UsageError as e:
            skin.error(str(e))
        except RuntimeError as e:
            skin.error(str(e))
        except SystemExit:
            pass
        except Exception as e:
            skin.error(f"Unexpected error: {e}")

    skin.print_goodbye()


# ---------------------------------------------------------------------------
# analyze / info
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("binary", type=click.Path(dir_okay=False))
@click.option("--loader", default=None, help="Ghidra loader, e.g. BinaryLoader for raw firmware")
@click.option("--processor", default=None, help="Language ID, e.g. x86:LE:64:default (needed for raw binaries)")
@click.option("--entry", default=None, help="Create a function at this address (raw binaries have no entry point)")
@click.option("--timeout", default=600, show_default=True, type=click.IntRange(10, 86400),
              help="Analysis timeout in seconds")
@click.pass_context
def analyze(ctx: click.Context, binary: str, loader, processor, entry, timeout: int):
    """Import and analyze BINARY into a Ghidra project (the binary is never executed)."""
    output(analysis_core.analyze(make_backend(ctx), binary, loader, processor, entry, timeout), ctx.obj["as_json"])


@cli.command()
@click.argument("binary", type=click.Path(dir_okay=False))
@click.pass_context
def info(ctx: click.Context, binary: str):
    """Show format, language, image base and function count."""
    output(analysis_core.info(make_backend(ctx), binary), ctx.obj["as_json"])


# ---------------------------------------------------------------------------
# queries
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("binary", type=click.Path(dir_okay=False))
@click.option("--filter", "name_filter", default=None, help="Only names containing this text")
@click.option("--limit", default=0, show_default=True, type=click.IntRange(0, 100000), help="0 = no limit")
@click.pass_context
def functions(ctx: click.Context, binary: str, name_filter, limit: int):
    """List functions (name, address, size)."""
    output(queries_core.list_functions(make_backend(ctx), binary, name_filter, limit), ctx.obj["as_json"])


@cli.command()
@click.argument("binary", type=click.Path(dir_okay=False))
@click.argument("target")
@click.pass_context
def decompile(ctx: click.Context, binary: str, target: str):
    """Decompile TARGET (function name or address) to C."""
    result = queries_core.decompile(make_backend(ctx), binary, target)
    if ctx.obj["as_json"]:
        output(result, True)
    else:
        click.echo(result["c"].strip())


@cli.command()
@click.argument("binary", type=click.Path(dir_okay=False))
@click.option("--min-length", default=4, show_default=True, type=click.IntRange(1, 10000))
@click.option("--limit", default=0, show_default=True, type=click.IntRange(0, 100000), help="0 = no limit")
@click.pass_context
def strings(ctx: click.Context, binary: str, min_length: int, limit: int):
    """List defined strings."""
    output(queries_core.list_strings(make_backend(ctx), binary, min_length, limit), ctx.obj["as_json"])


@cli.command()
@click.argument("binary", type=click.Path(dir_okay=False))
@click.pass_context
def imports(ctx: click.Context, binary: str):
    """List imported (external) symbols."""
    output(queries_core.list_imports(make_backend(ctx), binary), ctx.obj["as_json"])


@cli.command()
@click.argument("binary", type=click.Path(dir_okay=False))
@click.argument("target")
@click.pass_context
def xrefs(ctx: click.Context, binary: str, target: str):
    """List references to TARGET (symbol or address)."""
    output(queries_core.xrefs(make_backend(ctx), binary, target), ctx.obj["as_json"])


if __name__ == "__main__":
    main()
