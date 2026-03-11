#!/usr/bin/env python3
"""AnyGen CLI — Generate docs, slides, websites and more via AnyGen cloud API.

Usage:
    # One-shot commands
    cli-anything-anygen task run --operation slide --prompt "AI trends presentation" --output ./
    cli-anything-anygen task create --operation doc --prompt "Technical report"
    cli-anything-anygen task status <task-id>

    # Interactive REPL
    cli-anything-anygen
"""

import sys
import os
import json
import shlex
import click
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cli_anything.anygen.core.session import Session
from cli_anything.anygen.core import task as task_mod
from cli_anything.anygen.core import export as export_mod
from cli_anything.anygen.utils.anygen_backend import (
    get_api_key,
    load_config,
    save_config,
    VALID_OPERATIONS,
    DOWNLOADABLE_OPERATIONS,
)

_session: Optional[Session] = None
_json_output = False
_repl_mode = False
_api_key: Optional[str] = None


def get_session() -> Session:
    global _session
    if _session is None:
        from pathlib import Path
        sf = str(Path.home() / ".cli-anything-anygen" / "session.json")
        _session = Session(session_file=sf)
    return _session


def output(data, message: str = ""):
    if _json_output:
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        if message:
            click.echo(message)
        if isinstance(data, dict):
            _print_dict(data)
        elif isinstance(data, list):
            _print_list(data)
        else:
            click.echo(str(data))


def _print_dict(d: dict, indent: int = 0):
    prefix = "  " * indent
    for k, v in d.items():
        if isinstance(v, dict):
            click.echo(f"{prefix}{k}:")
            _print_dict(v, indent + 1)
        elif isinstance(v, list):
            click.echo(f"{prefix}{k}:")
            _print_list(v, indent + 1)
        else:
            click.echo(f"{prefix}{k}: {v}")


def _print_list(items: list, indent: int = 0):
    prefix = "  " * indent
    for i, item in enumerate(items):
        if isinstance(item, dict):
            click.echo(f"{prefix}[{i}]")
            _print_dict(item, indent + 1)
        else:
            click.echo(f"{prefix}- {item}")


