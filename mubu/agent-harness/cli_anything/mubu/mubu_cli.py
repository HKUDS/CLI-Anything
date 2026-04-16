from __future__ import annotations

import json
import os
import shlex
import sys
from pathlib import Path
from typing import Iterable, Sequence

import click

import mubu_probe
from cli_anything.mubu import __version__
from cli_anything.mubu.utils import ReplSkin


CONTEXT_SETTINGS = {"ignore_unknown_options": True, "allow_extra_args": True}
COMMAND_HISTORY_LIMIT = 50
PUBLIC_PROGRAM_NAME = "mubu-cli"
COMPAT_PROGRAM_NAME = "cli-anything-mubu"
DISCOVER_COMMANDS = {
    "docs": "List latest known document snapshots from local backups.",
    "folders": "List folder metadata from local RxDB storage.",
    "folder-docs": "List document metadata for one folder.",
    "path-docs": "List documents for one folder path or folder id.",
    "recent": "List recently active documents using backups, metadata, and sync logs.",
    "daily": "Find Daily-style folders and list the documents inside them.",
    "daily-current": "Resolve the current daily document from one Daily-style folder.",
}
INSPECT_COMMANDS = {
    "show": "Show the latest backup tree for one document.",
    "search": "Search latest backups for matching node text or note content.",
    "changes": "Parse recent client-sync change events from local logs.",
    "links": "Extract outbound Mubu document links from one document backup.",
    "open-path": "Open one document by full path, suffix path, title, or doc id.",
    "doc-nodes": "List live document nodes with node ids and update-target paths.",
    "daily-nodes": "List live nodes from the current daily document in one step.",
}
MUTATE_COMMANDS = {
    "create-child": "Build or execute one child-node creation against the live Mubu API.",
    "delete-node": "Build or execute one node deletion against the live Mubu API.",
    "update-text": "Build or execute one text update against the live Mubu API.",
}
LEGACY_COMMANDS = {}
LEGACY_COMMANDS.update(DISCOVER_COMMANDS)
LEGACY_COMMANDS.update(INSPECT_COMMANDS)
LEGACY_COMMANDS.update(MUTATE_COMMANDS)

REPL_HELP_TEMPLATE = """Interactive REPL for {program_name}

Builtins:
  help              Show this REPL help
  exit, quit        Leave the REPL
  use-doc <ref>     Set the current document reference for this REPL session
  use-node <id>     Set the current node reference for this REPL session
  use-daily [ref]   Resolve and set the current daily document
  current-doc       Show the current document reference
  current-node      Show the current node reference
  clear-doc         Clear the current document reference
  clear-node        Clear the current node reference
  status            Show the current session status
  history [limit]   Show recent command history from session state
  state-path        Show the session state file path

Examples:
  recent --limit 5 --json
  discover daily-current '<daily-folder-ref>'
  discover daily-current --json '<daily-folder-ref>'
  inspect daily-nodes '<daily-folder-ref>' --query '<anchor>' --json
  session use-doc '<doc-ref>'
  mutate create-child @doc --parent-node-id <node-id> --text 'scratch child' --json
  mutate delete-node @doc --node-id @node --json
  update-text '<doc-ref>' --node-id <node-id> --text 'new text' --json

If you prefer no-argument daily helpers, set MUBU_DAILY_FOLDER='<daily-folder-ref>'.
"""
REPL_COMMAND_HELP = REPL_HELP_TEMPLATE.format(program_name="the Mubu CLI")


def normalize_program_name(program_name: str | None) -> str:
    candidate = Path(program_name or "").name.strip()
    if candidate == PUBLIC_PROGRAM_NAME:
        return PUBLIC_PROGRAM_NAME
    return COMPAT_PROGRAM_NAME


def repl_help_text(program_name: str | None = None) -> str:
    return REPL_HELP_TEMPLATE.format(program_name=normalize_program_name(program_name))


