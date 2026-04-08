from __future__ import annotations

import json
import shlex
import sys
from dataclasses import dataclass
from typing import Any

import click

from cli_anything.zotero import __version__
from cli_anything.zotero.core import analysis, catalog, discovery, experimental, imports, notes, rendering, session as session_mod
from cli_anything.zotero.utils.repl_skin import ReplSkin

try:
    from prompt_toolkit.output.win32 import NoConsoleScreenBufferError
except Exception:  # pragma: no cover - platform-specific import guard
    NoConsoleScreenBufferError = RuntimeError


CONTEXT_SETTINGS = {"ignore_unknown_options": False}


@dataclass(frozen=True)
class RootCliConfig:
    backend: str = "auto"
    data_dir: str | None = None
    profile_dir: str | None = None
    executable: str | None = None
    json_output: bool = False


def _stdout_encoding() -> str:
    return getattr(sys.stdout, "encoding", None) or "utf-8"


def _can_encode_for_stdout(text: str) -> bool:
    try:
        text.encode(_stdout_encoding())
    except UnicodeEncodeError:
        return False
    return True


def _safe_text_for_stdout(text: str) -> str:
    if _can_encode_for_stdout(text):
        return text
    return text.encode(_stdout_encoding(), errors="backslashreplace").decode(_stdout_encoding())


def _json_text(data: Any) -> str:
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if _can_encode_for_stdout(text):
        return text
    return json.dumps(data, ensure_ascii=True, indent=2)


def root_json_output(ctx: click.Context | None) -> bool:
    if ctx is None:
        return False
    root = ctx.find_root()
    if root is None or root.obj is None:
        return False
    cli_config = root.obj.get("cli_config")
    if isinstance(cli_config, RootCliConfig):
        return cli_config.json_output
    return bool(root.obj.get("json_output"))


def _build_runtime_from_config(config: RootCliConfig) -> discovery.RuntimeContext:
    return discovery.build_runtime_context(
        backend=config.backend,
        data_dir=config.data_dir,
        profile_dir=config.profile_dir,
        executable=config.executable,
    )


def _current_cli_config(ctx: click.Context | None) -> RootCliConfig:
    if ctx is None:
        return RootCliConfig()
    root = ctx.find_root()
    assert root is not None
    root.ensure_object(dict)
    cli_config = root.obj.get("cli_config")
    if isinstance(cli_config, RootCliConfig):
        return cli_config
    legacy = root.obj.get("config", {})
    cli_config = RootCliConfig(
        backend=legacy.get("backend", "auto"),
        data_dir=legacy.get("data_dir"),
        profile_dir=legacy.get("profile_dir"),
        executable=legacy.get("executable"),
        json_output=bool(root.obj.get("json_output")),
    )
    root.obj["cli_config"] = cli_config
    return cli_config


def _repl_root_args(config: RootCliConfig) -> list[str]:
    args = ["--backend", config.backend]
    if config.json_output:
        args.append("--json")
    if config.data_dir:
        args.extend(["--data-dir", config.data_dir])
    if config.profile_dir:
        args.extend(["--profile-dir", config.profile_dir])
    if config.executable:
        args.extend(["--executable", config.executable])
    return args


def current_runtime(ctx: click.Context) -> discovery.RuntimeContext:
    root = ctx.find_root()
    assert root is not None
    root.ensure_object(dict)
    cached = root.obj.get("runtime")
    config = _current_cli_config(ctx)
    if cached is None:
        cached = _build_runtime_from_config(config)
        root.obj["runtime"] = cached
    return cached


def current_session() -> dict[str, Any]:
    return session_mod.load_session_state()


def emit(ctx: click.Context | None, data: Any, *, message: str = "") -> None:
    if root_json_output(ctx):
        click.echo(_json_text(data))
        return
    if isinstance(data, str):
        click.echo(_safe_text_for_stdout(data))
        return
    if message:
        click.echo(_safe_text_for_stdout(message))
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                click.echo(_json_text(item))
            else:
                click.echo(_safe_text_for_stdout(str(item)))
        if not data:
            click.echo("[]")
        return
    if isinstance(data, dict):
        click.echo(_json_text(data))
        return
    click.echo(_safe_text_for_stdout(str(data)))