def handle_error(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (FileNotFoundError, ValueError, RuntimeError, TimeoutError) as e:
            if _json_output:
                click.echo(json.dumps({"error": str(e), "type": type(e).__name__}))
            else:
                click.echo(f"Error: {e}", err=True)
            if not _repl_mode:
                sys.exit(1)
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


# ── Main CLI Group ──────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, help="Output as JSON")
@click.option("--api-key", "api_key_opt", type=str, default=None,
              help="AnyGen API key (sk-xxx)")
@click.pass_context
def cli(ctx, use_json, api_key_opt):
    """AnyGen CLI — Generate docs, slides, websites and more."""
    global _json_output, _api_key
    _json_output = use_json
    _api_key = get_api_key(api_key_opt)
    ctx.ensure_object(dict)

    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


# ── Task Command Group ──────────────────────────────────────────

@cli.group()
def task():
    """Task management — create, poll, download, and run tasks."""
    pass


@task.command("create")
@click.option("--operation", "-o", required=True,
              type=click.Choice(VALID_OPERATIONS, case_sensitive=False),
              help="Operation type")
@click.option("--prompt", "-p", required=True, help="Content prompt")
@click.option("--language", "-l", default=None, help="Language (zh-CN, en-US)")
@click.option("--slide-count", "-c", type=int, default=None, help="Number of slides")
@click.option("--template", "-t", default=None, help="Slide template")
@click.option("--ratio", "-r", type=click.Choice(["16:9", "4:3"]), default=None, help="Slide ratio")
@click.option("--export-format", "-f", default=None, help="Export format")
@click.option("--file-token", multiple=True, help="File token from upload (repeatable)")
@click.option("--style", "-s", default=None, help="Style preference")
@handle_error
def task_create(operation, prompt, language, slide_count, template, ratio,
                export_format, file_token, style):
    """Create a generation task."""
    sess = get_session()
    result = task_mod.create_task(
        _api_key, operation, prompt,
        language=language, slide_count=slide_count, template=template,
        ratio=ratio, export_format=export_format,
        file_tokens=list(file_token) if file_token else None,
        style=style,
    )
    sess.record("task create", {"operation": operation, "prompt": prompt}, result)
    output(result, f"✓ Task created: {result['task_id']}")


@task.command("status")
@click.argument("task_id")
@handle_error
def task_status(task_id):
    """Query task status (non-blocking)."""
    result = task_mod.query_task(_api_key, task_id)
    status = result.get("status")
    progress = result.get("progress", 0)
    out = {
        "task_id": task_id,
        "status": status,
        "progress": progress,
    }
    if status == "completed":
        o = result.get("output", {})
        if o.get("file_name"):
            out["file_name"] = o["file_name"]
        if o.get("task_url"):
            out["task_url"] = o["task_url"]
    output(out, f"Task {task_id}: {status} ({progress}%)")


@task.command("poll")
@click.argument("task_id")
@click.option("--output", "-o", "output_dir", default=None,
              help="Output directory for auto-download on completion")
@handle_error
def task_poll(task_id, output_dir):
    """Poll task until completion (blocking)."""
    def on_progress(status, pct):
        if not _json_output:
            click.echo(f"  ● {status}: {pct}%")

    result = task_mod.poll_task(_api_key, task_id, on_progress=on_progress)
    sess = get_session()
    sess.record("task poll", {"task_id": task_id}, {"status": result.get("status")})

    if output_dir and result.get("status") == "completed":
        dl = task_mod.download_file(_api_key, task_id, output_dir)
        output(dl, f"✓ Downloaded: {dl['local_path']} ({dl['file_size']:,} bytes)")
    else:
        output(result, f"✓ Task {task_id}: {result.get('status')}")


@task.command("download")
@click.argument("task_id")
@click.option("--output", "-o", "output_dir", required=True, help="Output directory")
@handle_error
def task_download(task_id, output_dir):
    """Download the generated file for a completed task."""
    dl = task_mod.download_file(_api_key, task_id, output_dir)
    sess = get_session()
    sess.record("task download", {"task_id": task_id}, dl)
    output(dl, f"✓ Downloaded: {dl['local_path']} ({dl['file_size']:,} bytes)")


@task.command("thumbnail")
@click.argument("task_id")
@click.option("--output", "-o", "output_dir", required=True, help="Output directory")
@handle_error
def task_thumbnail(task_id, output_dir):
    """Download thumbnail image for a completed task."""
    dl = task_mod.download_thumbnail(_api_key, task_id, output_dir)
    output(dl, f"✓ Thumbnail saved: {dl['local_path']}")


@task.command("run")
@click.option("--operation", "-o", required=True,
              type=click.Choice(VALID_OPERATIONS, case_sensitive=False),
              help="Operation type")
@click.option("--prompt", "-p", required=True, help="Content prompt")
@click.option("--output", "output_dir", default=None, help="Output directory")
@click.option("--language", "-l", default=None, help="Language (zh-CN, en-US)")
@click.option("--slide-count", "-c", type=int, default=None, help="Number of slides")
@click.option("--template", "-t", default=None, help="Slide template")
@click.option("--ratio", "-r", type=click.Choice(["16:9", "4:3"]), default=None)
@click.option("--export-format", "-f", default=None, help="Export format")
@click.option("--file-token", multiple=True, help="File token (repeatable)")
@click.option("--style", "-s", default=None, help="Style preference")
@handle_error
def task_run(operation, prompt, output_dir, language, slide_count, template,
             ratio, export_format, file_token, style):
    """Full workflow: create → poll → download."""
    def on_progress(status, pct):
        if not _json_output:
            click.echo(f"  ● {status}: {pct}%")

    result = task_mod.run_full_workflow(
        _api_key, operation, prompt, output_dir,
        on_progress=on_progress,
        language=language, slide_count=slide_count, template=template,
        ratio=ratio, export_format=export_format,
        file_tokens=list(file_token) if file_token else None,
        style=style,
    )
    sess = get_session()
    sess.record("task run", {"operation": operation, "prompt": prompt}, result)

    if result.get("local_path"):
        output(result, f"✓ Completed! File: {result['local_path']} ({result.get('file_size', 0):,} bytes)")
    else:
        output(result, f"✓ Completed! View at: {result.get('task_url', 'N/A')}")


@task.command("list")
@click.option("--limit", "-n", type=int, default=20, help="Max number of tasks")
@click.option("--status", "status_filter", default=None, help="Filter by status")
@handle_error
def task_list(limit, status_filter):
    """List locally cached task records."""
    records = task_mod.list_task_records(limit=limit, status_filter=status_filter)
    if not records:
        output([], "No tasks found.")
        return
    output(records, f"Found {len(records)} task(s):")


@task.command("prepare")
@click.option("--message", "-m", required=True, help="User message")
@click.option("--file-token", multiple=True, help="File token (repeatable)")
@click.option("--input", "input_file", default=None, help="Load conversation from JSON")
@click.option("--save", "save_file", default=None, help="Save conversation to JSON")
@handle_error
def task_prepare(message, file_token, input_file, save_file):
    """Multi-turn requirement analysis before creating a task."""
    messages = []
    loaded_file_tokens = set()

    if input_file:
        with open(input_file) as f:
            data = json.load(f)
        messages = data.get("messages", [])
        loaded_file_tokens = set(data.get("file_tokens", []))

    ft_list = list(file_token) if file_token else []
    all_tokens = ft_list + list(loaded_file_tokens)

    content = [{"type": "text", "text": message}]
    for ft in ft_list:
        if ft not in loaded_file_tokens:
            content.append({"type": "file", "file_token": ft})
    messages.append({"role": "user", "content": content})

    result = task_mod.prepare_task(
        _api_key, messages,
        file_tokens=all_tokens if all_tokens else None,
    )

    if save_file:
        save_data = {
            "messages": result.get("messages", messages),
            "file_tokens": all_tokens,
            "status": result.get("status"),
            "suggested_task_params": result.get("suggested_task_params"),
        }
        with open(save_file, "w") as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)

    reply = result.get("reply", "")
    status = result.get("status", "collecting")
    suggested = result.get("suggested_task_params")

    out = {"reply": reply, "status": status}
    if suggested:
        out["suggested_task_params"] = suggested

    msg = f"AnyGen: {reply}\nStatus: {status}"
    if suggested:
        msg += f"\nSuggested operation: {suggested.get('operation', 'N/A')}"
    output(out, msg)


