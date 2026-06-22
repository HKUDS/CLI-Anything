"""Generic single-harness eval runner."""

from __future__ import annotations

import importlib
import pkgutil
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from cli_anything.eval.contracts import EvalContext, Status, TaskSpec


def iso_now() -> str:
    return datetime.now().isoformat()


def default_output_dir() -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path("eval_results") / stamp


def discover_tasks(tasks_package: str) -> List[TaskSpec]:
    tasks_pkg = importlib.import_module(tasks_package)
    specs: List[TaskSpec] = []
    seen = set()
    for mod in pkgutil.iter_modules(tasks_pkg.__path__):
        if mod.ispkg:
            continue
        module = importlib.import_module(f"{tasks_pkg.__name__}.{mod.name}")
        meta = getattr(module, "TASK", None)
        run_fn = getattr(module, "run", None)
        if not isinstance(meta, dict) or not callable(run_fn):
            continue
        task_id = str(meta.get("id") or mod.name)
        if task_id in seen:
            raise ValueError(f"Duplicate task id: {task_id}")
        seen.add(task_id)
        specs.append(TaskSpec(
            task_id=task_id,
            name=str(meta.get("name", task_id)),
            description=str(meta.get("description", "")),
            run=run_fn,
            verify=getattr(module, "verify", None),
            precheck=getattr(module, "precheck", None),
            requires=list(meta.get("requires", []) or []),
            prompt=str(meta.get("prompt", "") or ""),
        ))
    specs.sort(key=lambda t: t.task_id)
    return specs


def _new_result(task: TaskSpec, status: str, **kw) -> Dict[str, Any]:
    base = {
        "id": task.task_id,
        "name": task.name,
        "description": task.description,
        "status": status,
        "duration_ms": 0,
        "metrics": {},
        "artifacts": [],
        "notes": "",
        "error": "",
        "prompt": task.prompt,
        "skip_reason": "",
    }
    base.update(kw)
    return base


def run_task(task: TaskSpec, ctx: EvalContext) -> Dict[str, Any]:
    ctx.task_id = task.task_id

    for binary in task.requires:
        if shutil.which(binary) is None:
            return _new_result(task, Status.SKIPPED,
                               skip_reason=f"required executable not found: {binary}")

    if task.precheck is not None:
        try:
            reason = task.precheck(ctx)
        except Exception as exc:  # precheck failure -> skip, not crash
            reason = f"precheck error: {type(exc).__name__}: {exc}"
        if reason:
            return _new_result(task, Status.SKIPPED, skip_reason=str(reason))

    ctx.task_work_dir()
    ctx.task_artifacts_dir()
    started = time.time()
    try:
        run_result = task.run(ctx) or {}
        metrics = dict(run_result.get("metrics", {}) or {})
        artifacts = list(run_result.get("artifacts", []) or [])
        notes = str(run_result.get("notes", "") or "")
        if task.verify is not None:
            verdict = task.verify(ctx) or {}
            ok = bool(verdict.get("ok", False))
            metrics.update(verdict.get("metrics", {}) or {})
        else:
            ok = bool(run_result.get("ok", False))
        duration_ms = int((time.time() - started) * 1000)
        return _new_result(task, Status.PASS if ok else Status.FAIL,
                           duration_ms=duration_ms, metrics=metrics,
                           artifacts=artifacts, notes=notes)
    except Exception as exc:  # pylint: disable=broad-except
        duration_ms = int((time.time() - started) * 1000)
        return _new_result(task, Status.ERROR, duration_ms=duration_ms,
                           error=f"{type(exc).__name__}: {exc}")


def build_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(results)
    passed = sum(1 for r in results if r["status"] == Status.PASS)
    failed = sum(1 for r in results if r["status"] == Status.FAIL)
    error = sum(1 for r in results if r["status"] == Status.ERROR)
    skipped = sum(1 for r in results if r["status"] == Status.SKIPPED)
    attempted = passed + failed + error
    success_rate = round(passed / attempted, 4) if attempted else 0.0
    return {"total": total, "attempted": attempted, "passed": passed, "failed": failed,
            "error": error, "skipped": skipped, "success_rate": success_rate}
