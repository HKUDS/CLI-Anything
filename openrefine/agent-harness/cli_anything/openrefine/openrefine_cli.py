from __future__ import annotations

import json
import os
import shlex
import sys
import tempfile
from pathlib import Path
from typing import Any

import click

from . import __version__
from .core.operations import column_addition, column_removal, mass_edit, save_operations, text_transform
from .core.project import OpenRefineService
from .core.session import SessionStore
from .utils.openrefine_backend import OpenRefineBackend, OpenRefineError, start_openrefine
from .utils.repl_skin import ReplSkin


def _service(ctx: click.Context) -> OpenRefineService:
    store = SessionStore(ctx.obj["session"])
    base_url = store.effective_base_url(ctx.obj["base_url"])
    ctx.obj["effective_base_url"] = base_url
    return OpenRefineService(OpenRefineBackend(base_url, timeout=ctx.obj["timeout"]), store)


def _emit(data: Any, as_json: bool) -> None:
    if as_json:
        click.echo(json.dumps(data, indent=2, sort_keys=True))
    elif isinstance(data, dict):
        for key, value in data.items():
            click.echo(f"{key}: {value}")
    else:
        click.echo(str(data))


def _handle(ctx: click.Context, func, *args, **kwargs) -> None:
    try:
        _emit(func(*args, **kwargs), ctx.obj["json"])
    except (OpenRefineError, ValueError, OSError) as exc:
        if ctx.obj["json"]:
            click.echo(json.dumps({"error": str(exc), "ok": False}, indent=2, sort_keys=True), err=True)
        else:
            click.echo(f"Error: {exc}", err=True)
        raise click.exceptions.Exit(1)


@click.group(invoke_without_command=True)
@click.option("--base-url", default=None, help="OpenRefine URL. Defaults to OPENREFINE_URL, then session state, then http://127.0.0.1:3333.")
@click.option("--session", "session_path", type=click.Path(dir_okay=False), default=None, help="Session JSON path.")
@click.option("--timeout", type=float, default=30.0, show_default=True)
@click.option("--json", "json_output", is_flag=True, help="Emit machine-readable JSON.")
@click.version_option(__version__)
@click.pass_context
def cli(ctx: click.Context, base_url: str, session_path: str | None, timeout: float, json_output: bool) -> None:
    """Agent-native CLI for OpenRefine's local HTTP API."""
    ctx.ensure_object(dict)
    requested_base_url = base_url or os.environ.get("OPENREFINE_URL")
    ctx.obj.update({"base_url": requested_base_url, "session": session_path, "timeout": timeout, "json": json_output})
    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


@cli.command()
@click.pass_context
def repl(ctx: click.Context) -> None:
    """Start the interactive REPL."""
    history_file = _repl_history_file(ctx)
    skin = ReplSkin("openrefine", version=__version__, history_file=history_file)
    skin.print_banner()
    prompt = skin.create_prompt_session()
    commands = {
        "status": "Check backend and session",
        "projects": "List OpenRefine projects",
        "import <path> [name]": "Create a project from a local data file",
        "open <project_id>": "Select an existing project",
        "rows [limit]": "Show rows for current project",
        "export <path> [format]": "Export rows from current project",
        "undo / redo": "Use OpenRefine undo-redo where possible",
        "exit": "Quit",
    }
    while True:
        try:
            state = SessionStore(ctx.obj["session"]).load()
            line = skin.get_input(prompt, project_name=state.project_name)
        except (EOFError, KeyboardInterrupt):
            skin.print_goodbye()
            return
        try:
            parts = shlex.split(line)
        except (IndexError, ValueError) as exc:
            skin.error(str(exc))
            continue
        if not parts:
            continue
        try:
            args = _repl_to_args(parts)
        except (IndexError, ValueError) as exc:
            skin.error(str(exc))
            continue
        if parts[0] in {"exit", "quit"}:
            skin.print_goodbye()
            return
        if parts[0] == "help":
            skin.help(commands)
            continue
        try:
            cli.main(args=_global_args(ctx) + args, prog_name="cli-anything-openrefine", obj=ctx.obj, standalone_mode=False)
        except SystemExit:
            pass
        except Exception as exc:
            skin.error(str(exc))


