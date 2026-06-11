#!/usr/bin/env python3

import json
import os
import shlex
import sys
from typing import Optional

import click

from cli_anything.joplin.core import attach as attach_mod
from cli_anything.joplin.core import backend as backend_mod
from cli_anything.joplin.core import config as config_mod
from cli_anything.joplin.core import interop as interop_mod
from cli_anything.joplin.core import notebooks as notebook_mod
from cli_anything.joplin.core import notes as note_mod
from cli_anything.joplin.core import project as project_mod
from cli_anything.joplin.core import search as search_mod
from cli_anything.joplin.core import status as status_mod
from cli_anything.joplin.core import sync as sync_mod
from cli_anything.joplin.core import tags as tag_mod
from cli_anything.joplin.core import todos as todo_mod
from cli_anything.joplin.core.session import Session
from cli_anything.joplin.utils.joplin_backend import BackendConfig
from cli_anything.joplin.utils.repl_skin import ReplSkin

_session: Optional[Session] = None
_json_output = False
_repl_mode = False


def get_session() -> Session:
    global _session
    if _session is None:
        _session = Session()
    return _session


def _json_envelope(ok: bool, command: str, data=None, error: Exception | None = None):
    payload = {
        "ok": ok,
        "command": command,
        "data": data,
        "error": None,
    }
    if error is not None:
        payload["error"] = {
            "type": type(error).__name__,
            "message": str(error),
        }
    return payload


def output(data, message: str = "", command: str = ""):
    if _json_output:
        click.echo(json.dumps(_json_envelope(True, command or "unknown", data=data), indent=2, ensure_ascii=False, default=str))
        return

    if message:
        click.echo(message)
    if isinstance(data, dict):
        for k, v in data.items():
            click.echo(f"{k}: {v}")
    elif isinstance(data, list):
        for item in data:
            click.echo(item)
    elif data is not None:
        click.echo(data)


def _emit_error(err: Exception, command: str = "unknown"):
    if _json_output:
        click.echo(json.dumps(_json_envelope(False, command, data=None, error=err), ensure_ascii=False))
    else:
        click.echo(f"Error: {err}", err=True)


def handle_error(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (RuntimeError, ValueError, FileNotFoundError, IndexError) as e:
            _emit_error(e, command=func.__name__.replace("_", ".", 1))
            if not _repl_mode:
                sys.exit(1)
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


def _backend_config(binary: Optional[str], profile: Optional[str]) -> BackendConfig:
    """Resolve the backend config for the current command.

    Resolution precedence:
      1. Explicit CLI flags (`--binary`, `--profile`) when the user passed them.
      2. Values persisted in the loaded harness project's `backend` section.
      3. Built-in defaults (`joplin` binary, no profile).

    The CLI options use sentinel `None` defaults so we can distinguish "user
    omitted the flag" from "user explicitly passed --binary joplin"; passing
    the default would otherwise silently override the project's saved binary.
    """
    sess = get_session()
    if sess.has_project():
        proj = sess.get_project()
        backend = proj.get("backend", {}) or {}
        resolved_binary = binary if binary is not None else backend.get("binary") or "joplin"
        resolved_profile = profile if profile is not None else backend.get("profile")
        return BackendConfig(binary=resolved_binary, profile=resolved_profile)
    return BackendConfig(binary=binary or "joplin", profile=profile)


@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, help="Output as JSON")
@click.option("--project", "project_path", type=str, default=None, help="Harness project JSON path")
@click.option(
    "--binary",
    type=str,
    default=None,
    help="Joplin CLI binary name/path (defaults to the project's saved binary or 'joplin')",
)
@click.option("--profile", type=str, default=None, help="Joplin profile path")
@click.option("--dry-run", "dry_run", is_flag=True, default=False, help="Run command without saving harness project")
@click.pass_context
def cli(ctx, use_json, project_path, binary, profile, dry_run):
    """cli-anything-joplin - Stateful Joplin harness CLI."""
    global _json_output
    _json_output = use_json

    sess = get_session()

    if project_path:
        if not sess.has_project() and os.path.exists(project_path):
            proj = project_mod.open_project(project_path)
            sess.set_project(proj, project_path)

    ctx.ensure_object(dict)
    ctx.obj["binary"] = binary
    ctx.obj["profile"] = profile
    ctx.obj["dry_run"] = dry_run

    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


