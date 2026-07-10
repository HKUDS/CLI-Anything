"""Backend base classes and result types.

All execution backends inherit from Backend and return StepResult.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class StepResult:
    """Result of a single macro step execution."""
    success: bool
    output: dict = field(default_factory=dict)
    error: str = ""
    duration_ms: float = 0.0
    backend_used: str = ""

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "backend_used": self.backend_used,
        }


class BackendContext:
    """Runtime context passed to each backend during step execution."""

    def __init__(
        self,
        params: dict,
        previous_results: Optional[list[StepResult]] = None,
        dry_run: bool = False,
        timeout_ms: int = 30_000,
    ):
        self.params = params
        self.previous_results: list[StepResult] = previous_results or []
        self.dry_run = dry_run
        self.timeout_ms = timeout_ms
        self._start = time.time()

    def elapsed_ms(self) -> float:
        return (time.time() - self._start) * 1000


class Backend(ABC):
    """Abstract base class for all execution backends.

    Concrete backends implement execute() and return a StepResult.
    """

    name: str = "base"
    priority: int = 0

    @abstractmethod
    def execute(
        self,
        step: "MacroStep",  # type: ignore[name-defined]
        params: dict,
        context: BackendContext,
    ) -> StepResult:
        """Execute a macro step.

        Args:
            step: The MacroStep definition being executed.
            params: Fully resolved (substituted) parameters.
            context: Runtime context with previous results and flags.

        Returns:
            StepResult describing success/failure and captured output.
        """

    def is_available(self) -> bool:
        """Return True if this backend can be used in the current environment."""
        return True

    def describe(self) -> dict:
        return {
            "name": self.name,
            "priority": self.priority,
            "available": self.is_available(),
        }
