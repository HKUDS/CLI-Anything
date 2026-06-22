import json as _json

import pytest

from cli_anything.eval.runner import build_summary, discover_tasks, run_eval, run_task
from cli_anything.eval.contracts import EvalContext, Status, TaskSpec
from tests._util import make_tasks_pkg

PASS_SRC = '''
TASK = {"id": "p", "name": "P", "description": "d", "prompt": "do p"}
def run(ctx):
    ctx.task_artifact_path("a.txt").write_text("hi")
    return {"metrics": {"n": 1}, "artifacts": ["a.txt"]}
def verify(ctx):
    p = ctx.task_artifact_path("a.txt")
    return {"ok": p.exists(), "metrics": {"size": p.stat().st_size}}
'''

LEGACY_FAIL_SRC = '''
TASK = {"id": "lf", "name": "LF", "description": "legacy ok-from-run"}
def run(ctx):
    return {"ok": False, "metrics": {}}
'''

ERROR_SRC = '''
TASK = {"id": "e", "name": "E", "description": "boom"}
def run(ctx):
    raise RuntimeError("boom")
'''

SKIP_REQ_SRC = '''
TASK = {"id": "sr", "name": "SR", "description": "needs binary",
        "requires": ["definitely-not-a-real-binary-xyz"]}
def run(ctx):
    return {"ok": True}
'''

SKIP_PRE_SRC = '''
TASK = {"id": "sp", "name": "SP", "description": "precheck skip"}
def precheck(ctx):
    return "missing dependency foo"
def run(ctx):
    return {"ok": True}
'''


def _ctx(tmp_path):
    return EvalContext(output_dir=tmp_path / "o", artifacts_dir=tmp_path / "a",
                       work_dir=tmp_path / "w")


def test_discover_sorts_and_dedupes(tmp_path):
    pkg = make_tasks_pkg(tmp_path, {"m1": PASS_SRC, "m2": ERROR_SRC})
    tasks = discover_tasks(pkg)
    assert [t.task_id for t in tasks] == ["e", "p"]
    assert tasks[1].prompt == "do p"


def test_discover_duplicate_id_raises(tmp_path):
    dup = PASS_SRC.replace('"id": "p"', '"id": "dup"')
    dup2 = ERROR_SRC.replace('"id": "e"', '"id": "dup"')
    pkg = make_tasks_pkg(tmp_path, {"x": dup, "y": dup2})
    with pytest.raises(ValueError):
        discover_tasks(pkg)


def test_run_task_pass_with_verify(tmp_path):
    pkg = make_tasks_pkg(tmp_path, {"m": PASS_SRC})
    task = discover_tasks(pkg)[0]
    res = run_task(task, _ctx(tmp_path))
    assert res["status"] == Status.PASS
    assert res["metrics"]["size"] > 0
    assert res["prompt"] == "do p"


def test_run_task_legacy_fail(tmp_path):
    pkg = make_tasks_pkg(tmp_path, {"m": LEGACY_FAIL_SRC})
    task = discover_tasks(pkg)[0]
    res = run_task(task, _ctx(tmp_path))
    assert res["status"] == Status.FAIL


def test_run_task_error(tmp_path):
    pkg = make_tasks_pkg(tmp_path, {"m": ERROR_SRC})
    task = discover_tasks(pkg)[0]
    res = run_task(task, _ctx(tmp_path))
    assert res["status"] == Status.ERROR
    assert "boom" in res["error"]


def test_run_task_skipped_requires(tmp_path):
    pkg = make_tasks_pkg(tmp_path, {"m": SKIP_REQ_SRC})
    task = discover_tasks(pkg)[0]
    res = run_task(task, _ctx(tmp_path))
    assert res["status"] == Status.SKIPPED
    assert "not found" in res["skip_reason"]


def test_run_task_skipped_precheck(tmp_path):
    pkg = make_tasks_pkg(tmp_path, {"m": SKIP_PRE_SRC})
    task = discover_tasks(pkg)[0]
    res = run_task(task, _ctx(tmp_path))
    assert res["status"] == Status.SKIPPED
    assert res["skip_reason"] == "missing dependency foo"


def test_build_summary():
    results = [{"status": "pass"}, {"status": "fail"}, {"status": "error"},
               {"status": "skipped"}]
    s = build_summary(results)
    assert s == {"total": 4, "attempted": 3, "passed": 1, "failed": 1,
                 "error": 1, "skipped": 1, "success_rate": round(1 / 3, 4)}


def test_run_eval_writes_reports(tmp_path):
    pkg = make_tasks_pkg(tmp_path, {"m1": PASS_SRC, "m2": LEGACY_FAIL_SRC})
    out = tmp_path / "out"
    result = run_eval(pkg, display_name="Demo", output_dir=str(out),
                      now="2026-06-22T00:00:00")
    assert (out / "eval_report.json").exists()
    assert (out / "eval_report.md").exists()
    data = _json.loads((out / "eval_report.json").read_text(encoding="utf-8"))
    assert data["schema_version"] == 2
    assert data["display_name"] == "Demo"
    s = data["summary"]
    assert s["total"] == 2 and s["passed"] == 1 and s["failed"] == 1
    assert "# Demo Eval Report" in (out / "eval_report.md").read_text(encoding="utf-8")


def test_run_eval_no_tasks_raises(tmp_path):
    pkg = make_tasks_pkg(tmp_path, {"empty": "X = 1\n"})
    with pytest.raises(RuntimeError):
        run_eval(pkg, output_dir=str(tmp_path / "o2"))


def test_run_eval_update_and_compare_baseline(tmp_path):
    pkg = make_tasks_pkg(tmp_path, {"m1": PASS_SRC})
    base = tmp_path / "baseline.json"
    run_eval(pkg, output_dir=str(tmp_path / "r1"), baseline_path=str(base),
             update_baseline=True, now="t")
    assert base.exists()
    # Re-run against the written baseline: stable -> no regression.
    result = run_eval(pkg, output_dir=str(tmp_path / "r2"),
                      baseline_path=str(base), now="t")
    assert result["comparison"]["regression"] is False
