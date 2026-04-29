"""
Persistent session state for Unreal Insights CLI workflows.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _normalize_path(path: str | None) -> str | None:
    return str(Path(path).expanduser().resolve()) if path else None


def state_dir() -> Path:
    override = os.environ.get("CLI_ANYTHING_UNREALINSIGHTS_STATE_DIR", "").strip()
    base = Path(override).expanduser() if override else Path.home() / ".cli-anything-unrealinsights"
    base.mkdir(parents=True, exist_ok=True)
    return base.resolve()


def _state_file() -> Path:
    return state_dir() / "session.json"


@dataclass
class UnrealInsightsSession:
    trace_path: str | None = None
    insights_exe: str | None = None
    trace_server_exe: str | None = None
    capture_pid: int | None = None
    capture_target_exe: str | None = None
    capture_target_args: list[str] = field(default_factory=list)
    capture_project_path: str | None = None
    capture_engine_root: str | None = None
    capture_trace_path: str | None = None
    capture_channels: str | None = None
    capture_started_at: str | None = None

    @classmethod
    def load(cls) -> "UnrealInsightsSession":
        path = _state_file()
        if not path.is_file():
            return cls()

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls()

        return cls(
            trace_path=data.get("trace_path"),
            insights_exe=data.get("insights_exe"),
            trace_server_exe=data.get("trace_server_exe"),
            capture_pid=data.get("capture_pid"),
            capture_target_exe=data.get("capture_target_exe"),
            capture_target_args=list(data.get("capture_target_args", [])),
            capture_project_path=data.get("capture_project_path"),
            capture_engine_root=data.get("capture_engine_root"),
            capture_trace_path=data.get("capture_trace_path"),
            capture_channels=data.get("capture_channels"),
            capture_started_at=data.get("capture_started_at"),
        )

    def save(self):
        path = _state_file()
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        os.replace(tmp, path)

    def set_trace(self, trace_path: str | None):
        self.trace_path = _normalize_path(trace_path)
        self.save()

    def set_insights_exe(self, path: str | None):
        self.insights_exe = _normalize_path(path)
        self.save()

    def set_trace_server_exe(self, path: str | None):
        self.trace_server_exe = _normalize_path(path)
        self.save()

    def set_capture(
        self,
        *,
        pid: int | None,
        target_exe: str,
        target_args: list[str],
        trace_path: str,
        channels: str,
        project_path: str | None = None,
        engine_root: str | None = None,
    ):
        self.capture_pid = pid
        self.capture_target_exe = _normalize_path(target_exe)
        self.capture_target_args = list(target_args)
        self.capture_trace_path = _normalize_path(trace_path)
        self.capture_channels = channels
        self.capture_project_path = _normalize_path(project_path)
        self.capture_engine_root = _normalize_path(engine_root)
        self.capture_started_at = datetime.now(timezone.utc).isoformat()
        if self.capture_trace_path:
            self.trace_path = self.capture_trace_path
        self.save()

    def clear_capture(self):
        self.capture_pid = None
        self.capture_target_exe = None
        self.capture_target_args = []
        self.capture_project_path = None
        self.capture_engine_root = None
        self.capture_trace_path = None
        self.capture_channels = None
        self.capture_started_at = None
        self.save()

    def trace_info(self) -> dict[str, Any]:
        if self.trace_path is None:
            return {
                "trace_path": None,
                "exists": False,
            }

        path = Path(self.trace_path)
        return {
            "trace_path": str(path),
            "exists": path.is_file(),
            "file_size": path.stat().st_size if path.is_file() else None,
        }

    def capture_info(self) -> dict[str, Any]:
        trace_path = self.capture_trace_path or self.trace_path
        path = Path(trace_path) if trace_path else None
        return {
            "active": self.capture_pid is not None or self.capture_trace_path is not None,
            "pid": self.capture_pid,
            "target_exe": self.capture_target_exe,
            "target_args": list(self.capture_target_args),
            "project_path": self.capture_project_path,
            "engine_root": self.capture_engine_root,
            "trace_path": str(path) if path else None,
            "trace_exists": path.is_file() if path else False,
            "trace_size": path.stat().st_size if path and path.is_file() else None,
            "channels": self.capture_channels,
            "started_at": self.capture_started_at,
        }
