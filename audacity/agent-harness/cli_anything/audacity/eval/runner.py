"""Evaluation and regression harness for Audacity CLI."""

from __future__ import annotations

import importlib
import json
import pkgutil
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from cli_anything.audacity.utils.file_io import safe_write_json


@dataclass
class TaskSpec:
    task_id: str
    name: str
    description: str
    run: Callable[["EvalContext"], Dict[str, Any]]


@dataclass
class EvalContext:
    output_dir: Path
    artifacts_dir: Path
    work_dir: Path
    task_id: str = ""

    def task_work_dir(self) -> Path:
        path = self.work_dir / self.task_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def task_artifacts_dir(self) -> Path:
        path = self.artifacts_dir / self.task_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def task_artifact_path(self, filename: str) -> Path:
        return self.task_artifacts_dir() / filename


def _iso_now() -> str:
    return datetime.now().isoformat()


def default_output_dir() -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path("eval_results") / stamp


def discover_tasks() -> List[TaskSpec]:
    tasks_pkg = importlib.import_module("cli_anything.audacity.eval.tasks")
    task_specs: List[TaskSpec] = []
    seen_ids = set()

    for mod in pkgutil.iter_modules(tasks_pkg.__path__):
        if mod.ispkg:
            continue
        module_name = f"{tasks_pkg.__name__}.{mod.name}"
        module = importlib.import_module(module_name)
        task_meta = getattr(module, "TASK", None)
        run_fn = getattr(module, "run", None)
        if not isinstance(task_meta, dict) or not callable(run_fn):
            continue

        task_id = str(task_meta.get("id") or mod.name)
        if task_id in seen_ids:
            raise ValueError(f"Duplicate task id: {task_id}")
        seen_ids.add(task_id)

        task_specs.append(TaskSpec(
            task_id=task_id,
            name=str(task_meta.get("name", task_id)),
            description=str(task_meta.get("description", "")),
            run=run_fn,
        ))

    task_specs.sort(key=lambda t: t.task_id)
    return task_specs


def _run_task(task: TaskSpec, ctx: EvalContext) -> Dict[str, Any]:
    ctx.task_id = task.task_id
    ctx.task_work_dir()
    ctx.task_artifacts_dir()

    started = time.time()
    ok = False
    metrics: Dict[str, Any] = {}
    artifacts: List[str] = []
    notes = ""
    error = ""

    try:
        result = task.run(ctx) or {}
        ok = bool(result.get("ok", False))
        metrics = result.get("metrics", {}) or {}
        artifacts = result.get("artifacts", []) or []
        notes = result.get("notes", "") or ""
    except Exception as exc:  # pylint: disable=broad-except
        error = f"{type(exc).__name__}: {exc}"

    duration_ms = int((time.time() - started) * 1000)
    status = "pass" if ok else "fail"

    return {
        "id": task.task_id,
        "name": task.name,
        "description": task.description,
        "status": status,
        "duration_ms": duration_ms,
        "metrics": metrics,
        "artifacts": artifacts,
        "notes": notes,
        "error": error,
    }


def _build_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(results)
    passed = sum(1 for r in results if r.get("status") == "pass")
    failed = total - passed
    success_rate = float(passed) / float(total) if total else 0.0
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "success_rate": round(success_rate, 4),
    }