def _repl_to_args(parts: list[str]) -> list[str]:
    command = parts[0]
    if command == "projects":
        return ["project", "list"]
    if command == "import":
        if len(parts) < 2:
            raise ValueError("Usage: import <path> [name]")
        args = ["project", "import", parts[1]]
        if len(parts) > 2:
            args.extend(["--name", parts[2]])
        return args
    if command == "open":
        if len(parts) < 2:
            raise ValueError("Usage: open <project_id>")
        return ["project", "open", parts[1]]
    if command == "rows":
        return ["data", "rows", "--limit", parts[1] if len(parts) > 1 else "10"]
    if command == "export":
        if len(parts) < 2:
            raise ValueError("Usage: export <path> [format]")
        args = ["data", "export", parts[1]]
        if len(parts) > 2:
            args.extend(["--format", parts[2]])
        return args
    if command in {"status", "undo", "redo"}:
        return ["session", command] if command in {"undo", "redo"} else ["status"]
    return parts


def _global_args(ctx: click.Context) -> list[str]:
    args: list[str] = []
    base_url = ctx.obj.get("effective_base_url") or ctx.obj.get("base_url")
    if base_url:
        args.extend(["--base-url", str(base_url)])
    if ctx.obj.get("session"):
        args.extend(["--session", str(ctx.obj["session"])])
    if ctx.obj.get("timeout") is not None:
        args.extend(["--timeout", str(ctx.obj["timeout"])])
    if ctx.obj.get("json"):
        args.append("--json")
    return args


