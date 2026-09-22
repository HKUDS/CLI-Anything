#!/usr/bin/env python3
"""
AnyGen CLI — Generate docs, slides, websites and more via AnyGen cloud API.

Author: Your Name
License: MIT

Notes:
- This CLI wraps AnyGen cloud APIs into a structured command interface.
- Designed for both scripting (JSON mode) and interactive usage (REPL).
- All commands are stateless except session/history tracking.

Best Practices:
- Use `--json` for automation pipelines.
- Store API key via `config set api_key` instead of passing inline.
- Prefer `task run` for end-to-end workflows.
"""

import sys
import os
import json
import click
from typing import Optional, Any, Dict

# ── Path Setup ──────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cli_anything.anygen.core.session import Session
from cli_anything.anygen.core import task as task_mod
from cli_anything.anygen.utils.anygen_backend import (
    get_api_key,
    load_config,
    save_config,
    VALID_OPERATIONS,
)

# ── Global Context (centralized) ─────────────────────────────
class AppContext:
    def __init__(self):
        self.session: Optional[Session] = None
        self.json_output: bool = False
        self.repl_mode: bool = False
        self.api_key: Optional[str] = None

CTX = AppContext()


# ── Session ────────────────────────────────────────────────
def get_session() -> Session:
    if CTX.session is None:
        from pathlib import Path
        sf = Path.home() / ".cli-anything-anygen" / "session.json"
        CTX.session = Session(session_file=str(sf))
    return CTX.session


# ── Output Handling ─────────────────────────────────────────
def output(data: Any, message: str = ""):
    """Unified output handler supporting JSON + human-readable formats."""
    if CTX.json_output:
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


def _print_dict(d: Dict, indent: int = 0):
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


# ── Error Handling ──────────────────────────────────────────
def handle_error(func):
    """Decorator to standardize CLI error handling."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            payload = {"error": str(e), "type": type(e).__name__}
            if CTX.json_output:
                click.echo(json.dumps(payload))
            else:
                click.echo(f"Error: {e}", err=True)

            if not CTX.repl_mode:
                sys.exit(1)

    return wrapper


# ── CLI Root ────────────────────────────────────────────────
@click.group(invoke_without_command=True)
@click.option("--json", is_flag=True, help="Output as JSON")
@click.option("--api-key", type=str, help="AnyGen API key (sk-xxx)")
@click.pass_context
def cli(ctx, json, api_key):
    """AnyGen CLI — Generate content via cloud API."""
    CTX.json_output = json
    CTX.api_key = get_api_key(api_key)
    ctx.ensure_object(dict)

    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


# ── Task Commands ───────────────────────────────────────────
@cli.group()
def task():
    """Task management — create, poll, download."""
    pass


@task.command("run")
@click.option("-o", "--operation", required=True,
              type=click.Choice(VALID_OPERATIONS, case_sensitive=False))
@click.option("-p", "--prompt", required=True)
@click.option("--output", "output_dir")
@handle_error
def task_run(operation, prompt, output_dir):
    """Full workflow: create → poll → download."""
    def on_progress(status, pct):
        if not CTX.json_output:
            click.echo(f"  ● {status}: {pct}%")

    result = task_mod.run_full_workflow(
        CTX.api_key,
        operation,
        prompt,
        output_dir,
        on_progress=on_progress,
    )

    get_session().record("task run", {"operation": operation}, result)

    msg = "✓ Completed!"
    if result.get("local_path"):
        msg += f" File: {result['local_path']}"
    else:
        msg += f" URL: {result.get('task_url')}"

    output(result, msg)


# ── Config Commands ─────────────────────────────────────────
@cli.group()
def config():
    """Configuration management."""
    pass


@config.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key, value):
    """Set configuration value."""
    cfg = load_config()
    cfg[key] = value
    save_config(cfg)

    output({"key": key, "value": value}, f"✓ Set {key}")


# ── REPL ────────────────────────────────────────────────────
@cli.command("repl", hidden=True)
def repl():
    """Interactive REPL mode."""
    CTX.repl_mode = True

    from cli_anything.anygen.utils.repl_skin import ReplSkin
    skin = ReplSkin("anygen", version="1.0.0")

    skin.print_banner()
    pt_session = skin.create_prompt_session()

    while True:
        try:
            line = skin.get_input(pt_session, context="anygen")
        except (EOFError, KeyboardInterrupt):
            skin.print_goodbye()
            break

        if line in ("exit", "quit", "q"):
            skin.print_goodbye()
            break

        try:
            cli.main(line.split(), standalone_mode=False)
        except Exception as e:
            skin.error(str(e))


def main():
    cli()


if __name__ == "__main__":
    main()