@cli.result_callback()
def auto_save_on_exit(result, use_json, project_path, binary, profile, dry_run, **kwargs):
    if _repl_mode:
        return
    if dry_run:
        return
    sess = get_session()
    if sess.has_project() and sess._modified and sess.project_path:
        try:
            sess.save_session()
        except Exception as e:
            click.echo(f"Warning: Auto-save failed: {e}", err=True)


@cli.group()
def project():
    """Project management commands."""


@project.command("new")
@click.option("--name", "name", default="joplin-project", help="Project name")
@click.option("--output", "output_path", "-o", required=False, help="Output path")
@click.pass_context
@handle_error
def project_new(ctx, name, output_path):
    proj = project_mod.create_project(
        name=name,
        backend_binary=ctx.obj["binary"] or "joplin",
        backend_profile=ctx.obj["profile"],
    )
    sess = get_session()
    sess.set_project(proj, output_path)
    if output_path:
        sess.save_session(output_path)
    output(project_mod.project_info(proj), f"Created project: {name}", command="project.new")


@project.command("open")
@click.argument("path")
@handle_error
def project_open(path):
    proj = project_mod.open_project(path)
    sess = get_session()
    sess.set_project(proj, path)
    output(project_mod.project_info(proj), f"Opened: {path}", command="project.open")


@project.command("save")
@click.argument("path", required=False)
@handle_error
def project_save(path):
    sess = get_session()
    saved = sess.save_session(path)
    output({"saved": saved}, f"Saved project: {saved}", command="project.save")


@project.command("info")
@handle_error
def project_info():
    sess = get_session()
    output(project_mod.project_info(sess.get_project()), command="project.info")


@project.command("json")
@handle_error
def project_json():
    sess = get_session()
    output(sess.get_project(), command="project.json")


@project.command("status")
@handle_error
def project_status():
    sess = get_session()
    proj = sess.get_project()
    output(
        {
            "project": project_mod.project_info(proj),
            "project_path": sess.project_path,
            "session": sess.status(),
        },
        command="project.status",
    )


@cli.group("notebooks")
def notebooks_group():
    """Notebook commands."""


@notebooks_group.command("list")
@click.option("--limit", "limit", type=int, default=None)
@click.option("--sort", "sort", default=None)
@click.option("--reverse", is_flag=True, default=False)
@click.option("--long", "long", is_flag=True, default=False)
@click.pass_context
@handle_error
def notebooks_list(ctx, limit, sort, reverse, long):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    result = notebook_mod.list_notebooks(cfg, limit=limit, sort=sort, reverse=reverse, long=long)
    output(result.get("data", result), command="notebooks.list")


@notebooks_group.command("create")
@click.argument("title")
@click.option("--parent", "parent", default=None)
@click.pass_context
@handle_error
def notebooks_create(ctx, title, parent):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    result = notebook_mod.create_notebook(cfg, title=title, parent=parent)
    sess = get_session()
    if sess.has_project():
        sess.snapshot(f"Create notebook: {title}")
        project_mod.add_history(sess.get_project(), "notebook.create", {"title": title, "parent": parent})
    output(result, f"Created notebook: {title}", command="notebooks.create")


@notebooks_group.command("use")
@click.argument("notebook")
@click.pass_context
@handle_error
def notebooks_use(ctx, notebook):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    result = notebook_mod.use_notebook(cfg, notebook=notebook)
    sess = get_session()
    if sess.has_project():
        sess.snapshot(f"Use notebook: {notebook}")
        sess.get_project().setdefault("context", {})["current_notebook"] = notebook
        project_mod.add_history(sess.get_project(), "notebook.use", {"notebook": notebook})
    output(result, f"Switched notebook: {notebook}", command="notebooks.use")


