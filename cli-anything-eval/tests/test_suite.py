import importlib
import sys

from cli_anything.eval.suite import discover_harness_task_packages, run_suite


def _make_fake_harness(tmp_path, sw, ok):
    """Create cli_anything/<sw>/eval/tasks/<sw>.py importable from tmp_path."""
    base = tmp_path / "cli_anything" / sw / "eval" / "tasks"
    base.mkdir(parents=True)
    # cli_anything is a namespace package (no __init__); sw/eval/tasks are regular packages.
    (tmp_path / "cli_anything" / sw / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "cli_anything" / sw / "eval" / "__init__.py").write_text("", encoding="utf-8")
    (base / "__init__.py").write_text("", encoding="utf-8")
    ok_literal = "True" if ok else "False"
    (base / f"{sw}.py").write_text(
        f'TASK = {{"id": "t", "name": "T", "description": "d"}}\n'
        f'def run(ctx):\n    return {{"ok": {ok_literal}}}\n',
        encoding="utf-8",
    )


def test_suite_ranks_by_success_rate(tmp_path, monkeypatch):
    _make_fake_harness(tmp_path, "aaa", ok=False)
    _make_fake_harness(tmp_path, "zzz", ok=True)
    sys.path.insert(0, str(tmp_path))
    import cli_anything  # noqa: F401
    importlib.invalidate_caches()

    out = tmp_path / "suite_out"
    result = run_suite(harnesses=["aaa", "zzz"], output_dir=str(out), now="t")
    harnesses = result["suite"]["harnesses"]
    assert [h["harness"] for h in harnesses] == ["zzz", "aaa"]  # 1.0 before 0.0
    assert (out / "leaderboard.json").exists()
    assert (out / "leaderboard.md").exists()

    empty = run_suite(harnesses=[], output_dir=str(tmp_path / "empty_out"), now="t")
    assert empty["suite"]["harnesses"] == []
