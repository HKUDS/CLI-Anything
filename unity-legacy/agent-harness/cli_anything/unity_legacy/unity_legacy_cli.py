import json
import shlex
import sys
import tempfile
import time
from pathlib import Path

import click

from . import automation_cli, camera_ui_cli, editing_cli, rendering_cli


class EditorError(Exception):
    pass


def find_project(explicit_path: Path | None) -> Path:
    search_root = explicit_path.resolve() if explicit_path else Path.cwd()
    for directory in (search_root, *(() if explicit_path else search_root.parents)):
        if (directory / "ProjectSettings" / "ProjectVersion.txt").is_file():
            return directory
    raise EditorError("Unity project not found. Pass --project with the Unity project directory.")


def ask_editor(project, command, timeout, arguments):
    if not (project / "Temp" / "UnityLockfile").is_file():
        raise EditorError(f"Open the project in Unity first: {project}")

    queue = project / "Library" / "UnityCli"
    queue.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    with tempfile.TemporaryDirectory(prefix="request-", dir=queue) as directory:
        job = Path(directory)
        staging = job / "request.tmp"
        staging.write_text(json.dumps({
            "Command": command,
            "ExpiresAt": int((time.time() + timeout) * 1000),
            **arguments,
        }), encoding="utf-8")
        staging.replace(job / "request.json")
        response = job / "response.json"
        while time.monotonic() < deadline:
            if response.is_file():
                return json.loads(response.read_text(encoding="utf-8"))
            if not (project / "Temp" / "UnityLockfile").is_file():
                raise EditorError("Unity closed before replying.")
            time.sleep(0.1)
    raise EditorError("Unity did not reply. Wait for script compilation and check the Editor console.")


def run(ctx, command, **arguments):
    project, _, timeout = ctx.obj
    try:
        result = ask_editor(find_project(project), command, timeout, arguments)
    except (EditorError, OSError, ValueError) as error:
        result = {"ok": False, "error": str(error)}
    emit_result(ctx, result)


def emit_result(ctx, result):
    _, json_mode, _ = ctx.obj
    if json_mode:
        click.echo(json.dumps(result, ensure_ascii=True))
    elif result["ok"]:
        click.echo(json.dumps(result["data"], ensure_ascii=False, indent=2))
    else:
        click.echo(f"Error: {result['error']}", err=True)
        if "data" in result:
            click.echo(json.dumps(result["data"], ensure_ascii=False, indent=2))
    if not result["ok"]:
        ctx.exit(1)


@click.group(invoke_without_command=True)
@click.version_option(package_name="unity-legacy-cli")
@click.option("--project", type=click.Path(exists=True, file_okay=False, path_type=Path),
              help="Unity project directory. Defaults to the nearest project above the current directory.")
@click.option("--json", "json_mode", is_flag=True, help="Return a compact JSON result with an ok field.")
@click.option("--timeout", type=click.IntRange(min=1, max=3600), default=15, show_default=True,
              help="Seconds to wait for the running Editor.")
@click.pass_context
def cli(ctx, project, json_mode, timeout):
    """Inspect and control a running Unity Editor."""
    ctx.obj = (project, json_mode, timeout)
    if ctx.invoked_subcommand is None:
        if json_mode:
            emit_result(ctx, {"ok": False, "error": "Provide a command, for example status."})
        elif sys.stdin.isatty() and sys.stdout.isatty():
            ctx.invoke(repl)
        else:
            click.echo(ctx.get_help())


@cli.command("bridge-path")
@click.pass_context
def bridge_path(ctx):
    """Locate the packaged Unity Editor bridge's package.json."""
    path = Path(__file__).resolve().with_name("bridge") / "package.json"
    if not path.is_file():
        emit_result(ctx, {"ok": False, "error": "The Unity bridge is missing from the installation."})
    elif ctx.obj[1]:
        emit_result(ctx, {"ok": True, "data": {"path": str(path)}})
    else:
        click.echo(str(path))


@cli.command()
@click.pass_context
def repl(ctx):
    """Run several commands against the same editor session."""
    project, json_mode, timeout = ctx.obj
    if json_mode or not sys.stdin.isatty() or not sys.stdout.isatty():
        emit_result(ctx, {"ok": False, "error": "REPL requires an interactive terminal. Use one-shot commands for JSON."})
        return
    from importlib.metadata import version

    from .utils.repl_skin import ReplSkin

    skin = ReplSkin("unity-legacy", version=version("unity-legacy-cli"))
    skin.print_banner()
    session = skin.create_prompt_session()
    defaults = ["--timeout", str(timeout)]
    if project is not None:
        defaults += ["--project", str(project)]
    while True:
        try:
            line = skin.get_input(session, project_name=project.name if project else "").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            continue
        if line in {"exit", "quit"}:
            break
        if line == "help":
            skin.help({name: command.get_short_help_str() for name, command in cli.commands.items() if name != "repl"})
            continue
        try:
            words = shlex.split(line)
            if words and words[0] != "repl":
                cli.main([*defaults, *words], prog_name=ctx.find_root().info_name, standalone_mode=False)
        except (click.ClickException, ValueError) as error:
            skin.error(str(error))
    skin.print_goodbye()


@cli.command()
@click.pass_context
def status(ctx):
    """Show project path, Editor version, build target and Play Mode state."""
    run(ctx, "status")