def _print_collection_tree(nodes: list[dict[str, Any]], level: int = 0) -> None:
    prefix = "  " * level
    for node in nodes:
        click.echo(f"{prefix}- {node['collectionName']} [{node['collectionID']}]")
        _print_collection_tree(node.get("children", []), level + 1)


def _require_experimental_flag(enabled: bool, command_name: str) -> None:
    if not enabled:
        raise click.ClickException(
            f"`{command_name}` is experimental and writes directly to zotero.sqlite. "
            "Pass --experimental to continue."
        )


def _normalize_session_library(runtime: discovery.RuntimeContext, library_ref: str) -> int:
    try:
        library_id = catalog.resolve_library_id(runtime, library_ref)
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc
    if library_id is None:
        raise click.ClickException("Library reference required")
    return library_id


def _import_exit_code(payload: dict[str, Any]) -> int:
    return 1 if payload.get("status") == "partial_success" else 0


@click.group(context_settings=CONTEXT_SETTINGS, invoke_without_command=True)
@click.option("--json", "json_output", is_flag=True, help="Emit machine-readable JSON.")
@click.option("--backend", type=click.Choice(["auto", "sqlite", "api"]), default="auto", show_default=True)
@click.option("--data-dir", default=None, help="Explicit Zotero data directory.")
@click.option("--profile-dir", default=None, help="Explicit Zotero profile directory.")
@click.option("--executable", default=None, help="Explicit Zotero executable path.")
@click.pass_context
def cli(ctx: click.Context, json_output: bool, backend: str, data_dir: str | None, profile_dir: str | None, executable: str | None) -> int:
    """Agent-native Zotero CLI using SQLite, connector, and Local API backends."""
    ctx.ensure_object(dict)
    cli_config = RootCliConfig(
        backend=backend,
        data_dir=data_dir,
        profile_dir=profile_dir,
        executable=executable,
        json_output=json_output,
    )
    ctx.obj["json_output"] = json_output
    ctx.obj["cli_config"] = cli_config
    ctx.obj["config"] = {
        "backend": backend,
        "data_dir": data_dir,
        "profile_dir": profile_dir,
        "executable": executable,
    }
    if ctx.invoked_subcommand is None:
        return run_repl(cli_config)
    return 0


@cli.group()
def app() -> None:
    """Application and runtime inspection commands."""


@app.command("status")
@click.pass_context
def app_status(ctx: click.Context) -> int:
    runtime = current_runtime(ctx)
    emit(ctx, runtime.to_status_payload())
    return 0


@app.command("version")
@click.pass_context
def app_version(ctx: click.Context) -> int:
    runtime = current_runtime(ctx)
    payload = {"package_version": __version__, "zotero_version": runtime.environment.version}
    emit(ctx, payload if root_json_output(ctx) else runtime.environment.version)
    return 0


@app.command("launch")
@click.option("--wait-timeout", default=30, show_default=True, type=int)
@click.pass_context
def app_launch(ctx: click.Context, wait_timeout: int) -> int:
    runtime = current_runtime(ctx)
    payload = discovery.launch_zotero(runtime, wait_timeout=wait_timeout)
    ctx.find_root().obj["runtime"] = None
    emit(ctx, payload)
    return 0


@app.command("enable-local-api")
@click.option("--launch", "launch_after_enable", is_flag=True, help="Launch Zotero and verify connector + Local API after enabling.")
@click.option("--wait-timeout", default=30, show_default=True, type=int)
@click.pass_context
def app_enable_local_api(ctx: click.Context, launch_after_enable: bool, wait_timeout: int) -> int:
    payload = imports.enable_local_api(current_runtime(ctx), launch=launch_after_enable, wait_timeout=wait_timeout)
    ctx.find_root().obj["runtime"] = None
    emit(ctx, payload)
    return 0


@app.command("ping")
@click.pass_context
def app_ping(ctx: click.Context) -> int:
    runtime = current_runtime(ctx)
    if not runtime.connector_available:
        raise click.ClickException(runtime.connector_message)
    emit(ctx, {"connector_available": True, "message": runtime.connector_message})
    return 0


@cli.group()
def collection() -> None:
    """Collection inspection and selection commands."""


@collection.command("list")
@click.pass_context
def collection_list(ctx: click.Context) -> int:
    emit(ctx, catalog.list_collections(current_runtime(ctx), session=current_session()))
    return 0