# ── File Command Group ──────────────────────────────────────────

@cli.group()
def file():
    """File operations — upload reference files."""
    pass


@file.command("upload")
@click.argument("path", type=click.Path(exists=True))
@handle_error
def file_upload(path):
    """Upload a reference file to get a file_token."""
    result = task_mod.upload_file(_api_key, path)
    sess = get_session()
    sess.record("file upload", {"path": path}, result)
    output(result, f"✓ Uploaded: {result['filename']} → token: {result['file_token']}")


# ── Config Command Group ────────────────────────────────────────

@cli.group()
def config():
    """Configuration management — API key and settings."""
    pass


@config.command("set")
@click.argument("key", type=click.Choice(["api_key", "default_language"]))
@click.argument("value")
def config_set(key, value):
    """Set a configuration value."""
    cfg = load_config()
    cfg[key] = value
    save_config(cfg)
    display = value[:10] + "..." if key == "api_key" and len(value) > 10 else value
    output({"key": key, "value": display}, f"✓ Set {key} = {display}")


@config.command("get")
@click.argument("key", required=False)
def config_get(key):
    """Get a configuration value (or show all)."""
    cfg = load_config()
    if key:
        val = cfg.get(key)
        if val:
            if key == "api_key" and len(val) > 10:
                val = val[:10] + "..."
            output({"key": key, "value": val}, f"{key} = {val}")
        else:
            output({"key": key, "value": None}, f"{key} is not set")
    else:
        if cfg:
            masked = {}
            for k, v in cfg.items():
                masked[k] = v[:10] + "..." if k == "api_key" and len(v) > 10 else v
            output(masked)
        else:
            output({}, "No configuration set")


