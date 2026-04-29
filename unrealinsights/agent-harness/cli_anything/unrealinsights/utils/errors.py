"""
Error handling utilities.
"""

from __future__ import annotations

import sys
import traceback
from typing import Any


def handle_error(exc: Exception, debug: bool = False) -> dict[str, Any]:
    """Convert an exception into a structured error payload."""
    result = {
        "error": str(exc),
        "type": type(exc).__name__,
    }
    if debug:
        result["traceback"] = traceback.format_exc()
    return result


def die(message: str, code: int = 1):
    """Print an error message and exit."""
    sys.stderr.write(f"Error: {message}\n")
    sys.exit(code)
