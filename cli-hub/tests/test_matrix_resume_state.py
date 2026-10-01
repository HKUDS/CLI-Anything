"""Matrix retries keep the original scope's durable outcomes."""

import json

from cli_hub import installer


def _setup(monkeypatch, tmp_path):
    matrix = {"name": "demo", "clis": ["first", "second"], "capabilities": []}
    monkeypatch.setattr(
        installer, "MATRIX_STATE_FILE", tmp_path / "matrix_state.json"
    )
    monkeypatch.setattr(installer, "get_matrix", lambda name: matrix)
    monkeypatch.setattr(installer, "get_cli", lambda name: {
        "name": name, "display_name": name, "version": "1", "entry_point": name,
    })
    monkeypatch.setattr(installer, "get_installed", lambda: {})
    monkeypatch.setattr(
        installer, "render_matrix_skill_file",
        lambda *a, **k: tmp_path / "SKILL.md",
    )
    return matrix


def test_resume_keeps_successful_original_members(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(
        installer, "install_cli", lambda name: (name == "first", name)
    )
    ok, initial = installer.install_matrix("demo")
    assert not ok
    monkeypatch.setattr(installer, "install_cli", lambda name: (True, name))
    ok, resumed = installer.install_matrix("demo", resume=True)
    assert ok
    assert [row["name"] for row in resumed["results"]] == ["second"]
    saved = json.loads(installer.MATRIX_STATE_FILE.read_text())["demo"]
    assert [row["name"] for row in saved["results"]] == ["first", "second"]
    assert all(row["status"] == "installed" for row in saved["results"])


def test_case_variant_install_can_resume_by_canonical_name(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(installer, "install_cli", lambda name: (False, name))
    installer.install_matrix("DEMO")
    monkeypatch.setattr(installer, "install_cli", lambda name: (True, name))
    ok, resumed = installer.install_matrix("demo", resume=True)
    assert ok, resumed
    assert resumed["summary"]["installed"] == 2
    assert list(json.loads(installer.MATRIX_STATE_FILE.read_text())) == ["demo"]


def test_resume_migrates_legacy_case_key(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    original = {"scope": {"type": "all"}, "results": [
        {"name": "first", "status": "installed"},
        {"name": "second", "status": "failed"},
    ]}
    installer.MATRIX_STATE_FILE.write_text(json.dumps({"DEMO": original}))
    monkeypatch.setattr(installer, "install_cli", lambda name: (False, name))
    ok, resumed = installer.install_matrix("demo", resume=True)
    assert not ok
    assert resumed["summary"]["failed"] == 1
    state = json.loads(installer.MATRIX_STATE_FILE.read_text())
    assert "DEMO" not in state
    assert state["demo"]["results"][0] == original["results"][0]
    assert state["demo"]["results"][1]["status"] == "failed"


def test_second_resume_runs_only_remaining_failure(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(installer, "install_cli", lambda name: (False, name))
    installer.install_matrix("demo")
    monkeypatch.setattr(
        installer, "install_cli", lambda name: (name == "first", name)
    )
    installer.install_matrix("demo", resume=True)
    calls = []

    def succeed(name):
        calls.append(name)
        return True, name

    monkeypatch.setattr(installer, "install_cli", succeed)
    ok, resumed = installer.install_matrix("demo", resume=True)
    assert ok and calls == ["second"]
    saved = json.loads(installer.MATRIX_STATE_FILE.read_text())["demo"]
    assert len(saved["results"]) == 2
    ok, settled = installer.install_matrix("DEMO", resume=True)
    assert ok and settled["nothing_to_resume"]
    assert calls == ["second"]
