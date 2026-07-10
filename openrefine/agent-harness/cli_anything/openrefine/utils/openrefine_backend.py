from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests


INSTALL_INSTRUCTIONS = """OpenRefine backend is not reachable.

Install OpenRefine 3.10.x or newer from https://openrefine.org/download.html, then start it:
  openrefine -i 127.0.0.1 -p 3333

For source builds, run the documented startup command from the OpenRefine repository.
Set OPENREFINE_URL or pass --base-url if your server uses another host or port.
"""


class OpenRefineError(RuntimeError):
    pass


class OpenRefineBackend:
    def __init__(self, base_url: str = "http://127.0.0.1:3333", timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self._csrf_token: str | None = None

    def ping(self) -> dict[str, Any]:
        response = self._request("GET", "/command/core/get-version", csrf=False)
        try:
            return response.json()
        except ValueError:
            return {"status": "ok", "text": response.text.strip()}

    def wait_until_ready(self, seconds: float = 30.0) -> dict[str, Any]:
        deadline = time.time() + seconds
        last_error: Exception | None = None
        while time.time() < deadline:
            try:
                return self.ping()
            except Exception as exc:  # pragma: no cover - exercised by backend E2E
                last_error = exc
                time.sleep(0.5)
        raise OpenRefineError(f"{INSTALL_INSTRUCTIONS}\nLast error: {last_error}")

    def list_projects(self) -> dict[str, Any]:
        return self._json("GET", "/command/core/get-all-project-metadata", csrf=False)

    def get_project_metadata(self, project_id: str) -> dict[str, Any]:
        return self._json("GET", "/command/core/get-project-metadata", params={"project": project_id}, csrf=False)

    def get_rows(self, project_id: str, start: int = 0, limit: int = 10) -> dict[str, Any]:
        return self._json(
            "GET",
            "/command/core/get-rows",
            params={"project": project_id, "start": start, "limit": limit},
            csrf=False,
        )

    def create_project(self, input_path: str | Path, name: str | None = None, project_format: str | None = None) -> dict[str, Any]:
        path = Path(input_path)
        if not path.exists():
            raise OpenRefineError(f"Input file not found: {path}")
        data = {"project-name": name or path.stem}
        if project_format:
            data["format"] = project_format
        with path.open("rb") as handle:
            files = {"project-file": (path.name, handle)}
            response = self._request("POST", "/command/core/create-project-from-upload", data=data, files=files, csrf=True)
        project_id = _project_id_from_url(response.url)
        if project_id:
            return {"project": project_id, "location": response.url}
        payload = _coerce_json_or_text(response.text)
        if isinstance(payload, dict):
            if payload.get("code") == "error":
                raise OpenRefineError(str(payload.get("message") or payload))
            return payload
        return {"status": "ok", "text": payload}

    def apply_operations(self, project_id: str, operations: list[dict[str, Any]]) -> dict[str, Any]:
        return self._json(
            "POST",
            "/command/core/apply-operations",
            data={"project": project_id, "operations": json.dumps(operations)},
            csrf=True,
        )

    def export_rows(self, project_id: str, output_path: str | Path, export_format: str = "csv") -> Path:
        response = self._request(
            "POST",
            "/command/core/export-rows",
            data={"project": project_id, "format": export_format},
            csrf=True,
        )
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(response.content)
        return target

    def get_history(self, project_id: str) -> dict[str, Any]:
        return self._json("GET", "/command/core/get-history", params={"project": project_id}, csrf=False)

    def undo(self, project_id: str) -> dict[str, Any]:
        entry_id = _latest_history_entry_id(self.get_history(project_id), "past")
        if not entry_id:
            raise OpenRefineError(f"No OpenRefine history entry to undo for project {project_id}")
        return self._json("POST", "/command/core/undo-redo", data={"project": project_id, "undoID": entry_id}, csrf=True)

    def redo(self, project_id: str) -> dict[str, Any]:
        entry_id = _latest_history_entry_id(self.get_history(project_id), "future")
        if not entry_id:
            raise OpenRefineError(f"No OpenRefine history entry to redo for project {project_id}")
        return self._json("POST", "/command/core/undo-redo", data={"project": project_id, "lastDoneID": entry_id}, csrf=True)

    def delete_project(self, project_id: str) -> dict[str, Any]:
        return self._json("POST", "/command/core/delete-project", data={"project": project_id}, csrf=True)

    def get_csrf_token(self) -> str:
        if self._csrf_token:
            return self._csrf_token
        try:
            response = self._request("GET", "/command/core/get-csrf-token", csrf=False)
            payload = _coerce_json_or_text(response.text)
            if isinstance(payload, dict):
                token = payload.get("token") or payload.get("csrfToken")
            else:
                token = str(payload).strip()
            if token:
                self._csrf_token = str(token)
                return self._csrf_token
        except OpenRefineError:
            pass
        self._csrf_token = "none"
        return self._csrf_token

    def _json(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        response = self._request(method, path, **kwargs)
        try:
            payload = response.json()
        except ValueError as exc:
            raise OpenRefineError(f"Expected JSON from {path}, got: {response.text[:200]}") from exc
        if not isinstance(payload, dict):
            raise OpenRefineError(f"Expected JSON object from {path}")
        return payload

    def _request(self, method: str, path: str, csrf: bool = True, **kwargs: Any) -> requests.Response:
        params = dict(kwargs.pop("params", {}) or {})
        data = dict(kwargs.pop("data", {}) or {})
        if csrf and method.upper() in {"POST", "PUT", "DELETE"}:
            params.setdefault("csrf_token", self.get_csrf_token())
        url = f"{self.base_url}{path}"
        try:
            response = self.session.request(method, url, params=params, data=data or None, timeout=self.timeout, **kwargs)
        except requests.RequestException as exc:
            raise OpenRefineError(f"{INSTALL_INSTRUCTIONS}\nRequest failed for {url}: {exc}") from exc
        if response.status_code >= 400:
            raise OpenRefineError(f"OpenRefine HTTP {response.status_code} for {url}: {response.text[:500]}")
        return response


def find_openrefine_executable() -> str | None:
    for name in ("openrefine", "refine", "OpenRefine"):
        path = shutil.which(name)
        if path:
            return path
    return None


def start_openrefine(port: int = 3333, host: str = "127.0.0.1", data_dir: str | Path | None = None) -> subprocess.Popen:
    exe = find_openrefine_executable()
    if not exe:
        raise OpenRefineError(INSTALL_INSTRUCTIONS)
    args = [exe, "-i", host, "-p", str(port)]
    if data_dir:
        args.extend(["-d", str(data_dir)])
    return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _coerce_json_or_text(text: str) -> Any:
    stripped = text.strip()
    if not stripped:
        return ""
    try:
        return json.loads(stripped)
    except ValueError:
        return stripped


def _project_id_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    values = parse_qs(parsed.query).get("project") or parse_qs(parsed.query).get("projectID")
    if values and values[0]:
        return str(values[0])
    return None


def _latest_history_entry_id(history: dict[str, Any], stack_name: str) -> str | None:
    entries = history.get(stack_name) or []
    if not isinstance(entries, list) or not entries:
        return None
    entry = entries[-1] if stack_name == "past" else entries[0]
    if not isinstance(entry, dict):
        return None
    for key in ("id", "historyEntryID", "history_entry_id"):
        value = entry.get(key)
        if value is not None:
            return str(value)
    return None
