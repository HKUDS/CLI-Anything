"""Patch generation, apply, export, and rollback helpers."""

from __future__ import annotations

import difflib
import json
from pathlib import Path
from typing import Any


def ensure_workspace_path(workspace: str | Path, candidate: str) -> Path:
    root = Path(workspace).resolve()
    full = (root / candidate).resolve()
    try:
        full.relative_to(root)
    except ValueError as exc:
        raise RuntimeError(f"Edit escapes workspace: {candidate}") from exc
    return full


def build_patch(actions: list[dict[str, Any]], workspace: str | Path) -> dict[str, Any]:
    diffs: list[str] = []
    snapshots: list[dict[str, Any]] = []
    for action in actions:
        path = ensure_workspace_path(workspace, action["path"])
        op = action.get("op", "write")
        before = path.read_text(encoding="utf-8") if path.exists() else ""
        if op == "append":
            after = before + action.get("content", "")
        elif op in {"write", "replace"}:
            after = action.get("content", "")
        elif op == "delete":
            after = ""
        else:
            raise RuntimeError(f"Unsupported patch operation: {op}")
        diff = difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{action['path']}",
            tofile=f"b/{action['path']}",
        )
        diffs.append("".join(diff))
        snapshots.append({"path": action["path"], "before": before, "after": after, "op": op})
    return {"diff": "\n".join(d for d in diffs if d), "snapshots": snapshots, "actions": actions}


def apply_actions(actions: list[dict[str, Any]], workspace: str | Path) -> list[str]:
    changed: list[str] = []
    for action in actions:
        path = ensure_workspace_path(workspace, action["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        op = action.get("op", "write")
        if op == "delete":
            if path.exists():
                path.unlink()
                changed.append(action["path"])
            continue
        before = path.read_text(encoding="utf-8") if path.exists() else ""
        if op == "append":
            content = before + action.get("content", "")
        else:
            content = action.get("content", "")
        path.write_text(content, encoding="utf-8")
        changed.append(action["path"])
    return changed


def rollback_patch(patch_info: dict[str, Any], workspace: str | Path) -> list[str]:
    restored: list[str] = []
    for snapshot in patch_info.get("snapshots", []):
        path = ensure_workspace_path(workspace, snapshot["path"])
        before = snapshot.get("before", "")
        if before == "" and path.exists():
            path.unlink()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(before, encoding="utf-8")
        restored.append(snapshot["path"])
    return restored


def export_patch(patch_info: dict[str, Any], outdir: str | Path) -> dict[str, str]:
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    diff_path = out / "last.patch"
    json_path = out / "last-actions.json"
    diff_path.write_text(patch_info.get("diff", ""), encoding="utf-8")
    json_path.write_text(json.dumps(patch_info.get("actions", []), indent=2), encoding="utf-8")
    return {"diff": str(diff_path), "actions": str(json_path)}
