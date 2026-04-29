"""
Output formatting: JSON and human-readable output helpers.
"""

from __future__ import annotations

import json
import sys
from typing import Any


def output_json(data: Any, indent: int = 2, file=None):
    """Write data as JSON to stdout or a file."""
    if file is None:
        file = sys.stdout
    json.dump(data, file, indent=indent, default=str)
    file.write("\n")


def output_table(rows: list, headers: list, file=None):
    """Print a simple ASCII table."""
    if file is None:
        file = sys.stdout

    if not rows:
        file.write("(no data)\n")
        return

    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(str(val)))

    header_line = "  ".join(str(h).ljust(col_widths[i]) for i, h in enumerate(headers))
    file.write(header_line + "\n")
    file.write("  ".join("-" * w for w in col_widths) + "\n")

    for row in rows:
        truncated = row[: len(headers)]
        line = "  ".join(str(v).ljust(col_widths[i]) for i, v in enumerate(truncated))
        file.write(line + "\n")
