"""File-locking I/O utilities for CLI session persistence."""

import json


def locked_save_json(path, data, **dump_kwargs) -> None:
    """Write *data* as JSON to *path* with an exclusive fcntl lock.

    Opens with ``r+`` to avoid truncating the file before the lock is
    acquired; falls back to ``w`` when the file does not yet exist.
    The seek/truncate, write, flush, and unlock all run inside a
    ``try/finally`` so the lock is always released even if the write
    raises.

    On platforms without ``fcntl`` (e.g. Windows) or filesystems that
    do not support advisory locks the write proceeds without locking.
    """
    try:
        f = open(path, "r+")
    except FileNotFoundError:
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
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
