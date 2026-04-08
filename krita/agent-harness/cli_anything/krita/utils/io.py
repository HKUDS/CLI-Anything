"""Shared I/O utilities for the Krita CLI harness."""

import json
import os
from typing import Any


def locked_save_json(path: str, data: Any, **dump_kwargs: Any) -> None:
    """Atomically write JSON with exclusive file locking.

    Uses fcntl on Unix; silently falls back to unlocked write on Windows
    where fcntl is unavailable.
    """
    path = str(path)
    try:
        f = open(path, "r+")
    except FileNotFoundError:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        f = open(path, "w")
    with f:
        _locked = False
        try:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            _locked = True
        except (ImportError, OSError):
            pass
        try:
            f.seek(0)
            f.truncate()
            json.dump(data, f, **dump_kwargs)
            f.flush()
        finally:
            if _locked:
                import fcntl  # noqa: F811
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
