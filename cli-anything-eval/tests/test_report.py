from cli_anything.eval.report import (
    leaderboard_to_markdown,
    report_to_baseline,
    report_to_markdown,
)

REPORT = {
    "schema_version": 2,
    "display_name": "Demo",
    "started_at": "2026-06-22T00:00:00",
    "summary": {"total": 2, "attempted": 2, "passed": 1, "failed": 1,
                "error": 0, "skipped": 0, "success_rate": 0.5},
    "tasks": [
        {"id": "a", "status": "pass", "duration_ms": 5, "metrics": {"x": 1},
         "skip_reason": "", "error": ""},
        {"id": "b", "status": "fail", "duration_ms": 7, "metrics": {},
         "skip_reason": "", "error": ""},
    ],
}


def test_markdown_has_title_and_summary():
    md = report_to_markdown(REPORT, "Demo")
    assert "# Demo Eval Report" in md
    assert "1/2 passed" in md
    assert "| a |" in md and "PASS" in md


def test_report_to_baseline_shape():
    base = report_to_baseline(REPORT)
    assert base["tasks"]["a"] == {"status": "pass", "metrics": {"x": 1}}
    assert base["summary"]["success_rate"] == 0.5


def test_leaderboard_markdown_ranks():
    suite = {"started_at": "t", "harnesses": [
        {"harness": "blender", "summary": {"passed": 1, "attempted": 2, "skipped": 1,
                                           "success_rate": 0.5}, "duration_ms": 9},
        {"harness": "gimp", "summary": {"passed": 2, "attempted": 2, "skipped": 0,
                                        "success_rate": 1.0}, "duration_ms": 3},
    ]}
    md = leaderboard_to_markdown(suite)
    assert "Leaderboard" in md
    assert md.index("gimp") < md.index("blender")
