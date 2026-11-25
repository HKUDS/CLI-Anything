"""CLI entry point for Flowise chatflow management and execution."""

import json
import os
import shlex
from dataclasses import dataclass
from functools import wraps
from pathlib import Path

import click
from click.core import ParameterSource

from cli_anything.flowise import __version__
from cli_anything.flowise.backend import Flowise, FlowiseError, parse_graph, read_graph


@dataclass
class Session:
    backend: Flowise
    as_json: bool


def emit(data, *, as_json: bool) -> None:
    click.echo(json.dumps(data, ensure_ascii=False, indent=None if as_json else 2))


def operation(function):
    """Use the same result and error handling in one-shot commands and the REPL."""
    @click.pass_obj
    @wraps(function)
    def run(session, *args, **kwargs):
        try:
            result = function(session.backend, *args, **kwargs)
        except FlowiseError as error:
            if session.as_json:
                emit({"error": str(error)}, as_json=True)
                raise click.exceptions.Exit(1) from error
            raise click.ClickException(str(error)) from error
        emit(result, as_json=session.as_json)

    return run


@click.group(invoke_without_command=True)
@click.option("--url", envvar="FLOWISE_URL", default="http://127.0.0.1:3000", show_default=True)
@click.option("--json", "as_json", is_flag=True, help="Output compact JSON.")
@click.version_option(__version__)
@click.pass_context
def cli(ctx, url, as_json):
    """Manage and run workflows on a Flowise server."""
    if ctx.obj is not None:
        if ctx.get_parameter_source("url") is ParameterSource.COMMANDLINE:
            raise click.UsageError("Set --url when starting the REPL.")
        if ctx.invoked_subcommand in (None, "repl"):
            raise click.UsageError("Enter a Flowise command or type exit.")
        ctx.obj = Session(ctx.obj.backend, ctx.obj.as_json or as_json)
    else:
        try:
            backend = Flowise(url, os.getenv("FLOWISE_API_KEY"), os.getenv("FLOWISE_PREDICTION_KEY"))
        except FlowiseError as error:
            if as_json:
                emit({"error": str(error)}, as_json=True)
                ctx.exit(1)
            raise click.ClickException(str(error)) from error
        ctx.obj = Session(backend, as_json)
    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


@cli.group()
def flow():
    """List, export, configure and deploy graphs."""


@flow.command("list")
@operation
def list_flows(backend):
    """List the flows available to the account."""
    return backend.list_flows()


@flow.command("show")
@click.argument("flow_id")
@operation
def show_flow(backend, flow_id):
    """Show the flow definition and deployment state."""
    return backend.get_flow(flow_id)


@flow.command("create")
@click.argument("name")
@click.argument("graph", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--type", "flow_type", type=click.Choice(["CHATFLOW", "AGENTFLOW", "MULTIAGENT"]),
              default="CHATFLOW", show_default=True)
@operation
def create_flow(backend, name, graph, flow_type):
    """Create a flow from an exported graph JSON file."""
    return backend.create_flow(name, read_graph(graph), flow_type)


@flow.command("update")
@click.argument("flow_id")
@click.option("--name")
@click.option("--graph", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@operation
def update_flow(backend, flow_id, name, graph):
    """Replace a flow's graph, change its name, or do both."""
    changes = {}
    if name is not None:
        changes["name"] = name
    if graph is not None:
        changes["flowData"] = json.dumps(read_graph(graph))
    if not changes:
        raise FlowiseError("Supply --name, --graph, or both.")
    return backend.update_flow(flow_id, changes)


@flow.command("export")
@click.argument("flow_id")
@operation
def export_flow(backend, flow_id):
    """Write the portable graph JSON to stdout."""
    definition = backend.get_flow(flow_id)
    try:
        contents = definition["flowData"]
    except (KeyError, TypeError) as error:
        raise FlowiseError("Flowise did not return flowData.") from error
    return parse_graph(contents)


@flow.command("deploy")
@click.argument("flow_id")
@click.option("--enable/--disable", default=True)
@operation
def deploy_flow(backend, flow_id, enable):
    """Set Flowise's deployed flag for an existing flow."""
    return backend.update_flow(flow_id, {"deployed": enable})


@cli.command()
@click.argument("flow_id")
@click.option("--question", required=True, help="Question to send to the flow.")
@operation
def predict(backend, flow_id, question):
    """Run a flow through Flowise's prediction endpoint."""
    return backend.predict(flow_id, question)


@cli.command()
@click.pass_obj
def repl(session):
    """Run commands interactively against the server selected at startup."""
    from cli_anything.flowise.utils.repl_skin import ReplSkin

    skin = ReplSkin("flowise", version=__version__)
    skin.print_banner()
    prompt = skin.create_prompt_session()

    while True:
        try:
            args = shlex.split(skin.get_input(prompt))
            if args in (["q"], ["quit"], ["exit"]):
                break
            if args:
                cli.main(args, standalone_mode=False, obj=session)
        except (EOFError, KeyboardInterrupt):
            break
        except click.ClickException as error:
            error.show()
        except ValueError as error:
            click.echo(str(error), err=True)


def main():
    cli()


if __name__ == "__main__":
    main()
