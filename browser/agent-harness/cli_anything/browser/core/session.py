"""Session management for browser automation.

Maintains page state across CLI commands:
- Current URL
- Current working directory (in accessibility tree)
- Navigation history for back/forward
- Daemon mode status
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Session:
    """Browser automation session state.

    The session tracks the current browser state including:
    - current_url: The URL of the currently loaded page
    - working_dir: The current path in the accessibility tree (filesystem view)
    - history: Stack of URLs for back navigation
    - forward_stack: Stack of URLs for forward navigation
    - daemon_mode: Whether persistent daemon connection is active
    """

    current_url: str = ""
    working_dir: str = "/"
    history: list[str] = field(default_factory=list)
    forward_stack: list[str] = field(default_factory=list)
    daemon_mode: bool = False
    persist_state: bool = False
    state_path: Optional[str] = None

    @classmethod
    def load_persisted(cls, state_path: Optional[str] = None) -> "Session":
        """Load a persisted session snapshot if present.

        The returned session is marked persistent so future mutations are written
        back to disk. If no active daemon snapshot exists, returns a fresh session.
        """
        session = cls(persist_state=True, state_path=state_path)
        try:
            path = session._resolve_state_path()
            if not path.exists():
                return session
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return session

        session.current_url = data.get("current_url", "")
        session.working_dir = data.get("working_dir", "/")
        session.history = list(data.get("history", []))
        session.forward_stack = list(data.get("forward_stack", []))
        session.daemon_mode = bool(data.get("daemon_mode", False))
        return session

    def _resolve_state_path(self) -> Path:
        if self.state_path:
            return Path(self.state_path)
        return Path.home() / ".cli-anything-browser" / "session.json"

    def save_state(self) -> None:
        """Persist the current session snapshot when enabled."""
        if not self.persist_state:
            return
        path = self._resolve_state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "current_url": self.current_url,
            "working_dir": self.working_dir,
            "history": self.history,
            "forward_stack": self.forward_stack,
            "daemon_mode": self.daemon_mode,
        }
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp_path.replace(path)

    def set_url(self, url: str, record_history: bool = True) -> None:
        """Set the current URL and update history.

        Args:
            url: New URL to navigate to
            record_history: Whether to add to history stack
        """
        if record_history and self.current_url:
            self.history.append(self.current_url)
            self.forward_stack.clear()  # Clear forward stack on new navigation
        self.current_url = url
        self.save_state()

    def go_back(self) -> Optional[str]:
        """Navigate back in history.

        Returns:
            Previous URL if available, None otherwise
        """
        if not self.history:
            return None
        previous = self.history.pop()
        self.forward_stack.append(self.current_url)
        self.current_url = previous
        self.save_state()
        return previous

    def go_forward(self) -> Optional[str]:
        """Navigate forward in history.

        Returns:
            Next URL if available, None otherwise
        """
        if not self.forward_stack:
            return None
        next_url = self.forward_stack.pop()
        self.history.append(self.current_url)
        self.current_url = next_url
        self.save_state()
        return next_url

    def set_working_dir(self, path: str) -> None:
        """Set the current working directory in the accessibility tree.

        Args:
            path: New path (e.g., "/main/div[0]")
        """
        self.working_dir = path
        self.save_state()

    def enable_daemon(self) -> None:
        """Enable daemon mode for persistent MCP connection."""
        self.daemon_mode = True
        self.save_state()

    def disable_daemon(self) -> None:
        """Disable daemon mode."""
        self.daemon_mode = False
        self.save_state()

    def status(self) -> dict:
        """Get session status as a dict.

        Returns:
            Dict with current session state
        """
        return {
            "current_url": self.current_url or "(no page loaded)",
            "working_dir": self.working_dir,
            "history_length": len(self.history),
            "forward_stack_length": len(self.forward_stack),
            "daemon_mode": self.daemon_mode,
        }
