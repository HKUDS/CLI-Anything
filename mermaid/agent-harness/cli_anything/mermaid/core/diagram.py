"""Diagram text operations."""

from __future__ import annotations

from .session import Session


def set_diagram(session: Session, text: str) -> dict:
    if not session.is_open:
        raise RuntimeError("No project is open")
    session.set_code(text)
    return {
        "action": "set_diagram",
        "line_count": len(text.splitlines()),
    }


def show_diagram(session: Session) -> dict:
    if not session.is_open or session.state is None:
        raise RuntimeError("No project is open")
    return {
        "action": "show_diagram",
        "code": session.state["code"],
    }
