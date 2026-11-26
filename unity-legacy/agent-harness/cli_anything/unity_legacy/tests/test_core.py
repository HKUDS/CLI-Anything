import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import monotonic, sleep

import pytest
from click.testing import CliRunner

from cli_anything.unity_legacy.editing_cli import _exact_number_text
from cli_anything.unity_legacy.unity_legacy_cli import EditorError, ask_editor, cli, find_project


@pytest.fixture
def project(tmp_path):
    (tmp_path / "ProjectSettings").mkdir()
    (tmp_path / "ProjectSettings/ProjectVersion.txt").write_text("m_EditorVersion: 2020.3.45f1\n", encoding="utf-8")
    return tmp_path


def test_packaged_bridge():
    result = CliRunner().invoke(cli, ["--json", "bridge-path"])
    assert result.exit_code == 0, result.output
    package = Path(json.loads(result.output)["data"]["path"])
    manifest = json.loads(package.read_text(encoding="utf-8"))
    assert manifest["name"] == "com.cli-anything.unity2020"
    assert set(manifest["dependencies"]) == {
        "com.unity.ugui", "com.unity.test-framework", "com.unity.nuget.newtonsoft-json",
    }
    assert (package.parent / "Editor/UnityCliBridge.cs").is_file()
    assert (package.parent.parent / "skills/SKILL.md").is_file()


def test_project_resolution(project, monkeypatch):
    nested = project / "Assets" / "Scenes"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    assert find_project(None) == project.resolve()
    assert find_project(project) == project.resolve()
    with pytest.raises(EditorError, match="Unity project not found"):
        find_project(nested)


def test_editor_closed(project):
    with pytest.raises(EditorError, match="Open the project in Unity"):
        ask_editor(project, "status", 0.2, {})
    assert not (project / "Library/UnityCli").exists()


def test_timeout_leaves_no_request(project):
    (project / "Temp").mkdir()
    (project / "Temp/UnityLockfile").touch()
    with pytest.raises(EditorError, match="did not reply"):
        ask_editor(project, "status", 0.2, {})
    assert list((project / "Library/UnityCli").iterdir()) == []


def test_concurrent_requests_are_isolated(project):
    (project / "Temp").mkdir()
    (project / "Temp/UnityLockfile").touch()
    queue = project / "Library/UnityCli"

    def reply():
        replied = set()
        deadline = monotonic() + 5
        while monotonic() < deadline and len(replied) < 2:
            for request in queue.glob("request-*/request.json"):
                if request in replied:
                    continue
                payload = json.loads(request.read_text(encoding="utf-8"))
                assert payload["Command"] == "status"
                assert payload["ExpiresAt"] > 0
                pending = request.with_name("response.tmp")
                pending.write_text(json.dumps({"ok": True, "data": payload["Nonce"]}), encoding="utf-8")
                pending.replace(request.with_name("response.json"))
                replied.add(request)
            sleep(0.02)
        assert len(replied) == 2

    with ThreadPoolExecutor(max_workers=3) as pool:
        worker = pool.submit(reply)
        first = pool.submit(ask_editor, project, "status", 5, {"Nonce": 1})
        second = pool.submit(ask_editor, project, "status", 5, {"Nonce": 2})
        assert first.result()["data"] == 1
        assert second.result()["data"] == 2
        worker.result()
    assert list(queue.iterdir()) == []


def test_exact_number_text_is_limited_to_bare_numbers():
    assert _exact_number_text(" 0.25 ") == "0.25"
    assert _exact_number_text("123456789012345678901234567890") == "123456789012345678901234567890"
    assert _exact_number_text("[1.5, 2]") is None
    assert _exact_number_text("true") is None
    assert _exact_number_text('"1.5"') is None
    assert _exact_number_text("hello") is None


def test_component_set_requests_the_typed_number_text(project):
    (project / "Temp").mkdir()
    (project / "Temp/UnityLockfile").touch()
    queue = project / "Library/UnityCli"
    captured = {}

    def reply():
        deadline = monotonic() + 5
        while monotonic() < deadline:
            for request in queue.glob("request-*/request.json"):
                text = request.read_text(encoding="utf-8")
                captured["payload"] = json.loads(text)
                captured["text"] = text
                pending = request.with_name("response.tmp")
                pending.write_text(json.dumps({"ok": True, "data": {}}), encoding="utf-8")
                pending.replace(request.with_name("response.json"))
                return
            sleep(0.02)
        raise AssertionError("no request arrived")

    with ThreadPoolExecutor(max_workers=1) as pool:
        worker = pool.submit(reply)
        result = CliRunner().invoke(cli, [
            "--project", str(project), "--json", "component", "set",
            "--id", "1", "--component", "Probe", "--property", "Amount",
            "--value", "1234567890.123456789012345678",
        ])
        worker.result()
    assert result.exit_code == 0, result.output
    assert captured["payload"]["ValueText"] == "1234567890.123456789012345678"
    assert '"1234567890.123456789012345678"' in captured["text"]
