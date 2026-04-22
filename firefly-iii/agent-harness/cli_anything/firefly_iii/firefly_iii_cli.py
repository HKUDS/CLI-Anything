#!/usr/bin/env python3
r"""
Firefly III CLI - Personal finance management via CLI-Anything

Firefly III command-line interface based on CLI-Anything spec,
converted from MCP mode to stateless CLI mode to avoid Node residual process issues.
"""

import click
import json
import os
import sys
from typing import Dict, Any, Optional

from .utils.firefly_iii_backend import FireflyIIIBackend
from .utils.repl_skin import ReplSkin

# Global state
_json_output = False
_backend = None
_repl_skin = None


def get_backend() -> FireflyIIIBackend:
    """Get backend instance, raise error if not initialized"""
    if _backend is None:
        raise RuntimeError("Backend not initialized, please check configuration")
    return _backend


def output(data: Any):
    """Unified output format: JSON or human-readable"""
    if _json_output:
        try:
            click.echo(json.dumps(data, indent=2, ensure_ascii=False))
        except UnicodeEncodeError:
            # If console does not support Unicode, use ASCII encoding
            click.echo(json.dumps(data, indent=2, ensure_ascii=True))
    else:
        # Human-readable format
        if isinstance(data, dict):
            if 'data' in data:
                # Firefly III API standard response format
                items = data['data']
                if isinstance(items, list):
                    for item in items:
                        attrs = item.get('attributes', {})
                        name = attrs.get('name', item.get('id'))
                        click.echo(f"  {item.get('id', 'N/A')}: {name}")
                else:
                    attrs = items.get('attributes', {})
                    for key, value in attrs.items():
                        click.echo(f"  {key}: {value}")
            elif 'meta' in data:
                # Response with metadata
                click.echo(f"  Total: {data.get('meta', {}).get('pagination', {}).get('total', 'N/A')}")
            else:
                for key, value in data.items():
                    click.echo(f"  {key}: {value}")
        elif isinstance(data, list):
            for item in data:
                click.echo(f"  - {item}")
        else:
            click.echo(f"  {data}")


@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, help="Output as JSON")
@click.option("--base-url", help="Firefly III base URL")
@click.option("--pat", help="Personal Access Token")
@click.option("--preset", default="default",
              type=click.Choice(['default', 'full', 'basic', 'budget', 'reporting', 'admin', 'automation']),
              help="Tool preset")
@click.pass_context
def cli(ctx, use_json, base_url, pat, preset):
    """Firefly III CLI - Personal finance management.

    Based on CLI-Anything spec, converted from MCP mode to stateless CLI mode,
    avoiding Node residual process issues.
    """
    global _json_output, _backend, _repl_skin

    _json_output = use_json

    # Get configuration from arguments and environment variables
    base_url = base_url or os.environ.get('FIREFLY_III_BASE_URL')
    pat = pat or os.environ.get('FIREFLY_III_PAT')

    if not base_url or not pat:
        click.echo("Error: FIREFLY_III_BASE_URL and FIREFLY_III_PAT are required", err=True)
        click.echo("\nUsage:", err=True)
        click.echo("  cli-anything-firefly-iii --base-url URL --pat TOKEN", err=True)
        click.echo("\nOr set environment variables:", err=True)
        click.echo("  export FIREFLY_III_BASE_URL=https://firefly.yourdomain.com", err=True)
        click.echo("  export FIREFLY_III_PAT=your-personal-access-token", err=True)
        ctx.exit(1)

    try:
        _backend = FireflyIIIBackend(base_url, pat)
        _repl_skin = ReplSkin("firefly-iii", "1.0.0")
    except RuntimeError as e:
        click.echo(f"Error: {e}", err=True)
        ctx.exit(1)

    # Enter REPL when no subcommand is provided
    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


# Import command groups
from .core.accounts import accounts
from .core.transactions import transactions
from .core.budgets import budgets
from .core.categories import categories
from .core.tags import tags
from .core.bills import bills
from .core.piggy_banks import piggy_banks
from .core.insights import insights
from .core.search import search
from .core.export import export
from .core.info import info

# Register command groups
cli.add_command(accounts)
cli.add_command(transactions)
cli.add_command(budgets)
cli.add_command(categories)
cli.add_command(tags)
cli.add_command(bills)
cli.add_command(piggy_banks)
cli.add_command(insights)
cli.add_command(search)
cli.add_command(export)
cli.add_command(info)


@cli.command()
def repl():
    """Start interactive REPL mode"""
    global _json_output

    if _repl_skin is None:
        click.echo("Error: REPL requires backend connection to be initialized first", err=True)
        return

    _repl_skin.print_banner()
    _repl_skin.info("Type 'help' for available commands, 'exit' to quit")

    while True:
        try:
            user_input = _repl_skin.prompt("firefly-iii")

            if not user_input.strip():
                continue

            if user_input.lower() in ['exit', 'quit', 'q']:
                _repl_skin.print_goodbye()
                break

            if user_input.lower() == 'help':
                _repl_skin.help(cli.commands)
                continue

            # Parse command
            parts = user_input.split()
            command_name = parts[0]
            args = parts[1:]

            if command_name in cli.commands:
                # Build command context
                ctx = click.Context(cli.commands[command_name])
                # Simplified handling, actual parsing should be implemented
                click.echo(f"Executing: {command_name} {' '.join(args)}")
            else:
                _repl_skin.error(f"Unknown command: {command_name}")

        except KeyboardInterrupt:
            _repl_skin.print_goodbye()
            break
        except Exception as e:
            _repl_skin.error(f"Error: {e}")


def main():
    """Entry point"""
    cli()


if __name__ == '__main__':
    main()
