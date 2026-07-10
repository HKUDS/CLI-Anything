"""JSON / human output helpers for cli-anything-mailchimp."""

from __future__ import annotations

import json
import sys
from typing import Any

# Module-level flag set by the root CLI group's --json option.
USE_JSON: bool = False


def _out(data: Any) -> None:
    """Print data as JSON (when --json) or human-readable text."""
    if USE_JSON:
        print(json.dumps(data, indent=2, default=str))
    elif isinstance(data, dict):
        _print_dict(data)
    elif isinstance(data, list):
        _print_list(data)
    else:
        print(data)


def _out_ok(message: str, data: dict | None = None) -> None:
    """Print a success/mutation result.

    JSON shape: {"ok": true, "message": "<msg>"} or {"ok": true, "message": "...", "data": {...}}
    """
    if USE_JSON:
        payload: dict = {"ok": True, "message": message}
        if data:
            payload["data"] = data
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(f"  \033[38;5;78m✓\033[0m {message}")
        if data:
            _print_dict(data)


def _out_err(status: int, title: str, detail: str, raw: dict | None = None) -> None:
    """Print an error and exit non-zero."""
    if USE_JSON:
        print(
            json.dumps(
                {"ok": False, "message": f"{title}: {detail}", "data": raw or {}},
                indent=2,
            ),
            file=sys.stderr,
        )
    else:
        print(f"  \033[38;5;196m✗\033[0m HTTP {status}: {title}", file=sys.stderr)
        if detail:
            print(f"    {detail}", file=sys.stderr)
    sys.exit(1)


# ── Formatting helpers ─────────────────────────────────────────────────


_GRAY = "\033[38;5;245m"
_WHITE = "\033[97m"
_CYAN = "\033[38;5;80m"
_RESET = "\033[0m"


def _print_dict(d: dict, indent: int = 2) -> None:
    prefix = " " * indent
    for k, v in d.items():
        key = f"{_GRAY}{k}:{_RESET}"
        if isinstance(v, dict):
            print(f"{prefix}{key}")
            _print_dict(v, indent + 2)
        elif isinstance(v, list):
            print(f"{prefix}{key} [{len(v)} items]")
        else:
            print(f"{prefix}{key} {_WHITE}{v}{_RESET}")


def _print_list(items: list, indent: int = 2) -> None:
    for item in items:
        if isinstance(item, dict):
            _print_dict(item, indent)
            print()
        else:
            print(" " * indent + str(item))
