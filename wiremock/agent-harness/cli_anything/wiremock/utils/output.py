import json
import sys
from typing import Any


def print_json(data: Any) -> None:
    """Print data as formatted JSON."""
    print(json.dumps(data, indent=2))


def print_table(headers: list, rows: list, title: str = None) -> None:
    """Print data as a simple ASCII table using rich if available."""
    try:
        from rich.console import Console
        from rich.table import Table

        table = Table(title=title, show_header=True)
        for h in headers:
            table.add_column(h)
        for row in rows:
            table.add_row(*[str(c) for c in row])
        Console().print(table)
    except ImportError:
        if title:
            print(f"\n{title}")
        print(" | ".join(headers))
        print("-" * 40)
        for row in rows:
            print(" | ".join(str(c) for c in row))


def success(message: str, data: Any = None, json_mode: bool = False) -> None:
    """Output a success result."""
    if json_mode:
        print_json({"status": "ok", "message": message, "data": data})
    else:
        print(f"✓ {message}")
        if data is not None:
            print_json(data)


def error(message: str, json_mode: bool = False) -> None:
    """Output an error result and exit."""
    if json_mode:
        print_json({"status": "error", "message": message})
    else:
        print(f"✗ {message}", file=sys.stderr)
    sys.exit(1)
