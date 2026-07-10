from __future__ import annotations

from pathlib import Path
from typing import Any

from .operations import load_operations
from .session import SessionState, SessionStore
from ..utils.openrefine_backend import OpenRefineBackend


class OpenRefineService:
    def __init__(self, backend: OpenRefineBackend, store: SessionStore):
        self.backend = backend
        self.store = store

    def status(self) -> dict[str, Any]:
        state = self.store.load()
        ping = self.backend.ping()
        return {"backend": ping, "session": state.to_dict()}

    def list_projects(self) -> dict[str, Any]:
        return self.backend.list_projects()

    def open_project(self, project_id: str, name: str | None = None) -> dict[str, Any]:
        metadata = self.backend.get_project_metadata(project_id)
        state = self.store.load()
        state.base_url = self._backend_base_url()
        state.project_id = project_id
        state.project_name = name or metadata.get("name") or metadata.get("projectName") or project_id
        self.store.record(state, "open", {"project_id": project_id, "project_name": state.project_name})
        self.store.save(state)
        return {"project_id": project_id, "project_name": state.project_name, "metadata": metadata}

    def import_file(self, path: str | Path, name: str | None = None, project_format: str | None = None) -> dict[str, Any]:
        created = self.backend.create_project(path, name=name, project_format=project_format)
        project_id = _extract_project_id(created)
        state = self.store.load()
        state.base_url = self._backend_base_url()
        state.project_id = project_id
        state.project_name = name or Path(path).stem
        self.store.record(state, "import", {"path": str(path), "project_id": project_id, "project_name": state.project_name})
        self.store.save(state)
        return {"project_id": project_id, "project_name": state.project_name, "response": created}

    def apply_operations_file(self, operations_path: str | Path, project_id: str | None = None) -> dict[str, Any]:
        operations = load_operations(operations_path)
        state = self.store.load()
        target_id = project_id or state.project_id
        if not target_id:
            raise ValueError("No project selected. Pass --project-id or import/open a project first.")
        response = self.backend.apply_operations(target_id, operations)
        state.base_url = self._backend_base_url()
        self.store.record(state, "apply-operations", {"project_id": target_id, "operations_path": str(operations_path), "count": len(operations)})
        state.project_id = target_id
        self.store.save(state)
        return {"project_id": target_id, "operation_count": len(operations), "response": response}

    def export_rows(self, output_path: str | Path, export_format: str = "csv", project_id: str | None = None) -> dict[str, Any]:
        state = self.store.load()
        target_id = project_id or state.project_id
        if not target_id:
            raise ValueError("No project selected. Pass --project-id or import/open a project first.")
        output = self.backend.export_rows(target_id, output_path, export_format)
        state.base_url = self._backend_base_url()
        state.project_id = target_id
        state.last_export = str(output)
        self.store.record(state, "export", {"project_id": target_id, "output": str(output), "format": export_format})
        self.store.save(state)
        return {"project_id": target_id, "output": str(output), "format": export_format, "bytes": output.stat().st_size}

    def rows(self, start: int = 0, limit: int = 10, project_id: str | None = None) -> dict[str, Any]:
        state = self.store.load()
        target_id = project_id or state.project_id
        if not target_id:
            raise ValueError("No project selected. Pass --project-id or import/open a project first.")
        return self.backend.get_rows(target_id, start=start, limit=limit)

    def undo(self, project_id: str | None = None) -> dict[str, Any]:
        state = self.store.load()
        target_id = project_id or state.project_id
        if not target_id:
            local = self.store.undo(state)
            self.store.save(state)
            return {"mode": "session", "undone": local}
        response = self.backend.undo(target_id)
        state.base_url = self._backend_base_url()
        local = self.store.undo(state) if state.history else None
        self.store.save(state)
        return {"mode": "backend", "project_id": target_id, "response": response, "local": local}

    def redo(self, project_id: str | None = None) -> dict[str, Any]:
        state = self.store.load()
        target_id = project_id or state.project_id
        if not target_id:
            local = self.store.redo(state)
            self.store.save(state)
            return {"mode": "session", "redone": local}
        response = self.backend.redo(target_id)
        state.base_url = self._backend_base_url()
        local = self.store.redo(state) if state.future else None
        self.store.save(state)
        return {"mode": "backend", "project_id": target_id, "response": response, "local": local}

    def _backend_base_url(self) -> str:
        return str(getattr(self.backend, "base_url", SessionState().base_url))


def _extract_project_id(payload: dict[str, Any]) -> str:
    for key in ("project", "projectID", "project_id", "id"):
        value = payload.get(key)
        if value:
            return str(value)
    if "Location" in payload:
        return str(payload["Location"]).rstrip("/").split("/")[-1]
    raise ValueError(f"Could not determine project id from OpenRefine response: {payload}")
