from __future__ import annotations

from dataclasses import dataclass
from typing import Any

JsonDict = dict[str, Any]


@dataclass(slots=True)
class PlannedAction:
    action: str
    payload: JsonDict
    reason: str

