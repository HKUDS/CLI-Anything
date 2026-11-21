"""Bounded byte-preserving input sources for fzf operations."""

from __future__ import annotations

import base64
import binascii
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterable

from cli_anything.fzf.core.errors import PolicyError, ValidationError


DEFAULT_MAX_BYTES = 16 * 1024 * 1024
HARD_MAX_BYTES = 128 * 1024 * 1024
DEFAULT_MAX_ITEMS = 200_000
HARD_MAX_ITEMS = 1_000_000


@dataclass
class InputSource:
    """Public description plus optional bytes loaded for execution."""

    kind: str
    description: dict
    data: bytes | None


def _bounded_read(handle: BinaryIO, max_bytes: int) -> bytes:
    data = handle.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValidationError(
            "input_too_large",
            f"Input exceeds the {max_bytes}-byte limit",
            details={"max_bytes": max_bytes},
        )
    return data


def _count_records(data: bytes, separator: bytes) -> int:
    if not data:
        return 0
    return len(data.split(separator)) - (1 if data.endswith(separator) else 0)


def _check_limits(data: bytes, separator: bytes, max_bytes: int, max_items: int) -> int:
    if len(data) > max_bytes:
        raise ValidationError("input_too_large", "Input byte limit exceeded")
    count = _count_records(data, separator)
    if count > max_items:
        raise ValidationError(
            "input_has_too_many_items",
            f"Input contains {count} records; limit is {max_items}",
        )
    return count


def prepare_input(
    *,
    items: Iterable[str] = (),
    input_file: str | None = None,
    input_base64: str | None = None,
    use_stdin: bool = False,
    read0: bool = False,
    dry_run: bool = False,
    allow_walker: bool = False,
    max_bytes: int = DEFAULT_MAX_BYTES,
    max_items: int = DEFAULT_MAX_ITEMS,
) -> InputSource:
    """Resolve exactly one input source and preserve its record delimiter."""

    if not 1 <= max_bytes <= HARD_MAX_BYTES:
        raise ValidationError(
            "input_limit_invalid", f"max input bytes must be between 1 and {HARD_MAX_BYTES}"
        )
    if not 1 <= max_items <= HARD_MAX_ITEMS:
        raise ValidationError(
            "input_limit_invalid", f"max input items must be between 1 and {HARD_MAX_ITEMS}"
        )
    item_list = list(items)
    source_count = (
        int(bool(item_list))
        + int(input_file is not None)
        + int(input_base64 is not None)
        + int(use_stdin)
    )
    # An explicit walker grant selects the backend walker even when the CLI is
    # launched from a non-TTY automation harness. Callers that intend to pipe
    # data alongside that grant must select it explicitly with --stdin.
    implicit_stdin = source_count == 0 and not allow_walker and not sys.stdin.isatty()
    if implicit_stdin:
        use_stdin = True
        source_count = 1
    if source_count > 1:
        raise ValidationError(
            "input_source_conflict",
            "Choose exactly one of --item, --input-file, --input-base64, or --stdin",
        )
    separator = b"\0" if read0 else b"\n"
    if item_list:
        if any("\x00" in item for item in item_list):
            raise ValidationError("input_item_invalid", "Items cannot contain NUL bytes")
        if not read0 and any("\n" in item or "\r" in item for item in item_list):
            raise ValidationError(
                "input_item_invalid",
                "Items with embedded newlines require --option read0 and an input file/stdin",
            )
        data = separator.join(item.encode("utf-8") for item in item_list) + separator
        count = _check_limits(data, separator, max_bytes, max_items)
        return InputSource(
            "items",
            {
                "kind": "items",
                "record_separator": "nul" if read0 else "newline",
                "item_count": count,
                "byte_count": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            },
            data,
        )
    if input_file is not None:
        path = Path(input_file).expanduser().resolve(strict=False)
        if not path.is_file():
            raise ValidationError("input_file_invalid", f"Input file does not exist: {path}")
        size = path.stat().st_size
        if size > max_bytes:
            raise ValidationError(
                "input_too_large", f"Input file is {size} bytes; limit is {max_bytes}"
            )
        if dry_run:
            return InputSource(
                "file",
                {
                    "kind": "file",
                    "path": str(path),
                    "record_separator": "nul" if read0 else "newline",
                    "byte_count": size,
                    "content_read": False,
                },
                None,
            )
        with path.open("rb") as handle:
            data = _bounded_read(handle, max_bytes)
        count = _check_limits(data, separator, max_bytes, max_items)
        return InputSource(
            "file",
            {
                "kind": "file",
                "path": str(path),
                "record_separator": "nul" if read0 else "newline",
                "item_count": count,
                "byte_count": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "content_read": True,
            },
            data,
        )
    if input_base64 is not None:
        try:
            data = base64.b64decode(input_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValidationError("input_base64_invalid", "Input is not canonical base64") from exc
        if base64.b64encode(data).decode("ascii") != input_base64:
            raise ValidationError("input_base64_invalid", "Input is not canonical base64")
        count = _check_limits(data, separator, max_bytes, max_items)
        return InputSource(
            "base64",
            {
                "kind": "base64",
                "record_separator": "nul" if read0 else "newline",
                "item_count": count,
                "byte_count": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            },
            data,
        )
    if use_stdin:
        if dry_run:
            return InputSource(
                "stdin",
                {
                    "kind": "stdin",
                    "record_separator": "nul" if read0 else "newline",
                    "content_read": False,
                    "max_bytes": max_bytes,
                    "max_items": max_items,
                },
                None,
            )
        data = _bounded_read(sys.stdin.buffer, max_bytes)
        count = _check_limits(data, separator, max_bytes, max_items)
        return InputSource(
            "stdin",
            {
                "kind": "stdin",
                "record_separator": "nul" if read0 else "newline",
                "item_count": count,
                "byte_count": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "content_read": True,
            },
            data,
        )
    if allow_walker:
        return InputSource(
            "walker",
            {"kind": "backend-walker", "content_read": False, "record_separator": "newline"},
            None,
        )
    raise PolicyError(
        "implicit_walker_denied",
        "No input source was provided; implicit directory traversal is denied. "
        "Use --stdin, --input-file, --item, or --allow-walker with --option walker-root=PATH",
    )