@collection.command("find")
@click.argument("query")
@click.option("--limit", default=20, show_default=True, type=int)
@click.pass_context
def collection_find_command(ctx: click.Context, query: str, limit: int) -> int:
    emit(ctx, catalog.find_collections(current_runtime(ctx), query, limit=limit, session=current_session()))
    return 0


@collection.command("tree")
@click.pass_context
def collection_tree_command(ctx: click.Context) -> int:
    tree = catalog.collection_tree(current_runtime(ctx), session=current_session())
    if root_json_output(ctx):
        emit(ctx, tree)
    else:
        _print_collection_tree(tree)
    return 0


@collection.command("get")
@click.argument("ref", required=False)
@click.pass_context
def collection_get(ctx: click.Context, ref: str | None) -> int:
    emit(ctx, catalog.get_collection(current_runtime(ctx), ref, session=current_session()))
    return 0


@collection.command("items")
@click.argument("ref", required=False)
@click.pass_context
def collection_items_command(ctx: click.Context, ref: str | None) -> int:
    emit(ctx, catalog.collection_items(current_runtime(ctx), ref, session=current_session()))
    return 0


def _persist_selected_collection(selected: dict[str, Any]) -> dict[str, Any]:
    state = current_session()
    state["current_library"] = selected.get("libraryID")
    state["current_collection"] = selected.get("id")
    session_mod.save_session_state(state)
    return state


@collection.command("use-selected")
@click.pass_context
def collection_use_selected(ctx: click.Context) -> int:
    selected = catalog.use_selected_collection(current_runtime(ctx))
    _persist_selected_collection(selected)
    session_mod.append_command_history("collection use-selected")
    emit(ctx, selected)
    return 0


@collection.command("create")
@click.argument("name")
@click.option("--parent", "parent_ref", default=None, help="Parent collection ID or key.")
@click.option("--library", "library_ref", default=None, help="Library ID or treeView ID (user library only).")
@click.option("--experimental", "experimental_mode", is_flag=True, help="Acknowledge experimental direct SQLite write mode.")
@click.pass_context
def collection_create_command(
    ctx: click.Context,
    name: str,
    parent_ref: str | None,
    library_ref: str | None,
    experimental_mode: bool,
) -> int:
    _require_experimental_flag(experimental_mode, "collection create")
    emit(
        ctx,
        experimental.create_collection(
            current_runtime(ctx),
            name,
            parent_ref=parent_ref,
            library_ref=library_ref,
            session=current_session(),
        ),
    )
    return 0


@cli.group()
def item() -> None:
    """Item inspection and rendering commands."""


@item.command("list")
@click.option("--limit", default=20, show_default=True, type=int)
@click.pass_context
def item_list(ctx: click.Context, limit: int) -> int:
    emit(ctx, catalog.list_items(current_runtime(ctx), session=current_session(), limit=limit))
    return 0


@item.command("find")
@click.argument("query")
@click.option("--collection", "collection_ref", default=None, help="Collection ID or key scope.")
@click.option("--limit", default=20, show_default=True, type=int)
@click.option("--exact-title", is_flag=True, help="Use exact title matching via SQLite.")
@click.pass_context
def item_find_command(
    ctx: click.Context,
    query: str,
    collection_ref: str | None,
    limit: int,
    exact_title: bool,
) -> int:
    emit(
        ctx,
        catalog.find_items(
            current_runtime(ctx),
            query,
            collection_ref=collection_ref,
            limit=limit,
            exact_title=exact_title,
            session=current_session(),
        ),
    )
    return 0


@item.command("get")
@click.argument("ref", required=False)
@click.pass_context
def item_get(ctx: click.Context, ref: str | None) -> int:
    emit(ctx, catalog.get_item(current_runtime(ctx), ref, session=current_session()))
    return 0


@item.command("children")
@click.argument("ref", required=False)
@click.pass_context
def item_children_command(ctx: click.Context, ref: str | None) -> int:
    emit(ctx, catalog.item_children(current_runtime(ctx), ref, session=current_session()))
    return 0


@item.command("notes")
@click.argument("ref", required=False)
@click.pass_context
def item_notes_command(ctx: click.Context, ref: str | None) -> int:
    emit(ctx, catalog.item_notes(current_runtime(ctx), ref, session=current_session()))
    return 0


