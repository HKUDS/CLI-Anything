"""Session persistence helpers for NotebookLM CLI context."""

from __future__ import annotations

import json
from pathlib import Path


class Session:
    """Persist the active notebook for REPL and one-shot commands."""

    def __init__(self, session_file: str | Path | None = None):
        if session_file is None:
            session_file = Path.home() / ".cli-anything-notebooklm" / "session.json"
        self.session_file = Path(session_file)
        self.session_file.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def _load(self) -> dict:
        if not self.session_file.exists():
            return {"active_notebook": None}
        try:
            return json.loads(self.session_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"active_notebook": None}

    def _save(self):
        self.session_file.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )

    def get_active_notebook(self) -> str | None:
        return self._data.get("active_notebook")

    def set_active_notebook(self, notebook_id: str):
        self._data["active_notebook"] = notebook_id
        self._save()

    def clear_active_notebook(self):
        self._data["active_notebook"] = None
        self._save()
