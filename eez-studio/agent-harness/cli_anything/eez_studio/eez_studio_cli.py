"""cli-anything-eez-studio: CLI harness for EEZ Studio.

The CLI edits native .eez-project JSON and calls the real EEZ Studio source
backend for build/export workflows when configured.
"""

from __future__ import annotations

import json
import os
import shlex
import sys
from typing import Any

import click

from cli_anything.eez_studio import __version__
from cli_anything.eez_studio.core import export as export_mod
from cli_anything.eez_studio.core import project as project_mod
from cli_anything.eez_studio.core import scpi as scpi_mod
from cli_anything.eez_studio.core.session import Session
from cli_anything.eez_studio.utils import eez_studio_backend
from cli_anything.eez_studio.utils.repl_skin import ReplSkin


_session: Session | None = None
_json_output = False
_repl_mode = False


def get_session() -> Session:
    global _session
    if _session is None:
        _session = Session()
    return _session


def _same_project_path(session: Session, project_path: str) -> bool:
    return session.project_path == os.path.abspath(project_path)


def _configure_session(session_id: str | None, project_path: str | None) -> None:
    global _session
    if _repl_mode:
        session = get_session()
        if session_id and session.session_id != session_id:
            session.session_id = session_id
        if project_path and not _same_project_path(session, project_path):
            session.open_project(project_path)
        return

    _session = Session(session_id)
    if project_path:
        _session.open_project(project_path)


def output(data: Any, message: str = "") -> None:
    if _json_output:
        click.echo(json.dumps(data, indent=2, default=str))
        return
    if message:
        click.echo(message)
    _pretty(data)


def _pretty(data: Any, indent: int = 0) -> None:
    prefix = "  " * indent
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                click.echo(f"{prefix}{key}:")
                _pretty(value, indent + 1)
            else:
                click.echo(f"{prefix}{key}: {value}")
    elif isinstance(data, list):
        for index, item in enumerate(data):
            if isinstance(item, dict):
                click.echo(f"{prefix}[{index}]")
                _pretty(item, indent + 1)
            else:
                click.echo(f"{prefix}- {item}")
    else:
        click.echo(f"{prefix}{data}")


def _emit_error(exc: Exception) -> None:
    if _json_output:
        click.echo(
            json.dumps({"error": str(exc), "type": type(exc).__name__}, indent=2),
            err=True,
        )
    else:
        click.echo(f"Error: {exc}", err=True)


