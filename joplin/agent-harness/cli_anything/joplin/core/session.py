from __future__ import annotations

import contextlib
import copy
import json
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

from cli_anything.joplin.core import project as project_mod

# ---------------------------------------------------------------------------
# Cross-platform exclusive file locking
# ---------------------------------------------------------------------------
# We want *real* mutual exclusion, not just a token file presence check.
# On POSIX we use fcntl.flock(LOCK_EX); on Windows msvcrt.locking.
# Both block until the lock is free, giving us a simple, reliable protocol:
#   1. open/create the .lock file
#   2. acquire an exclusive lock (blocks if another process holds it)
#   3. write data atomically via tmp → os.replace
#   4. release the lock

if sys.platform == "win32":
    import msvcrt as _msvcrt

    @contextlib.contextmanager
    def _exclusive_lock(fd: int):
        """Acquire an exclusive lock on the open file descriptor *fd*."""
        # msvcrt.locking works on byte ranges; we lock the first byte.
        # Retry loop: locking raises OSError(EDEADLK) if the lock is busy
        # (unlike fcntl which blocks).  We do an exponential-back-off retry
        # so that concurrent agents don't race on the first try.
        delay = 0.05
        while True:
            try:
                _msvcrt.locking(fd, _msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                if delay > 10:
                    raise RuntimeError(
                        "Could not acquire project lock after retries (Windows)"
                    )
                time.sleep(delay)
                delay = min(delay * 2, 2.0)
        try:
            yield
        finally:
            try:
                os.lseek(fd, 0, os.SEEK_SET)
                _msvcrt.locking(fd, _msvcrt.LK_UNLCK, 1)
            except OSError:
                pass  # best-effort unlock; fd will be closed immediately after

else:
    import fcntl as _fcntl

    @contextlib.contextmanager
    def _exclusive_lock(fd: int):
        """Acquire an exclusive lock on the open file descriptor *fd*."""
        _fcntl.flock(fd, _fcntl.LOCK_EX)  # blocks until free
        try:
            yield
        finally:
            _fcntl.flock(fd, _fcntl.LOCK_UN)


@dataclass
class Session:
    project: Optional[dict] = None
    project_path: Optional[str] = None
    _modified: bool = False
    _undo_stack: list[dict] = field(default_factory=list)
    _redo_stack: list[dict] = field(default_factory=list)

    def has_project(self) -> bool:
        return self.project is not None

    def set_project(self, project: dict, path: Optional[str] = None) -> None:
        self.project = project
        self.project_path = path
        self._modified = False
        self._undo_stack.clear()
        self._redo_stack.clear()

    def get_project(self) -> dict:
        if not self.project:
            raise RuntimeError("No project loaded")
        return self.project

    def snapshot(self, reason: str) -> None:
        if not self.project:
            raise RuntimeError("No project loaded")
        self._undo_stack.append(copy.deepcopy(self.project))
        self._redo_stack.clear()
        self._modified = True
        project_mod.add_history(self.project, "snapshot", {"reason": reason})

    def mark_dirty(self) -> None:
        """Mark the loaded project as modified without creating an undo snapshot.

        Used by commands that should auto-save (e.g. sync, export) but should
        not contribute to undo/redo depth.
        """
        if not self.project:
            raise RuntimeError("No project loaded")
        self._modified = True

    def undo(self) -> dict:
        if not self._undo_stack:
            raise RuntimeError("Nothing to undo")
        if self.project:
            self._redo_stack.append(copy.deepcopy(self.project))
        self.project = self._undo_stack.pop()
        self._modified = True
        return self.project

    def redo(self) -> dict:
        if not self._redo_stack:
            raise RuntimeError("Nothing to redo")
        if self.project:
            self._undo_stack.append(copy.deepcopy(self.project))
        self.project = self._redo_stack.pop()
        self._modified = True
        return self.project

    def status(self) -> dict:
        return {
            "has_project": self.has_project(),
            "project_path": self.project_path,
            "modified": self._modified,
            "undo_depth": len(self._undo_stack),
            "redo_depth": len(self._redo_stack),
        }

    def _locked_save_json(self, path: str, data: dict) -> None:
        # Ensure the parent directory exists before touching the lock or tmp
        # files. `project save nested/sub/file.json` (or any first save to a
        # not-yet-created directory) would otherwise fail with FileNotFoundError
        # at the lock open, before the data write even gets a chance to run.
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)

        lock_path = f"{path}.lock"
        # O_CREAT | O_RDWR: create the lock file if absent; never truncate it
        # so an existing holder's lock byte is not disturbed.
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR)
        try:
            # Acquire a real cross-process exclusive lock before writing.
            # _exclusive_lock blocks (POSIX) or retries with back-off (Windows)
            # until no other process holds the lock.  This prevents two
            # concurrent agent workers from racing on the shared .tmp file.
            with _exclusive_lock(lock_fd):
                tmp = f"{path}.tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                os.replace(tmp, path)
        finally:
            os.close(lock_fd)

    def save_session(self, path: Optional[str] = None) -> str:
        if not self.project:
            raise RuntimeError("No project loaded")
        target = path or self.project_path
        if not target:
            raise RuntimeError("No project path set")
        self.project["updated_at"] = project_mod.utc_now()
        self._locked_save_json(target, self.project)
        self.project_path = target
        self._modified = False
        return target