@item.command("attachments")
@click.argument("ref", required=False)
@click.pass_context
def item_attachments_command(ctx: click.Context, ref: str | None) -> int:
    emit(ctx, catalog.item_attachments(current_runtime(ctx), ref, session=current_session()))
    return 0


@item.command("file")
@click.argument("ref", required=False)
@click.pass_context
def item_file_command(ctx: click.Context, ref: str | None) -> int:
    emit(ctx, catalog.item_file(current_runtime(ctx), ref, session=current_session()))
    return 0


@item.command("export")
@click.argument("ref", required=False)
@click.option("--format", "fmt", type=click.Choice(list(rendering.SUPPORTED_EXPORT_FORMATS)), required=True)
@click.pass_context
def item_export(ctx: click.Context, ref: str | None, fmt: str) -> int:
    payload = rendering.export_item(current_runtime(ctx), ref, fmt, session=current_session())
    emit(ctx, payload if root_json_output(ctx) else payload["content"])
    return 0


@item.command("citation")
@click.argument("ref", required=False)
@click.option("--style", default=None)
@click.option("--locale", default=None)
@click.option("--linkwrap", is_flag=True)
@click.pass_context
def item_citation(ctx: click.Context, ref: str | None, style: str | None, locale: str | None, linkwrap: bool) -> int:
    payload = rendering.citation_item(current_runtime(ctx), ref, style=style, locale=locale, linkwrap=linkwrap, session=current_session())
    emit(ctx, payload if root_json_output(ctx) else (payload.get("citation") or ""))
    return 0


@item.command("bibliography")
@click.argument("ref", required=False)
@click.option("--style", default=None)
@click.option("--locale", default=None)
@click.option("--linkwrap", is_flag=True)
@click.pass_context
def item_bibliography(ctx: click.Context, ref: str | None, style: str | None, locale: str | None, linkwrap: bool) -> int:
    payload = rendering.bibliography_item(current_runtime(ctx), ref, style=style, locale=locale, linkwrap=linkwrap, session=current_session())
    emit(ctx, payload if root_json_output(ctx) else (payload.get("bibliography") or ""))
    return 0


@item.command("context")
@click.argument("ref", required=False)
@click.option("--include-notes", is_flag=True)
@click.option("--include-bibtex", is_flag=True)
@click.option("--include-csljson", is_flag=True)
@click.option("--include-links", is_flag=True)
@click.pass_context
def item_context_command(
    ctx: click.Context,
    ref: str | None,
    include_notes: bool,
    include_bibtex: bool,
    include_csljson: bool,
    include_links: bool,
) -> int:
    payload = analysis.build_item_context(
        current_runtime(ctx),
        ref,
        include_notes=include_notes,
        include_bibtex=include_bibtex,
        include_csljson=include_csljson,
        include_links=include_links,
        session=current_session(),
    )
    emit(ctx, payload if root_json_output(ctx) else payload["prompt_context"])
    return 0


@item.command("analyze")
@click.argument("ref", required=False)
@click.option("--question", required=True)
@click.option("--model", required=True)
@click.option("--include-notes", is_flag=True)
@click.option("--include-bibtex", is_flag=True)
@click.option("--include-csljson", is_flag=True)
@click.pass_context
def item_analyze_command(
    ctx: click.Context,
    ref: str | None,
    question: str,
    model: str,
    include_notes: bool,
    include_bibtex: bool,
    include_csljson: bool,
) -> int:
    payload = analysis.analyze_item(
        current_runtime(ctx),
        ref,
        question=question,
        model=model,
        include_notes=include_notes,
        include_bibtex=include_bibtex,
        include_csljson=include_csljson,
        session=current_session(),
    )
    emit(ctx, payload if root_json_output(ctx) else payload["answer"])
    return 0


@item.command("add-to-collection")
@click.argument("item_ref")
@click.argument("collection_ref")
@click.option("--experimental", "experimental_mode", is_flag=True, help="Acknowledge experimental direct SQLite write mode.")
@click.pass_context
def item_add_to_collection_command(ctx: click.Context, item_ref: str, collection_ref: str, experimental_mode: bool) -> int:
    _require_experimental_flag(experimental_mode, "item add-to-collection")
    emit(ctx, experimental.add_item_to_collection(current_runtime(ctx), item_ref, collection_ref, session=current_session()))
    return 0


