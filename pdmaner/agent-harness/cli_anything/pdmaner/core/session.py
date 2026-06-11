"""Session and undo/redo management (in-memory)."""

import json
import copy
import os


class Session:
    """Stateful session wrapping a PDManer project."""

    def __init__(self):
        self.data = None
        self._history = []
        self._history_index = -1
        self._max_history = 100

    def load(self, path):
        """Load a project file into the session."""
        from .project import open_project
        self.data = open_project(path)
        self._snapshot()

    def create(self, name, describe="", path=None):
        """Create a new project in the session."""
        from .project import create_project
        self.data = create_project(name, describe, path)
        self._snapshot()

    def _snapshot(self):
        """Save undo snapshot."""
        snap = copy.deepcopy(self.data)
        # Truncate future if we're not at tip
        self._history = self._history[:self._history_index + 1]
        self._history.append(snap)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
        self._history_index = len(self._history) - 1

    def undo(self):
        """Undo last change."""
        if self._history_index > 0:
            self._history_index -= 1
            self.data = copy.deepcopy(self._history[self._history_index])
            return True
        return False

    def redo(self):
        """Redo last undone change."""
        if self._history_index < len(self._history) - 1:
            self._history_index += 1
            self.data = copy.deepcopy(self._history[self._history_index])
            return True
        return False

    def mark_changed(self):
        """Call after any mutation to record a snapshot."""
        self._snapshot()

    def save(self, path=None):
        """Save the current project."""
        from .project import save_project
        return save_project(self.data, path)

    def status(self):
        """Return session status."""
        from .project import get_project_info
        info = get_project_info(self.data, as_dict=True)
        info["canUndo"] = self._history_index > 0
        info["canRedo"] = self._history_index < len(self._history) - 1
        info["historySize"] = len(self._history)
        info["modified"] = self.data.get("_modified", False)
        info["path"] = self.data.get("_path", "")
        return info

    def close(self):
        """Close the session."""
        self.data = None
        self._history = []
        self._history_index = -1


# Global session singleton
_session = Session()


def get_session():
    return _session
