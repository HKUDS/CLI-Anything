"""Stateful session: the open workspace, modification tracking and locked saves."""

import copy
import json
import os
from typing import Optional

from cli_anything.voxtype.core import project as project_mod

MAX_HISTORY = 200


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


class Session:
    """Holds the current workspace. Without a workspace, commands still work
    against voxtype's default config; only undo history is unavailable."""

    def __init__(self):
        self.workspace: Optional[dict] = None
        self.project_path: Optional[str] = None
        self._modified = False
        self.config_override: Optional[str] = None

    # ── workspace lifecycle ────────────────────────────────────────────
    def has_project(self) -> bool:
        return self.workspace is not None

    def set_project(self, ws: dict, path: Optional[str] = None) -> None:
        self.workspace = project_mod.validate_workspace(ws)
        self.project_path = os.path.abspath(path) if path else None
        self._modified = False

    def open(self, path: str) -> dict:
        self.set_project(project_mod.load_workspace(path), path)
        return self.workspace

    def new(self, path: str, name: str, config_path: Optional[str] = None) -> dict:
        self.set_project(project_mod.create_workspace(name, config_path), path)
        self._modified = True
        return self.workspace

    def save_session(self, path: Optional[str] = None) -> str:
        if not self.has_project():
            raise RuntimeError("No workspace open. Use 'project new -o FILE' or --project FILE.")
        target = path or self.project_path
        if not target:
            raise RuntimeError("Workspace has no file path; pass one to save.")
        _locked_save_json(target, self.workspace, indent=2)
        self.project_path = os.path.abspath(target)
        self._modified = False
        return self.project_path

    def mark_modified(self) -> None:
        self._modified = True

    # ── config path resolution ─────────────────────────────────────────
    def config_path(self) -> Optional[str]:
        """--config beats the workspace; None means voxtype's own default."""
        if self.config_override:
            return self.config_override
        if self.workspace and self.workspace.get("config_path"):
            return self.workspace["config_path"]
        return None

    def overrides(self) -> dict:
        return dict(self.workspace.get("overrides", {})) if self.workspace else {}

    # ── undo / redo of config mutations ────────────────────────────────
    def record(self, entry: dict) -> None:
        if not self.has_project():
            return
        hist = self.workspace["history"]
        hist.append(copy.deepcopy(entry))
        if len(hist) > MAX_HISTORY:
            del hist[: len(hist) - MAX_HISTORY]
        self.workspace["redo"] = []
        self._modified = True

    def pop_undo(self) -> dict:
        if not self.has_project() or not self.workspace["history"]:
            raise RuntimeError("Nothing to undo.")
        entry = self.workspace["history"].pop()
        self.workspace["redo"].append(entry)
        self._modified = True
        return entry

    def pop_redo(self) -> dict:
        if not self.has_project() or not self.workspace["redo"]:
            raise RuntimeError("Nothing to redo.")
        entry = self.workspace["redo"].pop()
        self.workspace["history"].append(entry)
        self._modified = True
        return entry

    def log_transcription(self, result: dict) -> None:
        if not self.has_project():
            return
        self.workspace["transcriptions"].append(copy.deepcopy(result))
        self._modified = True

    def status(self) -> dict:
        info = {
            "has_workspace": self.has_project(),
            "workspace_path": self.project_path,
            "modified": self._modified,
            "config_path": self.config_path(),
        }
        if self.workspace:
            info.update(project_mod.workspace_info(self.workspace, self.project_path))
        return info
