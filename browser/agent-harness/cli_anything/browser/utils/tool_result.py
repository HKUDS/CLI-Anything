"""Shared helpers for DOMShell/MCP tool results.

The browser harness often receives payloads where `isError=False` but the text
payload clearly says the operation failed. This module centralizes the best-
effort classification and message extraction so command handlers can make one
consistent decision instead of duplicating heuristics.
"""

from __future__ import annotations

from typing import Any, Iterable

_FAILURE_TOKENS = (
    "no such",
    "failed",
    "could not",
    "cannot",
    "invalid",
    "not found",
    "denied",
    "timed out",
    "timeout",
    "error occurred",
    "an error occurred",
    "error:",
    "fatal",
)

_ERROR_STATUS_VALUES = {"error", "failed", "failure"}


def normalize_tool_result(result: Any) -> Any:
    """Convert tool result objects into JSON-friendly Python data."""
    if hasattr(result, "model_dump"):
        return result.model_dump()
    if hasattr(result, "dict"):
        try:
            return result.dict()
        except Exception:
            pass
    if isinstance(result, (dict, list, str, int, float, bool)) or result is None:
        return result
    return str(result)


def _iter_text_payloads(result: Any) -> Iterable[str]:
    data = normalize_tool_result(result)
    if isinstance(data, str):
        yield data
        return
    if not isinstance(data, dict):
        return

    for key in ("error", "message", "detail", "stdout"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            yield value

    content = data.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                text = item.get("text", "")
                if isinstance(text, str) and text.strip():
                    yield text
            elif isinstance(item, str) and item.strip():
                yield item


def _looks_like_failure_text(text: str) -> bool:
    lowered = text.lower().strip()
    if not lowered:
        return False
    return any(token in lowered for token in _FAILURE_TOKENS)


def tool_result_has_error(result: Any) -> bool:
    """Best-effort detection of a tool failure payload."""
    data = normalize_tool_result(result)
    if isinstance(data, str):
        return _looks_like_failure_text(data)
    if not isinstance(data, dict):
        return False

    if data.get("error") is not None:
        return True
    if data.get("isError") is True:
        return True
    status = data.get("status")
    if isinstance(status, str) and status.lower().strip() in _ERROR_STATUS_VALUES:
        return True

    for text in _iter_text_payloads(data):
        if _looks_like_failure_text(text):
            return True

    return False


def tool_result_error_text(result: Any, default: str = "") -> str:
    """Extract a concise human-readable error text from a tool result."""
    data = normalize_tool_result(result)
    if isinstance(data, str):
        return data.strip() or default
    if not isinstance(data, dict):
        return default

    error_value = data.get("error")
    if error_value is not None:
        if isinstance(error_value, str) and error_value.strip():
            return error_value
        return str(error_value)

    for text in _iter_text_payloads(data):
        if _looks_like_failure_text(text):
            return text

    return default


def tool_result_body_text(result: Any, default: str = "") -> str:
    """Extract a concise success payload for human-readable output.

    Joins all textual payload fragments into a single string. If nothing useful
    is present, returns `default`.
    """
    data = normalize_tool_result(result)
    if isinstance(data, str):
        text = data.strip()
        return text or default
    if not isinstance(data, dict):
        return default

    lines = [text.strip() for text in _iter_text_payloads(data) if text.strip()]
    if lines:
        return "\n".join(lines)

    return default
