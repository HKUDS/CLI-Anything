"""Detached PTY owner for one managed fzf listener."""

from __future__ import annotations

import json
import os
import pty
import select
import signal
import stat
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from cli_anything.fzf.core.validation import ensure_contained, process_start_time


_child: subprocess.Popen[bytes] | None = None
_stopping = False


@contextmanager
def _state_lock(state_dir: Path):
    lock_path = state_dir / ".listener.lock"
    with lock_path.open("a+", encoding="utf-8") as lock:
        try:
            import fcntl

            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        except (ImportError, OSError):
            pass
        yield


def _atomic_json(path: Path, data: dict[str, Any]) -> None:
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _signal_handler(_signum: int, _frame: object) -> None:
    global _stopping
    _stopping = True
    if _child is not None and _child.poll() is None:
        try:
            os.killpg(_child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass


def _cleanup_socket(address: dict[str, Any], state_dir: Path) -> None:
    if address.get("kind") != "unix":
        return
    path = ensure_contained(Path(address["path"]), state_dir)
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return
    if stat.S_ISSOCK(mode):
        path.unlink()


def run(config_path_value: str) -> int:
    global _child
    config_path = Path(config_path_value).resolve(strict=True)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    state_dir = Path(config["state_dir"]).resolve(strict=True)
    ensure_contained(config_path, state_dir)
    state_path = ensure_contained(Path(config["state_path"]), state_dir)
    input_path = ensure_contained(Path(config["input_path"]), state_dir)
    selection_path = ensure_contained(Path(config["selection_path"]), state_dir)
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)
    master_fd, slave_fd = pty.openpty()
    exit_code = 2
    try:
        with input_path.open("rb") as source, selection_path.open("wb") as output:
            _child = subprocess.Popen(
                config["argv"],
                stdin=source,
                stdout=output,
                stderr=slave_fd,
                env=dict(os.environ),
                start_new_session=True,
            )
            os.close(slave_fd)
            slave_fd = -1
            with _state_lock(state_dir):
                state = json.loads(state_path.read_text(encoding="utf-8"))
                state.update(
                    {
                        "status": "running",
                        "backend_pid": _child.pid,
                        "backend_start_time": process_start_time(_child.pid),
                    }
                )
                _atomic_json(state_path, state)
            # Drain the PTY so terminal rendering and previews cannot block.
            while _child.poll() is None:
                ready, _, _ = select.select([master_fd], [], [], 0.1)
                if ready:
                    try:
                        os.read(master_fd, 65_536)
                    except OSError:
                        break
            exit_code = _child.wait()
            if _stopping and exit_code == 0:
                exit_code = 130
    finally:
        if slave_fd >= 0:
            os.close(slave_fd)
        try:
            os.close(master_fd)
        except OSError:
            pass
        if _child is not None and _child.poll() is None:
            try:
                os.killpg(_child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            _child.wait()
        _cleanup_socket(config["address"], state_dir)
        for path in (config_path, input_path):
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        try:
            with _state_lock(state_dir):
                state = json.loads(state_path.read_text(encoding="utf-8"))
                state.update(
                    {
                        "status": "stopped" if _stopping else "exited",
                        "backend_exit_code": exit_code,
                        "last_worker_pid": state.get("worker_pid"),
                        "last_backend_pid": state.get("backend_pid"),
                        "worker_pid": None,
                        "backend_pid": None,
                        "exited_at": time.time(),
                    }
                )
                _atomic_json(state_path, state)
        except (OSError, json.JSONDecodeError):
            pass
    return exit_code


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(2)
    raise SystemExit(run(sys.argv[1]))


if __name__ == "__main__":
    main()
