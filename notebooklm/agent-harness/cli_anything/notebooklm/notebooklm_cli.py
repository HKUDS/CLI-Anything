#!/usr/bin/env python3
"""NotebookLM CLI — Experimental NotebookLM wrapper for AI agents."""

from __future__ import annotations

import json
import sys

import click

from cli_anything.notebooklm import __version__
from cli_anything.notebooklm.core.session import Session
from cli_anything.notebooklm.utils.notebooklm_backend import run_notebooklm

_json_output = False
_session: Session | None = None


def get_session() -> Session:
    global _session
    if _session is None:
        _session = Session()
    return _session


def emit(data, message: str = ""):
    if _json_output:
        click.echo(json.dumps(data, indent=2, default=str))
    elif message:
        click.echo(message)
    elif isinstance(data, str):
        click.echo(data)
    else:
        click.echo(json.dumps(data, indent=2, default=str))


def handle_error(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as exc:  # pragma: no cover - scaffold behavior
            if _json_output:
                click.echo(json.dumps({"error": str(exc), "type": type(exc).__name__}))
            else:
                click.echo(f"Error: {exc}", err=True)
            sys.exit(1)

    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


def resolve_notebook_id(notebook_id: str | None) -> str | None:
    return notebook_id or get_session().get_active_notebook()


@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, help="Output as JSON")
@click.option("--notebook", "notebook_id", default=None, help="Active notebook ID")
@click.pass_context
def cli(ctx, use_json, notebook_id):
    """NotebookLM CLI — Experimental NotebookLM wrapper for AI agents."""
    global _json_output
    _json_output = use_json
    if notebook_id:
        get_session().set_active_notebook(notebook_id)
    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


@cli.command()
def repl():
    """Start a minimal REPL placeholder."""
    click.echo(f"cli-anything-notebooklm v{__version__}")
    click.echo("Experimental harness scaffold. Use --help to inspect command groups.")


@cli.group()
def auth():
    """Authentication and login helpers."""


@auth.command("status")
@handle_error
def auth_status():
    """Check authentication status."""
    emit(run_notebooklm(["auth", "check"], json_output=_json_output))


@auth.command("login")
@handle_error
def auth_login():
    """Open the browser login flow."""
    emit(run_notebooklm(["login"], json_output=_json_output))


@auth.command("check")
@handle_error
def auth_check():
    """Run a lightweight authentication check."""
    emit(run_notebooklm(["auth", "check"], json_output=_json_output))


@cli.group()
def notebook():
    """Notebook management commands."""


@notebook.command("list")
@handle_error
def notebook_list():
    """List notebooks."""
    emit(run_notebooklm(["list"], json_output=_json_output))


@notebook.command("create")
@click.argument("name")
@handle_error
def notebook_create(name):
    """Create a notebook."""
    emit(run_notebooklm(["create", name], json_output=_json_output))


@notebook.command("summary")
@handle_error
def notebook_summary():
    """Summarize the active notebook."""
    emit(
        run_notebooklm(
            ["summary"],
            notebook_id=resolve_notebook_id(None),
            json_output=_json_output,
        )
    )


@cli.group()
def source():
    """Source ingestion and inspection commands."""


@source.command("list")
@click.option("--notebook", "notebook_id", default=None, help="Notebook ID")
@handle_error
def source_list(notebook_id):
    """List sources for a notebook."""
    emit(
        run_notebooklm(
            ["source", "list"],
            notebook_id=resolve_notebook_id(notebook_id),
            json_output=_json_output,
        )
    )


@source.command("add-url")
@click.argument("url")
@click.option("--notebook", "notebook_id", default=None, help="Notebook ID")
@handle_error
def source_add_url(url, notebook_id):
    """Add a URL source."""
    emit(
        run_notebooklm(
            ["source", "add", url],
            notebook_id=resolve_notebook_id(notebook_id),
            json_output=_json_output,
        )
    )


@cli.group()
def chat():
    """Chat and history commands."""


@chat.command("ask")
@click.argument("prompt")
@click.option("--notebook", "notebook_id", default=None, help="Notebook ID")
@handle_error
def chat_ask(prompt, notebook_id):
    """Ask a question against a notebook."""
    emit(
        run_notebooklm(
            ["ask", prompt],
            notebook_id=resolve_notebook_id(notebook_id),
            json_output=_json_output,
        )
    )


@chat.command("history")
@click.option("--notebook", "notebook_id", default=None, help="Notebook ID")
@handle_error
def chat_history(notebook_id):
    """Show chat history."""
    emit(
        run_notebooklm(
            ["history"],
            notebook_id=resolve_notebook_id(notebook_id),
            json_output=_json_output,
        )
    )


@cli.group()
def artifact():
    """Artifact generation and inspection commands."""


@artifact.command("list")
@click.option("--notebook", "notebook_id", default=None, help="Notebook ID")
@handle_error
def artifact_list(notebook_id):
    """List notebook artifacts."""
    emit(
        run_notebooklm(
            ["artifact", "list"],
            notebook_id=resolve_notebook_id(notebook_id),
            json_output=_json_output,
        )
    )


@artifact.command("generate-report")
@click.option("--notebook", "notebook_id", default=None, help="Notebook ID")
@handle_error
def artifact_generate_report(notebook_id):
    """Generate a report artifact."""
    emit(
        run_notebooklm(
            ["generate", "report", "--wait"],
            notebook_id=resolve_notebook_id(notebook_id),
            json_output=_json_output,
        )
    )


@cli.group()
def download():
    """Artifact download helpers."""


@download.command("report")
@click.argument("output_path")
@click.option("--notebook", "notebook_id", default=None, help="Notebook ID")
@handle_error
def download_report(output_path, notebook_id):
    """Download the latest report artifact."""
    emit(
        run_notebooklm(
            ["download", "report", output_path],
            notebook_id=resolve_notebook_id(notebook_id),
            json_output=_json_output,
        )
    )


@cli.group()
def share():
    """Sharing and access control commands."""


@share.command("status")
@click.option("--notebook", "notebook_id", default=None, help="Notebook ID")
@handle_error
def share_status(notebook_id):
    """Inspect notebook sharing state."""
    emit(
        run_notebooklm(
            ["share", "status"],
            notebook_id=resolve_notebook_id(notebook_id),
            json_output=_json_output,
        )
    )


def main():
    cli()


if __name__ == "__main__":
    main()
