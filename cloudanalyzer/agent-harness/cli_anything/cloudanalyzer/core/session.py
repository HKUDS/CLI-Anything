"""Session management with undo support."""

from __future__ import annotations

import copy
from typing import Any

from cli_anything.cloudanalyzer.core.project import (
    load_project,
    record_operation,
    save_project,
)


class Session:
    """Wraps a project file with undo/redo."""

    def __init__(self, project_path: str) -> None:
        self.path = project_path
        self.project = load_project(project_path)
        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []

    def save(self) -> None:
        save_project(self.path, self.project)

    def do(self, operation: str, details: dict[str, Any] | None = None) -> None:
        """Record an operation and push state for undo."""
        self._undo_stack.append(copy.deepcopy(self.project))
        self._redo_stack.clear()
        record_operation(self.project, operation, details)
        self.save()

    def undo(self) -> bool:
        """Undo the last operation. Returns True if successful."""
        if not self._undo_stack:
            return False
        self._redo_stack.append(copy.deepcopy(self.project))
        self.project = self._undo_stack.pop()
        self.save()
        return True

    def redo(self) -> bool:
        """Redo the last undone operation. Returns True if successful."""
        if not self._redo_stack:
            return False
        self._undo_stack.append(copy.deepcopy(self.project))
        self.project = self._redo_stack.pop()
        self.save()
        return True

    @property
    def history(self) -> list[dict]:
        return list(self.project.get("history", []))
