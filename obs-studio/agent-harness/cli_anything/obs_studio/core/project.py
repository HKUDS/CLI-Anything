"""Project-level operations for OBS Studio scene collections."""

from __future__ import annotations

import json
from pathlib import Path

from .session import Session, create_project


def new_project(session: Session, name: str = "obs_project") -> dict:
    state = session.new_project(name)
    return {
        "action": "new_project",
        "name": state["name"],
        "scene_count": len(state["scenes"]),
        "active_scene": state["active_scene"],
    }


def save_project(session_or_proj, path: str | None = None) -> dict | str:
    if isinstance(session_or_proj, Session):
        saved = session_or_proj.save_project(path)
        return {"action": "save_project", "path": saved}
    proj = session_or_proj
    if path is None:
        raise ValueError("path is required for standalone save")
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(proj, indent=2), encoding="utf-8")
    return path


def open_project(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)
    return json.loads(p.read_text(encoding="utf-8"))


def get_project_info(proj: dict) -> dict:
    total_sources = sum(len(s.get("sources", [])) for s in proj.get("scenes", []))
    return {
        "name": proj.get("name", ""),
        "counts": {
            "scenes": len(proj.get("scenes", [])),
            "total_sources": total_sources,
            "audio_sources": len(proj.get("audio_sources", [])),
            "transitions": len(proj.get("transitions", [])),
        },
        "settings": proj.get("settings", {}),
        "streaming": proj.get("streaming", {}),
        "recording": proj.get("recording", {}),
    }


def project_info(session: Session) -> dict:
    if not session.is_open or session.state is None:
        raise RuntimeError("No project is open")
    state = session.state
    return {
        "name": state["name"],
        "project_id": state["project_id"],
        "project_path": session.project_path,
        "scene_count": len(state["scenes"]),
        "active_scene": state["active_scene"],
        "transitions": len(state["transitions"]),
        "audio_sources": len(state["audio_sources"]),
        "settings": state["settings"],
        "streaming": state["streaming"],
        "recording": state["recording"],
    }
