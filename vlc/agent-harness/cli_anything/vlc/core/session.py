"""Stateful session with undo/redo over a job spec.

Every mutation snapshots the previous job so it can be undone. This backs both the
REPL and the scripted ``--project`` workflow.
"""

from __future__ import annotations

import copy
from typing import Callable, Dict, Any, List, Optional

from .project import new_job


class Session:
    """Holds the current job plus undo/redo command stacks."""

    def __init__(self, job: Optional[Dict[str, Any]] = None, project_path=None):
        self.job: Dict[str, Any] = job if job is not None else new_job()
        self.project_path = project_path
        self._undo: List[Dict[str, Any]] = []
        self._redo: List[Dict[str, Any]] = []

    def mutate(self, label: str, mutator: Callable[[Dict[str, Any]], None]) -> None:
        """Apply ``mutator`` to the job in place, recording an undo entry."""
        snapshot = copy.deepcopy(self.job)
        mutator(self.job)
        self._undo.append({"label": label, "job": snapshot})
        self._redo.clear()

    def undo(self) -> Optional[str]:
        """Undo the last mutation. Returns its label or None if nothing to undo."""
        if not self._undo:
            return None
        entry = self._undo.pop()
        self._redo.append({"label": entry["label"], "job": copy.deepcopy(self.job)})
        self.job = entry["job"]
        return entry["label"]

    def redo(self) -> Optional[str]:
        """Redo the last undone mutation. Returns its label or None if nothing to redo."""
        if not self._redo:
            return None
        entry = self._redo.pop()
        self._undo.append({"label": entry["label"], "job": copy.deepcopy(self.job)})
        self.job = entry["job"]
        return entry["label"]

    def can_undo(self) -> bool:
        return bool(self._undo)

    def can_redo(self) -> bool:
        return bool(self._redo)

    def history(self) -> List[str]:
        """Labels of applied mutations, oldest first."""
        return [e["label"] for e in self._undo]
