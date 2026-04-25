"""Session management for OBS Studio scene collection projects."""

from __future__ import annotations

import copy
import json
import uuid
from pathlib import Path


DEFAULT_TRANSITIONS = [
    {"name": "Cut", "type": "cut", "duration": 0},
    {"name": "Fade", "type": "fade", "duration": 300},
]


def create_project(name: str = "obs_project", output_width: int = 1920, output_height: int = 1080, fps: int = 30) -> dict:
    """Create a new blank OBS project state."""
    return {
        "version": "1.0",
        "name": name,
        "settings": {
            "output_width": output_width,
            "output_height": output_height,
            "fps": fps,
            "video_bitrate": 6000,
            "audio_bitrate": 160,
            "encoder": "x264",
            "preset": "balanced",
        },
        "scenes": [
            {
                "id": 0,
                "name": "Main Scene",
                "sources": [],
            }
        ],
        "transitions": copy.deepcopy(DEFAULT_TRANSITIONS),
        "active_scene": 0,
        "audio_sources": [],
        "streaming": {"service": "", "server": "auto", "key": ""},
        "recording": {"path": "./recordings/", "format": "mkv", "quality": "high"},
        "history": [],
        "project_id": str(uuid.uuid4()),
    }


class Session:
    """Mutable in-memory project session with basic undo/redo."""

    def __init__(self):
        self.state: dict | None = None
        self.project_path: str | None = None
        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []

    @property
    def is_open(self) -> bool:
        return self.state is not None

    @property
    def is_modified(self) -> bool:
        return bool(self._undo_stack)

    def new_project(self, name: str = "obs_project") -> dict:
        self.state = create_project(name)
        self.project_path = None
        self._undo_stack.clear()
        self._redo_stack.clear()
        return self.state

    def open_project(self, path: str) -> dict:
        project_path = Path(path)
        if not project_path.exists():
            raise FileNotFoundError(path)
        self.state = json.loads(project_path.read_text(encoding="utf-8"))
        self.project_path = str(project_path)
        self._undo_stack.clear()
        self._redo_stack.clear()
        return self.state

    def save_project(self, path: str | None = None) -> str:
        if self.state is None:
            raise RuntimeError("No project is open")
        target = path or self.project_path
        if not target:
            raise RuntimeError("No project path provided")
        target_path = Path(target)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(json.dumps(self.state, indent=2), encoding="utf-8")
        self.project_path = str(target_path)
        return self.project_path

    def checkpoint(self) -> None:
        if self.state is None:
            raise RuntimeError("No project is open")
        self._undo_stack.append(copy.deepcopy(self.state))
        self._redo_stack.clear()

    def undo(self) -> bool:
        if not self._undo_stack or self.state is None:
            return False
        self._redo_stack.append(copy.deepcopy(self.state))
        self.state = self._undo_stack.pop()
        return True

    def redo(self) -> bool:
        if not self._redo_stack or self.state is None:
            return False
        self._undo_stack.append(copy.deepcopy(self.state))
        self.state = self._redo_stack.pop()
        return True

    def set_project(self, proj: dict) -> None:
        self.state = proj
        self._undo_stack.clear()
        self._redo_stack.clear()

    def get_project(self) -> dict:
        if self.state is None:
            raise RuntimeError("No project is open")
        return self.state

    def snapshot(self, label: str | None = None) -> None:
        self.checkpoint()

    def save_session(self) -> str:
        if not self.project_path:
            raise ValueError("No save path")
        return self.save_project(self.project_path)

    def status(self) -> dict:
        scene_count = len(self.state["scenes"]) if self.state else 0
        source_count = sum(len(scene["sources"]) for scene in self.state["scenes"]) if self.state else 0
        return {
            "project_open": self.is_open,
            "project_path": self.project_path,
            "modified": self.is_modified,
            "scene_count": scene_count,
            "source_count": source_count,
            "can_undo": bool(self._undo_stack),
            "can_redo": bool(self._redo_stack),
        }
