"""SeaClip-Lite CLI — Click CLI with REPL mode.

Entry point for the cli-anything-seaclip harness.
Supports both one-shot commands and an interactive REPL.
"""

import json as json_mod
import shlex
import sys

import click

from .core.issues import issue_group
from .core.agents import agent_group
from .core.pipeline import pipeline_group
from .core.scheduler import scheduler_group
from .core.activity import activity_group
from .utils.seaclip_backend import SeaClipBackend
from .utils.repl_skin import ReplSkin

VERSION = "1.0.0"


# ── Server command group ─────────────────────────────────────────────

@click.group("server")
def server_group():
    """Server utilities."""


@server_group.command("health")
@click.pass_context
def server_health(ctx):
    """Check backend health."""
    backend: SeaClipBackend = ctx.obj["backend"]
    skin = ctx.obj.get("skin")
    as_json = ctx.obj.get("json", False)

    try:
        result = backend.health()
    except Exception as e:
        if as_json:
            click.echo(json_mod.dumps({"error": str(e)}))
        elif skin:
            skin.error(f"Health check failed: {e}")
        raise SystemExit(1)

    if as_json:
        click.echo(json_mod.dumps(result, indent=2))
    elif skin:
        skin.success("SeaClip-Lite backend is healthy")
        if isinstance(result, dict):
            for k, v in result.items():
                skin.status(k, str(v))


# ── Main CLI group ───────────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON")
@click.option("--url", default=None, help="SeaClip backend URL (default: http://127.0.0.1:5200)")
@click.version_option(VERSION, prog_name="cli-anything-seaclip")
@click.pass_context
def cli(ctx, as_json, url):
    """SeaClip-Lite CLI — manage issues, pipelines, agents, and schedules."""
    ctx.ensure_object(dict)
    backend = SeaClipBackend(base_url=url)
    skin = ReplSkin("seaclip", version=VERSION)

    ctx.obj["backend"] = backend
    ctx.obj["skin"] = skin
    ctx.obj["json"] = as_json

    # If no subcommand given, launch the REPL
    if ctx.invoked_subcommand is None:
        _run_repl(ctx, backend, skin)


# Register command groups
cli.add_command(issue_group)
cli.add_command(agent_group)
cli.add_command(pipeline_group)
cli.add_command(scheduler_group)
cli.add_command(activity_group)
cli.add_command(server_group)


# ── REPL ─────────────────────────────────────────────────────────────

REPL_COMMANDS = {
    "issue list":       "List issues (options: --status, --priority, --search, --limit)",
    "issue create":     "Create issue (--title, --description, --priority)",
    "issue move":       "Move issue to column (ISSUE_ID --column COL)",
    "issue status":     "Update issue status (ISSUE_ID --set STATUS)",
    "issue delete":     "Delete issue (ISSUE_ID)",
    "agent list":       "List pipeline agents",
    "pipeline start":   "Start pipeline (--issue UUID --mode auto|manual)",
    "pipeline status":  "Get pipeline status (--issue UUID)",
    "pipeline resume":  "Resume paused pipeline (--issue UUID)",
    "pipeline stop":    "Stop running pipeline (--issue UUID)",
    "scheduler list":   "List schedules",
    "scheduler add":    "Add schedule (--name, --cron, --repo)",
    "scheduler sync":   "Trigger sync (SCHEDULE_ID)",
    "activity list":    "Recent activity (--limit N)",
    "server health":    "Check backend health",
    "help":             "Show this help",
    "quit / exit":      "Exit the REPL",
}


def _run_repl(ctx, backend: SeaClipBackend, skin: ReplSkin):
    """Interactive REPL loop."""
    skin.print_banner()

    # Try prompt_toolkit, fall back to plain input
    pt_session = skin.create_prompt_session()

    while True:
        try:
            line = skin.get_input(pt_session, context="seaclip")
        except (EOFError, KeyboardInterrupt):
            skin.print_goodbye()
            break

        if not line:
            continue

        cmd = line.strip().lower()
        if cmd in ("quit", "exit", "q"):
            skin.print_goodbye()
            break

        if cmd in ("help", "?"):
            skin.help(REPL_COMMANDS)
            continue

        # Parse and dispatch through Click
        try:
            args = shlex.split(line)
        except ValueError as e:
            skin.error(f"Parse error: {e}")
            continue

        try:
            cli.main(args=args, standalone_mode=False, obj=ctx.obj)
        except SystemExit:
            pass
        except click.UsageError as e:
            skin.error(str(e))
        except click.exceptions.MissingParameter as e:
            skin.error(str(e))
        except Exception as e:
            skin.error(f"Error: {e}")


# ── Entry point ──────────────────────────────────────────────────────

def main():
    cli(auto_envvar_prefix="SEACLIP")


if __name__ == "__main__":
    main()
