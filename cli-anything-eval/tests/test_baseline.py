import pytest

from cli_anything.eval.baseline import compare_baseline, load_baseline


def test_load_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_baseline(str(tmp_path / "nope.json"))


def test_regression_pass_to_fail():
    baseline = {"summary": {"success_rate": 1.0},
                "tasks": {"a": {"status": "pass"}, "b": {"status": "pass"}}}
    report = {"summary": {"success_rate": 0.5},
              "tasks": [{"id": "a", "status": "fail"}, {"id": "b", "status": "pass"}]}
    cmp = compare_baseline(baseline, report)
    assert cmp["regression"] is True
    assert any(r["task_id"] == "a" for r in cmp["regressions"])
    assert cmp["success_rate_delta"] == -0.5


def test_pass_to_error_is_regression():
    baseline = {"summary": {"success_rate": 1.0}, "tasks": {"a": {"status": "pass"}}}
    report = {"summary": {"success_rate": 0.0}, "tasks": [{"id": "a", "status": "error"}]}
    cmp = compare_baseline(baseline, report)
    assert any(r["task_id"] == "a" for r in cmp["regressions"])


def test_no_regression_when_stable():
    baseline = {"summary": {"success_rate": 1.0}, "tasks": {"a": {"status": "pass"}}}
    report = {"summary": {"success_rate": 1.0}, "tasks": [{"id": "a", "status": "pass"}]}
    cmp = compare_baseline(baseline, report)
    assert cmp["regression"] is False
    assert cmp["regressions"] == []
