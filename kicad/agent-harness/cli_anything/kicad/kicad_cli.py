"""KiCad command line and interactive shell."""

import json
import os
import shlex
from dataclasses import dataclass
from functools import wraps
from pathlib import Path

import click
from click.core import ParameterSource

from cli_anything.kicad import __version__
from cli_anything.kicad.backend import (
    KiCadError,
    electrical_rule_check,
    export_fabrication,
    find_binary,
)


@dataclass
class Options:
    binary: str | None
    as_json: bool


def workflow(function):
    """Run a workflow and preserve its exit status in both entry points."""
    @click.pass_obj
    @wraps(function)
    def invoke(options, *args, **kwargs):
        try:
            data, status = function(find_binary(options.binary), *args, **kwargs)
        except (KiCadError, OSError) as error:
            if not options.as_json:
                raise click.ClickException(str(error)) from error
            click.echo(json.dumps({"error": str(error)}, ensure_ascii=False))
            raise click.exceptions.Exit(1) from error
        click.echo(json.dumps(data, ensure_ascii=False, indent=None if options.as_json else 2))
        if status:
            raise click.exceptions.Exit(status)

    return invoke


@click.group(invoke_without_command=True)
@click.option("--binary", envvar="KICAD_CLI", help="Path to the native kicad-cli executable.")
@click.option("--json", "as_json", is_flag=True, help="Print compact JSON.")
@click.version_option(__version__)
@click.pass_context
def cli(ctx, binary, as_json):
    """Run headless KiCad checks and fabrication exports."""
    if ctx.obj is None:
        ctx.obj = Options(binary, as_json)
    else:
        if ctx.get_parameter_source("binary") is ParameterSource.COMMANDLINE:
            raise click.UsageError("Set --binary when starting the REPL.")
        if ctx.invoked_subcommand is None:
            raise click.UsageError("Enter a command or type exit.")
        ctx.obj = Options(ctx.obj.binary, ctx.obj.as_json or as_json)
    if ctx.invoked_subcommand is None:
        repl(ctx.obj)


@cli.group()
def sch():
    """Schematic checks."""


@sch.command()
@click.argument("schematic", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@workflow
def lint(binary, schematic):
    """Run electrical rule checks and return the native report."""
    report, status = electrical_rule_check(binary, schematic)
    return {"exit_code": status, "report": report}, status


@cli.group()
def pcb():
    """Board fabrication outputs."""


@pcb.command("export-fab")
@click.argument("board", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--schematic", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path),
              help="Schematic to use as the source for the BOM.")
@click.option("--output", required=True, type=click.Path(dir_okay=False, path_type=Path),
              help="Path for a new fabrication ZIP archive.")
@click.option("--layers", help="Comma-separated Gerber layers. Defaults to KiCad's selection.")
@workflow
def export_fab(binary, board, schematic, output, layers):
    """Package Gerbers, drill files, placements, and a BOM into one ZIP."""
    files = export_fabrication(binary, board, schematic, output, layers)
    return {"archive": str(output), "files": files}, 0


def repl(options):
    from cli_anything.kicad.utils.repl_skin import ReplSkin

    skin = ReplSkin("kicad", version=__version__)
    skin.print_banner()
    prompt = skin.create_prompt_session()
    while True:
        try:
            lexer = shlex.shlex(skin.get_input(prompt), posix=True)
            lexer.whitespace_split = True
            lexer.commenters = ""
            if os.name == "nt":
                lexer.escape = ""
            args = list(lexer)
            if args in (["exit"], ["quit"], ["q"]):
                return
            if args:
                cli.main(args, standalone_mode=False, obj=options)
        except (EOFError, KeyboardInterrupt):
            return
        except click.ClickException as error:
            error.show()
        except ValueError as error:
            click.echo(str(error), err=True)


def main():
    cli()


if __name__ == "__main__":
    main()
