"""Agent-friendly command line interface for the native COPT solver."""

import json
from pathlib import Path
import shlex

import click

from cli_anything.copt.core import backend
from cli_anything.copt.utils.repl_skin import ReplSkin


def _emit(ctx, data):
    if ctx.obj["json"]:
        click.echo(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        for key, value in data.items():
            if key == "attributes":
                for attribute, number in value.items():
                    click.echo(f"{attribute}: {number}")
            elif value is not None:
                click.echo(f"{key}: {value}")


def _call(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except backend.CoptError as exc:
        raise click.ClickException(str(exc)) from exc


@click.group(invoke_without_command=True)
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON")
@click.pass_context
def cli(ctx, as_json):
    """Control the installed COPT solver with structured commands."""
    ctx.ensure_object(dict)
    ctx.obj["json"] = as_json
    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


@cli.command()
@click.pass_context
def doctor(ctx):
    """Check the solver executable and license startup."""
    _emit(ctx, _call(backend.doctor))


@cli.group()
def model():
    """Inspect or convert model files."""


@model.command()
@click.argument("model_path", type=click.Path(path_type=Path))
@click.pass_context
def inspect(ctx, model_path):
    """Report dimensions and type of an LP or MPS model."""
    actions = [f"get {name}" for name in ("Rows", "Cols", "Elems", "IsMIP", "Bins", "Ints")]
    result = _call(backend.run_model, model_path, actions)
    _emit(ctx, {"model": result["model"], "attributes": result["attributes"]})


@model.command()
@click.argument("model_path", type=click.Path(path_type=Path))
@click.option("--output", "output_path", required=True, type=click.Path(path_type=Path))
@click.pass_context
def convert(ctx, model_path, output_path):
    """Convert a model to .lp or .mps using COPT."""
    suffix = output_path.suffix.lower()
    if suffix not in (".lp", ".mps"):
        raise click.ClickException("Output must end in .lp or .mps")
    command = "writelp" if suffix == ".lp" else "writemps"
    result = _call(backend.run_model, model_path, [], output_path=output_path, output_command=command)
    _emit(ctx, {"model": result["model"], "output": result["output"], "format": suffix[1:]})


@cli.command()
@click.argument("model_path", type=click.Path(path_type=Path))
@click.option("--time-limit", type=float, help="COPT TimeLimit in seconds")
@click.option("--threads", type=int, help="COPT Threads")
@click.option("--rel-gap", type=float, help="COPT RelGap, 0 to 1")
@click.option("--lp-relaxation", is_flag=True, help="Run optimizelp")
@click.option("--solution", type=click.Path(path_type=Path), help="Export .json solution")
@click.pass_context
def solve(ctx, model_path, time_limit, threads, rel_gap, lp_relaxation, solution):
    """Optimize a model and optionally export a JSON solution."""
    if solution and solution.suffix.lower() != ".json":
        raise click.ClickException("Solution output must end in .json")
    actions = _call(backend.validate_parameters, time_limit=time_limit, threads=threads, rel_gap=rel_gap)
    actions.append("optimizelp" if lp_relaxation else "optimize")
    actions.extend(f"get {name}" for name in (
        "IsMIP", "LpStatus", "MipStatus", "HasLpSol", "HasMipSol", "LpObjval", "BestObj", "BestBnd", "BestGap", "SolvingTime"
    ))
    result = _call(
        backend.run_model, model_path, actions, output_path=solution,
        output_command="writejsonsol" if solution else None,
    )
    attributes = result["attributes"]
    is_mip = bool(attributes.get("IsMIP")) and not lp_relaxation
    prefix = "Mip" if is_mip else "Lp"
    has_solution = bool(attributes.get("HasMipSol" if is_mip else "HasLpSol"))
    data = {
        "model": result["model"],
        "status": attributes.get(prefix + "StatusText", "unknown"),
        "status_code": attributes.get(prefix + "Status"),
        "objective": attributes.get("BestObj" if is_mip else "LpObjval") if has_solution else None,
        "attributes": attributes,
    }
    if solution:
        data["output"] = result["output"]
    _emit(ctx, data)


@cli.group()
def diagnose():
    """Diagnose solver results."""


@diagnose.command()
@click.argument("model_path", type=click.Path(path_type=Path))
@click.option("--output", "output_path", required=True, type=click.Path(path_type=Path))
@click.pass_context
def iis(ctx, model_path, output_path):
    """Compute an irreducible infeasible subsystem and write .iis."""
    if output_path.suffix.lower() != ".iis":
        raise click.ClickException("IIS output must end in .iis")
    result = _call(
        backend.run_model, model_path,
        ["optimize", "iis", "get IISRows", "get IISCols"],
        output_path=output_path, output_command="writeiis",
    )
    _emit(ctx, {"model": result["model"], "output": result["output"], "attributes": result["attributes"]})


@cli.command()
def repl():
    """Start an interactive prompt for the same commands."""
    skin = ReplSkin("copt", version="1.0.0")
    skin.print_banner()
    skin.help({"doctor": "check COPT", "model inspect PATH": "model dimensions",
               "model convert PATH --output PATH": "convert format",
               "solve PATH": "solve model", "diagnose iis PATH --output PATH": "export IIS",
               "exit": "leave the prompt"})
    prompt = skin.create_prompt_session()
    while True:
        try:
            line = skin.get_input(prompt)
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            continue
        if line.lower() in ("exit", "quit"):
            break
        if line.lower() == "help":
            click.echo(cli.get_help(click.Context(cli)))
            continue
        try:
            cli.main(args=shlex.split(line), standalone_mode=False)
        except (click.ClickException, click.UsageError, ValueError) as exc:
            skin.error(str(exc))
    skin.print_goodbye()


main = cli


if __name__ == "__main__":
    main()