@item.command("move-to-collection")
@click.argument("item_ref")
@click.argument("collection_ref")
@click.option("--from", "from_refs", multiple=True, help="Source collection ID or key. Repeatable.")
@click.option("--all-other-collections", is_flag=True, help="Remove the item from all other collections after adding the target.")
@click.option("--experimental", "experimental_mode", is_flag=True, help="Acknowledge experimental direct SQLite write mode.")
@click.pass_context
def item_move_to_collection_command(
    ctx: click.Context,
    item_ref: str,
    collection_ref: str,
    from_refs: tuple[str, ...],
    all_other_collections: bool,
    experimental_mode: bool,
) -> int:
    _require_experimental_flag(experimental_mode, "item move-to-collection")
    emit(
        ctx,
        experimental.move_item_to_collection(
            current_runtime(ctx),
            item_ref,
            collection_ref,
            from_refs=list(from_refs),
            all_other_collections=all_other_collections,
            session=current_session(),
        ),
    )
    return 0


@cli.group()
def search() -> None:
    """Saved-search inspection commands."""


@search.command("list")
@click.pass_context
def search_list(ctx: click.Context) -> int:
    emit(ctx, catalog.list_searches(current_runtime(ctx), session=current_session()))
    return 0


@search.command("get")
@click.argument("ref")
@click.pass_context
def search_get(ctx: click.Context, ref: str) -> int:
    emit(ctx, catalog.get_search(current_runtime(ctx), ref, session=current_session()))
    return 0


@search.command("items")
@click.argument("ref")
@click.pass_context
def search_items_command(ctx: click.Context, ref: str) -> int:
    emit(ctx, catalog.search_items(current_runtime(ctx), ref, session=current_session()))
    return 0


@cli.group()
def tag() -> None:
    """Tag inspection commands."""


@tag.command("list")
@click.pass_context
def tag_list(ctx: click.Context) -> int:
    emit(ctx, catalog.list_tags(current_runtime(ctx), session=current_session()))
    return 0


@tag.command("items")
@click.argument("tag_ref")
@click.pass_context
def tag_items_command(ctx: click.Context, tag_ref: str) -> int:
    emit(ctx, catalog.tag_items(current_runtime(ctx), tag_ref, session=current_session()))
    return 0


@cli.group()
def style() -> None:
    """Installed CSL style inspection commands."""


@style.command("list")
@click.pass_context
def style_list(ctx: click.Context) -> int:
    emit(ctx, catalog.list_styles(current_runtime(ctx)))
    return 0


@cli.group("import")
def import_group() -> None:
    """Official Zotero import and write commands."""


@import_group.command("file")
@click.argument("path")
@click.option("--collection", "collection_ref", default=None, help="Collection ID, key, or treeViewID target.")
@click.option("--tag", "tags", multiple=True, help="Tag to apply after import. Repeatable.")
@click.option("--attachments-manifest", default=None, help="Optional JSON manifest describing attachments for imported records.")
@click.option("--attachment-delay-ms", default=0, show_default=True, type=int, help="Default delay before each URL attachment download.")
@click.option("--attachment-timeout", default=60, show_default=True, type=int, help="Default timeout in seconds for attachment download/upload.")
@click.pass_context
def import_file_command(
    ctx: click.Context,
    path: str,
    collection_ref: str | None,
    tags: tuple[str, ...],
    attachments_manifest: str | None,
    attachment_delay_ms: int,
    attachment_timeout: int,
) -> int:
    payload = imports.import_file(
        current_runtime(ctx),
        path,
        collection_ref=collection_ref,
        tags=list(tags),
        session=current_session(),
        attachments_manifest=attachments_manifest,
        attachment_delay_ms=attachment_delay_ms,
        attachment_timeout=attachment_timeout,
    )
    emit(ctx, payload)
    return _import_exit_code(payload)


