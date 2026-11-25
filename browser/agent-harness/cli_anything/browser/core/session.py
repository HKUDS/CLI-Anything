"""Session management for browser automation.

Maintains page state across CLI commands:
- Current URL
- Current working directory (in accessibility tree)
- Navigation history for back/forward
- Daemon mode status
"""

import threading
from typing import TYPE_CHECKING, Callable, Optional
from dataclasses import dataclass, field

if TYPE_CHECKING:
    from cli_anything.browser.utils.mcp_connection import MCPConnection

@dataclass
class Session:
    """Browser automation session state.

    The session tracks the current browser state including:
    - current_url: The URL of the currently loaded page
    - working_dir: The current path in the accessibility tree (filesystem view)
    - history: Stack of URLs for back navigation
    - forward_stack: Stack of URLs for forward navigation
    - daemon_mode: Whether persistent daemon connection is active
    - domshell_lane_id: The DOMShell 2.x lane (Chrome tab-group) the harness
      has been pinned to. ``None`` until the first ``_call_execute`` reply
      arrives carrying a ``[lane: <id>]`` marker; thereafter passed as
      ``group_id`` on every subsequent call so browser state (current tab,
      cwd, focus) persists across REPL commands in non-daemon mode.
    """

    current_url: str = ""
    working_dir: str = "/"
    history: list[str] = field(default_factory=list)
    forward_stack: list[str] = field(default_factory=list)
    daemon_mode: bool = False
    domshell_lane_id: Optional[str] = None
    _connection: Optional["MCPConnection"] = field(
        default=None, init=False, repr=False, compare=False,
    )
    _connection_lock: threading.Lock = field(
        default_factory=threading.Lock, init=False, repr=False, compare=False,
    )
    _connection_users: int = field(default=0, init=False, repr=False, compare=False)
    _closed: bool = field(default=False, init=False, repr=False, compare=False)

    def _get_connection(self, factory: Callable[[], "MCPConnection"]) -> "MCPConnection":
        with self._connection_lock:
            if self._closed:
                raise RuntimeError("Browser session is closed")
            if self._connection is None:
                self._connection = factory()
                self._connection_users = 0
            self._connection_users += 1
            return self._connection

    def _release_connection(
        self, connection: "MCPConnection", *, cancelled: bool = False, failed: bool = False,
    ) -> None:
        with self._connection_lock:
            if self._connection is not connection:
                return
            self._connection_users -= 1
            if failed or (cancelled and self._connection_users == 0 and connection.starting):
                self._connection = None
                connection.close()

    def close(self) -> None:
        """Stop this session's proxy and leave its browser tabs open."""
        with self._connection_lock:
            self._closed = True
            connection, self._connection = self._connection, None
            if connection is not None:
                connection.close()

    def __enter__(self) -> "Session":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

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
        return next_url

    def set_working_dir(self, path: str) -> None:
        """Set the current working directory in the accessibility tree.

        Args:
            path: New path (e.g., "/main/div[0]")
        """
        self.working_dir = path

    def enable_daemon(self) -> None:
        """Enable daemon mode for persistent MCP connection."""
        self.daemon_mode = True

    def disable_daemon(self) -> None:
        """Disable daemon mode."""
        self.daemon_mode = False

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
            "domshell_lane_id": self.domshell_lane_id,
        }