def handle_error(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (FileNotFoundError, FileExistsError, ValueError, RuntimeError, OSError) as exc:
            _emit_error(exc)
            if not _repl_mode:
                sys.exit(1)

    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


def require_project() -> Session:
    session = get_session()
    if session.project is None:
        raise RuntimeError("no project is open; use --project PATH or `project new -o PATH`")
    return session


def _mark_changed(session: Session) -> None:
    session._modified = True


@click.group(invoke_without_command=True)
@click.option("--json", "json_mode", is_flag=True, help="Output machine-readable JSON.")
@click.option("--project", "-p", "project_path", default=None, help="Open a .eez-project file.")
@click.option("--session", "session_id", default=None, help="Session ID to use.")
@click.option("--dry-run", is_flag=True, help="Do not auto-save modified project files.")
@click.pass_context
def cli(ctx: click.Context, json_mode: bool, project_path: str | None, session_id: str | None, dry_run: bool) -> None:
    """EEZ Studio CLI harness for project, LVGL, and SCPI workflows.

    Run without a subcommand to enter the interactive REPL.
    """
    global _json_output
    _json_output = json_mode
    _configure_session(session_id, project_path)
    ctx.ensure_object(dict)
    ctx.obj["project_path"] = project_path
    ctx.obj["json"] = json_mode
    ctx.obj["dry_run"] = dry_run

    @ctx.call_on_close
    def _auto_save() -> None:
        if dry_run or _repl_mode:
            return
        session = get_session()
        if session.project is not None and session.is_modified and session.project_path:
            session.save_project()

    if ctx.invoked_subcommand is None:
        ctx.invoke(repl, project_path=None)


@cli.command()
@click.option("--project", "-p", "project_path", default=None, help="Project file to open in REPL.")
@click.pass_context
def repl(ctx: click.Context, project_path: str | None) -> None:
    """Start the interactive REPL."""
    global _repl_mode
    _repl_mode = True
    skin = ReplSkin("eez-studio", version=__version__)
    skin.print_banner()

    session = get_session()
    if project_path:
        try:
            session.open_project(project_path)
        except Exception as exc:
            skin.error(str(exc))

    commands = {
        "project new -o app.eez-project": "Create an LVGL project",
        "project info": "Show project summary",
        "project save": "Save current project",
        "project widgets": "List LVGL widgets",
        "lvgl add-label --text Hello": "Add a label to a screen",
        "lvgl add-button --text Run": "Add a button to a screen",
        "lvgl ensure-destination": "Create the build destination directory",
        "lvgl backend-inspect": "Inspect through EEZ Studio backend",
        "lvgl simulator-build out": "Run full LVGL simulator backend",
        "scpi subsystem-add SOURCE": "Add a SCPI subsystem",
        "scpi command-add SOURCE :VOLTage?": "Add a SCPI command",
        "session undo / redo": "Undo or redo project mutations",
        "backend status": "Check EEZ Studio backend availability",
        "help": "Show this help",
        "quit / exit": "Exit",
    }
    pt_session = skin.create_prompt_session()
    while True:
        try:
            line = skin.get_input(pt_session, project_name=session.name, modified=session.is_modified)
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            continue
        if line.lower() in {"quit", "exit", "q"}:
            if session.is_modified:
                skin.warning("Unsaved changes. Use `project save` before exiting.")
            break
        if line.lower() in {"help", "h", "?"}:
            skin.help(commands)
            continue
        try:
            args = shlex.split(line)
            if session.project_path and "--project" not in args and "-p" not in args:
                args = ["--project", session.project_path] + args
            if ctx.obj and ctx.obj.get("json"):
                args = ["--json"] + args
            cli.main(args=args, standalone_mode=False)
        except SystemExit:
            pass
        except Exception as exc:
            skin.error(str(exc))
    skin.print_goodbye()
    _repl_mode = False


@cli.group()
def project() -> None:
    """Project management and native .eez-project inspection."""


@project.command("new")
@click.option("--name", "-n", default="Untitled", help="Project name.")
@click.option("--width", type=int, default=800, help="LVGL display width.")
@click.option("--height", type=int, default=480, help="LVGL display height.")
@click.option("--lvgl-version", default=project_mod.DEFAULT_LVGL_VERSION, help="LVGL version.")
@click.option("--destination", default=project_mod.DEFAULT_DESTINATION, help="Build destination folder.")
@click.option("--flow-support", is_flag=True, help="Enable EEZ Flow support flag.")
@click.option("--output", "-o", "output_path", required=True, help="Output .eez-project path.")
@handle_error
def project_new(
    name: str,
    width: int,
    height: int,
    lvgl_version: str,
    destination: str,
    flow_support: bool,
    output_path: str,
) -> None:
    """Create a new native EEZ Studio LVGL project."""
    project_data = project_mod.create_project(
        name=name,
        display_width=width,
        display_height=height,
        lvgl_version=lvgl_version,
        destination=destination,
        flow_support=flow_support,
    )
    session = get_session()
    session.set_project(project_data, output_path)
    result = session.save_project(output_path)
    result.update(project_mod.project_info(project_data))
    output(result, f"Created EEZ Studio project: {result['path']}")


@project.command("open")
@click.argument("path")
@handle_error
def project_open(path: str) -> None:
    """Open a .eez-project file."""
    session = get_session()
    session.open_project(path)
    output(session.status(), f"Opened: {path}")


@project.command("save")
@click.argument("path", required=False)
@handle_error
def project_save(path: str | None) -> None:
    """Save the current project."""
    session = require_project()
    result = session.save_project(path)
    output(result, f"Saved: {result['path']}")


@project.command("info")
@handle_error
def project_info() -> None:
    """Show project summary."""
    session = require_project()
    output(project_mod.project_info(session.project or {}), "Project info:")


@project.command("validate")
@click.argument("path", required=False)
@handle_error
def project_validate(path: str | None) -> None:
    """Validate native EEZ project structure."""
    data = project_mod.load_project(path) if path else (require_project().project or {})
    project_mod.validate_project(data)
    output({"valid": True, **project_mod.project_info(data)}, "Project is valid.")


@project.command("pages")
@handle_error
def project_pages() -> None:
    """List LVGL pages/screens."""
    session = require_project()
    output(project_mod.list_pages(session.project or {}), "Pages:")


@project.command("widgets")
@click.option("--page", "page_name", default=None, help="Filter by page name.")
@handle_error
def project_widgets(page_name: str | None) -> None:
    """List LVGL widgets."""
    session = require_project()
    output(project_mod.list_widgets(session.project or {}, page_name), "Widgets:")


@project.command("set")
@click.argument("key")
@click.argument("value")
@handle_error
def project_set(key: str, value: str) -> None:
    """Set a supported settings.general key."""
    session = require_project()
    session.checkpoint()
    result = project_mod.set_general(session.project or {}, key, value)
    output(result, f"Set settings.general.{key}")


@project.command("set-destination")
@click.argument("destination")
@handle_error
def project_set_destination(destination: str) -> None:
    """Set settings.build.destinationFolder."""
    session = require_project()
    session.checkpoint()
    result = project_mod.set_build_destination(session.project or {}, destination)
    output(result, f"Set build destination: {destination}")


@project.command("add-build-file")
@click.argument("file_name")
@click.option("--template", "-t", required=True, help="Template text with EEZ Studio markers.")
@click.option("--description", default="", help="Build file description.")
@click.option("--replace", is_flag=True, help="Replace an existing build file.")
@handle_error
def project_add_build_file(file_name: str, template: str, description: str, replace: bool) -> None:
    """Add or replace a settings.build.files template."""
    session = require_project()
    session.checkpoint()
    result = project_mod.add_build_file(session.project or {}, file_name, template, description, replace)
    output(result, f"Updated build file: {file_name}")


@cli.group()
def lvgl() -> None:
    """LVGL screen/widget and real backend build commands."""


@lvgl.command("add-page")
@click.argument("name")
@click.option("--width", type=int, default=None, help="Screen width.")
@click.option("--height", type=int, default=None, help="Screen height.")
@handle_error
def lvgl_add_page(name: str, width: int | None, height: int | None) -> None:
    """Add a LVGL page/screen."""
    session = require_project()
    session.checkpoint()
    result = project_mod.add_page(session.project or {}, name, width, height)
    output(result, f"Added page: {name}")


@lvgl.command("add-label")
@click.option("--page", "page_name", default="Main", help="Page name.")
@click.option("--text", required=True, help="Label text.")
@click.option("--name", default=None, help="Widget name.")
@click.option("--x", type=int, default=20)
@click.option("--y", type=int, default=20)
@click.option("--width", type=int, default=160)
@click.option("--height", type=int, default=32)
@handle_error
def lvgl_add_label(page_name: str, text: str, name: str | None, x: int, y: int, width: int, height: int) -> None:
    """Add a LVGL label widget."""
    session = require_project()
    session.checkpoint()
    result = project_mod.add_label(session.project or {}, page_name, text, name, x, y, width, height)
    output(result, f"Added label: {result['name']}")


@lvgl.command("add-button")
@click.option("--page", "page_name", default="Main", help="Page name.")
@click.option("--text", required=True, help="Button label.")
@click.option("--name", default=None, help="Widget name.")
@click.option("--x", type=int, default=20)
@click.option("--y", type=int, default=72)
@click.option("--width", type=int, default=140)
@click.option("--height", type=int, default=48)
@handle_error
def lvgl_add_button(page_name: str, text: str, name: str | None, x: int, y: int, width: int, height: int) -> None:
    """Add a LVGL button widget with child label."""
    session = require_project()
    session.checkpoint()
    result = project_mod.add_button(session.project or {}, page_name, text, name, x, y, width, height)
    output(result, f"Added button: {result['name']}")


@lvgl.command("ensure-destination")
@handle_error
def lvgl_ensure_destination() -> None:
    """Create the build destination directory beside the project."""
    session = require_project()
    if not session.project_path:
        raise RuntimeError("project must be saved before creating destination directory")
    result = export_mod.ensure_destination(session.project_path)
    output(result, f"Destination ready: {result['destination']}")


@lvgl.command("backend-inspect")
@click.option("--source", default=None, help="EEZ Studio source tree; defaults to EEZ_STUDIO_SOURCE.")
@click.option("--path", "project_path", default=None, help="Project path; defaults to open project.")
@handle_error
def lvgl_backend_inspect(source: str | None, project_path: str | None) -> None:
    """Inspect project metadata through EEZ Studio's real Node backend."""
    session = get_session()
    path = project_path or session.project_path
    if not path:
        raise RuntimeError("project path required")
    result = export_mod.inspect_with_backend(path, source=source)
    output(result, "EEZ backend project info:")


@lvgl.command("build-files")
@click.option("--path", "project_path", default=None, help="Project path; defaults to open project.")
@click.option("--timeout", type=int, default=300)
@handle_error
def lvgl_build_files(project_path: str | None, timeout: int) -> None:
    """Run a configured real EEZ Studio build-files command."""
    session = get_session()
    path = project_path or session.project_path
    if not path:
        raise RuntimeError("project path required")
    result = export_mod.build_files(path, timeout=timeout)
    output(result, "EEZ build command finished:")


@lvgl.command("simulator-build")
@click.argument("output_dir")
@click.option("--source", default=None, help="EEZ Studio source tree; defaults to EEZ_STUDIO_SOURCE.")
@click.option("--path", "project_path", default=None, help="Project path; defaults to open project.")
@click.option("--repository-name", default="eez-framework", help="Repository used by EEZ docker build.")
@click.option("--docker-volume", default="eez-studio-cli-anything", help="Docker volume name.")
@click.option("--timeout", type=int, default=900)
@handle_error
def lvgl_simulator_build(
    output_dir: str,
    source: str | None,
    project_path: str | None,
    repository_name: str,
    docker_volume: str,
    timeout: int,
) -> None:
    """Run EEZ Studio's full LVGL simulator Docker backend."""
    session = get_session()
    path = project_path or session.project_path
    if not path:
        raise RuntimeError("project path required")
    result = export_mod.simulator_build(
        project_path=path,
        output_dir=output_dir,
        source=source,
        repository_name=repository_name,
        docker_volume_name=docker_volume,
        timeout=timeout,
    )
    result["verification"] = export_mod.verify_simulator_output(output_dir)
    output(result, f"Simulator built: {os.path.abspath(output_dir)}")


@lvgl.command("verify-simulator")
@click.argument("output_dir")
@handle_error
def lvgl_verify_simulator(output_dir: str) -> None:
    """Verify simulator output artifacts by structure and magic bytes."""
    result = export_mod.verify_simulator_output(output_dir)
    output(result, f"Verified simulator output: {result['output_dir']}")


@cli.group()
def scpi() -> None:
    """SCPI subsystem and command model editing."""


@scpi.command("subsystem-list")
@handle_error
def scpi_subsystem_list() -> None:
    """List SCPI subsystems."""
    session = require_project()
    output(scpi_mod.list_subsystems(session.project or {}), "SCPI subsystems:")


@scpi.command("subsystem-add")
@click.argument("name")
@click.option("--description", "-d", default="", help="Subsystem description.")
@handle_error
def scpi_subsystem_add(name: str, description: str) -> None:
    """Add a SCPI subsystem."""
    session = require_project()
    session.checkpoint()
    result = scpi_mod.add_subsystem(session.project or {}, name, description)
    output(result, f"Added SCPI subsystem: {name}")


@scpi.command("command-list")
@click.option("--subsystem", "-s", default=None, help="Filter by subsystem.")
@handle_error
def scpi_command_list(subsystem: str | None) -> None:
    """List SCPI commands."""
    session = require_project()
    output(scpi_mod.list_commands(session.project or {}, subsystem), "SCPI commands:")


@scpi.command("command-add")
@click.argument("subsystem")
@click.argument("name")
@click.option("--description", "-d", default="", help="Command description.")
@click.option("--response-type", default=None, help="Query response type.")
@handle_error
def scpi_command_add(subsystem: str, name: str, description: str, response_type: str | None) -> None:
    """Add a SCPI command to a subsystem."""
    session = require_project()
    session.checkpoint()
    result = scpi_mod.add_command(session.project or {}, subsystem, name, description, response_type)
    output(result, f"Added SCPI command: {name}")


@scpi.command("parameter-add")
@click.argument("subsystem")
@click.argument("command")
@click.argument("name")
@click.option("--type", "parameter_type", default="nr1", help="SCPI parameter type.")
@click.option("--optional", is_flag=True, help="Mark parameter optional.")
@click.option("--description", "-d", default="", help="Parameter description.")
@handle_error
def scpi_parameter_add(
    subsystem: str,
    command: str,
    name: str,
    parameter_type: str,
    optional: bool,
    description: str,
) -> None:
    """Add a parameter to a SCPI command."""
    session = require_project()
    session.checkpoint()
    result = scpi_mod.add_parameter(session.project or {}, subsystem, command, name, parameter_type, optional, description)
    output(result, f"Added SCPI parameter: {name}")


@cli.group()
def backend() -> None:
    """Backend detection and version probes."""


@backend.command("status")
@click.option("--source", default=None, help="EEZ Studio source tree; defaults to EEZ_STUDIO_SOURCE.")
@handle_error
def backend_status(source: str | None) -> None:
    """Show backend availability."""
    result = eez_studio_backend.backend_status(source)
    output(result, "Backend status:")


@cli.group()
def session() -> None:
    """Session management and undo/redo."""


@session.command("status")
@handle_error
def session_status() -> None:
    """Show session status."""
    output(get_session().status(), "Session status:")


@session.command("undo")
@handle_error
def session_undo() -> None:
    """Undo the last mutation."""
    ok = get_session().undo()
    output({"undone": ok, **get_session().status()}, "Undo" if ok else "Nothing to undo")


@session.command("redo")
@handle_error
def session_redo() -> None:
    """Redo the last undone mutation."""
    ok = get_session().redo()
    output({"redone": ok, **get_session().status()}, "Redo" if ok else "Nothing to redo")


@session.command("save-state")
@handle_error
def session_save_state() -> None:
    """Save session metadata to disk."""
    path = get_session().save_state()
    output({"path": path}, f"Saved session state: {path}")


@session.command("list")
@handle_error
def session_list() -> None:
    """List saved session metadata."""
    output(Session.list_states(), "Saved sessions:")


main = cli


if __name__ == "__main__":
    main()
