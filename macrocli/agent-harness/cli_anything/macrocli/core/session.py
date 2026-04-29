"""ExecutionSession — tracks macro run history and telemetry.

Persists run records to ~/.macrocli/sessions/ so agents can inspect
what was run, what succeeded, and what the outputs were.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

SESSION_DIR = Path.home() / ".macrocli" / "sessions"
MAX_HISTORY = 200


def _locked_save_json(path: str, data, **dump_kwargs) -> None:
    """Atomically write JSON with exclusive file locking."""
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


class RunRecord:
    """A single macro execution record."""

    def __init__(
        self,
        macro_name: str,
        params: dict,
        success: bool,
        output: dict,
        error: str,
        duration_ms: float,
        backends_used: list[str],
        steps_run: int,
        timestamp: Optional[float] = None,
    ):
        self.macro_name = macro_name
        self.params = params
        self.success = success
        self.output = output
        self.error = error
        self.duration_ms = duration_ms
        self.backends_used = backends_used
        self.steps_run = steps_run
        self.timestamp = timestamp or time.time()

    def to_dict(self) -> dict:
        return {
            "macro_name": self.macro_name,
            "params": self.params,
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "backends_used": self.backends_used,
            "steps_run": self.steps_run,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RunRecord":
        return cls(
            macro_name=d.get("macro_name", ""),
            params=d.get("params", {}),
            success=d.get("success", False),
            output=d.get("output", {}),
            error=d.get("error", ""),
            duration_ms=d.get("duration_ms", 0),
            backends_used=d.get("backends_used", []),
            steps_run=d.get("steps_run", 0),
            timestamp=d.get("timestamp"),
        )


class ExecutionSession:
    """Tracks macro run history for the current session."""

    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id or f"session_{int(time.time())}"
        self._history: list[RunRecord] = []

    # ── Record management ─────────────────────────────────────────────

    def record(self, run: RunRecord) -> None:
        """Add a run record to history."""
        self._history.append(run)
        if len(self._history) > MAX_HISTORY:
            self._history = self._history[-MAX_HISTORY:]

    def last(self) -> Optional[RunRecord]:
        """Return the most recent run record."""
        return self._history[-1] if self._history else None

    def history(self, limit: int = 20) -> list[RunRecord]:
        """Return recent run records, newest first."""
        return list(reversed(self._history[-limit:]))

    def stats(self) -> dict:
        """Return aggregate statistics for this session."""
        total = len(self._history)
        if total == 0:
            return {"total": 0, "success_rate": 0.0, "avg_duration_ms": 0.0}
        successes = sum(1 for r in self._history if r.success)
        avg_dur = sum(r.duration_ms for r in self._history) / total
        return {
            "total": total,
            "success": successes,
            "failure": total - successes,
            "success_rate": successes / total,
            "avg_duration_ms": avg_dur,
        }

    def status(self) -> dict:
        return {
            "session_id": self.session_id,
            "runs": len(self._history),
            **self.stats(),
        }

    # ── Persistence ───────────────────────────────────────────────────

    def save(self) -> str:
        """Persist session to disk. Returns the file path."""
        SESSION_DIR.mkdir(parents=True, exist_ok=True)
        path = str(SESSION_DIR / f"{self.session_id}.json")
        data = {
            "session_id": self.session_id,
            "timestamp": time.time(),
            "history": [r.to_dict() for r in self._history],
        }
        _locked_save_json(path, data, indent=2, sort_keys=True)
        return path

    @classmethod
    def load(cls, session_id: str) -> Optional["ExecutionSession"]:
        """Load a session from disk."""
        path = SESSION_DIR / f"{session_id}.json"
        if not path.is_file():
            return None
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        session = cls(session_id=data.get("session_id", session_id))
        session._history = [RunRecord.from_dict(r) for r in data.get("history", [])]
        return session

    @classmethod
    def list_sessions(cls) -> list[dict]:
        """List all saved sessions (metadata only)."""
        SESSION_DIR.mkdir(parents=True, exist_ok=True)
        sessions = []
        for p in SESSION_DIR.glob("*.json"):
            try:
                with open(p, encoding="utf-8") as f:
                    d = json.load(f)
                sessions.append({
                    "session_id": d.get("session_id"),
                    "timestamp": d.get("timestamp", 0),
                    "runs": len(d.get("history", [])),
                })
            except Exception:
                continue
        sessions.sort(key=lambda s: s.get("timestamp", 0), reverse=True)
        return sessions
