"""Doctor checks the executable stored at install time if registry entries disappear."""

import json
import os

from cli_hub import installer


def _setup(tmp_path, monkeypatch, record, current=None):
    state = tmp_path / "installed.json"
    state.write_text(json.dumps({"retired": record}), encoding="utf-8")
    monkeypatch.setattr(installer, "INSTALLED_FILE", state)
    monkeypatch.setattr(
        installer, "MATRIX_STATE_FILE", tmp_path / "matrix_state.json"
    )
    monkeypatch.setattr(
        installer,
        "get_matrix",
        lambda name: {"name": "demo", "clis": ["retired"]},
    )
    monkeypatch.setattr(installer, "get_cli", lambda name: current)
    binary_dir = tmp_path / "bin"
    binary_dir.mkdir()
    monkeypatch.setenv("PATH", str(binary_dir))
    return state, binary_dir


def test_missing_recorded_binary_is_broken(tmp_path, monkeypatch):
    state, _ = _setup(tmp_path, monkeypatch, {"entry_point": "missing-runner"})
    before = state.read_bytes()
    ok, payload = installer.doctor_matrix("demo")
    assert not ok
    assert payload["summary"]["broken"] == 1
    assert payload["checks"][0]["entry_point"] == "missing-runner"
    assert payload["checks"][0]["status"] == "broken"
    assert state.read_bytes() == before


def test_present_recorded_binary_is_healthy(tmp_path, monkeypatch):
    entry = "installed-runner.exe" if os.name == "nt" else "installed-runner"
    _, binary_dir = _setup(tmp_path, monkeypatch, {"entry_point": entry})
    binary = binary_dir / entry
    binary.write_text("test executable", encoding="utf-8")
    binary.chmod(0o755)
    ok, payload = installer.doctor_matrix("demo")
    assert ok
    assert payload["checks"][0]["entry_point"] == entry
    assert payload["checks"][0]["status"] == "ok"


def test_record_with_no_resolvable_entry_point_is_not_healthy(
    tmp_path, monkeypatch
):
    _setup(tmp_path, monkeypatch, {"version": "old"})
    ok, payload = installer.doctor_matrix("demo")
    assert not ok
    assert payload["checks"][0]["status"] == "broken"


def test_current_registry_entry_overrides_old_recorded_entry(
    tmp_path, monkeypatch
):
    _setup(
        tmp_path,
        monkeypatch,
        {"entry_point": "obsolete"},
        {"entry_point": "new-runner"},
    )
    ok, payload = installer.doctor_matrix("demo")
    assert not ok
    assert payload["checks"][0]["entry_point"] == "new-runner"
    assert payload["checks"][0]["status"] == "broken"
