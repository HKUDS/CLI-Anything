"""Core data structures for the cli-anything eval framework."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class Status:
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass
class EvalContext:
    output_dir: Path
    artifacts_dir: Path
    work_dir: Path
    task_id: str = ""

    def task_work_dir(self) -> Path:
        path = self.work_dir / self.task_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def task_artifacts_dir(self) -> Path:
        path = self.artifacts_dir / self.task_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def task_artifact_path(self, filename: str) -> Path:
        return self.task_artifacts_dir() / filename


@dataclass
class TaskSpec:
    task_id: str
    name: str
    description: str
    run: Callable[["EvalContext"], Optional[Dict[str, Any]]]
    verify: Optional[Callable[["EvalContext"], Dict[str, Any]]] = None
    precheck: Optional[Callable[["EvalContext"], Optional[str]]] = None
    requires: List[str] = field(default_factory=list)
    prompt: str = ""
