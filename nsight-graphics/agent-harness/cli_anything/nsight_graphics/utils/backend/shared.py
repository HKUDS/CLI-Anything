"""Shared helpers for Nsight Graphics backend internals."""

from __future__ import annotations

import os
import re
import subprocess
from typing import Iterable, Optional, Sequence


def _command_string(args: Sequence[str]) -> str:
    """Render a command for display."""
    if os.name == "nt":
        return subprocess.list2cmdline(list(args))
    return " ".join(args)


def _dedupe(values: Iterable[str]) -> list[str]:
    """Deduplicate while preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = os.path.normcase(os.path.normpath(value))
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(value)
    return result


def _extract_version_from_text(text: str) -> Optional[str]:
    """Extract a version string from CLI output or display text."""
    match = re.search(r"(\d{4}\.\d+(?:\.\d+)?)", text)
    if match:
        return match.group(1)
    return None


def _extract_version_from_path(path: str) -> Optional[str]:
    """Extract a version-like token from an installation path."""
    return _extract_version_from_text(path)


def _version_sort_key(version: Optional[str]) -> tuple[int, ...]:
    """Convert a dotted version string into a sortable tuple."""
    if not version:
        return tuple()
    parts: list[int] = []
    for token in version.split("."):
        try:
            parts.append(int(token))
        except ValueError:
            parts.append(0)
    return tuple(parts)
