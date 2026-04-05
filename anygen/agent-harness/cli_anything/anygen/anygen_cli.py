#!/usr/bin/env python3
"""AnyGen CLI — Pro version (refactored & optimized)"""

import sys
import os
import json
import click
from pathlib import Path
from typing import Optional, Any, Dict

# ─────────────────────────────────────────────
# Context Object (thay global variables)
# ─────────────────────────────────────────────

class CLIContext:
    def __init__(self):
        self.json_output: bool = False
        self.api_key: Optional[str] = None
        self.session: Optional["Session"] = None

    def get_session(self):
        if not self.session:
            from cli_anything.anygen.core.session import Session
            sf = str(Path.home() / ".cli-anything-anygen" / "session.json")
            self.session = Session(session_file=sf)
        return self.session


pass_ctx = click.make_pass_decorator(CLIContext, ensure=True)

# ─────────────────────────────────────────────
# Utils
# ─────────────────────────────────────────────

def print_output(ctx: CLIContext, data: Any, message: str = ""):
    if ctx.json_output:
        click.echo(json.dumps(data, indent=2, default=str))
        return

    if message:
        click.echo(message)

    if isinstance(data, dict):
        _print_dict(data)
    elif isinstance(data, list):
        _print_list(data)
    else:
        click.echo(str(data))


def _print_dict(d: Dict, indent=0):
    pad = "  " * indent
    for k, v in d.items():
        if isinstance(v, dict):
            click.echo(f"{pad}{k}:")
            _print_dict(v, indent + 1)
        elif isinstance(v, list):
            click.echo(f"{pad}{k}:")
            _print_list(v, indent + 1)
        else:
            click.echo(f"{pad}{k}: {v}")


def _print_list(lst, indent=0):
    pad = "  " * indent
    for i, item in enumerate(lst):
        if isinstance(item, dict):
            click.echo(f"{pad}[{i}]")
            _print_dict(item, indent + 1)
        else:
            click.echo(f"{pad}- {item}")


def handle_error(func):
    def wrapper(*args, **kwargs):
        ctx: CLIContext = args[0] if args else None
        try:
            return func(*args, **kwargs)
        except Exception as e:
            err = {"error": str(e), "type": type(e).__name__}
            if ctx and ctx.json_output:
                click.echo(json.dumps(err))
            else:
                click.echo(f"Error: {e}", err=True)
            sys.exit(1)
    return wrapper

# ─────────────────────────────────────────────
# CLI ROOT
# ─────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.option("--json", is_flag=True)
@click.option("--api-key", type=str)
@pass_ctx
def cli(ctx: CLIContext, json, api_key):
    """AnyGen CLI — Clean version"""
    from cli_anything.anygen.utils.anygen_backend import get_api_key

    ctx.json_output = json
    ctx.api_key = get_api_key(api_key)

    if not click.get_current_context().invoked_subcommand:
        click.echo("Use --help or run `repl`")


# ─────────────────────────────────────────────
# TASK COMMANDS
# ─────────────────────────────────────────────

@cli.group()
def task():
    """Task operations"""
    pass


@task.command("run")
@click.option("--operation", "-o", required=True)
@click.option("--prompt", "-p", required=True)
@click.option("--output", "-out", default=None)
@pass_ctx
@handle_error
def task_run(ctx: CLIContext, operation, prompt, output):
    """Run full workflow"""

    from cli_anything.anygen.core import task as task_mod

    def progress(s, p):
        if not ctx.json_output:
            click.echo(f"● {s}: {p}%")

    result = task_mod.run_full_workflow(
        ctx.api_key,
        operation,
        prompt,
        output,
        on_progress=progress
    )

    ctx.get_session().record("task run", {"operation": operation}, result)

    msg = f"✓ Done: {result.get('local_path', result.get('task_url'))}"
    print_output(ctx, result, msg)


# ─────────────────────────────────────────────
# FILE COMMAND
# ─────────────────────────────────────────────

@cli.group()
def file():
    pass


@file.command("upload")
@click.argument("path", type=click.Path(exists=True))
@pass_ctx
@handle_error
def upload(ctx: CLIContext, path):
    from cli_anything.anygen.core import task as task_mod

    result = task_mod.upload_file(ctx.api_key, path)
    ctx.get_session().record("upload", {"path": path}, result)

    print_output(ctx, result, f"✓ Uploaded: {result['file_token']}")


# ─────────────────────────────────────────────
# CONFIG COMMAND
# ─────────────────────────────────────────────

@cli.group()
def config():
    pass


@config.command("set")
@click.argument("key")
@click.argument("value")
@pass_ctx
def config_set(ctx: CLIContext, key, value):
    from cli_anything.anygen.utils.anygen_backend import load_config, save_config

    cfg = load_config()
    cfg[key] = value
    save_config(cfg)

    print_output(ctx, cfg, f"✓ Set {key}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    cli()


if __name__ == "__main__":
    main()