def _repl_history_file(ctx: click.Context) -> str:
    if ctx.obj.get("session"):
        return str(Path(ctx.obj["session"]).expanduser().with_name("history"))
    return str(Path(tempfile.gettempdir()) / "cli-anything-openrefine-history")


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show backend health and current session."""
    _handle(ctx, lambda: _service(ctx).status())


@cli.group()
def server() -> None:
    """Start or inspect an OpenRefine backend."""


@server.command("start")
@click.option("--port", default=3333, show_default=True)
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--data-dir", type=click.Path(file_okay=False))
@click.pass_context
def server_start(ctx: click.Context, port: int, host: str, data_dir: str | None) -> None:
    _handle(ctx, lambda: {"pid": start_openrefine(port=port, host=host, data_dir=data_dir).pid, "host": host, "port": port})


@server.command("ping")
@click.pass_context
def server_ping(ctx: click.Context) -> None:
    _handle(ctx, lambda: _service(ctx).backend.ping())


@cli.group()
def project() -> None:
    """Project import, open, list, and metadata commands."""


@project.command("list")
@click.pass_context
def project_list(ctx: click.Context) -> None:
    _handle(ctx, lambda: _service(ctx).list_projects())


@project.command("open")
@click.argument("project_id")
@click.option("--name")
@click.pass_context
def project_open(ctx: click.Context, project_id: str, name: str | None) -> None:
    _handle(ctx, lambda: _service(ctx).open_project(project_id, name))


@project.command("import")
@click.argument("input_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--name")
@click.option("--format", "project_format")
@click.pass_context
def project_import(ctx: click.Context, input_path: str, name: str | None, project_format: str | None) -> None:
    _handle(ctx, lambda: _service(ctx).import_file(input_path, name, project_format))


@cli.group()
def data() -> None:
    """Rows, operation histories, and exports."""


@data.command("rows")
@click.option("--project-id")
@click.option("--start", default=0, show_default=True)
@click.option("--limit", default=10, show_default=True)
@click.pass_context
def data_rows(ctx: click.Context, project_id: str | None, start: int, limit: int) -> None:
    _handle(ctx, lambda: _service(ctx).rows(start, limit, project_id))


@data.command("apply")
@click.argument("operations_json", type=click.Path(exists=True, dir_okay=False))
@click.option("--project-id")
@click.pass_context
def data_apply(ctx: click.Context, operations_json: str, project_id: str | None) -> None:
    _handle(ctx, lambda: _service(ctx).apply_operations_file(operations_json, project_id))


@data.command("export")
@click.argument("output_path", type=click.Path(dir_okay=False))
@click.option("--project-id")
@click.option("--format", "export_format", default="csv", show_default=True)
@click.pass_context
def data_export(ctx: click.Context, output_path: str, project_id: str | None, export_format: str) -> None:
    _handle(ctx, lambda: _service(ctx).export_rows(output_path, export_format, project_id))


@cli.group()
def ops() -> None:
    """Build reusable OpenRefine operation-history JSON files."""


@ops.command("text-transform")
@click.argument("output", type=click.Path(dir_okay=False))
@click.option("--column", required=True)
@click.option("--expression", required=True)
@click.pass_context
def ops_text_transform(ctx: click.Context, output: str, column: str, expression: str) -> None:
    def _build() -> dict[str, Any]:
        op = text_transform(column, expression)
        path = save_operations([op], output)
        return {"output": str(path), "operations": [op]}

    _handle(ctx, _build)


@ops.command("mass-edit")
@click.argument("output", type=click.Path(dir_okay=False))
@click.option("--column", required=True)
@click.option("--edit", multiple=True, help="Mapping in old=new form. Repeatable.")
@click.pass_context
def ops_mass_edit(ctx: click.Context, output: str, column: str, edit: tuple[str, ...]) -> None:
    def _build() -> dict[str, Any]:
        edits = {}
        for item in edit:
            if "=" not in item:
                raise ValueError("--edit must be in old=new form")
            src, dst = item.split("=", 1)
            edits[src] = dst
        op = mass_edit(column, edits)
        path = save_operations([op], output)
        return {"output": str(path), "operations": [op]}

    _handle(ctx, _build)


@ops.command("add-column")
@click.argument("output", type=click.Path(dir_okay=False))
@click.option("--name", required=True)
@click.option("--source-column", required=True)
@click.option("--expression", required=True)
@click.pass_context
def ops_add_column(ctx: click.Context, output: str, name: str, source_column: str, expression: str) -> None:
    def _build() -> dict[str, Any]:
        op = column_addition(name, source_column, expression)
        path = save_operations([op], output)
        return {"output": str(path), "operations": [op]}

    _handle(ctx, _build)


@ops.command("remove-column")
@click.argument("output", type=click.Path(dir_okay=False))
@click.option("--column", required=True)
@click.pass_context
def ops_remove_column(ctx: click.Context, output: str, column: str) -> None:
    def _build() -> dict[str, Any]:
        op = column_removal(column)
        path = save_operations([op], output)
        return {"output": str(path), "operations": [op]}

    _handle(ctx, _build)


@cli.group()
def session() -> None:
    """Session state and undo/redo."""


@session.command("show")
@click.pass_context
def session_show(ctx: click.Context) -> None:
    _handle(ctx, lambda: SessionStore(ctx.obj["session"]).load().to_dict())


@session.command("undo")
@click.option("--project-id")
@click.pass_context
def session_undo(ctx: click.Context, project_id: str | None) -> None:
    _handle(ctx, lambda: _service(ctx).undo(project_id))


@session.command("redo")
@click.option("--project-id")
@click.pass_context
def session_redo(ctx: click.Context, project_id: str | None) -> None:
    _handle(ctx, lambda: _service(ctx).redo(project_id))


def main(argv: list[str] | None = None) -> int:
    try:
        return cli.main(args=argv, prog_name="cli-anything-openrefine", standalone_mode=True) or 0
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