@cli.command()
@click.pass_context
def scenes(ctx):
    """List scenes currently open in the Editor."""
    run(ctx, "scenes")


@cli.command("asset-info")
@click.argument("asset_path")
@click.pass_context
def asset_info(ctx, asset_path):
    """Read the GUID and type of an indexed Assets/... path."""
    run(ctx, "asset-info", AssetPath=asset_path)


@cli.group()
def editor():
    """Query or control the Editor."""


@cli.group()
def console():
    """Read or clear the Editor Console."""


@cli.group()
def scene():
    """Inspect, open or save Unity scenes."""


@cli.group()
def gameobject():
    """Find GameObjects in loaded scenes."""


@cli.group()
def component():
    """Inspect components on a GameObject."""


@cli.group()
def prefab():
    """Inspect Prefab assets."""


@cli.group()
def asset():
    """Find and inspect project assets."""


def add_simple_command(group, name, help_text, command=None):
    @group.command(name, help=help_text)
    @click.pass_context
    def invoke(ctx):
        run(ctx, command or f"{group.name}.{name}")


add_simple_command(editor, "status", "Show Editor and Play Mode state.", "status")
add_simple_command(editor, "play", "Request entry into Play Mode.")
add_simple_command(editor, "pause", "Pause Play Mode.")
add_simple_command(editor, "resume", "Resume Play Mode.")
add_simple_command(editor, "stop", "Request exit from Play Mode.")
add_simple_command(editor, "undo", "Undo the last Editor operation.")
add_simple_command(editor, "redo", "Redo the last Editor operation.")
add_simple_command(editor, "tags-layers", "List the project's tags and named layers.")
add_simple_command(editor, "refresh", "Request an AssetDatabase refresh.")
add_simple_command(editor, "compile", "Request script compilation.")
add_simple_command(console, "clear", "Clear the current Editor Console.")
add_simple_command(scene, "list", "List scenes currently open in the Editor.", "scenes")
add_simple_command(scene, "build-settings", "List the scenes in Build Settings.")
asset.add_command(asset_info, "info")


@console.command("read")
@click.option("--type", "log_type", type=click.Choice(["all", "error", "warning", "log"]), default="all")
@click.option("--limit", type=click.IntRange(1, 200), default=20, show_default=True)
@click.pass_context
def console_read(ctx, log_type, limit):
    """Read recent Console entries, newest first."""
    run(ctx, "console.read", Filter=log_type, Limit=limit)


@scene.command()
@click.option("--limit", type=click.IntRange(1, 2000), default=250, show_default=True)
@click.pass_context
def hierarchy(ctx, limit):
    """List scene hierarchy nodes with their parent IDs."""
    run(ctx, "scene.hierarchy", Limit=limit)


@scene.command("open")
@click.argument("asset_path")
@click.option("--additive", is_flag=True, help="Keep currently loaded scenes open.")
@click.pass_context
def scene_open(ctx, asset_path, additive):
    """Open an existing scene in Edit Mode."""
    run(ctx, "scene.open", AssetPath=asset_path, Additive=additive)


@scene.command("save")
@click.option("--output", "asset_path", help="Save as an unused Assets/... .unity path.")
@click.pass_context
def scene_save(ctx, asset_path):
    """Save the active scene. Provide --output for an untitled scene."""
    run(ctx, "scene.save", AssetPath=asset_path)


@gameobject.command("find")
@click.argument("name")
@click.option("--limit", type=click.IntRange(1, 2000), default=100, show_default=True)
@click.pass_context
def gameobject_find(ctx, name, limit):
    """Find loaded scene objects whose names contain NAME."""
    run(ctx, "gameobject.find", Filter=name, Limit=limit)


@component.command("list")
@click.argument("object_id", type=int)
@click.pass_context
def component_list(ctx, object_id):
    """List component types for a live GameObject instance ID."""
    run(ctx, "component.list", ObjectId=object_id)


@prefab.command("inspect")
@click.argument("asset_path")
@click.option("--limit", type=click.IntRange(1, 2000), default=250, show_default=True)
@click.pass_context
def prefab_inspect(ctx, asset_path, limit):
    """Read a prefab hierarchy and its component types."""
    run(ctx, "prefab.inspect", AssetPath=asset_path, Limit=limit)


@asset.command("search")
@click.argument("query")
@click.option("--limit", type=click.IntRange(1, 2000), default=100, show_default=True)
@click.pass_context
def asset_search(ctx, query, limit):
    """Search Assets using Unity's AssetDatabase query syntax."""
    run(ctx, "asset.search", Filter=query, Limit=limit)


@asset.command("dependencies")
@click.argument("asset_path")
@click.pass_context
def asset_dependencies(ctx, asset_path):
    """List an asset's direct dependencies."""
    run(ctx, "asset.dependencies", AssetPath=asset_path)


@cli.command()
@click.argument("commands", type=click.File("r", encoding="utf-8-sig"))
@click.pass_context
def batch(ctx, commands):
    """Execute a JSON array of command objects in order. Pass - to read stdin."""
    try:
        entries = json.load(commands)
    except ValueError as error:
        raise click.BadParameter(f"Invalid JSON: {error}", param_hint="commands") from error
    run(ctx, "batch", Commands=entries)


automation_cli.register(cli, run)
camera_ui_cli.register(cli, run)
editing_cli.register(cli, run)
rendering_cli.register(cli, run)


if __name__ == "__main__":
    cli()