@notebooks_group.command("remove")
@click.argument("notebook")
@click.option("--force/--no-force", default=True)
@click.option("--permanent", is_flag=True, default=False)
@click.pass_context
@handle_error
def notebooks_remove(ctx, notebook, force, permanent):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    result = notebook_mod.remove_notebook(cfg, notebook, force=force, permanent=permanent)
    sess = get_session()
    if sess.has_project():
        sess.snapshot(f"Remove notebook: {notebook}")
        project_mod.add_history(sess.get_project(), "notebook.remove", {"notebook": notebook, "permanent": permanent})
    output(result, f"Removed notebook: {notebook}", command="notebooks.remove")


@cli.group("notes")
def notes_group():
    """Note commands."""


@notes_group.command("list")
@click.option("--pattern", "pattern", default=None)
@click.option("--limit", "limit", type=int, default=None)
@click.option("--sort", "sort", default=None)
@click.option("--reverse", is_flag=True, default=False)
@click.option("--type", "item_type", default=None, help="Joplin item type filter: n, t, or nt")
@click.option("--long", "long", is_flag=True, default=False)
@click.pass_context
@handle_error
def notes_list(ctx, pattern, limit, sort, reverse, item_type, long):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    result = note_mod.list_notes(
        cfg,
        pattern=pattern,
        limit=limit,
        sort=sort,
        reverse=reverse,
        item_type=item_type,
        long=long,
    )
    output(result.get("data", result), command="notes.list")


@notes_group.command("create")
@click.argument("title")
@click.pass_context
@handle_error
def notes_create(ctx, title):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    result = note_mod.create_note(cfg, title)
    sess = get_session()
    if sess.has_project():
        sess.snapshot(f"Create note: {title}")
        project_mod.add_history(sess.get_project(), "note.create", {"title": title})
    output(result, f"Created note: {title}", command="notes.create")


@notes_group.command("set")
@click.argument("note_ref")
@click.argument("field")
@click.argument("value")
@click.pass_context
@handle_error
def notes_set(ctx, note_ref, field, value):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    result = note_mod.set_note_field(cfg, note_ref, field, value)
    sess = get_session()
    if sess.has_project():
        sess.snapshot(f"Set note field {field}")
        project_mod.add_history(sess.get_project(), "note.set", {"note": note_ref, "field": field})
    output(result, f"Updated note: {note_ref}", command="notes.set")


@notes_group.command("get")
@click.argument("note_ref")
@click.option("--verbose", "-v", is_flag=True, default=False)
@click.pass_context
@handle_error
def notes_get(ctx, note_ref, verbose):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    result = note_mod.get_note(cfg, note_ref, verbose=verbose)
    output(result, command="notes.get")


@notes_group.command("remove")
@click.argument("note_ref")
@click.option("--force/--no-force", default=True)
@click.option("--permanent", is_flag=True, default=False)
@click.pass_context
@handle_error
def notes_remove(ctx, note_ref, force, permanent):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    result = note_mod.remove_note(cfg, note_ref, force=force, permanent=permanent)
    sess = get_session()
    if sess.has_project():
        sess.snapshot(f"Remove note: {note_ref}")
        project_mod.add_history(sess.get_project(), "note.remove", {"note": note_ref, "permanent": permanent})
    output(result, f"Removed note: {note_ref}", command="notes.remove")


@notes_group.command("copy")
@click.argument("note_ref")
@click.argument("notebook", required=False)
@click.pass_context
@handle_error
def notes_copy(ctx, note_ref, notebook):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    result = note_mod.copy_note(cfg, note_ref, notebook=notebook)
    sess = get_session()
    if sess.has_project():
        sess.snapshot(f"Copy note: {note_ref}")
        project_mod.add_history(sess.get_project(), "note.copy", {"note": note_ref, "notebook": notebook})
    output(result, f"Copied note: {note_ref}", command="notes.copy")


@notes_group.command("move")
@click.argument("item")
@click.argument("notebook")
@click.pass_context
@handle_error
def notes_move(ctx, item, notebook):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    result = note_mod.move_note(cfg, item, notebook)
    sess = get_session()
    if sess.has_project():
        sess.snapshot(f"Move note: {item}")
        project_mod.add_history(sess.get_project(), "note.move", {"item": item, "notebook": notebook})
    output(result, f"Moved {item} to {notebook}", command="notes.move")