@import_group.command("json")
@click.argument("path")
@click.option("--collection", "collection_ref", default=None, help="Collection ID, key, or treeViewID target.")
@click.option("--tag", "tags", multiple=True, help="Tag to apply after import. Repeatable.")
@click.option("--attachment-delay-ms", default=0, show_default=True, type=int, help="Default delay before each URL attachment download.")
@click.option("--attachment-timeout", default=60, show_default=True, type=int, help="Default timeout in seconds for attachment download/upload.")
@click.pass_context
def import_json_command(
    ctx: click.Context,
    path: str,
    collection_ref: str | None,
    tags: tuple[str, ...],
    attachment_delay_ms: int,
    attachment_timeout: int,
) -> int:
    payload = imports.import_json(
        current_runtime(ctx),
        path,
        collection_ref=collection_ref,
        tags=list(tags),
        session=current_session(),
        attachment_delay_ms=attachment_delay_ms,
        attachment_timeout=attachment_timeout,
    )
    emit(ctx, payload)
    return _import_exit_code(payload)


@cli.group()
def note() -> None:
    """Read and add child notes."""


@note.command("get")
@click.argument("ref")
@click.pass_context
def note_get_command(ctx: click.Context, ref: str) -> int:
    payload = notes.get_note(current_runtime(ctx), ref, session=current_session())
    emit(ctx, payload if root_json_output(ctx) else (payload.get("noteText") or payload.get("noteContent") or ""))
    return 0


@note.command("add")
@click.argument("item_ref")
@click.option("--text", default=None, help="Inline note content.")
@click.option("--file", "file_path", default=None, help="Read note content from a file.")
@click.option("--format", "fmt", type=click.Choice(["text", "markdown", "html"]), default="text", show_default=True)
@click.pass_context
def note_add_command(
    ctx: click.Context,
    item_ref: str,
    text: str | None,
    file_path: str | None,
    fmt: str,
) -> int:
    emit(
        ctx,
        notes.add_note(
            current_runtime(ctx),
            item_ref,
            text=text,
            file_path=file_path,
            fmt=fmt,
            session=current_session(),
        ),
    )
    return 0


@cli.group()
def session() -> None:
    """Session and REPL context commands."""


@session.command("status")
@click.pass_context
def session_status(ctx: click.Context) -> int:
    emit(ctx, session_mod.build_session_payload(current_session()))
    return 0


@session.command("use-library")
@click.argument("library_ref")
@click.pass_context
def session_use_library(ctx: click.Context, library_ref: str) -> int:
    state = current_session()
    state["current_library"] = _normalize_session_library(current_runtime(ctx), library_ref)
    session_mod.save_session_state(state)
    session_mod.append_command_history(f"session use-library {library_ref}")
    emit(ctx, session_mod.build_session_payload(state))
    return 0


@session.command("use-collection")
@click.argument("collection_ref")
@click.pass_context
def session_use_collection(ctx: click.Context, collection_ref: str) -> int:
    state = current_session()
    state["current_collection"] = collection_ref
    session_mod.save_session_state(state)
    session_mod.append_command_history(f"session use-collection {collection_ref}")
    emit(ctx, session_mod.build_session_payload(state))
    return 0


@session.command("use-item")
@click.argument("item_ref")
@click.pass_context
def session_use_item(ctx: click.Context, item_ref: str) -> int:
    state = current_session()
    state["current_item"] = item_ref
    session_mod.save_session_state(state)
    session_mod.append_command_history(f"session use-item {item_ref}")
    emit(ctx, session_mod.build_session_payload(state))
    return 0


@session.command("use-selected")
@click.pass_context
def session_use_selected(ctx: click.Context) -> int:
    selected = catalog.use_selected_collection(current_runtime(ctx))
    state = _persist_selected_collection(selected)
    session_mod.append_command_history("session use-selected")
    emit(ctx, {"selected": selected, "session": session_mod.build_session_payload(state)})
    return 0


@session.command("clear-library")
@click.pass_context
def session_clear_library(ctx: click.Context) -> int:
    state = current_session()
    state["current_library"] = None
    session_mod.save_session_state(state)
    session_mod.append_command_history("session clear-library")
    emit(ctx, session_mod.build_session_payload(state))
    return 0


@session.command("clear-collection")
@click.pass_context
def session_clear_collection(ctx: click.Context) -> int:
    state = current_session()
    state["current_collection"] = None
    session_mod.save_session_state(state)
    session_mod.append_command_history("session clear-collection")
    emit(ctx, session_mod.build_session_payload(state))
    return 0


