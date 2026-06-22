"""Baseline persistence and regression comparison."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


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
    for task_id, b in baseline_tasks.items():
        if b.get("status") != "pass":
            continue
        current = report_tasks.get(task_id)
        if current and current.get("status") in ("fail", "error"):
            regressions.append({"task_id": task_id, "reason": f"pass_to_{current.get('status')}"})

    baseline_rate = float(baseline.get("summary", {}).get("success_rate", 0.0))
    current_rate = float(report.get("summary", {}).get("success_rate", 0.0))
    rate_delta = round(current_rate - baseline_rate, 4)
    if rate_delta < 0:
        regressions.append({"task_id": "__summary__", "reason": "success_rate_decrease",
                            "delta": rate_delta})

    return {"success_rate_delta": rate_delta, "regressions": regressions,
            "regression": len(regressions) > 0}
