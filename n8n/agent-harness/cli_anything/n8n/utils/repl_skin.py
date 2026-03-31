"""REPL UI — banner, prompt, colors, table formatting."""

from __future__ import annotations

import json
import shutil
from typing import Any

import click


# --- Colors ---

ORANGE = "bright_yellow"
GREEN = "green"
RED = "red"
CYAN = "cyan"
DIM = "bright_black"


# --- Banner ---

BANNER = r"""
  _ __ | (_)      __ _ _ __  _   _| |_| |__ (_)_ __   __ _     _ __ | |_ _ __
 / __| | | |___  / _` | '_ \| | | | __| '_ \| | '_ \ / _` |   | '_ \| | | '_ \
| (__ | | |     | (_| | | | | |_| | |_| | | | | | | | (_| |   | | | | |_| | | |
 \___|_|_|      \__,_|_| |_|\__, |\__|_| |_|_|_| |_|\__, |   |_| |_|_|_|_| |_|
                             |___/                    |___/
"""


def print_banner(base_url: str) -> None:
    click.secho(BANNER, fg=ORANGE)
    click.secho(f"  Connected to: {base_url}", fg=GREEN)
    click.secho("  Type 'help' for commands, 'exit' to quit.\n", fg=DIM)


# --- Output helpers ---

def output(data: Any, as_json: bool) -> None:
    """Print data as JSON or human-readable."""
    if as_json:
        click.echo(json.dumps(data, indent=2, default=str))
        return

    if isinstance(data, dict):
        if "data" in data and isinstance(data["data"], list):
            _print_table(data["data"])
            if "nextCursor" in data:
                click.secho(f"\n  Next cursor: {data['nextCursor']}", fg=DIM)
        else:
            _print_dict(data)
    elif isinstance(data, list):
        _print_table(data)
    else:
        click.echo(str(data))


def _print_dict(d: dict[str, Any], indent: int = 0) -> None:
    prefix = "  " * indent
    for k, v in d.items():
        if isinstance(v, dict):
            click.secho(f"{prefix}{k}:", fg=CYAN)
            _print_dict(v, indent + 1)
        elif isinstance(v, list) and v and isinstance(v[0], dict):
            click.secho(f"{prefix}{k}:", fg=CYAN)
            _print_table(v)
        else:
            click.echo(f"{prefix}{click.style(str(k), fg=CYAN)}: {v}")


def _print_table(rows: list[dict[str, Any]]) -> None:
    if not rows:
        click.secho("  (empty)", fg=DIM)
        return

    term_width = shutil.get_terminal_size().columns
    keys = list(rows[0].keys())

    # Filter out overly complex nested fields for table view
    simple_keys = [k for k in keys if not isinstance(rows[0].get(k), (dict, list))]
    if not simple_keys:
        simple_keys = keys[:5]

    col_widths = {k: len(str(k)) for k in simple_keys}
    for row in rows:
        for k in simple_keys:
            val = str(row.get(k, ""))
            col_widths[k] = min(max(col_widths[k], len(val)), 40)

    # Truncate columns if they exceed terminal width
    total = sum(col_widths.values()) + (len(simple_keys) - 1) * 3
    if total > term_width:
        max_col = max(10, term_width // len(simple_keys) - 3)
        col_widths = {k: min(v, max_col) for k, v in col_widths.items()}

    header = " | ".join(click.style(k.ljust(col_widths[k])[:col_widths[k]], fg=CYAN) for k in simple_keys)
    click.echo(header)
    click.echo("-+-".join("-" * col_widths[k] for k in simple_keys))

    for row in rows:
        vals = []
        for k in simple_keys:
            v = str(row.get(k, ""))
            w = col_widths[k]
            if len(v) > w and w > 3:
                vals.append(v[: w - 1] + "\u2026")
            else:
                vals.append(v.ljust(w)[:w])
        click.echo(" | ".join(vals))


def success(msg: str) -> None:
    click.secho(f"  OK: {msg}", fg=GREEN)


def error(msg: str) -> None:
    click.secho(f"  ERROR: {msg}", fg=RED, err=True)


def warn(msg: str) -> None:
    click.secho(f"  WARN: {msg}", fg=ORANGE)