@session.command("clear-item")
@click.pass_context
def session_clear_item(ctx: click.Context) -> int:
    state = current_session()
    state["current_item"] = None
    session_mod.save_session_state(state)
    session_mod.append_command_history("session clear-item")
    emit(ctx, session_mod.build_session_payload(state))
    return 0


@session.command("history")
@click.option("--limit", default=10, show_default=True, type=int)
@click.pass_context
def session_history(ctx: click.Context, limit: int) -> int:
    emit(ctx, {"history": current_session().get("command_history", [])[-limit:]})
    return 0


def repl_help_text() -> str:
    return """Interactive REPL for cli-anything-zotero

Builtins:
  help                    Show this help
  exit, quit              Leave the REPL
  current-library         Show the current library reference
  current-collection      Show the current collection reference
  current-item            Show the current item reference
  use-library <ref>       Persist current library
  use-collection <ref>    Persist current collection
  use-item <ref>          Persist current item
  use-selected            Read and persist the collection selected in Zotero
  clear-library           Clear current library
  clear-collection        Clear current collection
  clear-item              Clear current item
  status                  Show current session status
  history [limit]         Show recent command history
  state-path              Show the session state file path
"""


def _repl_echo(config: RootCliConfig, data: Any = None, *, text: str | None = None) -> None:
    if config.json_output:
        click.echo(_json_text(data))
        return
    if text is not None:
        click.echo(_safe_text_for_stdout(text))
        return
    if isinstance(data, str):
        click.echo(_safe_text_for_stdout(data))
        return
    click.echo(_json_text(data))


def _handle_repl_builtin(argv: list[str], skin: ReplSkin, config: RootCliConfig) -> tuple[bool, int]:
    if not argv:
        return True, 0
    cmd = argv[0]
    state = current_session()
    if cmd in {"exit", "quit"}:
        return True, 1
    if cmd == "help":
        click.echo(repl_help_text())
        return True, 0
    if cmd == "current-library":
        _repl_echo(
            config,
            {"current_library": state.get("current_library")},
            text=f"Current library: {state.get('current_library') or '<unset>'}",
        )
        return True, 0
    if cmd == "current-collection":
        _repl_echo(
            config,
            {"current_collection": state.get("current_collection")},
            text=f"Current collection: {state.get('current_collection') or '<unset>'}",
        )
        return True, 0
    if cmd == "current-item":
        _repl_echo(
            config,
            {"current_item": state.get("current_item")},
            text=f"Current item: {state.get('current_item') or '<unset>'}",
        )
        return True, 0
    if cmd == "status":
        _repl_echo(config, session_mod.build_session_payload(state))
        return True, 0
    if cmd == "history":
        limit = 10
        if len(argv) > 1:
            try:
                limit = max(1, int(argv[1]))
            except ValueError:
                skin.warning(f"history limit must be an integer: {argv[1]}")
                return True, 0
        _repl_echo(config, {"history": state.get("command_history", [])[-limit:]})
        return True, 0
    if cmd == "state-path":
        _repl_echo(config, {"state_path": str(session_mod.session_state_path())}, text=str(session_mod.session_state_path()))
        return True, 0
    if cmd == "use-library" and len(argv) > 1:
        library_ref = " ".join(argv[1:])
        try:
            state["current_library"] = _normalize_session_library(_build_runtime_from_config(config), library_ref)
        except click.ClickException as exc:
            skin.error(exc.format_message())
            return True, 0
        session_mod.save_session_state(state)
        session_mod.append_command_history(f"use-library {library_ref}")
        _repl_echo(
            config,
            session_mod.build_session_payload(state),
            text=f"Current library: {state['current_library']}",
        )
        return True, 0
    if cmd == "use-collection" and len(argv) > 1:
        state["current_collection"] = " ".join(argv[1:])
        session_mod.save_session_state(state)
        session_mod.append_command_history(f"use-collection {' '.join(argv[1:])}")
        _repl_echo(
            config,
            session_mod.build_session_payload(state),
            text=f"Current collection: {state['current_collection']}",
        )
        return True, 0
    if cmd == "use-item" and len(argv) > 1:
        state["current_item"] = " ".join(argv[1:])
        session_mod.save_session_state(state)
        session_mod.append_command_history(f"use-item {' '.join(argv[1:])}")
        _repl_echo(
            config,
            session_mod.build_session_payload(state),
            text=f"Current item: {state['current_item']}",
        )
        return True, 0
    if cmd == "clear-library":
        state["current_library"] = None
        session_mod.save_session_state(state)
        _repl_echo(config, session_mod.build_session_payload(state), text="Current library cleared.")
        return True, 0
    if cmd == "clear-collection":
        state["current_collection"] = None
        session_mod.save_session_state(state)
        _repl_echo(config, session_mod.build_session_payload(state), text="Current collection cleared.")
        return True, 0
    if cmd == "clear-item":
        state["current_item"] = None
        session_mod.save_session_state(state)
        _repl_echo(config, session_mod.build_session_payload(state), text="Current item cleared.")
        return True, 0
    if cmd == "use-selected":
        try:
            runtime = _build_runtime_from_config(config)
            selected = catalog.use_selected_collection(runtime)
        except Exception as exc:
            skin.error(str(exc))
            return True, 0
        persisted_state = _persist_selected_collection(selected)
        session_mod.append_command_history("use-selected")
        if config.json_output:
            _repl_echo(config, {"selected": selected, "session": session_mod.build_session_payload(persisted_state)})
        else:
            _repl_echo(config, selected)
        return True, 0
    return False, 0


