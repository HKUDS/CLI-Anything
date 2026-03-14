"""Stateful session management for the Shotcut CLI.

A session tracks the currently open project, undo history, and working state.
Sessions persist to disk as JSON so they survive process restarts.
"""

import json
import os
import copy
import time
from pathlib import Path
from typing import Optional
from lxml import etree

from ..utils import mlt_xml


SESSION_DIR = Path.home() / ".shotcut-cli" / "sessions"
MAX_UNDO_DEPTH = 50


class Session:
    """Represents a stateful CLI editing session."""

    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id or f"session_{int(time.time())}"
        self.project_path: Optional[str] = None
        self.root: Optional[etree._Element] = None
        self._undo_stack: list[bytes] = []  # Serialized XML snapshots
        self._redo_stack: list[bytes] = []
        self._modified = False
        self._metadata: dict = {}

    @property
    def is_open(self) -> bool:
        return self.root is not None

    @property
    def is_modified(self) -> bool:
        return self._modified

    def _snapshot(self) -> bytes:
        """Capture current state for undo."""
        if self.root is None:
            return b""
        return etree.tostring(self.root, xml_declaration=True, encoding="utf-8")

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
        # Save current state to redo
        self._redo_stack.append(self._snapshot())
        # Restore previous state
        prev = self._undo_stack.pop()
        self.root = etree.fromstring(prev)
        self._modified = bool(self._undo_stack)
        return True

    def redo(self) -> bool:
        """Redo the last undone operation. Returns True if successful."""
        if not self._redo_stack:
            return False
        self._undo_stack.append(self._snapshot())
        nxt = self._redo_stack.pop()
        self.root = etree.fromstring(nxt)
        self._modified = True
        return True

    def new_project(self, profile: Optional[dict] = None) -> None:
        """Create a new blank project."""
        if profile is None:
            profile = {
                "width": "1920", "height": "1080",
                "frame_rate_num": "30000", "frame_rate_den": "1001",
                "sample_aspect_num": "1", "sample_aspect_den": "1",
                "display_aspect_num": "16", "display_aspect_den": "9",
                "progressive": "1", "colorspace": "709",
            }
        self.root = mlt_xml.create_blank_project(profile)
        self.project_path = None
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._modified = False

    def open_project(self, path: str) -> None:
        """Open an existing MLT project file."""
        path = os.path.abspath(path)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Project file not found: {path}")
        self.root = mlt_xml.parse_mlt(path)
        self.project_path = path
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._modified = False

    def save_project(self, path: Optional[str] = None) -> str:
        """Save the project. Returns the path saved to."""
        if self.root is None:
            raise RuntimeError("No project is open")
        save_path = path or self.project_path
        if not save_path:
            raise RuntimeError("No save path specified and project has no path")
        save_path = os.path.abspath(save_path)
        mlt_xml.write_mlt(self.root, save_path)
        self.project_path = save_path
        self._modified = False
        return save_path

    def get_profile(self) -> dict:
        """Get the project's video profile as a dict."""
        if self.root is None:
            raise RuntimeError("No project is open")
        prof = self.root.find("profile")
        if prof is None:
            return {}
        return dict(prof.attrib)

    def get_main_tractor(self) -> etree._Element:
        """Get the main timeline tractor."""
        if self.root is None:
            raise RuntimeError("No project is open")
        tractor = mlt_xml.get_main_tractor(self.root)
        if tractor is None:
            raise RuntimeError("No main tractor found in project")
        return tractor

    def save_session_state(self) -> str:
        """Persist session metadata to disk (not the project, just session info)."""
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
        with open(path, "w") as f:
            try:
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                json.dump(state, f, indent=2)
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            except (ImportError, OSError):
                json.dump(state, f, indent=2)
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
            profile = self.get_profile()
            result["profile"] = profile
            try:
                tractor = self.get_main_tractor()
                tracks = mlt_xml.get_tractor_tracks(tractor)
                result["track_count"] = len(tracks)
            except RuntimeError:
                result["track_count"] = 0
        return result