@config.command("delete")
@click.argument("key")
def config_delete(key):
    """Delete a configuration value."""
    cfg = load_config()
    if key in cfg:
        del cfg[key]
        save_config(cfg)
        output({"deleted": key}, f"✓ Deleted {key}")
    else:
        output({"error": f"{key} not found"}, f"{key} not found in config")


@config.command("path")
def config_path():
    """Show the config file path."""
    from cli_anything.anygen.utils.anygen_backend import CONFIG_FILE
    output({"path": str(CONFIG_FILE)}, f"Config file: {CONFIG_FILE}")


# ── Session Command Group ───────────────────────────────────────

@cli.group()
def session():
    """Session management — history, undo, redo."""
    pass


@session.command("status")
def session_status():
    """Show session status."""
    sess = get_session()
    output(sess.status())


@session.command("history")
@click.option("--limit", "-n", type=int, default=20, help="Max entries")
def session_history(limit):
    """Show command history."""
    sess = get_session()
    entries = sess.history(limit=limit)
    if not entries:
        output([], "No history.")
        return
    output(entries, f"History ({len(entries)} entries):")


@session.command("undo")
def session_undo():
    """Undo last command."""
    sess = get_session()
    entry = sess.undo()
    if entry:
        output(entry.to_dict(), f"✓ Undone: {entry.command}")
    else:
        output({"error": "Nothing to undo"}, "Nothing to undo")


@session.command("redo")
def session_redo():
    """Redo last undone command."""
    sess = get_session()
    entry = sess.redo()
    if entry:
        output(entry.to_dict(), f"✓ Redone: {entry.command}")
    else:
        output({"error": "Nothing to redo"}, "Nothing to redo")


# ── REPL ────────────────────────────────────────────────────────

@cli.command("repl", hidden=True)
def repl():
    """Enter interactive REPL mode."""
    global _repl_mode
    _repl_mode = True

    from cli_anything.anygen.utils.repl_skin import ReplSkin

    skin = ReplSkin("anygen", version="1.0.0")
    skin.print_banner()

    pt_session = skin.create_prompt_session()

    commands = {
        "task create": "Create a generation task",
        "task run": "Full workflow: create → poll → download",
        "task status <id>": "Check task status",
        "task poll <id>": "Poll until completion",
        "task download <id>": "Download generated file",
        "task list": "List local task history",
        "task prepare": "Multi-turn requirement analysis",
        "file upload <path>": "Upload a reference file",
        "config set <key> <val>": "Set configuration",
        "config get [key]": "Show configuration",
        "session history": "Show command history",
        "session undo": "Undo last command",
        "session redo": "Redo last undone command",
        "help": "Show this help",
        "quit / exit": "Exit REPL",
    }

    while True:
        try:
            line = skin.get_input(pt_session, context="anygen")
        except (EOFError, KeyboardInterrupt):
            skin.print_goodbye()
            break

        if not line:
            continue
        if line in ("quit", "exit", "q"):
            skin.print_goodbye()
            break
        if line == "help":
            skin.help(commands)
            continue

        parts = shlex.split(line)
        try:
            cli.main(parts, standalone_mode=False)
        except SystemExit:
            pass
        except click.exceptions.UsageError as e:
            skin.error(str(e))
        except Exception as e:
            skin.error(str(e))


def main():
    cli()


if __name__ == "__main__":
    main()
