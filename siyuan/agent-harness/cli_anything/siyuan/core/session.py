"""Session state management for the SiYuan CLI REPL."""

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


@dataclass
class SessionState:
    """Mutable session state — represents current notebook/doc context."""
    current_notebook_id: str = ""
    current_notebook_name: str = ""
    current_doc_id: str = ""
    current_doc_path: str = ""
    connected: bool = False
    history: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionState":
        return cls(
            current_notebook_id=data.get("current_notebook_id", ""),
            current_notebook_name=data.get("current_notebook_name", ""),
            current_doc_id=data.get("current_doc_id", ""),
            current_doc_path=data.get("current_doc_path", ""),
            connected=data.get("connected", False),
            history=data.get("history", []),
        )


class SessionManager:
    """Manages session persistence for the REPL."""

    def __init__(self, state_dir: str | None = None):
        if state_dir is None:
            state_dir = str(Path.home() / ".cli-anything-siyuan")
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.session_path = self.state_dir / "session.json"
        self.state = SessionState()
        self._dirty = False

    def load(self) -> SessionState:
        """Load session state from disk."""
        if self.session_path.is_file():
            try:
                data = json.loads(self.session_path.read_text(encoding="utf-8"))
                self.state = SessionState.from_dict(data)
            except (json.JSONDecodeError, KeyError):
                self.state = SessionState()
        return self.state

    def save(self) -> None:
        """Save current session state to disk."""
        self.session_path.write_text(
            json.dumps(self.state.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def update(self, **kwargs: Any) -> None:
        """Update session state fields and mark dirty."""
        for key, value in kwargs.items():
            if hasattr(self.state, key):
                setattr(self.state, key, value)
        self._dirty = True

    def flush(self) -> None:
        """Write to disk if dirty."""
        if self._dirty:
            self.save()
            self._dirty = False
