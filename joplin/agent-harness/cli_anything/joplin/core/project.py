from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Optional


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_project(name: str = "joplin-project", backend_binary: str = "joplin", backend_profile: Optional[str] = None) -> dict:
    now = utc_now()
    return {
        "name": name,
        "created_at": now,
        "updated_at": now,
        "backend": {
            "binary": backend_binary,
            "profile": backend_profile,
        },
        "context": {
            "current_notebook": None,
        },
        "history": [],
    }


def open_project(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_project(project: dict, path: str) -> str:
    project["updated_at"] = utc_now()
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(project, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, path)
    return path


def add_history(project: dict, action: str, payload: Optional[dict] = None) -> None:
    project.setdefault("history", []).append(
        {
            "at": utc_now(),
            "action": action,
            "payload": payload or {},
        }
    )


def project_info(project: dict) -> dict[str, Any]:
    return {
        "name": project.get("name"),
        "created_at": project.get("created_at"),
        "updated_at": project.get("updated_at"),
        "backend": project.get("backend", {}),
        "context": project.get("context", {}),
        "history_count": len(project.get("history", [])),
    }