def session_state_dir() -> Path:
    override = os.environ.get("CLI_ANYTHING_MUBU_STATE_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    config_root = Path.home() / ".config"
    public_dir = config_root / PUBLIC_PROGRAM_NAME
    legacy_dir = config_root / COMPAT_PROGRAM_NAME
    if public_dir.exists():
        return public_dir
    if legacy_dir.exists():
        return legacy_dir
    return public_dir


def session_state_path() -> Path:
    return session_state_dir() / "session.json"


def default_session_state() -> dict[str, object]:
    return {
        "current_doc": None,
        "current_node": None,
        "command_history": [],
    }


def load_session_state() -> dict[str, object]:
    path = session_state_path()
    try:
        data = json.loads(path.read_text(errors="replace"))
    except FileNotFoundError:
        return default_session_state()
    except json.JSONDecodeError:
        return default_session_state()

    history = data.get("command_history")
    normalized_history = [item for item in history if isinstance(item, str)] if isinstance(history, list) else []
    return {
        "current_doc": data.get("current_doc") if isinstance(data.get("current_doc"), str) else None,
        "current_node": data.get("current_node") if isinstance(data.get("current_node"), str) else None,
        "command_history": normalized_history[-COMMAND_HISTORY_LIMIT:],
    }


def locked_save_json(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        handle = open(path, "r+")
    except FileNotFoundError:
        handle = open(path, "w")
    with handle:
        locked = False
        try:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            locked = True
        except (ImportError, OSError):
            pass
        try:
            handle.seek(0)
            handle.truncate()
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.flush()
        finally:
            if locked:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def save_session_state(session: dict[str, object]) -> None:
    locked_save_json(
        session_state_path(),
        {
            "current_doc": session.get("current_doc"),
            "current_node": session.get("current_node"),
            "command_history": list(session.get("command_history", [])),
        },
    )


def append_command_history(command_line: str) -> None:
    command_line = command_line.strip()
    if not command_line:
        return
    session = load_session_state()
    history = list(session.get("command_history", []))
    history.append(command_line)
    session["command_history"] = history[-COMMAND_HISTORY_LIMIT:]
    save_session_state(session)


def resolve_current_daily_doc_ref(folder_ref: str | None = None) -> str:
    resolved_folder_ref = mubu_probe.resolve_daily_folder_ref(folder_ref)
    metas = mubu_probe.load_document_metas(mubu_probe.DEFAULT_STORAGE_ROOT)
    folders = mubu_probe.load_folders(mubu_probe.DEFAULT_STORAGE_ROOT)
    docs, folder, ambiguous = mubu_probe.folder_documents(metas, folders, resolved_folder_ref)
    if folder is None:
        if ambiguous:
            raise RuntimeError(mubu_probe.ambiguous_error_message("folder", resolved_folder_ref, ambiguous, "path"))
        raise RuntimeError(f"folder not found: {resolved_folder_ref}")
    selected, _ = mubu_probe.choose_current_daily_document(docs)
    if selected is None or not selected.get("doc_path"):
        raise RuntimeError(f"no current daily document found in {folder['path']}")
    return str(selected["doc_path"])


def expand_repl_aliases(argv: list[str], current_doc: str | None) -> list[str]:
    return expand_repl_aliases_with_state(argv, {"current_doc": current_doc, "current_node": None})


def expand_repl_aliases_with_state(argv: list[str], session: dict[str, object]) -> list[str]:
    current_doc = session.get("current_doc")
    current_node = session.get("current_node")
    expanded: list[str] = []
    for token in argv:
        if token in {"@doc", "@current"} and isinstance(current_doc, str):
            expanded.append(current_doc)
        elif token == "@node" and isinstance(current_node, str):
            expanded.append(current_node)
        else:
            expanded.append(token)
    return expanded


def build_session_payload(session: dict[str, object]) -> dict[str, object]:
    history = list(session.get("command_history", []))
    return {
        "current_doc": session.get("current_doc"),
        "current_node": session.get("current_node"),
        "state_path": str(session_state_path()),
        "history_count": len(history),
    }


def root_json_output(ctx: click.Context | None) -> bool:
    if ctx is None:
        return False
    root = ctx.find_root()
    if root is None or root.obj is None:
        return False
    return bool(root.obj.get("json_output"))


def emit_json(payload: object) -> None:
    click.echo(json.dumps(payload, ensure_ascii=False, indent=2))


def emit_session_status(session: dict[str, object], json_output: bool) -> None:
    payload = build_session_payload(session)
    if json_output:
        emit_json(payload)
        return
    current_doc = payload["current_doc"] or "<unset>"
    current_node = payload["current_node"] or "<unset>"
    click.echo(f"Current doc: {current_doc}")
    click.echo(f"Current node: {current_node}")
    click.echo(f"State path: {payload['state_path']}")
    click.echo(f"History count: {payload['history_count']}")


def emit_session_history(session: dict[str, object], limit: int, json_output: bool) -> None:
    history = list(session.get("command_history", []))[-limit:]
    if json_output:
        emit_json({"history": history})
        return
    if not history:
        click.echo("History: <empty>")
        return
    click.echo("History:")
    for index, entry in enumerate(history, start=max(1, len(history) - limit + 1)):
        click.echo(f"  {index}. {entry}")


def invoke_probe_command(ctx: click.Context | None, command_name: str, probe_args: Sequence[str]) -> int:
    argv = [command_name, *list(probe_args)]
    if root_json_output(ctx) and "--json" not in argv:
        argv.append("--json")
    try:
        result = mubu_probe.main(argv)
    except SystemExit as exc:
        result = exc.code if isinstance(exc.code, int) else 1
    if result in (0, None) and "--help" not in argv and "-h" not in argv:
        append_command_history(" ".join(argv))
    return int(result or 0)


def print_repl_banner(skin: ReplSkin, program_name: str | None = None) -> None:
    normalized_program_name = normalize_program_name(program_name)
    click.echo("Mubu REPL")
    if normalized_program_name == PUBLIC_PROGRAM_NAME:
        click.echo(f"Command: {PUBLIC_PROGRAM_NAME}")
        click.echo(f"Version: {__version__}")
        if skin.skill_path:
            click.echo(f"Skill: {skin.skill_path}")
        click.echo("Type help for commands, quit to exit")
        click.echo()
    else:
        skin.print_banner()
    click.echo(f"History: {skin.history_file}")


def print_repl_help(program_name: str | None = None) -> None:
    click.echo(repl_help_text(program_name).rstrip())


def parse_history_limit(argv: Sequence[str]) -> int:
    if len(argv) < 2:
        return 10
    try:
        return max(1, int(argv[1]))
    except ValueError as exc:
        raise RuntimeError(f"history limit must be an integer: {argv[1]}") from exc


def handle_repl_builtin(
    argv: list[str],
    session: dict[str, object],
    program_name: str | None = None,
) -> tuple[bool, int]:
    if not argv:
        return True, 0

    command = argv[0]
    if command in {"exit", "quit"}:
        return True, 1
    if command == "help":
        print_repl_help(program_name)
        return True, 0
    if command == "current-doc":
        current_doc = session.get("current_doc")
        click.echo(f"Current doc: {current_doc}" if current_doc else "Current doc: <unset>")
        return True, 0
    if command == "current-node":
        current_node = session.get("current_node")
        click.echo(f"Current node: {current_node}" if current_node else "Current node: <unset>")
        return True, 0
    if command == "status":
        emit_session_status(session, json_output=False)
        return True, 0
    if command == "history":
        try:
            limit = parse_history_limit(argv)
        except RuntimeError as exc:
            click.echo(str(exc), err=True)
            return True, 0
        emit_session_history(session, limit, json_output=False)
        return True, 0
    if command == "state-path":
        click.echo(f"State path: {session_state_path()}")
        return True, 0
    if command == "clear-doc":
        session["current_doc"] = None
        save_session_state(session)
        append_command_history("clear-doc")
        click.echo("Current doc cleared.")
        return True, 0
    if command == "clear-node":
        session["current_node"] = None
        save_session_state(session)
        append_command_history("clear-node")
        click.echo("Current node cleared.")
        return True, 0
    if command == "use-doc":
        if len(argv) < 2:
            click.echo("use-doc requires a document reference.", err=True)
            return True, 0
        doc_ref = " ".join(argv[1:])
        session["current_doc"] = doc_ref
        save_session_state(session)
        append_command_history(f"use-doc {doc_ref}")
        click.echo(f"Current doc: {doc_ref}")
        return True, 0
    if command == "use-node":
        if len(argv) < 2:
            click.echo("use-node requires a node reference.", err=True)
            return True, 0
        node_ref = " ".join(argv[1:])
        session["current_node"] = node_ref
        save_session_state(session)
        append_command_history(f"use-node {node_ref}")
        click.echo(f"Current node: {node_ref}")
        return True, 0
    if command == "use-daily":
        folder_ref = " ".join(argv[1:]).strip() if len(argv) > 1 else None
        try:
            resolved_folder_ref = mubu_probe.resolve_daily_folder_ref(folder_ref)
            doc_ref = resolve_current_daily_doc_ref(resolved_folder_ref)
        except RuntimeError as exc:
            click.echo(str(exc), err=True)
            return True, 0
        session["current_doc"] = doc_ref
        save_session_state(session)
        append_command_history(f"use-daily {resolved_folder_ref}")
        click.echo(f"Current doc: {doc_ref}")
        return True, 0

    return False, 0


def run_repl(program_name: str | None = None) -> int:
    session = load_session_state()
    skin = ReplSkin("mubu", version=__version__, history_file=str(session_state_dir() / "history.txt"))
    prompt_session = skin.create_prompt_session()
    print_repl_banner(skin, program_name)
    if session.get("current_doc"):
        click.echo(f"Current doc: {session['current_doc']}")
    if session.get("current_node"):
        click.echo(f"Current node: {session['current_node']}")
    while True:
        try:
            line = skin.get_input(prompt_session)
        except EOFError:
            click.echo()
            skin.print_goodbye()
            return 0
        except KeyboardInterrupt:
            click.echo()
            continue

        line = line.strip()
        if not line:
            continue

        try:
            argv = shlex.split(line)
        except ValueError as exc:
            click.echo(f"parse error: {exc}", err=True)
            continue

        handled, control = handle_repl_builtin(argv, session, program_name)
        if handled:
            if control == 1:
                skin.print_goodbye()
                return 0
            session = load_session_state()
            continue

        argv = expand_repl_aliases_with_state(argv, session)
        result = dispatch(argv)
        if result not in (0, None):
            click.echo(f"command exited with status {result}", err=True)
        session = load_session_state()


@click.group(context_settings=CONTEXT_SETTINGS, invoke_without_command=True)
@click.option("--json", "json_output", is_flag=True, help="Emit JSON output for wrapped probe commands when supported.")
@click.pass_context
def cli(ctx: click.Context, json_output: bool) -> int:
    """Agent-native CLI for the Mubu desktop app with REPL and grouped command domains."""
    ctx.ensure_object(dict)
    ctx.obj["json_output"] = json_output
    ctx.obj["prog_name"] = normalize_program_name(ctx.info_name)
    if ctx.invoked_subcommand is None:
        return run_repl(ctx.obj["prog_name"])
    return 0


@cli.group(context_settings=CONTEXT_SETTINGS)
def discover() -> None:
    """Discovery commands for folders, documents, recency, and daily-document resolution."""


@discover.command("docs", context_settings=CONTEXT_SETTINGS, add_help_option=False)
@click.argument("probe_args", nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def discover_docs(ctx: click.Context, probe_args: tuple[str, ...]) -> int:
    """List latest known document snapshots from local backups."""
    return invoke_probe_command(ctx, "docs", probe_args)


@discover.command("folders", context_settings=CONTEXT_SETTINGS, add_help_option=False)
@click.argument("probe_args", nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def folders(ctx: click.Context, probe_args: tuple[str, ...]) -> int:
    """List folder metadata from local RxDB storage."""
    return invoke_probe_command(ctx, "folders", probe_args)


@discover.command("folder-docs", context_settings=CONTEXT_SETTINGS, add_help_option=False)
@click.argument("probe_args", nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def folder_docs(ctx: click.Context, probe_args: tuple[str, ...]) -> int:
    """List document metadata for one folder."""
    return invoke_probe_command(ctx, "folder-docs", probe_args)


@discover.command("path-docs", context_settings=CONTEXT_SETTINGS, add_help_option=False)
@click.argument("probe_args", nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def path_docs(ctx: click.Context, probe_args: tuple[str, ...]) -> int:
    """List documents for one folder path or folder id."""
    return invoke_probe_command(ctx, "path-docs", probe_args)


@discover.command("recent", context_settings=CONTEXT_SETTINGS, add_help_option=False)
@click.argument("probe_args", nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def recent(ctx: click.Context, probe_args: tuple[str, ...]) -> int:
    """List recently active documents using backups, metadata, and sync logs."""
    return invoke_probe_command(ctx, "recent", probe_args)


@discover.command("daily", context_settings=CONTEXT_SETTINGS, add_help_option=False)
@click.argument("probe_args", nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def daily(ctx: click.Context, probe_args: tuple[str, ...]) -> int:
    """Find Daily-style folders and list the documents inside them."""
    return invoke_probe_command(ctx, "daily", probe_args)


@discover.command("daily-current", context_settings=CONTEXT_SETTINGS, add_help_option=False)
@click.argument("probe_args", nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def daily_current(ctx: click.Context, probe_args: tuple[str, ...]) -> int:
    """Resolve the current daily document from one Daily-style folder."""
    return invoke_probe_command(ctx, "daily-current", probe_args)


@cli.group(context_settings=CONTEXT_SETTINGS)
def inspect() -> None:
    """Inspection commands for tree views, search, links, sync events, and live node targeting."""


@inspect.command("show", context_settings=CONTEXT_SETTINGS, add_help_option=False)
@click.argument("probe_args", nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def show(ctx: click.Context, probe_args: tuple[str, ...]) -> int:
    """Show the latest backup tree for one document."""
    return invoke_probe_command(ctx, "show", probe_args)


@inspect.command("search", context_settings=CONTEXT_SETTINGS, add_help_option=False)
@click.argument("probe_args", nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def search(ctx: click.Context, probe_args: tuple[str, ...]) -> int:
    """Search latest backups for matching node text or note content."""
    return invoke_probe_command(ctx, "search", probe_args)


@inspect.command("changes", context_settings=CONTEXT_SETTINGS, add_help_option=False)
@click.argument("probe_args", nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def changes(ctx: click.Context, probe_args: tuple[str, ...]) -> int:
    """Parse recent client-sync change events from local logs."""
    return invoke_probe_command(ctx, "changes", probe_args)


@inspect.command("links", context_settings=CONTEXT_SETTINGS, add_help_option=False)
@click.argument("probe_args", nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def links(ctx: click.Context, probe_args: tuple[str, ...]) -> int:
    """Extract outbound Mubu document links from one document backup."""
    return invoke_probe_command(ctx, "links", probe_args)


@inspect.command("open-path", context_settings=CONTEXT_SETTINGS, add_help_option=False)
@click.argument("probe_args", nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def open_path(ctx: click.Context, probe_args: tuple[str, ...]) -> int:
    """Open one document by full path, suffix path, title, or doc id."""
    return invoke_probe_command(ctx, "open-path", probe_args)


@inspect.command("doc-nodes", context_settings=CONTEXT_SETTINGS, add_help_option=False)
@click.argument("probe_args", nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def doc_nodes(ctx: click.Context, probe_args: tuple[str, ...]) -> int:
    """List live document nodes with node ids and update-target paths."""
    return invoke_probe_command(ctx, "doc-nodes", probe_args)


@inspect.command("daily-nodes", context_settings=CONTEXT_SETTINGS, add_help_option=False)
@click.argument("probe_args", nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def daily_nodes(ctx: click.Context, probe_args: tuple[str, ...]) -> int:
    """List live nodes from the current daily document in one step."""
    return invoke_probe_command(ctx, "daily-nodes", probe_args)


@cli.group(context_settings=CONTEXT_SETTINGS)
def mutate() -> None:
    """Mutation commands for dry-run-first atomic live edits against the Mubu API."""


@mutate.command("create-child", context_settings=CONTEXT_SETTINGS, add_help_option=False)
@click.argument("probe_args", nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def create_child(ctx: click.Context, probe_args: tuple[str, ...]) -> int:
    """Build or execute one child-node creation against the live Mubu API."""
    return invoke_probe_command(ctx, "create-child", probe_args)


@mutate.command("delete-node", context_settings=CONTEXT_SETTINGS, add_help_option=False)
@click.argument("probe_args", nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def delete_node(ctx: click.Context, probe_args: tuple[str, ...]) -> int:
    """Build or execute one node deletion against the live Mubu API."""
    return invoke_probe_command(ctx, "delete-node", probe_args)


@mutate.command("update-text", context_settings=CONTEXT_SETTINGS, add_help_option=False)
@click.argument("probe_args", nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def update_text(ctx: click.Context, probe_args: tuple[str, ...]) -> int:
    """Build or execute one text update against the live Mubu API."""
    return invoke_probe_command(ctx, "update-text", probe_args)


@cli.group()
def session() -> None:
    """Session and state commands for current document/node context and local command history."""


@session.command("status")
@click.option("--json", "json_output", is_flag=True, help="Emit session state as JSON.")
@click.pass_context
def session_status(ctx: click.Context, json_output: bool) -> int:
    """Show the current session state."""
    emit_session_status(load_session_state(), json_output=json_output or root_json_output(ctx))
    return 0


@session.command("state-path")
@click.option("--json", "json_output", is_flag=True, help="Emit the session state path as JSON.")
@click.pass_context
def state_path_command(ctx: click.Context, json_output: bool) -> int:
    """Show the session state file path."""
    payload = {"state_path": str(session_state_path())}
    if json_output or root_json_output(ctx):
        emit_json(payload)
    else:
        click.echo(payload["state_path"])
    return 0


@session.command("use-doc")
@click.argument("doc_ref", nargs=-1)
def use_doc(doc_ref: tuple[str, ...]) -> int:
    """Persist the current document reference."""
    if not doc_ref:
        raise click.UsageError("use-doc requires a document reference.")
    value = " ".join(doc_ref)
    session_state = load_session_state()
    session_state["current_doc"] = value
    save_session_state(session_state)
    append_command_history(f"session use-doc {value}")
    click.echo(f"Current doc: {value}")
    return 0


@session.command("use-node")
@click.argument("node_ref", nargs=-1)
def use_node(node_ref: tuple[str, ...]) -> int:
    """Persist the current node reference."""
    if not node_ref:
        raise click.UsageError("use-node requires a node reference.")
    value = " ".join(node_ref)
    session_state = load_session_state()
    session_state["current_node"] = value
    save_session_state(session_state)
    append_command_history(f"session use-node {value}")
    click.echo(f"Current node: {value}")
    return 0


@session.command("use-daily")
@click.argument("folder_ref", nargs=-1)
def use_daily(folder_ref: tuple[str, ...]) -> int:
    """Resolve and persist the current daily document reference."""
    raw_value = " ".join(folder_ref).strip() if folder_ref else None
    try:
        resolved_folder_ref = mubu_probe.resolve_daily_folder_ref(raw_value)
        doc_ref = resolve_current_daily_doc_ref(resolved_folder_ref)
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc
    session_state = load_session_state()
    session_state["current_doc"] = doc_ref
    save_session_state(session_state)
    append_command_history(f"session use-daily {resolved_folder_ref}")
    click.echo(f"Current doc: {doc_ref}")
    return 0


@session.command("clear-doc")
def clear_doc() -> int:
    """Clear the current document reference."""
    session_state = load_session_state()
    session_state["current_doc"] = None
    save_session_state(session_state)
    append_command_history("session clear-doc")
    click.echo("Current doc cleared.")
    return 0


@session.command("clear-node")
def clear_node() -> int:
    """Clear the current node reference."""
    session_state = load_session_state()
    session_state["current_node"] = None
    save_session_state(session_state)
    append_command_history("session clear-node")
    click.echo("Current node cleared.")
    return 0


@session.command("history")
@click.option("--limit", default=10, show_default=True, type=int, help="How many recent entries to show.")
@click.option("--json", "json_output", is_flag=True, help="Emit command history as JSON.")
@click.pass_context
def history_command(ctx: click.Context, limit: int, json_output: bool) -> int:
    """Show recent command history stored in session state."""
    emit_session_history(load_session_state(), max(1, limit), json_output=json_output or root_json_output(ctx))
    return 0


@cli.command("repl", help=REPL_COMMAND_HELP)
@click.pass_context
def repl_command(ctx: click.Context) -> int:
    """Interactive REPL for the Mubu CLI."""
    root = ctx.find_root()
    program_name = None
    if root is not None and root.obj is not None:
        program_name = root.obj.get("prog_name")
    return run_repl(program_name)


def create_legacy_command(command_name: str, help_text: str) -> click.Command:
    @click.command(name=command_name, help=help_text, context_settings=CONTEXT_SETTINGS, add_help_option=False)
    @click.argument("probe_args", nargs=-1, type=click.UNPROCESSED)
    @click.pass_context
    def legacy(ctx: click.Context, probe_args: tuple[str, ...]) -> int:
        return invoke_probe_command(ctx, command_name, probe_args)

    return legacy


for _command_name, _help_text in LEGACY_COMMANDS.items():
    cli.add_command(create_legacy_command(_command_name, _help_text))


def dispatch(argv: list[str] | None = None, prog_name: str | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    normalized_prog_name = normalize_program_name(prog_name or sys.argv[0])
    try:
        result = cli.main(args=args, prog_name=normalized_prog_name, standalone_mode=False)
    except click.exceptions.Exit as exc:
        return int(exc.exit_code)
    except click.ClickException as exc:
        exc.show()
        return int(exc.exit_code)
    return int(result or 0)


def entrypoint(argv: list[str] | None = None) -> int:
    return dispatch(argv, prog_name=sys.argv[0])


__all__ = [
    "REPL_HELP",
    "append_command_history",
    "build_session_payload",
    "cli",
    "default_session_state",
    "dispatch",
    "entrypoint",
    "normalize_program_name",
    "expand_repl_aliases",
    "expand_repl_aliases_with_state",
    "handle_repl_builtin",
    "load_session_state",
    "repl_help_text",
    "resolve_current_daily_doc_ref",
    "run_repl",
    "save_session_state",
    "session_state_dir",
    "session_state_path",
]
