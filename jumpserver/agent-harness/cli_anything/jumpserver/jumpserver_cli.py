#!/usr/bin/env python3
"""
JumpServer CLI - A stateful command-line interface for JumpServer bastion host.

Supports both one-shot commands and interactive REPL mode.
Output formats: table (default), json, yaml.

Usage:
    jumpserver auth login --url https://jumpserver.example.com --username admin
    jumpserver asset list --type host
    jumpserver user list --search admin
    jumpserver session list --active
    jumpserver                  # Enter REPL mode
"""

import sys
import os
import cmd
import shlex
import json
from typing import Any

import click

from cli_anything.jumpserver import __version__
from cli_anything.jumpserver.core.session import Session
from cli_anything.jumpserver.core.state import get_state, reset_state
from cli_anything.jumpserver.core.output import format_output
from cli_anything.jumpserver.utils import print_result, CLIError, wants_json_output

# Import command groups
from cli_anything.jumpserver.core.commands_auth import auth_group
from cli_anything.jumpserver.core.commands_asset import asset_group
from cli_anything.jumpserver.core.commands_user import user_group
from cli_anything.jumpserver.core.commands_perm import perm_group
from cli_anything.jumpserver.core.commands_account import account_group
from cli_anything.jumpserver.core.commands_session import session_group
from cli_anything.jumpserver.core.commands_audit import audit_group, ops_group
from cli_anything.jumpserver.core.commands_system import (
    system_group,
    label_group,
    role_group,
)


