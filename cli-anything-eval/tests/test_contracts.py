from pathlib import Path

from cli_anything.eval.contracts import EvalContext, Status, TaskSpec


def test_status_constants():
    assert Status.PASS == "pass"
    assert Status.FAIL == "fail"
    assert Status.ERROR == "error"
    assert Status.SKIPPED == "skipped"


def test_eval_context_dirs(tmp_path):
    ctx = EvalContext(
        output_dir=tmp_path / "out",
        artifacts_dir=tmp_path / "art",
        work_dir=tmp_path / "work",
        task_id="t1",
    )
    assert ctx.task_work_dir() == tmp_path / "work" / "t1"
    assert ctx.task_work_dir().is_dir()
    assert ctx.task_artifact_path("x.bin") == tmp_path / "art" / "t1" / "x.bin"
    assert ctx.task_artifacts_dir().is_dir()


def test_taskspec_defaults():
    spec = TaskSpec(task_id="a", name="A", description="d", run=lambda ctx: {"ok": True})
    assert spec.verify is None
    assert spec.precheck is None
    assert spec.requires == []
    assert spec.prompt == ""
