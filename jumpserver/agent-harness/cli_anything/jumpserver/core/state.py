"""
State management for JumpServer CLI.

Tracks CLI operational state across commands, including current org,
selected assets, filters, and pagination.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


STATE_FILE = Path.home() / ".jumpserver-cli" / "state.json"


@dataclass
class CLIState:
    """Ephemeral CLI operational state."""

    current_org_id: str = ""
    current_org_name: str = ""
    selected_asset_ids: list[str] = field(default_factory=list)
    selected_node_ids: list[str] = field(default_factory=list)
    last_filters: dict[str, Any] = field(default_factory=dict)
    pagination: dict[str, int] = field(default_factory=lambda: {"limit": 20, "offset": 0})
    dry_run: bool = False

    def save(self) -> None:
        """Persist state to disk."""
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(self.__dict__, indent=2))

    @classmethod
    def load(cls) -> "CLIState":
        """Load state from disk."""
        if STATE_FILE.exists():
            try:
                data = json.loads(STATE_FILE.read_text())
                return cls(**data)
            except (json.JSONDecodeError, TypeError):
                pass
        return cls()

    def clear_selection(self) -> None:
        """Clear current asset/node selection."""
        self.selected_asset_ids.clear()
        self.selected_node_ids.clear()

    def set_filters(self, **kwargs) -> None:
        """Set search filters."""
        self.last_filters.update(kwargs)

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__


# Global state instance (session-scoped)
_state: CLIState | None = None


def get_state() -> CLIState:
    global _state
    if _state is None:
        _state = CLIState.load()
    return _state


def reset_state() -> None:
    global _state
    _state = CLIState()
    if STATE_FILE.exists():
        STATE_FILE.unlink()
