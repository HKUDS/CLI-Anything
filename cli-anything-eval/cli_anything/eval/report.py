"""Rendering of eval reports (JSON-ready dicts -> Markdown) and baseline projection."""

from __future__ import annotations

from typing import Any, Dict, List


def report_to_markdown(report: Dict[str, Any], display_name: str = "") -> str:
    title = display_name or report.get("display_name") or "Harness"
    s = report.get("summary", {})
    lines: List[str] = [
        f"# {title} Eval Report",
        "",
        f"Run at: {report.get('started_at', '')}",
        "",
        f"Summary: {s.get('passed', 0)}/{s.get('attempted', 0)} passed "
        f"({s.get('success_rate', 0.0):.2%}); skipped: {s.get('skipped', 0)}",
        "",
        "| Task | Status | Duration (ms) | Notes |",
        "| --- | --- | --- | --- |",
    ]
    for t in report.get("tasks", []):
        note = t.get("skip_reason") or t.get("error") or ""
        lines.append(
            f"| {t.get('id', '')} | {str(t.get('status', '')).upper()} | "
            f"{t.get('duration_ms', 0)} | {note} |"
        )

    comp = report.get("baseline_comparison")
    if comp:
        lines += ["", "## Baseline Comparison", "",
                  f"Baseline: {comp.get('baseline_path', '')}",
                  f"Success rate delta: {comp.get('success_rate_delta', 0.0):.4f}"]
        if comp.get("regressions"):
            lines += ["", "Regressions:"]
            for r in comp.get("regressions", []):
                lines.append(f"- {r.get('task_id', '')}: {r.get('reason', '')}")
        else:
            lines += ["", "Regressions: none"]

    lines.append("")
    return "\n".join(lines)


def report_to_baseline(report: Dict[str, Any]) -> Dict[str, Any]:
    task_map = {}
    for t in report.get("tasks", []):
        task_map[t.get("id", "")] = {"status": t.get("status"), "metrics": t.get("metrics", {})}
    return {"summary": report.get("summary", {}), "tasks": task_map}


def leaderboard_to_markdown(suite: Dict[str, Any]) -> str:
    lines: List[str] = [
        "# CLI-Anything Eval Leaderboard",
        "",
        f"Run at: {suite.get('started_at', '')}",
        "",
        "| Rank | Harness | Passed/Attempted | Skipped | Success Rate | Duration (ms) |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    ranked = sorted(suite.get("harnesses", []),
                    key=lambda h: h.get("summary", {}).get("success_rate", 0.0),
                    reverse=True)
    for i, h in enumerate(ranked, start=1):
        s = h.get("summary", {})
        lines.append(
            f"| {i} | {h.get('harness', '')} | {s.get('passed', 0)}/{s.get('attempted', 0)} "
            f"| {s.get('skipped', 0)} | {s.get('success_rate', 0.0):.2%} | {h.get('duration_ms', 0)} |"
        )
    lines.append("")
    return "\n".join(lines)
