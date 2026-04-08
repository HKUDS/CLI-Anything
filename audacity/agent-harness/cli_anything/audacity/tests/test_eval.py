"""Tests for Audacity eval harness."""

import json

from cli_anything.audacity.eval.runner import compare_baseline, discover_tasks, run_eval


def test_discover_tasks():
    tasks = discover_tasks()
    assert len(tasks) >= 3
    task_ids = [t.task_id for t in tasks]
    assert len(task_ids) == len(set(task_ids))


def test_run_eval_creates_reports(tmp_path):
    out_dir = tmp_path / "eval_out"
    result = run_eval(output_dir=str(out_dir))
    paths = result.get("paths", {})

    report_json = paths.get("report_json")
    report_md = paths.get("report_md")

    assert report_json and report_md
    assert (out_dir / "eval_report.json").exists()
    assert (out_dir / "eval_report.md").exists()

    data = json.loads((out_dir / "eval_report.json").read_text(encoding="utf-8"))
    summary = data.get("summary", {})
    assert summary.get("total") == len(data.get("tasks", []))
    assert summary.get("passed") + summary.get("failed") == summary.get("total")


def test_compare_baseline_detects_regression():
    baseline = {
        "summary": {"success_rate": 1.0},
        "tasks": {
            "task_a": {"status": "pass"},
            "task_b": {"status": "pass"},
        },
    }
    report = {
        "summary": {"success_rate": 0.5},
        "tasks": [
            {"id": "task_a", "status": "fail", "duration_ms": 1},
            {"id": "task_b", "status": "pass", "duration_ms": 1},
        ],
    }

    comparison = compare_baseline(baseline, report)
    assert comparison.get("regression") is True
    assert any(r.get("task_id") == "task_a" for r in comparison.get("regressions", []))
