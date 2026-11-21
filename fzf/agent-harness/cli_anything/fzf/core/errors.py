"""Typed errors and stable exit codes for the fzf harness."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class HarnessError(Exception):
    """An expected error suitable for a deterministic JSON envelope."""

    code: str
    message: str
    exit_code: int = 2
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.message

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            payload["details"] = self.details
        return payload


class BackendError(HarnessError):
    """A backend discovery, compatibility, or execution error."""


class PolicyError(HarnessError):
    """A default-deny policy refusal."""


class ValidationError(HarnessError):
    """Invalid declarative input."""
