"""Execution engine for repo and workflow mutation loops."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from cli_anything.litellm.core.patches import apply_actions, build_patch
from cli_anything.litellm.utils.litellm_backend import chat_completion


SYSTEM_PROMPT = """You are an agentic software editing engine.
Return JSON only with this shape:
{
  "summary": "short text",
  "goal_met": false,
  "actions": [
    {"op": "write|replace|append|delete", "path": "relative/path", "content": "full file content when writing/replacing"}
  ],
  "notes": ["optional strings"]
}
Rules:
- Only edit files already discussed in the provided context unless a new file is clearly required.
- Paths must be relative to the workspace.
- Prefer full-file replacement for deterministic patching.
- Default toward app-building and app-editing work, especially agent execution engines,
  orchestration flows, retry loops, and control loops.
- If no change is needed, return an empty actions list.
"""


def parse_completion_payload(response: dict[str, Any]) -> dict[str, Any]:
    choices = response.get("choices") or []
    if not choices:
        raise RuntimeError("LiteLLM returned no choices")
    content = choices[0].get("message", {}).get("content", "")
    if not content:
        raise RuntimeError("LiteLLM returned empty content")
    content = content.strip()
    if content.startswith("```"):
        parts = [part for part in content.split("```") if part.strip()]
        for part in parts:
            candidate = part.strip()
            if candidate.startswith("json"):
                candidate = candidate[4:].strip()
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError("LiteLLM response was not valid JSON") from exc


def collect_context(workspace: str | Path, include: list[str], max_chars: int = 24000) -> str:
    root = Path(workspace).resolve()
    chunks: list[str] = []
    used = 0
    for relative in include:
        path = (root / relative).resolve()
        if not path.exists() or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        block = f"\n# FILE: {relative}\n{text}\n"
        if used + len(block) > max_chars:
            remaining = max_chars - used
            if remaining <= 0:
                break
            block = block[:remaining]
        chunks.append(block)
        used += len(block)
        if used >= max_chars:
            break
    return "".join(chunks)


def run_verify(command: str | None, workspace: str | Path) -> dict[str, Any]:
    if not command:
        return {"status": "skipped", "command": None}
    proc = subprocess.run(
        command,
        cwd=str(Path(workspace).resolve()),
        shell=True,
        capture_output=True,
        text=True,
    )
    return {
        "status": "passed" if proc.returncode == 0 else "failed",
        "command": command,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def default_verify_command(workspace: str | Path, include: list[str]) -> str | None:
    root = Path(workspace).resolve()
    if (root / "pytest.ini").exists() or (root / "pyproject.toml").exists() or (root / "tests").exists():
        return "pytest -q"
    python_targets = [item for item in include if item.endswith(".py")]
    if python_targets:
        joined = " ".join(python_targets)
        return f"python -m py_compile {joined}"
    return None


def execute_task(
    task: dict[str, Any],
    *,
    workspace: str | Path,
    host: str,
    api_key: str | None,
    model: str,
    max_iterations: int | None = None,
) -> dict[str, Any]:
    include = task.get("target", {}).get("include") or []
    verify_cmd = (task.get("verify") or {}).get("command") or default_verify_command(workspace, include)
    iterations = max_iterations or int(task.get("max_iterations", 3))
    history: list[dict[str, Any]] = []
    last_patch: dict[str, Any] | None = None

    for iteration in range(1, iterations + 1):
        context = collect_context(workspace, include)
        step_prompt = task.get("steps", [{"prompt": task["goal"]}])[0].get("prompt", task["goal"])
        user_prompt = (
            f"Goal: {task['goal']}\n"
            f"Success criteria: {task.get('success_criteria', [])}\n"
            f"Workspace targets: {include}\n"
            f"Task step: {step_prompt}\n"
            f"Current context:\n{context}"
        )
        response = chat_completion(
            host,
            api_key=api_key,
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )
        payload = parse_completion_payload(response)
        actions = payload.get("actions") or []
        patch = build_patch(actions, workspace)
        changed_files = apply_actions(actions, workspace) if task.get("patch_policy", {}).get("auto_apply", True) else []
        verify = run_verify(verify_cmd, workspace)
        step = {
            "iteration": iteration,
            "summary": payload.get("summary", ""),
            "goal_met": bool(payload.get("goal_met")),
            "changed_files": changed_files,
            "verify": verify,
            "notes": payload.get("notes", []),
        }
        history.append(step)
        last_patch = patch
        if payload.get("goal_met") and verify["status"] in {"passed", "skipped"}:
            return {
                "status": "completed",
                "iterations": iteration,
                "history": history,
                "last_patch": last_patch,
                "model": model,
            }
    return {
        "status": "max_iterations",
        "iterations": iterations,
        "history": history,
        "last_patch": last_patch,
        "model": model,
    }


def execute_flow(
    flow: dict[str, Any],
    *,
    workspace: str | Path,
    host: str,
    api_key: str | None,
    model: str,
) -> dict[str, Any]:
    results = []
    for step in flow.get("steps", []):
        task = {
            "name": step.get("name", flow.get("name", "flow-step")),
            "goal": step.get("goal") or step.get("prompt") or flow.get("goal") or "Execute flow step",
            "target": step.get("target", flow.get("target", {})),
            "steps": [{"prompt": step.get("prompt") or step.get("goal") or flow.get("goal", "")}],
            "success_criteria": step.get("success_criteria", flow.get("success_criteria", [])),
            "verify": step.get("verify", flow.get("verify", {})),
            "max_iterations": step.get("max_iterations", flow.get("max_iterations", 3)),
            "patch_policy": step.get("patch_policy", flow.get("patch_policy", {"auto_apply": True, "repo_scoped_only": True})),
        }
        results.append(
            execute_task(task, workspace=workspace, host=host, api_key=api_key, model=step.get("model", model))
        )
    status = "completed" if all(result["status"] == "completed" for result in results) else "partial"
    return {"status": status, "results": results}
