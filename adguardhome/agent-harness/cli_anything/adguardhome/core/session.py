"""Session state management for cli-anything-adguardhome."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Session:
    """In-memory session state for the REPL."""
    host: str = "localhost"
    port: int = 3000
    username: str = ""
    password: str = ""
    history: list[str] = field(default_factory=list)

    def add_history(self, command: str) -> None:
        self.history.append(command)

    def to_dict(self) -> dict[str, Any]:
        return {
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "connected": True,
        }
