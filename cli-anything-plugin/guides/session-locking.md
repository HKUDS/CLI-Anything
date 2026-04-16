# Session File Locking

When saving session JSON, use exclusive file locking to prevent concurrent writes from corrupting data.

## The Problem

Never use bare `open("w") + json.dump()` — `open("w")` truncates the file before any lock can be acquired.

## The Solution: `_locked_save_json`

Open with `"r+"`, lock, then truncate inside the lock:

```python
def _locked_save_json(path, data, **dump_kwargs) -> None:
    """Atomically write JSON with exclusive file locking."""
    try:
        f = open(path, "r+")            # no truncation on open
    except FileNotFoundError:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        f = open(path, "w")             # first save — file doesn't exist yet
    with f:
        _locked = False
        try:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            _locked = True
        except (ImportError, OSError):
            pass                        # Windows / unsupported FS — proceed unlocked
        try:
            f.seek(0)
            f.truncate()                # truncate INSIDE the lock
            json.dump(data, f, **dump_kwargs)
            f.flush()
        finally:
            if _locked:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
```

Copy this pattern into `core/session.py` for all session saves.
