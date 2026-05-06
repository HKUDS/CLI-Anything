"""YAML task and flow loading."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def _load_yaml(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise RuntimeError(f"Task/flow file not found: {p}")
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise RuntimeError(f"Invalid YAML in {p}: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError("Task/flow YAML root must be an object")
    return data


def load_task(path: str | Path) -> dict[str, Any]:
    data = _load_yaml(path)
    for key in ("name", "goal"):
        if not data.get(key):
            raise RuntimeError(f"Task is missing required field: {key}")
    data.setdefault("target", {})
    data.setdefault(
        "steps",
        [
            {
                "prompt": (
                    "Build or edit the target app or workflow. Prefer robust changes to "
                    "agent execution engines, orchestration flows, and control loops when relevant."
                )
            }
        ],
    )
    data.setdefault(
        "success_criteria",
        [
            "The target app or workflow behaves as intended.",
            "Agentic execution loops stop, retry, and recover correctly.",
            "Verification commands pass.",
        ],
    )
    data.setdefault("max_iterations", 3)
    data.setdefault(
        "defaults",
        {
            "mode": "task_runner",
            "edit_scope": "plan_plus_patch",
            "output_mode": "text_first",
            "loop_mode": "auto_loop",
            "target_mode": "code_and_workflow",
            "patch_mode": "diff_and_action_json",
            "task_storage": "repo_local_yaml",
        },
    )
    data.setdefault("patch_policy", {"auto_apply": True, "repo_scoped_only": True})
    data.setdefault("stop_conditions", {"mode": "goal_met_or_max_iterations"})
    data.setdefault("safety", {"destructive_shell": False})
    return data


def load_flow(path: str | Path) -> dict[str, Any]:
    data = _load_yaml(path)
    if not data.get("name"):
        raise RuntimeError("Flow is missing required field: name")
    steps = data.get("steps")
    if not isinstance(steps, list) or not steps:
        raise RuntimeError("Flow must define a non-empty steps list")
    data.setdefault("max_iterations", 3)
    data.setdefault("patch_policy", {"auto_apply": True, "repo_scoped_only": True})
    data.setdefault("stop_conditions", {"mode": "goal_met_or_max_iterations"})
    return data


def validate_definition(path: str | Path) -> dict[str, Any]:
    data = _load_yaml(path)
    if "steps" in data and isinstance(data["steps"], list) and data["steps"]:
        if "goal" in data:
            kind = "task"
            normalized = load_task(path)
        else:
            kind = "flow"
            normalized = load_flow(path)
    else:
        kind = "task"
        normalized = load_task(path)
    return {"valid": True, "kind": kind, "name": normalized.get("name")}
