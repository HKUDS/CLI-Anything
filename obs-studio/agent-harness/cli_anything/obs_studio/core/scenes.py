"""Scene operations."""

from __future__ import annotations

import copy

from .session import Session


def _get_state(session: Session) -> dict:
    if not session.is_open or session.state is None:
        raise RuntimeError("No project is open")
    return session.state


def _find_scene(state: dict, scene_name: str) -> dict:
    for scene in state["scenes"]:
        if scene["name"] == scene_name:
            return scene
    raise ValueError(f"Scene not found: {scene_name}")


def add_scene(session_or_proj, name: str | None = None) -> dict:
    if isinstance(session_or_proj, Session):
        state = _get_state(session_or_proj)
        if any(scene["name"] == name for scene in state["scenes"]):
            raise ValueError(f"Scene already exists: {name}")
        session_or_proj.checkpoint()
        scene = {"id": len(state["scenes"]), "name": name, "sources": []}
        state["scenes"].append(scene)
        return {"action": "add_scene", "scene": scene}
    proj = session_or_proj
    scene = {"id": len(proj["scenes"]), "name": name, "sources": []}
    proj["scenes"].append(scene)
    return scene


def remove_scene(proj: dict, index: int) -> dict:
    if index < 0 or index >= len(proj["scenes"]):
        raise IndexError(f"Scene index {index} out of range")
    removed = proj["scenes"].pop(index)
    if proj["active_scene"] >= len(proj["scenes"]):
        proj["active_scene"] = max(0, len(proj["scenes"]) - 1)
    return removed


def duplicate_scene(proj: dict, index: int) -> dict:
    if index < 0 or index >= len(proj["scenes"]):
        raise IndexError(f"Scene index {index} out of range")
    original = proj["scenes"][index]
    dup = copy.deepcopy(original)
    dup["id"] = len(proj["scenes"])
    dup["name"] = f"{original['name']} (Copy)"
    proj["scenes"].append(dup)
    return dup


def set_active_scene(proj: dict, index: int) -> None:
    if index < 0 or index >= len(proj["scenes"]):
        raise IndexError(f"Scene index {index} out of range")
    proj["active_scene"] = index


def list_scenes(session_or_proj) -> dict | list:
    if isinstance(session_or_proj, Session):
        state = _get_state(session_or_proj)
        return {
            "active_scene": state["active_scene"],
            "scenes": [
                {
                    "id": scene["id"],
                    "name": scene["name"],
                    "source_count": len(scene["sources"]),
                }
                for scene in state["scenes"]
            ],
        }
    proj = session_or_proj
    return [
        {
            "id": scene.get("id", i),
            "name": scene.get("name", f"Scene {i}"),
            "source_count": len(scene.get("sources", [])),
        }
        for i, scene in enumerate(proj["scenes"])
    ]


def select_scene(session: Session, name: str) -> dict:
    state = _get_state(session)
    scene = _find_scene(state, name)
    session.checkpoint()
    state["active_scene"] = scene["id"]
    return {"action": "select_scene", "active_scene": scene["id"], "name": scene["name"]}
