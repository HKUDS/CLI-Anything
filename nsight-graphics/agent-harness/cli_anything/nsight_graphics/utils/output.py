"""Output helpers."""

from __future__ import annotations

import json
import sys
from typing import Any


def output_json(data: Any, indent: int = 2, file=None) -> None:
    """Write JSON to stdout or a supplied file object."""
    if file is None:
        file = sys.stdout
    json.dump(data, file, indent=indent, default=str)
    file.write("\n")