@notes_group.command("rename")
@click.argument("item")
@click.argument("new_name")
@click.pass_context
@handle_error
def notes_rename(ctx, item, new_name):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    result = note_mod.rename_note(cfg, item, new_name)
    sess = get_session()
    if sess.has_project():
        sess.snapshot(f"Rename {item} -> {new_name}")
        project_mod.add_history(sess.get_project(), "note.rename", {"item": item, "new_name": new_name})
    output(result, f"Renamed {item} -> {new_name}", command="notes.rename")


@cli.group("todos")
def todos_group():
    """To-do commands."""


@todos_group.command("list")
@click.option("--limit", "limit", type=int, default=None)
@click.option("--sort", "sort", default=None)
@click.option("--reverse", is_flag=True, default=False)
@click.option("--long", "long", is_flag=True, default=False)
@click.pass_context
@handle_error
def todos_list(ctx, limit, sort, reverse, long):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    result = todo_mod.list_todos(cfg, limit=limit, sort=sort, reverse=reverse, long=long)
    output(result.get("data", result), command="todos.list")


@todos_group.command("create")
@click.argument("title")
@click.pass_context
@handle_error
def todos_create(ctx, title):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    result = todo_mod.create_todo(cfg, title)
    sess = get_session()
    if sess.has_project():
        sess.snapshot(f"Create todo: {title}")
        project_mod.add_history(sess.get_project(), "todo.create", {"title": title})
    output(result, f"Created todo: {title}", command="todos.create")


@todos_group.command("toggle")
@click.argument("pattern")
@click.pass_context
@handle_error
def todos_toggle(ctx, pattern):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    result = todo_mod.toggle_todo(cfg, pattern)
    sess = get_session()
    if sess.has_project():
        sess.snapshot(f"Toggle todo: {pattern}")
        project_mod.add_history(sess.get_project(), "todo.toggle", {"pattern": pattern})
    output(result, f"Toggled todo: {pattern}", command="todos.toggle")


@todos_group.command("clear")
@click.argument("pattern")
@click.pass_context
@handle_error
def todos_clear(ctx, pattern):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    result = todo_mod.clear_todo(cfg, pattern)
    sess = get_session()
    if sess.has_project():
        sess.snapshot(f"Clear todo: {pattern}")
        project_mod.add_history(sess.get_project(), "todo.clear", {"pattern": pattern})
    output(result, f"Cleared todo: {pattern}", command="todos.clear")


@todos_group.command("done")
@click.argument("note_ref")
@click.pass_context
@handle_error
def todos_done(ctx, note_ref):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    result = todo_mod.mark_done(cfg, note_ref)
    sess = get_session()
    if sess.has_project():
        sess.snapshot(f"Mark done: {note_ref}")
        project_mod.add_history(sess.get_project(), "todo.done", {"note": note_ref})
    output(result, f"Marked done: {note_ref}", command="todos.done")


@todos_group.command("undone")
@click.argument("note_ref")
@click.pass_context
@handle_error
def todos_undone(ctx, note_ref):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    result = todo_mod.mark_undone(cfg, note_ref)
    sess = get_session()
    if sess.has_project():
        sess.snapshot(f"Mark undone: {note_ref}")
        project_mod.add_history(sess.get_project(), "todo.undone", {"note": note_ref})
    output(result, f"Marked undone: {note_ref}", command="todos.undone")


@cli.group("tags")
def tags_group():
    """Tag commands."""


@tags_group.command("list")
@click.pass_context
@handle_error
def tags_list(ctx):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    output(tag_mod.list_tags(cfg), command="tags.list")


@tags_group.command("add")
@click.argument("tag")
@click.argument("note")
@click.pass_context
@handle_error
def tags_add(ctx, tag, note):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    result = tag_mod.add_tag(cfg, tag, note)
    sess = get_session()
    if sess.has_project():
        sess.snapshot(f"Add tag: {tag}")
        project_mod.add_history(sess.get_project(), "tag.add", {"tag": tag, "note": note})
    output(result, f"Added tag '{tag}' to {note}", command="tags.add")


