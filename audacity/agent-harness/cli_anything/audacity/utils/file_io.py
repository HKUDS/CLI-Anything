"""Helpers for safe JSON writes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Optional, Union


def safe_write_json(
    path: Union[str, Path],
    data: Any,
    *,
    indent: int = 2,
    default: Optional[Callable] = None,
) -> None:
    """Write JSON to disk with best-effort file locking on Unix.

    On platforms without fcntl (e.g., Windows), it falls back to a normal write.
    """
    path_str = str(path)
    try:
        f = open(path_str, "r+")
    except FileNotFoundError:
        f = open(path_str, "w")

    with f:
        locked = False
        fcntl_mod = None
        try:
            import fcntl as _fcntl
            _fcntl.flock(f.fileno(), _fcntl.LOCK_EX)
            locked = True
            fcntl_mod = _fcntl
        except (ImportError, OSError):
            pass

        try:
            f.seek(0)
            f.truncate()
            if default is None:
                json.dump(data, f, indent=indent)
            else:
                json.dump(data, f, indent=indent, default=default)
        finally:
            if locked and fcntl_mod is not None:
                try:
                    fcntl_mod.flock(f.fileno(), fcntl_mod.LOCK_UN)
                except OSError:
                    pass