class JumpserverCLI(click.Group):
    """Custom CLI group with global options and REPL support."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_command(auth_group)
        self.add_command(asset_group)
        self.add_command(user_group)
        self.add_command(perm_group)
        self.add_command(account_group)
        self.add_command(session_group)
        self.add_command(audit_group)
        self.add_command(ops_group)
        self.add_command(system_group)
        self.add_command(label_group)
        self.add_command(role_group)

    @staticmethod
    def _start_repl(ctx: click.Context) -> None:
        """Start interactive REPL mode."""
        click.echo(click.style(f"JumpServer CLI v{__version__}", fg="cyan", bold=True))
        session = Session.load()
        if session.is_authenticated():
            click.echo(
                click.style(
                    f"Connected as {session.username} @ {session.base_url}",
                    fg="green",
                )
            )
        else:
            click.echo(
                click.style(
                    "Not authenticated. Use 'auth login' to connect.",
                    fg="yellow",
                )
            )
        click.echo('Type "help" for available commands, "exit" to quit.\n')

        repl = JumpServerREPL(ctx)
        repl.cmdloop()


class JumpServerREPL(cmd.Cmd):
    """JumpServer CLI REPL shell."""

    prompt = click.style("jumpserver> ", fg="cyan")

    def __init__(self, cli_ctx: click.Context):
        super().__init__()
        self._ctx = cli_ctx
        self._session = Session.load()
        self._available_commands = [
            "auth login", "auth logout", "auth status", "auth org",
            "asset list", "asset get", "asset create", "asset update", "asset delete",
            "asset node list", "asset node create", "asset node delete",
            "asset platform list", "asset gateway list", "asset gateway test",
            "asset zone list",
            "user list", "user get", "user create", "user update", "user delete",
            "user reset-password", "user unblock", "user profile", "user my-assets",
            "user group list", "user group create", "user group members",
            "perm list", "perm get", "perm create", "perm update", "perm delete",
            "perm users", "perm assets",
            "account list", "account get", "account create", "account update",
            "account delete", "account secret view", "account secret history",
            "account template list",
            "session list", "session get", "session replay", "session kill",
            "session command list", "session terminal list", "session terminal status",
            "audit login", "audit operate", "audit ftp", "audit password", "audit activity",
            "ops job-list", "ops job-log", "ops adhoc-list", "ops playbook-list",
            "system settings", "system health", "system info",
            "label list",
            "role list", "role bindings",
            "exit", "help",
        ]

    def default(self, line: str) -> None:
        """Execute a Click command from the REPL."""
        if not line.strip():
            return

        if line.strip() in ("exit", "quit", "q"):
            return self.do_exit(line)

        # Rebuild CLI context and invoke
        args = shlex.split(line)
        try:
            with self._ctx.scope():
                self._ctx.args = args
                cli = JumpserverCLI(name="jumpserver")
                cli.main(args=args, prog_name="jumpserver", standalone_mode=False)
        except SystemExit:
            pass
        except click.ClickException as e:
            e.show()
        except Exception as e:
            click.echo(click.style(f"Error: {e}", fg="red"))

    def do_exit(self, arg: str) -> bool:
        """Exit the REPL."""
        click.echo("Goodbye!")
        return True

    def do_EOF(self, arg: str) -> bool:
        """Ctrl+D to exit."""
        click.echo()
        return self.do_exit(arg)

    def completedefault(self, text: str, line: str, begidx: int, endidx: int) -> list[str]:
        """Tab completion for commands."""
        parts = line[:begidx].split()
        completions = []

        for cmd in self._available_commands:
            cmd_parts = cmd.split()
            if len(cmd_parts) >= len(parts):
                if all(
                    cmd_parts[i].startswith(parts[i])
                    for i in range(len(parts))
                ):
                    if len(cmd_parts) > len(parts):
                        completions.append(cmd_parts[len(parts)])
                    elif text and cmd_parts[-1].startswith(text):
                        completions.append(cmd_parts[-1])

        return sorted(set(completions))

    def do_help(self, arg: str) -> None:
        """Show available commands."""
        if arg:
            return self.default(f"{arg} --help")

        click.echo(click.style("\nJumpServer CLI Commands:", bold=True))
        groups = {
            "Authentication": ["auth login", "auth logout", "auth status", "auth org"],
            "Asset Management": [
                "asset list", "asset get", "asset create", "asset update", "asset delete",
                "asset node *", "asset platform list", "asset gateway *", "asset zone list",
            ],
            "User Management": [
                "user list", "user get", "user create", "user update", "user delete",
                "user profile", "user my-assets", "user group *",
            ],
            "Permissions": ["perm list", "perm get", "perm create", "perm update", "perm delete"],
            "Accounts": ["account list", "account get", "account create", "account update",
                         "account delete", "account secret *", "account template list"],
            "Sessions": ["session list", "session get", "session replay", "session kill",
                         "session command list", "session terminal *"],
            "Audit & Ops": ["audit login", "audit operate", "audit ftp", "audit password",
                            "ops job-list", "ops job-log", "ops playbook-list"],
            "System": ["system settings", "system health", "system info",
                       "label list", "role list", "role bindings"],
        }

        for group_name, commands in groups.items():
            click.echo(click.style(f"\n  {group_name}:", fg="yellow"))
            for cmd in commands:
                click.echo(f"    {cmd}")

        click.echo(click.style("\n  Session:", fg="yellow"))
        click.echo("    exit, quit, Ctrl+D  - Exit REPL")
        click.echo("    help <command>       - Show command help")
        click.echo()


@click.group(cls=JumpserverCLI)
@click.version_option(version=__version__, prog_name="jumpserver-cli")
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    default=False,
    help="Output in JSON format",
)
@click.option(
    "--json-output",
    "json_output",
    is_flag=True,
    default=False,
    help="Output in JSON format (shortcut for -o json)",
)
@click.option(
    "--interactive", "-i",
    is_flag=True,
    default=False,
    help="Start interactive REPL mode",
)
@click.option(
    "--url",
    default=None,
    help="JumpServer URL (overrides saved session)",
    envvar="JUMPSERVER_URL",
)
@click.pass_context
def main(ctx, output_json, json_output, interactive, url):
    """JumpServer CLI - Command-line interface for JumpServer bastion host.

    Manage assets, users, permissions, sessions, and more from your terminal.

    \b
    Quick Start:
      jumpserver auth login --url https://js.example.com --username admin
      jumpserver asset list --type host
      jumpserver --interactive
    """
    ctx.ensure_object(dict)
    ctx.obj["output_json"] = output_json or json_output

    if url:
        session = Session.load()
        session.base_url = url.rstrip("/")
        session.save()

    if interactive and ctx.invoked_subcommand is None:
        JumpserverCLI._start_repl(ctx)
        return

    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        return

    if interactive:
        ctx.obj["interactive"] = True


def _show_click_error(error: click.ClickException, json_mode: bool) -> None:
    """Render Click errors in JSON mode when requested."""
    if json_mode:
        click.echo(
            json.dumps(
                {"status": "error", "message": error.format_message()},
                ensure_ascii=False,
            ),
            err=True,
        )
        return
    error.show()


def cli_main():
    """Entry point for console_scripts."""
    json_mode = wants_json_output()
    try:
        main(standalone_mode=False)
    except click.exceptions.Exit as e:
        sys.exit(e.exit_code)
    except KeyboardInterrupt:
        click.echo("\nInterrupted.")
        sys.exit(130)
    except click.Abort:
        if json_mode:
            click.echo(
                json.dumps({"status": "error", "message": "Aborted."}),
                err=True,
            )
        else:
            click.echo("Aborted!", err=True)
        sys.exit(1)
    except CLIError as e:
        e.show(json_mode=json_mode)
        sys.exit(1)
    except click.ClickException as e:
        _show_click_error(e, json_mode=json_mode)
        sys.exit(e.exit_code or 1)


if __name__ == "__main__":
    cli_main()
