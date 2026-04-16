"""Render and share operations for Mermaid Live Editor state."""

from __future__ import annotations

import os

from .session import Session
from ..utils import mermaid_backend


def render(session: Session, output_path: str, fmt: str = "svg", overwrite: bool = False) -> dict:
    if not session.is_open or session.state is None:
        raise RuntimeError("No project is open")
    if os.path.exists(output_path) and not overwrite:
        raise FileExistsError(f"Output already exists: {output_path}")
    serialized = mermaid_backend.serialize_state(session.state)
    result = mermaid_backend.render_to_file(serialized, output_path, fmt)
    result["action"] = "render"
    return result


def share(session: Session, mode: str = "edit") -> dict:
    if not session.is_open or session.state is None:
        raise RuntimeError("No project is open")
    serialized = mermaid_backend.serialize_state(session.state)
    return {
        "action": "share",
        "mode": mode,
        "url": mermaid_backend.build_live_url(serialized, mode),
    }