def _supports_fancy_repl_output() -> bool:
    is_tty = getattr(sys.stdout, "isatty", lambda: False)()
    if not is_tty:
        return False
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        "▸↑⊙﹞".encode(encoding)
    except UnicodeEncodeError:
        return False
    return True


def _safe_print_banner(skin: ReplSkin) -> None:
    if not _supports_fancy_repl_output():
        click.echo("cli-anything-zotero REPL")
        click.echo(f"Skill: {skin.skill_path}")
        click.echo("Type help for commands, quit to exit")
        return
    try:
        skin.print_banner()
    except UnicodeEncodeError:
        click.echo("cli-anything-zotero REPL")
        click.echo(f"Skill: {skin.skill_path}")
        click.echo("Type help for commands, quit to exit")


def _safe_print_goodbye(skin: ReplSkin) -> None:
    if not _supports_fancy_repl_output():
        click.echo("Goodbye!")
        return
    try:
        skin.print_goodbye()
    except UnicodeEncodeError:
        click.echo("Goodbye!")


def run_repl(config: RootCliConfig | None = None) -> int:
    config = config or RootCliConfig()
    skin = ReplSkin("zotero", version=__version__)
    prompt_session = None
    try:
        prompt_session = skin.create_prompt_session()
    except NoConsoleScreenBufferError:
        prompt_session = None
    _safe_print_banner(skin)
    while True:
        try:
            if prompt_session is None:
                line = input("zotero> ").strip()
            else:
                line = skin.get_input(prompt_session).strip()
        except EOFError:
            click.echo()
            _safe_print_goodbye(skin)
            return 0
        except KeyboardInterrupt:
            click.echo()
            continue
        if not line:
            continue
        try:
            argv = shlex.split(line)
        except ValueError as exc:
            skin.error(f"parse error: {exc}")
            continue
        handled, control = _handle_repl_builtin(argv, skin, config)
        if handled:
            if control == 1:
                _safe_print_goodbye(skin)
                return 0
            continue
        expanded = session_mod.expand_repl_aliases_with_state(argv, current_session())
        result = dispatch(_repl_root_args(config) + expanded)
        if result not in (0, None):
            skin.warning(f"command exited with status {result}")
        else:
            session_mod.append_command_history(line)


@cli.command("repl")
@click.pass_context
def repl_command(ctx: click.Context) -> int:
    """Start the interactive REPL."""
    return run_repl(_current_cli_config(ctx))


def dispatch(argv: list[str] | None = None, prog_name: str | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        result = cli.main(args=args, prog_name=prog_name or "cli-anything-zotero", standalone_mode=False)
    except click.exceptions.Exit as exc:
        return int(exc.exit_code)
    except click.ClickException as exc:
        exc.show()
        return int(exc.exit_code)
    return int(result or 0)


def entrypoint(argv: list[str] | None = None) -> int:
    return dispatch(argv, prog_name=sys.argv[0])
