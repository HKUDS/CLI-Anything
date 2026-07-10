"""
Output formatting helpers.
"""

from __future__ import annotations

import json
import sys
from typing import Any


def output_json(data: Any, indent: int = 2, file=None):
    """Write JSON data to stdout or a file-like object."""
    if file is None:
        file = sys.stdout
    json.dump(data, file, indent=indent, default=str)
    file.write("\n")


def output_table(rows: list[list[Any]], headers: list[str], file=None):
    """Print a simple ASCII table."""
    if file is None:
        file = sys.stdout

    if not rows:
        file.write("(no data)\n")
        return

    col_widths = [len(header) for header in headers]
    for row in rows:
        for idx, value in enumerate(row[: len(headers)]):
            col_widths[idx] = max(col_widths[idx], len(str(value)))

    header_line = "  ".join(str(headers[idx]).ljust(col_widths[idx]) for idx in range(len(headers)))
    file.write(header_line + "\n")
    file.write("  ".join("-" * width for width in col_widths) + "\n")

    for row in rows:
        truncated = row[: len(headers)]
        line = "  ".join(str(value).ljust(col_widths[idx]) for idx, value in enumerate(truncated))
        file.write(line + "\n")


def format_size(size_bytes: int | None) -> str:
    """Format a byte count as a human-readable string."""
    if size_bytes is None:
        return "unknown"
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    if size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