@tags_group.command("remove")
@click.argument("tag")
@click.argument("note")
@click.pass_context
@handle_error
def tags_remove(ctx, tag, note):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    result = tag_mod.remove_tag(cfg, tag, note)
    sess = get_session()
    if sess.has_project():
        sess.snapshot(f"Remove tag: {tag}")
        project_mod.add_history(sess.get_project(), "tag.remove", {"tag": tag, "note": note})
    output(result, f"Removed tag '{tag}' from {note}", command="tags.remove")


@tags_group.command("notetags")
@click.argument("note")
@click.pass_context
@handle_error
def tags_notetags(ctx, note):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    output(tag_mod.note_tags(cfg, note), command="tags.notetags")


@tags_group.command("tagnotes")
@click.argument("tag")
@click.pass_context
@handle_error
def tags_tagnotes(ctx, tag):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    output(tag_mod.tag_notes(cfg, tag), command="tags.tagnotes")


@cli.group("search")
def search_group():
    """Search commands."""


@search_group.command("run")
@click.argument("pattern")
@click.option("--notebook", "notebook", default=None)
@click.pass_context
@handle_error
def search_run(ctx, pattern, notebook):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    output(search_mod.search(cfg, pattern, notebook=notebook), command="search.run")


@cli.group("sync")
def sync_group():
    """Sync commands."""


@sync_group.command("run")
@click.option("--target", "target", default=None)
@click.option("--upgrade", is_flag=True, default=False)
@click.option("--use-lock", "use_lock", default=None)
@click.pass_context
@handle_error
def sync_run(ctx, target, upgrade, use_lock):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    result = sync_mod.run_sync(cfg, target=target, upgrade=upgrade, use_lock=use_lock)
    sess = get_session()
    if sess.has_project():
        project_mod.add_history(sess.get_project(), "sync.run", {"target": target, "upgrade": upgrade, "use_lock": use_lock})
        sess.mark_dirty()
    output(result, "Sync completed", command="sync.run")


@cli.group("interop")
def interop_group():
    """Import/export commands."""


@interop_group.command("import")
@click.argument("path")
@click.option("--notebook", "notebook", default=None)
@click.option("--format", "fmt", default=None)
@click.option("--force", is_flag=True, default=False)
@click.option("--output-format", "output_format", default=None)
@click.pass_context
@handle_error
def interop_import(ctx, path, notebook, fmt, force, output_format):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    result = interop_mod.import_data(cfg, path, notebook=notebook, fmt=fmt, force=force, output_format=output_format)
    sess = get_session()
    if sess.has_project():
        sess.snapshot(f"Import: {path}")
        project_mod.add_history(
            sess.get_project(),
            "interop.import",
            {"path": path, "format": fmt, "force": force, "output_format": output_format},
        )
    output(result, f"Imported: {path}", command="interop.import")


@interop_group.command("export")
@click.argument("path")
@click.option("--format", "fmt", default="jex")
@click.option("--note", "note", default=None)
@click.option("--notebook", "notebook", default=None)
@click.pass_context
@handle_error
def interop_export(ctx, path, fmt, note, notebook):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    result = interop_mod.export_data(cfg, path, fmt=fmt, note=note, notebook=notebook)
    sess = get_session()
    if sess.has_project():
        project_mod.add_history(sess.get_project(), "interop.export", {"path": path, "format": fmt})
        sess.mark_dirty()
    output(result, f"Exported: {path}", command="interop.export")


@cli.group("config")
def config_group():
    """Joplin config commands."""


@config_group.command("get")
@click.argument("key")
@click.option("--verbose", "-v", is_flag=True, default=False)
@click.pass_context
@handle_error
def config_get(ctx, key, verbose):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    output(config_mod.config_get(cfg, key, verbose=verbose), command="config.get")


@config_group.command("set")
@click.argument("key")
@click.argument("value")
@click.pass_context
@handle_error
def config_set(ctx, key, value):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    result = config_mod.config_set(cfg, key, value)
    output(result, command="config.set")


