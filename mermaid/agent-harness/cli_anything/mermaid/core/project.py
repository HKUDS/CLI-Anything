"""Project commands for Mermaid state files."""

from __future__ import annotations

from .session import SAMPLE_DIAGRAMS, Session


def new_project(session: Session, sample: str = "flowchart", theme: str = "default") -> dict:
    state = session.new_project(sample=sample, theme=theme)
    return {
        "action": "new_project",
        "sample": sample,
        "theme": theme,
        "line_count": len(state["code"].splitlines()),
    }


def open_project(session: Session, path: str) -> dict:
    state = session.open_project(path)
    return {
        "action": "open_project",
        "path": session.project_path,
        "line_count": len(state["code"].splitlines()),
    }


def save_project(session: Session, path: str | None = None) -> dict:
    saved = session.save_project(path)
    return {
        "action": "save_project",
        "path": saved,
    }


def project_info(session: Session) -> dict:
    if not session.is_open or session.state is None:
        raise RuntimeError("No project is open")
    return {
        "project_path": session.project_path,
        "line_count": len(session.state["code"].splitlines()),
        "theme_json": session.state["mermaid"],
        "modified": session.modified,
    }


def list_samples() -> dict:
    return SAMPLE_DIAGRAMS.copy()
