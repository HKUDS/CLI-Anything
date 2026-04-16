"""Session state for Mermaid projects."""

from __future__ import annotations

import copy
import json
import os
from dataclasses import dataclass, field


SAMPLE_DIAGRAMS = {
    "flowchart": "flowchart TD\n  A[Start] --> B{Ready?}\n  B -->|Yes| C[Run test]\n  B -->|No| D[Fix input]\n",
    "sequence": "sequenceDiagram\n  participant U as User\n  participant C as CLI\n  U->>C: Run command\n  C-->>U: JSON result\n",
    "er": "erDiagram\n  USER ||--o{ ORDER : places\n  USER {\n    int id\n    string email\n  }\n  ORDER {\n    int id\n    decimal total\n  }\n",
}


def default_state(sample: str = "flowchart", theme: str = "default") -> dict:
    if sample not in SAMPLE_DIAGRAMS:
        raise ValueError(f"Unknown sample: {sample}")
    return {
        "code": SAMPLE_DIAGRAMS[sample],
        "mermaid": json.dumps({"theme": theme}, indent=2),
        "updateDiagram": True,
        "rough": False,
        "panZoom": True,
        "grid": True,
    }


@dataclass
class Session:
    state: dict | None = None
    project_path: str | None = None
    modified: bool = False
    undo_stack: list[dict] = field(default_factory=list)
    redo_stack: list[dict] = field(default_factory=list)

    @property
    def is_open(self) -> bool:
        return self.state is not None

    def checkpoint(self) -> None:
        if self.state is None:
            return
        self.undo_stack.append(copy.deepcopy(self.state))
        self.redo_stack.clear()

    def new_project(self, sample: str = "flowchart", theme: str = "default") -> dict:
        self.state = default_state(sample=sample, theme=theme)
        self.project_path = None
        self.modified = True
        self.undo_stack.clear()
        self.redo_stack.clear()
        return copy.deepcopy(self.state)

    def open_project(self, path: str) -> dict:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Project not found: {path}")
        with open(path, "r", encoding="utf-8") as fh:
            self.state = json.load(fh)
        self.project_path = os.path.abspath(path)
        self.modified = False
        self.undo_stack.clear()
        self.redo_stack.clear()
        return copy.deepcopy(self.state)

    def save_project(self, path: str | None = None) -> str:
        if self.state is None:
            raise RuntimeError("No project is open")
        target = os.path.abspath(path or self.project_path or "diagram.mermaid.json")
        parent = os.path.dirname(target)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(target, "w", encoding="utf-8") as fh:
            json.dump(self.state, fh, indent=2)
        self.project_path = target
        self.modified = False
        return target

    def set_code(self, code: str) -> None:
        if self.state is None:
            raise RuntimeError("No project is open")
        self.checkpoint()
        self.state["code"] = code
        self.state["updateDiagram"] = True
        self.modified = True

    def status(self) -> dict:
        return {
            "project_open": self.is_open,
            "project_path": self.project_path,
            "modified": self.modified,
            "undo_depth": len(self.undo_stack),
            "redo_depth": len(self.redo_stack),
        }

    def undo(self) -> bool:
        if self.state is None or not self.undo_stack:
            return False
        self.redo_stack.append(copy.deepcopy(self.state))
        self.state = self.undo_stack.pop()
        self.modified = True
        return True

    def redo(self) -> bool:
        if self.state is None or not self.redo_stack:
            return False
        self.undo_stack.append(copy.deepcopy(self.state))
        self.state = self.redo_stack.pop()
        self.modified = True
        return True