def _report_to_markdown(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# Audacity Eval Report")
    lines.append("")
    lines.append(f"Run at: {report.get('started_at', '')}")
    lines.append("")
    summary = report.get("summary", {})
    lines.append(
        f"Summary: {summary.get('passed', 0)}/{summary.get('total', 0)} passed "
        f"({summary.get('success_rate', 0.0):.2%})"
    )
    lines.append("")
    lines.append("| Task | Status | Duration (ms) |")
    lines.append("| --- | --- | --- |")
    for task in report.get("tasks", []):
        status = str(task.get("status", "")).upper()
        lines.append(
            f"| {task.get('id', '')} | {status} | {task.get('duration_ms', 0)} |"
        )

    comparison = report.get("baseline_comparison")
    if comparison:
        lines.append("")
        lines.append("## Baseline Comparison")
        lines.append("")
        lines.append(f"Baseline: {comparison.get('baseline_path', '')}")
        lines.append(
            f"Success rate delta: {comparison.get('success_rate_delta', 0.0):.4f}"
        )
        if comparison.get("regressions"):
            lines.append("")
            lines.append("Regressions:")
            for reg in comparison.get("regressions", []):
                lines.append(
                    f"- {reg.get('task_id', '')}: {reg.get('reason', '')}"
                )
        else:
            lines.append("")
            lines.append("Regressions: none")

    lines.append("")
    return "\n".join(lines)


def _report_to_baseline(report: Dict[str, Any]) -> Dict[str, Any]:
    task_map = {}
    for task in report.get("tasks", []):
        task_map[task.get("id", "")] = {
            "status": task.get("status"),
            "metrics": task.get("metrics", {}),
        }
    return {
        "summary": report.get("summary", {}),
        "tasks": task_map,
    }


def load_baseline(path: str) -> Dict[str, Any]:
    baseline_path = Path(path)
    if not baseline_path.exists():
        raise FileNotFoundError(f"Baseline file not found: {path}")
    with baseline_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def compare_baseline(baseline: Dict[str, Any], report: Dict[str, Any]) -> Dict[str, Any]:
    baseline_tasks = baseline.get("tasks", {}) or {}
    report_tasks = {t.get("id", ""): t for t in report.get("tasks", [])}

    regressions: List[Dict[str, Any]] = []

    for task_id, baseline_task in baseline_tasks.items():
        if baseline_task.get("status") != "pass":
            continue
        current = report_tasks.get(task_id)
        if current and current.get("status") == "fail":
            regressions.append({
                "task_id": task_id,
                "reason": "pass_to_fail",
            })

    baseline_rate = float(baseline.get("summary", {}).get("success_rate", 0.0))
    current_rate = float(report.get("summary", {}).get("success_rate", 0.0))
    rate_delta = round(current_rate - baseline_rate, 4)
    if rate_delta < 0:
        regressions.append({
            "task_id": "__summary__",
            "reason": "success_rate_decrease",
            "delta": rate_delta,
        })

    return {
        "success_rate_delta": rate_delta,
        "regressions": regressions,
        "regression": len(regressions) > 0,
    }


def run_eval(
    output_dir: Optional[str] = None,
    baseline_path: Optional[str] = None,
    update_baseline: bool = False,
) -> Dict[str, Any]:
    out_dir = Path(output_dir) if output_dir else default_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir = out_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    tasks = discover_tasks()
    if not tasks:
        raise RuntimeError("No eval tasks discovered.")

    started_at = _iso_now()
    results: List[Dict[str, Any]] = []

    with tempfile.TemporaryDirectory() as tmp_dir:
        ctx = EvalContext(
            output_dir=out_dir,
            artifacts_dir=artifacts_dir,
            work_dir=Path(tmp_dir),
        )
        for task in tasks:
            results.append(_run_task(task, ctx))

    summary = _build_summary(results)
    report = {
        "schema_version": 1,
        "started_at": started_at,
        "summary": summary,
        "tasks": results,
    }

    comparison = None
    if baseline_path:
        baseline = load_baseline(baseline_path)
        comparison = compare_baseline(baseline, report)
        comparison["baseline_path"] = str(baseline_path)
        report["baseline_comparison"] = comparison

    report_json_path = out_dir / "eval_report.json"
    report_md_path = out_dir / "eval_report.md"

    safe_write_json(report_json_path, report, indent=2, default=str)
    report_md_path.write_text(_report_to_markdown(report), encoding="utf-8")

    baseline_written = None
    if update_baseline:
        baseline_out = Path(baseline_path) if baseline_path else (out_dir / "baseline.json")
        baseline_out.parent.mkdir(parents=True, exist_ok=True)
        baseline_data = _report_to_baseline(report)
        safe_write_json(baseline_out, baseline_data, indent=2, default=str)
        baseline_written = str(baseline_out)

    return {
        "report": report,
        "comparison": comparison,
        "paths": {
            "output_dir": str(out_dir),
            "report_json": str(report_json_path),
            "report_md": str(report_md_path),
            "baseline_written": baseline_written,
        },
    }
