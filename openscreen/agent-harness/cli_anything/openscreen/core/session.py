"""Stateful session management for the Openscreen CLI.

A session tracks the currently open project, undo history, and working state.
Sessions persist to disk as JSON so they survive process restarts.

Openscreen projects are JSON files (.openscreen) containing all editor state:
zoom regions, speed regions, trim regions, annotations, crop, wallpaper, etc.
"""

import json
import copy
import os
import time
from pathlib import Path
from typing import Optional


def _locked_save_json(path, data, **dump_kwargs) -> None:
    """Atomically write JSON with exclusive file locking."""
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
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)


SESSION_DIR = Path.home() / ".openscreen-cli" / "sessions"
MAX_UNDO_DEPTH = 50


class Session:
    """Represents a stateful CLI editing session."""

    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id or f"session_{int(time.time())}"
        self.project_path: Optional[str] = None
        self.data: Optional[dict] = None  # The full project JSON
        self._undo_stack: list[str] = []  # Serialized JSON snapshots
        self._redo_stack: list[str] = []
        self._modified = False
        self._metadata: dict = {}

    @property
    def is_open(self) -> bool:
        return self.data is not None

    @property
    def is_modified(self) -> bool:
        return self._modified

    @property
    def editor(self) -> dict:
        """Get the editor state dict. Raises if no project open."""
        if self.data is None:
            raise RuntimeError("No project is open")
        return self.data.get("editor", {})

    def _snapshot(self) -> str:
        """Capture current state for undo."""
        if self.data is None:
            return ""
        return json.dumps(self.data)

    def _push_undo(self) -> None:
        """Save current state to undo stack before a mutation."""
        snap = self._snapshot()
        if snap:
            self._undo_stack.append(snap)
            if len(self._undo_stack) > MAX_UNDO_DEPTH:
                self._undo_stack.pop(0)
            self._redo_stack.clear()

    def checkpoint(self) -> None:
        """Create a checkpoint before performing a mutation.
        Call this before any operation that changes the project.
        """
        self._push_undo()
        self._modified = True

    def undo(self) -> bool:
        """Undo the last operation. Returns True if successful."""
        if not self._undo_stack:
            return False
        self._redo_stack.append(self._snapshot())
        prev = self._undo_stack.pop()
        self.data = json.loads(prev)
        self._modified = bool(self._undo_stack)
        return True

    def redo(self) -> bool:
        """Redo the last undone operation. Returns True if successful."""
        if not self._redo_stack:
            return False
        self._undo_stack.append(self._snapshot())
        nxt = self._redo_stack.pop()
        self.data = json.loads(nxt)
        self._modified = True
        return True

    def new_project(self, video_path: Optional[str] = None) -> None:
        """Create a new blank project."""
        self.data = {
            "version": 2,
            "editor": {
                "wallpaper": "gradient_dark",
                "shadowIntensity": 0,
                "showBlur": False,
                "motionBlurAmount": 0,
                "borderRadius": 12,
                "padding": 50,
                "cropRegion": {"x": 0, "y": 0, "width": 1, "height": 1},
                "zoomRegions": [],
                "trimRegions": [],
                "speedRegions": [],
                "annotationRegions": [],
                "aspectRatio": "16:9",
                "webcamLayoutPreset": "picture-in-picture",
                "webcamMaskShape": "rectangle",
                "webcamPosition": None,
                "exportQuality": "good",
                "exportFormat": "mp4",
                "gifFrameRate": 15,
                "gifLoop": True,
                "gifSizePreset": "medium",
            },
        }
        if video_path:
            self.data["media"] = {
                "screenVideoPath": os.path.abspath(video_path),
            }
        self.project_path = None
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._modified = False

    def open_project(self, path: str) -> None:
        """Open an existing .openscreen project file."""
        path = os.path.abspath(path)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Project file not found: {path}")

        with open(path) as f:
            data = json.load(f)

        if not isinstance(data, dict) or "editor" not in data:
            raise ValueError(f"Invalid Openscreen project file: {path}")

        self.data = data
        self.project_path = path
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._modified = False

    def save_project(self, path: Optional[str] = None) -> str:
        """Save the project. Returns the path saved to."""
        if self.data is None:
            raise RuntimeError("No project is open")
        save_path = path or self.project_path
        if not save_path:
            raise RuntimeError("No save path specified and project has no path")
        save_path = os.path.abspath(save_path)
        _locked_save_json(save_path, self.data, indent=2, sort_keys=False)
        self.project_path = save_path
        self._modified = False
        return save_path

    def save_session_state(self) -> str:
        """Persist session metadata to disk."""
        SESSION_DIR.mkdir(parents=True, exist_ok=True)
        state = {
            "session_id": self.session_id,
            "project_path": self.project_path,
            "modified": self._modified,
            "undo_depth": len(self._undo_stack),
            "redo_depth": len(self._redo_stack),
            "metadata": self._metadata,
            "timestamp": time.time(),
        }
        path = SESSION_DIR / f"{self.session_id}.json"
        _locked_save_json(path, state, indent=2, sort_keys=True)
        return str(path)

    @classmethod
    def load_session_state(cls, session_id: str) -> Optional[dict]:
        """Load session metadata from disk."""
        path = SESSION_DIR / f"{session_id}.json"
        if not path.is_file():
            return None
        with open(path) as f:
            return json.load(f)

    @classmethod
    def list_sessions(cls) -> list[dict]:
        """List all saved sessions."""
        SESSION_DIR.mkdir(parents=True, exist_ok=True)
        sessions = []
        for p in SESSION_DIR.glob("*.json"):
            try:
                with open(p) as f:
                    sessions.append(json.load(f))
            except (json.JSONDecodeError, OSError):
                continue
        sessions.sort(key=lambda s: s.get("timestamp", 0), reverse=True)
        return sessions

    def status(self) -> dict:
        """Get current session status."""
        result = {
            "session_id": self.session_id,
            "project_open": self.is_open,
            "project_path": self.project_path,
            "modified": self._modified,
            "undo_available": len(self._undo_stack),
            "redo_available": len(self._redo_stack),
        }
        if self.is_open:
            editor = self.editor
            result["zoom_region_count"] = len(editor.get("zoomRegions", []))
            result["speed_region_count"] = len(editor.get("speedRegions", []))
            result["trim_region_count"] = len(editor.get("trimRegions", []))
            result["annotation_count"] = len(editor.get("annotationRegions", []))
            result["aspect_ratio"] = editor.get("aspectRatio", "16:9")
            result["background"] = editor.get("wallpaper", "gradient_dark")
            result["padding"] = editor.get("padding", 50)
        return result
