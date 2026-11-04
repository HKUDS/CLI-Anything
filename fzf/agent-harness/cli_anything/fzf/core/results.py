"""Exact fzf output framing and exit semantics."""

from __future__ import annotations

import base64
import hashlib
from typing import Any

from cli_anything.fzf.core.capabilities import load_capabilities


def _record(data: bytes) -> dict[str, Any]:
    try:
        text: str | None = data.decode("utf-8")
        utf8 = True
    except UnicodeDecodeError:
        text = None
        utf8 = False
    return {
        "text": text,
        "utf8": utf8,
        "base64": base64.b64encode(data).decode("ascii"),
        "byte_count": len(data),
    }


def split_records(data: bytes, *, print0: bool) -> list[bytes]:
    """Split output records while preserving intentional empty records."""

    separator = b"\0" if print0 else b"\n"
    if not data:
        return []
    records = data.split(separator)
    if data.endswith(separator):
        records.pop()
    return records


def parse_output(
    data: bytes,
    *,
    print0: bool,
    print_query: bool,
    expect: bool,
) -> dict[str, Any]:
    """Separate query/expect prefixes from selected records."""

    records = split_records(data, print0=print0)
    query = _record(records.pop(0)) if print_query and records else None
    expected_key = _record(records.pop(0)) if expect and records else None
    return {
        "record_separator": "nul" if print0 else "newline",
        "query": query,
        "expect_key": expected_key,
        "selections": [_record(record) for record in records],
        "selection_count": len(records),
        "output_base64": base64.b64encode(data).decode("ascii"),
        "output_byte_count": len(data),
        "output_sha256": hashlib.sha256(data).hexdigest(),
    }


def parse_benchmark(data: bytes) -> dict[str, Any]:
    """Represent fzf's benchmark report without calling it a selection."""

    try:
        text: str | None = data.decode("utf-8")
        utf8 = True
    except UnicodeDecodeError:
        text = None
        utf8 = False
    return {
        "benchmark": {
            "text": text,
            "utf8": utf8,
            "base64": base64.b64encode(data).decode("ascii"),
            "byte_count": len(data),
        },
        "output_base64": base64.b64encode(data).decode("ascii"),
        "output_byte_count": len(data),
        "output_sha256": hashlib.sha256(data).hexdigest(),
    }


def exit_semantics(exit_code: int) -> dict[str, Any]:
    """Map process status without conflating completion and selection."""

    meanings = load_capabilities()["exit_status"]
    meaning = meanings.get(str(exit_code), "unknown-backend-exit")
    return {
        "process_exit_code": exit_code,
        "meaning": meaning,
        "backend_completed": exit_code in {0, 1},
        "semantic_success": exit_code == 0,
        "no_match": exit_code == 1,
        "interrupted": exit_code == 130,
    }
