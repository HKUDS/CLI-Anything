"""
Output formatting for JumpServer CLI.

Supports table, JSON, YAML, and human-readable formats.
"""
import json
import sys
from typing import Any


def format_output(
    data: Any,
    fmt: str = "table",
    columns: list[str] | None = None,
    stream=sys.stdout,
) -> None:
    """Format and print data in the specified format."""
    if fmt == "json":
        print(json.dumps(data, indent=2, ensure_ascii=False, default=str), file=stream)
    elif fmt == "yaml":
        import yaml

        print(yaml.dump(data, allow_unicode=True, default_flow_style=False), file=stream)
    elif fmt == "table":
        _format_table(data, columns, stream)
    else:
        print(data, file=stream)


def _format_table(
    data: Any,
    columns: list[str] | None = None,
    stream=sys.stdout,
) -> None:
    """Format data as a human-readable table."""
    if isinstance(data, dict):
        _format_dict_table(data, stream)
    elif isinstance(data, list) and data and isinstance(data[0], dict):
        _format_list_table(data, columns, stream)
    elif isinstance(data, list):
        if not data:
            print("  (no results)", file=stream)
        else:
            for item in data:
                print(f"  - {item}", file=stream)
    else:
        print(data, file=stream)


def _format_dict_table(data: dict, stream) -> None:
    """Print a single dict as key-value pairs."""
    max_key_len = max((len(str(k)) for k in data), default=0)
    for key, value in data.items():
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        print(f"  {key:<{max_key_len}} : {value}", file=stream)


def _format_list_table(
    data: list[dict],
    columns: list[str] | None = None,
    stream=sys.stdout,
) -> None:
    """Print a list of dicts as a table."""
    if not data:
        print("  (no results)", file=stream)
        return

    if columns is None:
        columns = list(data[0].keys())

    cols = [c for c in columns if any(c in row for row in data)]
    if not cols:
        cols = list(data[0].keys())

    col_widths = {}
    for col in cols:
        col_widths[col] = max(
            len(col),
            max((len(str(row.get(col, ""))) for row in data), default=0),
        )
        col_widths[col] = min(col_widths[col], 50)

    header = "  " + "  ".join(
        str(col).ljust(col_widths[col]) for col in cols
    )
    print(header, file=stream)
    print("  " + "-" * (len(header) - 2), file=stream)

    for row in data:
        line = "  " + "  ".join(
            _truncate(str(row.get(col, "")), col_widths[col]) for col in cols
        )
        print(line, file=stream)

    print(f"\n  ({len(data)} result(s))", file=stream)


def _truncate(value: str, width: int) -> str:
    """Truncate a string to fit the given width."""
    if len(value) > width:
        return value[: width - 3] + "..."
    return value.ljust(width)
