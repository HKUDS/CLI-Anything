#!/usr/bin/env python3
"""AnyGen CLI — Generate docs, slides, websites via AnyGen cloud API."""

import json
import shlex
import sys
from functools import lru_cache, wraps
from pathlib import Path
from typing import Optional

import click

from cli_anything.anygen.core.session import Session
from cli_anything.anygen.core import task as task_mod
from cli_anything.anygen.utils.anygen_backend import (
    get_api_key,
    load_config,
    save_config,
    VALID_OPERATIONS,
)

_json_output = False
_repl_mode = False
_api_key: Optional[str] = None


# ─────────────────────────────────────────────
# Session
# ─────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_session() -> Session:
    sf = Path.home() / ".cli-anything-anygen" / "session.json"
    return Session(session_file=str(sf))


# ─────────────────────────────────────────────
# Output utilities
# ─────────────────────────────────────────────

def pretty_print(data, indent=0):
    prefix = "  " * indent

    if isinstance(data, dict):
        for k, v in data.items():
            click.echo(f"{prefix}{k}:")
            pretty_print(v, indent + 1)

    elif isinstance(data, list):
        for i, item in enumerate(data):
            click.echo(f"{prefix}[{i}]")
            pretty_print(item, indent + 1)

    else:
        click.echo(f"{prefix}{data}")


def output(data, message: str = ""):
    if _json_output:
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        if message:
            click.echo(message)
        pretty_print(data)


# ─────────────────────────────────────────────
# Error handling
# ─────────────────────────────────────────────

def handle_error(func):
    @wraps(func)
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

    return wrapper


# ─────────────────────────────────────────────
# CLI root
# ─────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True)
@click.option("--api-key", default=None)
@click.pass_context
def cli(ctx, use_json, api_key):
    """AnyGen CLI."""
    global _json_output, _api_key

    _json_output = use_json
    _api_key = get_api_key(api_key)

    ctx.ensure_object(dict)

    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


# ─────────────────────────────────────────────
# Task commands
# ─────────────────────────────────────────────

@cli.group()
def task():
    """Task operations."""
    pass


@task.command("create")
@click.option("-o", "--operation",
              required=True,
              type=click.Choice(VALID_OPERATIONS))
@click.option("-p", "--prompt", required=True)
@handle_error
def task_create(operation, prompt):
    """Create task."""
    sess = get_session()

    result = task_mod.create_task(
        _api_key,
        operation,
        prompt,
    )

    sess.record("task create", {"operation": operation}, result)

    output(result, f"✓ Task created: {result['task_id']}")


@task.command("status")
@click.argument("task_id")
@handle_error
def task_status(task_id):
    """Check task status."""
    result = task_mod.query_task(_api_key, task_id)

    output(result, f"Task {task_id}: {result.get('status')}")


@task.command("run")
@click.option("-o", "--operation",
              required=True,
              type=click.Choice(VALID_OPERATIONS))
@click.option("-p", "--prompt", required=True)
@click.option("--output", default=None)
@handle_error
def task_run(operation, prompt, output):
    """Create + poll + download."""
    sess = get_session()

    def progress(status, pct):
        if not _json_output:
            click.echo(f"  ● {status}: {pct}%")

    result = task_mod.run_full_workflow(
        _api_key,
        operation,
        prompt,
        output,
        on_progress=progress,
    )

    sess.record("task run", {"operation": operation}, result)

    output(result, "✓ Completed")


# ─────────────────────────────────────────────
# File
# ─────────────────────────────────────────────

@cli.group()
def file():
    """File operations."""
    pass


@file.command("upload")
@click.argument("path", type=click.Path(exists=True))
@handle_error
def file_upload(path):
    result = task_mod.upload_file(_api_key, path)

    get_session().record("file upload", {"path": path}, result)

    output(result, f"✓ Uploaded → token: {result['file_token']}")


# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────

@cli.group()
def config():
    """Config management."""
    pass


@config.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key, value):
    cfg = load_config()

    cfg[key] = value
    save_config(cfg)

    output({"key": key, "value": value}, f"✓ Set {key}")


@config.command("get")
@click.argument("key", required=False)
def config_get(key):
    cfg = load_config()

    if key:
        output({key: cfg.get(key)})
    else:
        output(cfg)


# ─────────────────────────────────────────────
# Session
# ─────────────────────────────────────────────

@cli.group()
def session():
    """Session history."""
    pass


@session.command("history")
@click.option("-n", "--limit", default=20)
def session_history(limit):
    entries = get_session().history(limit=limit)

    output(entries, f"{len(entries)} entries")


@session.command("undo")
def session_undo():
    entry = get_session().undo()

    if entry:
        output(entry.to_dict(), "✓ Undone")
    else:
        output({"error": "Nothing to undo"})


@session.command("redo")
def session_redo():
    entry = get_session().redo()

    if entry:
        output(entry.to_dict(), "✓ Redone")
    else:
        output({"error": "Nothing to redo"})


# ─────────────────────────────────────────────
# REPL
# ─────────────────────────────────────────────

@cli.command(hidden=True)
def repl():
    """Interactive shell."""
    global _repl_mode
    _repl_mode = True

    from cli_anything.anygen.utils.repl_skin import ReplSkin

    skin = ReplSkin("anygen", version="1.0.0")
    skin.print_banner()

    pt = skin.create_prompt_session()

    while True:
        try:
            line = skin.get_input(pt, context="anygen")
        except (EOFError, KeyboardInterrupt):
            skin.print_goodbye()
            break

        if not line:
            continue

        if line in ("quit", "exit", "q"):
            skin.print_goodbye()
            break

        if line == "help":
            click.echo("Commands: task, file, config, session")
            continue

        try:
            parts = shlex.split(line)
            cli.main(parts, standalone_mode=False)

        except SystemExit:
            pass

        except Exception as e:
            skin.error(str(e))


# ─────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────

def main():
    cli()


if __name__ == "__main__":
    main()
