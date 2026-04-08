#!/usr/bin/env python3
"""CLI-Anything wrapper for the upstream dify-workflow CLI."""

from __future__ import annotations

import shlex
import sys

import click

from cli_anything.dify_workflow import __version__
from cli_anything.dify_workflow.utils.dify_workflow_backend import run_dify_workflow
from cli_anything.dify_workflow.utils.repl_skin import ReplSkin

PASS_ARGS = {
    "ignore_unknown_options": True,
    "allow_extra_args": True,
}


def _configure_stdio() -> None:
    """Prefer UTF-8 stdio so forwarded output stays readable on Windows."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8")
        except ValueError:
            pass


_configure_stdio()


def _emit(output: str) -> None:
    if output:
        click.echo(output)


def _forward(*prefix: str) -> None:
    try:
        output = run_dify_workflow([*prefix, *list(click.get_current_context().args)])
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc
    _emit(output)


@click.group(invoke_without_command=True, context_settings=PASS_ARGS)
@click.version_option(version=__version__, prog_name="cli-anything-dify-workflow")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """CLI-Anything wrapper for the Dify workflow DSL editor."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


@cli.command()
def repl() -> None:
    """Start a lightweight forwarding REPL."""
    skin = ReplSkin("dify_workflow", version=__version__)
    skin.print_banner()
    skin.info("Type upstream dify-workflow commands without the binary name.")
    skin.info("Examples: guide | list-node-types | create -o app.yaml --template llm")
    skin.hint("Type help for wrapper commands, quit to exit.")

    commands = {
        "guide": "Show the upstream tutorial",
        "list-node-types": "List supported Dify node types",
        "create": "Create a new Dify app",
        "inspect": "Inspect a workflow file",
        "validate": "Validate a workflow file",
        "edit": "Workflow graph mutation commands",
        "config": "Model config mutation commands",
        "export": "Export YAML or JSON",
        "import": "Import and normalize a workflow file",
        "diff": "Compare two workflow files",
        "layout": "Auto-layout nodes",
    }

    pt_session = skin.create_prompt_session()
    while True:
        try:
            line = skin.get_input(pt_session, context="dify")
        except (EOFError, KeyboardInterrupt):
            skin.print_goodbye()
            return

        if not line:
            continue
        if line in {"quit", "exit"}:
            skin.print_goodbye()
            return
        if line == "help":
            skin.help(commands)
            continue

        try:
            output = run_dify_workflow(shlex.split(line))
        except RuntimeError as exc:
            skin.error(str(exc))
            continue
        if output:
            click.echo(output)


@cli.command(context_settings=PASS_ARGS)
def guide() -> None:
    """Forward to dify-workflow guide."""
    _forward("guide")


@cli.command("list-node-types", context_settings=PASS_ARGS)
def list_node_types() -> None:
    """Forward to dify-workflow list-node-types."""
    _forward("list-node-types")


@cli.command(context_settings=PASS_ARGS)
def create() -> None:
    """Forward to dify-workflow create."""
    _forward("create")


@cli.command(context_settings=PASS_ARGS)
def inspect() -> None:
    """Forward to dify-workflow inspect."""
    _forward("inspect")


@cli.command(context_settings=PASS_ARGS)
def validate() -> None:
    """Forward to dify-workflow validate."""
    _forward("validate")


@cli.command(context_settings=PASS_ARGS)
def checklist() -> None:
    """Forward to dify-workflow checklist."""
    _forward("checklist")


@cli.command(context_settings=PASS_ARGS)
def export() -> None:
    """Forward to dify-workflow export."""
    _forward("export")


@cli.command("import", context_settings=PASS_ARGS)
def import_cmd() -> None:
    """Forward to dify-workflow import."""
    _forward("import")


@cli.command(context_settings=PASS_ARGS)
def diff() -> None:
    """Forward to dify-workflow diff."""
    _forward("diff")


@cli.command(context_settings=PASS_ARGS)
def layout() -> None:
    """Forward to dify-workflow layout."""
    _forward("layout")


@cli.group(context_settings=PASS_ARGS)
def edit() -> None:
    """Workflow graph editing commands."""


@edit.command("add-node", context_settings=PASS_ARGS)
def edit_add_node() -> None:
    _forward("edit", "add-node")


@edit.command("remove-node", context_settings=PASS_ARGS)
def edit_remove_node() -> None:
    _forward("edit", "remove-node")


@edit.command("update-node", context_settings=PASS_ARGS)
def edit_update_node() -> None:
    _forward("edit", "update-node")


@edit.command("add-edge", context_settings=PASS_ARGS)
def edit_add_edge() -> None:
    _forward("edit", "add-edge")


@edit.command("remove-edge", context_settings=PASS_ARGS)
def edit_remove_edge() -> None:
    _forward("edit", "remove-edge")


@edit.command("set-title", context_settings=PASS_ARGS)
def edit_set_title() -> None:
    _forward("edit", "set-title")


@cli.group(context_settings=PASS_ARGS)
def config() -> None:
    """Chat/agent/completion config commands."""


@config.command("set-model", context_settings=PASS_ARGS)
def config_set_model() -> None:
    _forward("config", "set-model")


@config.command("set-prompt", context_settings=PASS_ARGS)
def config_set_prompt() -> None:
    _forward("config", "set-prompt")


@config.command("add-variable", context_settings=PASS_ARGS)
def config_add_variable() -> None:
    _forward("config", "add-variable")


@config.command("set-opening", context_settings=PASS_ARGS)
def config_set_opening() -> None:
    _forward("config", "set-opening")


@config.command("add-question", context_settings=PASS_ARGS)
def config_add_question() -> None:
    _forward("config", "add-question")


@config.command("add-tool", context_settings=PASS_ARGS)
def config_add_tool() -> None:
    _forward("config", "add-tool")


@config.command("remove-tool", context_settings=PASS_ARGS)
def config_remove_tool() -> None:
    _forward("config", "remove-tool")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