@config_group.command("list")
@click.option("--verbose", "-v", is_flag=True, default=False)
@click.pass_context
@handle_error
def config_list(ctx, verbose):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    output(config_mod.config_list(cfg, verbose=verbose), command="config.list")


@config_group.command("export")
@click.option("--verbose", "-v", is_flag=True, default=False)
@click.pass_context
@handle_error
def config_export(ctx, verbose):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    output(config_mod.config_export(cfg, verbose=verbose), command="config.export")


@config_group.command("import-file")
@click.argument("file_path")
@click.pass_context
@handle_error
def config_import_file(ctx, file_path):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    result = config_mod.config_import_file(cfg, file_path)
    sess = get_session()
    if sess.has_project():
        project_mod.add_history(sess.get_project(), "config.import_file", {"file": file_path})
        sess.mark_dirty()
    output(result, command="config.import_file")


@cli.group("attach")
def attach_group():
    """Attachment commands."""


@attach_group.command("add")
@click.argument("note_ref")
@click.argument("file_path")
@click.pass_context
@handle_error
def attach_add(ctx, note_ref, file_path):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    result = attach_mod.attach_file(cfg, note_ref, file_path)
    sess = get_session()
    if sess.has_project():
        sess.snapshot(f"Attach file to: {note_ref}")
        project_mod.add_history(sess.get_project(), "attach.add", {"note": note_ref, "file": file_path})
    output(result, f"Attached {file_path} to {note_ref}", command="attach.add")


@cli.group("status")
def status_group():
    """Backend status commands."""


@status_group.command("show")
@click.pass_context
@handle_error
def status_show(ctx):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    output(status_mod.get_status(cfg), command="status.show")


@status_group.command("restore")
@click.argument("pattern")
@click.pass_context
@handle_error
def status_restore(ctx, pattern):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    result = status_mod.restore_items(cfg, pattern)
    sess = get_session()
    if sess.has_project():
        sess.snapshot(f"Restore: {pattern}")
        project_mod.add_history(sess.get_project(), "status.restore", {"pattern": pattern})
    output(result, f"Restored: {pattern}", command="status.restore")


@cli.group("backend")
def backend_group():
    """Backend utility commands."""


@backend_group.command("version")
@click.pass_context
@handle_error
def backend_version(ctx):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    output(backend_mod.version_info(cfg), command="backend.version")


@backend_group.command("dump")
@click.pass_context
@handle_error
def backend_dump(ctx):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    output(backend_mod.dump_database(cfg), command="backend.dump")


@backend_group.command("keymap")
@click.pass_context
@handle_error
def backend_keymap(ctx):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    output(backend_mod.keymap(cfg), command="backend.keymap")


@backend_group.command("geoloc")
@click.argument("note_ref")
@click.pass_context
@handle_error
def backend_geoloc(ctx, note_ref):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    output(backend_mod.geoloc(cfg, note_ref), command="backend.geoloc")


@backend_group.command("export-sync-status")
@click.pass_context
@handle_error
def backend_export_sync_status(ctx):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    output(backend_mod.export_sync_status(cfg), command="backend.export_sync_status")


@cli.group("server")
def server_group():
    """Joplin API server commands."""


@server_group.command("status")
@click.pass_context
@handle_error
def server_status(ctx):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    output(backend_mod.server_status(cfg), command="server.status")


@server_group.command("start")
@click.option("--exit-early/--wait", default=True, help="Return after starting instead of waiting forever")
@click.option("--quiet", is_flag=True, default=False)
@click.pass_context
@handle_error
def server_start(ctx, exit_early, quiet):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    result = backend_mod.server_start(cfg, exit_early=exit_early, quiet=quiet)
    sess = get_session()
    if sess.has_project():
        project_mod.add_history(sess.get_project(), "server.start", {"exit_early": exit_early, "quiet": quiet})
        sess.mark_dirty()
    output(result, command="server.start")


@server_group.command("stop")
@click.pass_context
@handle_error
def server_stop(ctx):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    result = backend_mod.server_stop(cfg)
    sess = get_session()
    if sess.has_project():
        project_mod.add_history(sess.get_project(), "server.stop")
        sess.mark_dirty()
    output(result, command="server.stop")


