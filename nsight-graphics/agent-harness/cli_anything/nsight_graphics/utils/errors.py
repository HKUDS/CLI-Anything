"""Error handling helpers."""

from __future__ import annotations

import traceback
from typing import Any


def handle_error(exc: Exception, debug: bool = False) -> dict[str, Any]:
    """Convert an exception into a JSON-friendly error payload."""
    payload: dict[str, Any] = {
        "error": str(exc),
        "type": type(exc).__name__,
    }
    if debug:
        payload["traceback"] = traceback.format_exc()
    return payload
