"""
Error handling utilities.
"""

from __future__ import annotations

import sys
import traceback
from typing import Any, Dict


def handle_error(e: Exception, debug: bool = False) -> Dict[str, Any]:
    """Convert an exception into an error dict."""
    result = {
        "error": str(e),
        "type": type(e).__name__,
    }
    if debug:
        result["traceback"] = traceback.format_exc()
    return result


def die(message: str, code: int = 1):
    """Print error message and exit."""
    sys.stderr.write(f"Error: {message}\n")
    sys.exit(code)
