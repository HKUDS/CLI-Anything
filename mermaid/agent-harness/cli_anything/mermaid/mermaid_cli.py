"""Stateful CLI harness for Mermaid Live Editor."""

from __future__ import annotations

import json

import click

from .core import diagram as diagram_mod
from .core import export as export_mod
from .core import project as project_mod
from .core.session import Session
from .utils.repl_skin import ReplSkin


_session: Session | None = None
_json_output = False


def get_session() -> Session:
    global _session
    if _session is None:
        _session = Session()
    return _session


def emit(data, message: str | None = None) -> None:
    if _json_output:
        click.echo(json.dumps(data, indent=2))
        return
    if message:
        click.echo(message)
    if isinstance(data, dict):
        for key, value in data.items():
            click.echo(f"{key}: {value}")
    else:
        click.echo(str(data))


@click.group(invoke_without_command=True)
@click.option("--json", "json_mode", is_flag=True, help="Emit machine-readable JSON")
@click.option("--project", "project_path", default=None, help="Open a Mermaid project file")
@click.pass_context
def cli(ctx, json_mode: bool, project_path: str | None) -> None:
    """CLI harness for Mermaid Live Editor state files and renderer URLs."""
    global _json_output, _session
    _json_output = json_mode
    _session = Session()
    if project_path:
        _session.open_project(project_path)

    @ctx.call_on_close
    def _auto_save() -> None:
        if project_path and _session and _session.is_open and _session.modified:
            _session.save_project()

    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


@cli.group()
def project() -> None:
    """Project lifecycle commands."""


@project.command("new")
@click.option("--sample", default="flowchart", help="Sample diagram preset")
@click.option("--theme", default="default", help="Mermaid theme")
@click.option("-o", "--output", "output_path", default=None, help="Optional file path to save")
def project_new(sample: str, theme: str, output_path: str | None) -> None:
    session = get_session()
    result = project_mod.new_project(session, sample=sample, theme=theme)
    if output_path:
        saved = project_mod.save_project(session, output_path)
        result["path"] = saved["path"]
    emit(result, "Created Mermaid project")


@project.command("open")
@click.argument("path")
def project_open(path: str) -> None:
    emit(project_mod.open_project(get_session(), path), "Opened Mermaid project")


@project.command("save")
@click.argument("path", required=False)
def project_save(path: str | None) -> None:
    emit(project_mod.save_project(get_session(), path), "Saved Mermaid project")


@project.command("info")
def project_info() -> None:
    emit(project_mod.project_info(get_session()), "Project info")


@project.command("samples")
def project_samples() -> None:
    emit(project_mod.list_samples(), "Available samples")


@cli.group()
def diagram() -> None:
    """Diagram source commands."""


@diagram.command("set")
@click.option("--text", default=None, help="Inline Mermaid source")
@click.option("--file", "file_path", default=None, help="Read Mermaid source from file")
def diagram_set(text: str | None, file_path: str | None) -> None:
    session = get_session()
    if not session.is_open:
        raise click.ClickException("No project is open")
    if bool(text) == bool(file_path):
        raise click.ClickException("Provide exactly one of --text or --file")
    if file_path:
        with open(file_path, "r", encoding="utf-8") as fh:
            text = fh.read()
    emit(diagram_mod.set_diagram(session, text or ""), "Updated Mermaid source")


@diagram.command("show")
def diagram_show() -> None:
    result = diagram_mod.show_diagram(get_session())
    if _json_output:
        emit(result)
    else:
        click.echo(result["code"])


@cli.group()
def export() -> None:
    """Render and share commands."""


@export.command("render")
@click.argument("output_path")
@click.option("--format", "-f", "fmt", type=click.Choice(["svg", "png"]), default="svg")
@click.option("--overwrite", is_flag=True, help="Overwrite existing output")
def export_render(output_path: str, fmt: str, overwrite: bool) -> None:
    emit(export_mod.render(get_session(), output_path, fmt=fmt, overwrite=overwrite), "Rendered output")


@export.command("share")
@click.option("--mode", type=click.Choice(["edit", "view"]), default="edit")
def export_share(mode: str) -> None:
    emit(export_mod.share(get_session(), mode=mode), "Generated share URL")


@cli.group()
def session() -> None:
    """Session state commands."""


@session.command("status")
def session_status() -> None:
    emit(get_session().status(), "Session status")


@session.command("undo")
def session_undo() -> None:
    success = get_session().undo()
    emit({"action": "undo", "success": success}, "Undo complete" if success else "Nothing to undo")


@session.command("redo")
def session_redo() -> None:
    success = get_session().redo()
    emit({"action": "redo", "success": success}, "Redo complete" if success else "Nothing to redo")


REPL_COMMANDS = {
    "new [sample]": "Create a Mermaid project",
    "open <path>": "Open a Mermaid project file",
    "save [path]": "Save the current project",
    "show": "Print the current Mermaid source",
    "set <text>": "Replace the Mermaid source text",
    "render <path> [svg|png]": "Render an artifact through the Mermaid renderer",
    "share [edit|view]": "Generate a Mermaid Live URL",
    "status": "Show session status",
    "undo": "Undo the last source change",
    "redo": "Redo the last undone change",
    "quit": "Exit the REPL",
}


@cli.command()
def repl() -> None:
    """Interactive REPL."""
    session = get_session()
    skin = ReplSkin("mermaid", version="1.0.0")
    skin.print_banner()
    prompt_session = skin.create_prompt_session()
    while True:
        project_name = session.project_path or "(unsaved)" if session.is_open else ""
        line = skin.get_input(prompt_session, project_name=project_name, modified=session.modified).strip()
        if not line:
            continue
        if line in {"quit", "exit"}:
            skin.print_goodbye()
            break
        if line == "help":
            skin.help(REPL_COMMANDS)
            continue
        try:
            parts = line.split()
            command, args = parts[0], parts[1:]
            if command == "new":
                sample = args[0] if args else "flowchart"
                emit(project_mod.new_project(session, sample=sample), "Created Mermaid project")
            elif command == "open":
                emit(project_mod.open_project(session, args[0]), "Opened Mermaid project")
            elif command == "save":
                path = args[0] if args else None
                emit(project_mod.save_project(session, path), "Saved Mermaid project")
            elif command == "show":
                click.echo(diagram_mod.show_diagram(session)["code"])
            elif command == "set":
                emit(diagram_mod.set_diagram(session, " ".join(args)), "Updated Mermaid source")
            elif command == "render":
                fmt = args[1] if len(args) > 1 else "svg"
                emit(export_mod.render(session, args[0], fmt=fmt, overwrite=True), "Rendered output")
            elif command == "share":
                mode = args[0] if args else "edit"
                emit(export_mod.share(session, mode=mode), "Generated share URL")
            elif command == "status":
                emit(session.status(), "Session status")
            elif command == "undo":
                emit({"action": "undo", "success": session.undo()})
            elif command == "redo":
                emit({"action": "redo", "success": session.redo()})
            else:
                skin.error(f"Unknown command: {command}")
        except Exception as exc:  # pragma: no cover
            skin.error(str(exc))


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