@cli.group("e2ee")
def e2ee_group():
    """Joplin E2EE commands."""


@e2ee_group.command("status")
@click.pass_context
@handle_error
def e2ee_status(ctx):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    output(backend_mod.e2ee_status(cfg), command="e2ee.status")


@e2ee_group.command("target-status")
@click.argument("target_path")
@click.option("--verbose", "-v", is_flag=True, default=False)
@click.pass_context
@handle_error
def e2ee_target_status(ctx, target_path, verbose):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    output(backend_mod.e2ee_target_status(cfg, target_path, verbose=verbose), command="e2ee.target_status")


@e2ee_group.command("decrypt")
@click.argument("encrypted_text", required=False)
@click.option("--retry-failed-items", is_flag=True, default=False)
@click.option("--force", is_flag=True, default=False)
@click.pass_context
@handle_error
def e2ee_decrypt(ctx, encrypted_text, retry_failed_items, force):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    output(
        backend_mod.e2ee_decrypt(
            cfg,
            encrypted_text=encrypted_text,
            retry_failed_items=retry_failed_items,
            force=force,
        ),
        command="e2ee.decrypt",
    )


@e2ee_group.command("decrypt-file")
@click.argument("file_path")
@click.option("--output", "output_dir", default=None)
@click.pass_context
@handle_error
def e2ee_decrypt_file(ctx, file_path, output_dir):
    cfg = _backend_config(ctx.obj["binary"], ctx.obj["profile"])
    output(backend_mod.e2ee_decrypt_file(cfg, file_path, output_dir=output_dir), command="e2ee.decrypt_file")


@cli.group("session")
def session_group():
    """Session commands."""


@session_group.command("status")
@handle_error
def session_status():
    output(get_session().status(), command="session.status")


@session_group.command("undo")
@handle_error
def session_undo():
    sess = get_session()
    sess.undo()
    output(sess.status(), "Undo complete", command="session.undo")


@session_group.command("redo")
@handle_error
def session_redo():
    sess = get_session()
    sess.redo()
    output(sess.status(), "Redo complete", command="session.redo")


@session_group.command("history")
@handle_error
def session_history():
    sess = get_session()
    proj = sess.get_project()
    output(proj.get("history", []), command="session.history")


@cli.command(hidden=True)
@click.pass_context
def repl(ctx):
    global _repl_mode
    _repl_mode = True

    skin = ReplSkin("joplin", version="1.0.0")
    skin.print_banner()
    skin.info("Type 'help' to list commands, 'exit' to quit.")

    pt_session = skin.create_prompt_session()

    while True:
        try:
            line = skin.get_input(pt_session, project_name="joplin-harness", modified=get_session()._modified)
        except (EOFError, KeyboardInterrupt):
            break

        line = line.strip()
        if not line:
            continue
        if line in ("exit", "quit"):
            break
        if line == "help":
            skin.help({
                "project new/open/save/info/json/status": "Harness project management",
                "notebooks list/create/use/remove": "Notebook operations",
                "notes list/create/set/get/remove/copy/move/rename": "Note operations",
                "todos list/create/toggle/clear/done/undone": "To-do operations",
                "tags list/add/remove/notetags/tagnotes": "Tag operations",
                "search run": "Search notes",
                "sync run": "Run sync",
                "interop import/export": "Import and export",
                "config get/set/list/export/import-file": "Joplin config",
                "attach add": "Attach file to note",
                "status show/restore": "Backend status and trash restore",
                "backend version/dump/keymap/geoloc/export-sync-status": "Backend utilities",
                "server status/start/stop": "Joplin API server",
                "e2ee status/target-status/decrypt/decrypt-file": "Encryption utilities",
                "session status/undo/redo/history": "Session controls",
            })
            continue

        try:
            args = shlex.split(line)
            cli.main(args=args, obj=dict(ctx.obj), standalone_mode=False)
        except click.exceptions.UsageError as e:
            skin.error(str(e))
        except Exception as e:
            skin.error(str(e))

    skin.print_goodbye()


def main():
    cli(obj={})


if __name__ == "__main__":
    main()
