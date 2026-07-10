from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from cli_anything.openrefine.core.operations import (
    column_addition,
    column_removal,
    load_operations,
    mass_edit,
    save_operations,
    text_transform,
)
from cli_anything.openrefine.core.project import OpenRefineService, _extract_project_id
from cli_anything.openrefine.core.session import SessionState, SessionStore
from cli_anything.openrefine import openrefine_cli
from cli_anything.openrefine.openrefine_cli import _repl_to_args, cli
from cli_anything.openrefine.utils.openrefine_backend import OpenRefineBackend, OpenRefineError, _coerce_json_or_text


class FakeBackend:
    def __init__(self, base_url="http://127.0.0.1:3333", timeout=30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.created = {"project": "123"}
        self.operations = []
        self.deleted = []

    def ping(self):
        return {"version": "3.10.1"}

    def list_projects(self):
        return {"projects": {"123": {"name": "Messy"}}}

    def get_project_metadata(self, project_id):
        return {"name": f"Project {project_id}", "project_id": project_id}

    def create_project(self, path, name=None, project_format=None):
        return dict(self.created, name=name, format=project_format, path=str(path))

    def apply_operations(self, project_id, operations):
        self.operations.append((project_id, operations))
        return {"code": "ok"}

    def export_rows(self, project_id, output_path, export_format="csv"):
        path = Path(output_path)
        path.write_text("name,value\nAlice,1\n", encoding="utf-8")
        return path

    def get_rows(self, project_id, start=0, limit=10):
        return {"rows": [{"cells": [{"v": "Alice"}]}], "start": start, "limit": limit, "project": project_id}

    def undo(self, project_id):
        return {"undone": project_id}

    def redo(self, project_id):
        return {"redone": project_id}


class RecordingOpenRefineBackend(OpenRefineBackend):
    def __init__(self, history):
        self.history = history
        self.calls = []

    def _json(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        if path == "/command/core/get-history":
            return self.history
        if path == "/command/core/undo-redo":
            return {"code": "ok", "data": kwargs["data"]}
        raise AssertionError(f"Unexpected endpoint: {path}")


def test_text_transform_shape():
    op = text_transform("Name", "value.trim()")
    assert op["op"] == "core/text-transform"
    assert op["columnName"] == "Name"
    assert op["expression"] == "value.trim()"


@pytest.mark.parametrize("column,expression", [("", "value"), ("Name", ""), ("   ", "value")])
def test_text_transform_rejects_blank(column, expression):
    with pytest.raises(ValueError):
        text_transform(column, expression)


def test_mass_edit_shape():
    op = mass_edit("City", {"NYC": "New York", "SF": "San Francisco"})
    assert op["op"] == "core/mass-edit"
    assert len(op["edits"]) == 2
    assert op["edits"][0]["from"] == ["NYC"]


def test_mass_edit_rejects_empty_edits():
    with pytest.raises(ValueError):
        mass_edit("City", {})


def test_mass_edit_stringifies_values():
    op = mass_edit("Code", {1: 2})
    assert op["edits"][0]["from"] == ["1"]
    assert op["edits"][0]["to"] == "2"


def test_column_addition_shape():
    op = column_addition("slug", "Name", "value.toLowercase()")
    assert op["op"] == "core/column-addition"
    assert op["newColumnName"] == "slug"
    assert op["baseColumnName"] == "Name"


def test_column_removal_shape():
    op = column_removal("unused")
    assert op == {"op": "core/column-removal", "columnName": "unused", "description": "Remove column unused"}


@pytest.mark.parametrize("factory,args", [(column_addition, ("", "Name", "value")), (column_removal, ("",))])
def test_column_builders_reject_blank(factory, args):
    with pytest.raises(ValueError):
        factory(*args)


def test_save_and_load_operations_roundtrip(tmp_path):
    path = tmp_path / "ops.json"
    ops = [text_transform("Name", "value.trim()")]
    save_operations(ops, path)
    assert load_operations(path) == ops


def test_load_operations_rejects_non_list(tmp_path):
    path = tmp_path / "ops.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        load_operations(path)


def test_load_operations_rejects_non_object_item(tmp_path):
    path = tmp_path / "ops.json"
    path.write_text("[1]", encoding="utf-8")
    with pytest.raises(ValueError):
        load_operations(path)


def test_session_defaults():
    state = SessionState()
    assert state.base_url == "http://127.0.0.1:3333"
    assert state.project_id is None
    assert state.history == []


def test_session_to_from_dict_roundtrip():
    state = SessionState(project_id="abc", project_name="Demo", last_export="out.csv", history=[{"action": "x"}])
    assert SessionState.from_dict(state.to_dict()).to_dict() == state.to_dict()


def test_session_load_missing_returns_default(tmp_path):
    assert SessionStore(tmp_path / "missing.json").load().project_id is None


def test_session_save_creates_parent_and_loads(tmp_path):
    store = SessionStore(tmp_path / "nested" / "session.json")
    store.save(SessionState(project_id="p1"))
    assert store.load().project_id == "p1"


def test_session_effective_base_url_prefers_requested(tmp_path):
    store = SessionStore(tmp_path / "s.json")
    store.save(SessionState(base_url="http://127.0.0.1:4444"))
    assert store.effective_base_url("http://127.0.0.1:5555") == "http://127.0.0.1:5555"


def test_session_effective_base_url_reuses_session(tmp_path):
    store = SessionStore(tmp_path / "s.json")
    store.save(SessionState(base_url="http://127.0.0.1:4444"))
    assert store.effective_base_url() == "http://127.0.0.1:4444"


def test_session_record_clears_future():
    store = SessionStore()
    state = SessionState(future=[{"action": "redo"}])
    store.record(state, "import", {"project": "p1"})
    assert state.history[-1]["action"] == "import"
    assert state.future == []


def test_session_undo_moves_to_future():
    store = SessionStore()
    state = SessionState(history=[{"action": "import"}])
    undone = store.undo(state)
    assert undone["action"] == "import"
    assert state.future == [undone]


def test_session_redo_moves_to_history():
    store = SessionStore()
    state = SessionState(future=[{"action": "import"}])
    redone = store.redo(state)
    assert redone["action"] == "import"
    assert state.history == [redone]


def test_session_undo_empty_raises():
    with pytest.raises(ValueError):
        SessionStore().undo(SessionState())


def test_session_redo_empty_raises():
    with pytest.raises(ValueError):
        SessionStore().redo(SessionState())


@pytest.mark.parametrize("payload,expected", [
    ({"project": 123}, "123"),
    ({"projectID": "abc"}, "abc"),
    ({"project_id": "def"}, "def"),
    ({"id": "ghi"}, "ghi"),
    ({"Location": "http://x/project/jkl"}, "jkl"),
])
def test_extract_project_id_variants(payload, expected):
    assert _extract_project_id(payload) == expected


def test_extract_project_id_failure():
    with pytest.raises(ValueError):
        _extract_project_id({"ok": True})


def test_service_status(tmp_path):
    service = OpenRefineService(FakeBackend(), SessionStore(tmp_path / "s.json"))
    assert service.status()["backend"]["version"] == "3.10.1"


def test_service_list_projects(tmp_path):
    service = OpenRefineService(FakeBackend(), SessionStore(tmp_path / "s.json"))
    assert "123" in service.list_projects()["projects"]


def test_service_open_project_persists_session(tmp_path):
    store = SessionStore(tmp_path / "s.json")
    result = OpenRefineService(FakeBackend(base_url="http://127.0.0.1:4444"), store).open_project("123")
    assert result["project_name"] == "Project 123"
    assert store.load().project_id == "123"
    assert store.load().base_url == "http://127.0.0.1:4444"


def test_service_import_file_persists_project(tmp_path):
    csv = tmp_path / "input.csv"
    csv.write_text("a\n1\n", encoding="utf-8")
    store = SessionStore(tmp_path / "s.json")
    result = OpenRefineService(FakeBackend(base_url="http://127.0.0.1:4444"), store).import_file(csv, name="Imported")
    assert result["project_id"] == "123"
    assert store.load().project_name == "Imported"
    assert store.load().base_url == "http://127.0.0.1:4444"


def test_service_apply_operations_uses_session_project(tmp_path):
    ops = tmp_path / "ops.json"
    save_operations([text_transform("a", "value.trim()")], ops)
    store = SessionStore(tmp_path / "s.json")
    store.save(SessionState(project_id="123"))
    backend = FakeBackend()
    result = OpenRefineService(backend, store).apply_operations_file(ops)
    assert result["operation_count"] == 1
    assert backend.operations[0][0] == "123"


def test_service_apply_operations_requires_project(tmp_path):
    ops = tmp_path / "ops.json"
    save_operations([text_transform("a", "value.trim()")], ops)
    with pytest.raises(ValueError):
        OpenRefineService(FakeBackend(), SessionStore(tmp_path / "s.json")).apply_operations_file(ops)


def test_service_export_writes_output_and_session(tmp_path):
    store = SessionStore(tmp_path / "s.json")
    store.save(SessionState(project_id="123"))
    output = tmp_path / "out.csv"
    result = OpenRefineService(FakeBackend(), store).export_rows(output)
    assert output.read_text(encoding="utf-8").startswith("name,value")
    assert result["bytes"] > 0
    assert store.load().last_export == str(output)


def test_service_rows_uses_project_override(tmp_path):
    result = OpenRefineService(FakeBackend(), SessionStore(tmp_path / "s.json")).rows(project_id="override", limit=3)
    assert result["project"] == "override"
    assert result["limit"] == 3


def test_service_rows_requires_project(tmp_path):
    with pytest.raises(ValueError):
        OpenRefineService(FakeBackend(), SessionStore(tmp_path / "s.json")).rows()


def test_service_undo_local_when_no_project(tmp_path):
    store = SessionStore(tmp_path / "s.json")
    store.save(SessionState(history=[{"action": "open"}]))
    result = OpenRefineService(FakeBackend(), store).undo()
    assert result["mode"] == "session"


def test_service_redo_local_when_no_project(tmp_path):
    store = SessionStore(tmp_path / "s.json")
    store.save(SessionState(future=[{"action": "open"}]))
    result = OpenRefineService(FakeBackend(), store).redo()
    assert result["mode"] == "session"


def test_service_undo_backend_when_project(tmp_path):
    store = SessionStore(tmp_path / "s.json")
    store.save(SessionState(project_id="123", history=[{"action": "apply"}]))
    result = OpenRefineService(FakeBackend(), store).undo()
    assert result["mode"] == "backend"
    assert result["response"]["undone"] == "123"


def test_service_redo_backend_when_project(tmp_path):
    store = SessionStore(tmp_path / "s.json")
    store.save(SessionState(project_id="123", future=[{"action": "apply"}]))
    result = OpenRefineService(FakeBackend(), store).redo()
    assert result["mode"] == "backend"
    assert result["response"]["redone"] == "123"


@pytest.mark.parametrize("text,expected", [("{\"a\": 1}", {"a": 1}), ("plain", "plain"), ("", "")])
def test_coerce_json_or_text(text, expected):
    assert _coerce_json_or_text(text) == expected


def test_backend_undo_uses_openrefine_undo_id():
    backend = RecordingOpenRefineBackend({"past": [{"id": 10}, {"id": 11}], "future": []})
    result = backend.undo("123")
    assert result["data"] == {"project": "123", "undoID": "11"}


def test_backend_redo_uses_openrefine_last_done_id():
    backend = RecordingOpenRefineBackend({"past": [], "future": [{"id": 12}, {"id": 13}]})
    result = backend.redo("123")
    assert result["data"] == {"project": "123", "lastDoneID": "12"}


def test_backend_undo_without_history_raises():
    with pytest.raises(OpenRefineError):
        RecordingOpenRefineBackend({"past": []}).undo("123")


def test_backend_redo_without_history_raises():
    with pytest.raises(OpenRefineError):
        RecordingOpenRefineBackend({"future": []}).redo("123")


@pytest.mark.parametrize("parts,args", [
    (["projects"], ["project", "list"]),
    (["import", "x.csv"], ["project", "import", "x.csv"]),
    (["import", "x.csv", "Demo"], ["project", "import", "x.csv", "--name", "Demo"]),
    (["open", "123"], ["project", "open", "123"]),
    (["rows"], ["data", "rows", "--limit", "10"]),
    (["rows", "5"], ["data", "rows", "--limit", "5"]),
    (["export", "out.csv"], ["data", "export", "out.csv"]),
    (["export", "out.tsv", "tsv"], ["data", "export", "out.tsv", "--format", "tsv"]),
    (["undo"], ["session", "undo"]),
    (["redo"], ["session", "redo"]),
])
def test_repl_to_args(parts, args):
    assert _repl_to_args(parts) == args


@pytest.mark.parametrize("parts", [["import"], ["open"], ["export"]])
def test_repl_to_args_rejects_incomplete_commands(parts):
    with pytest.raises(ValueError):
        _repl_to_args(parts)


def test_cli_uses_session_base_url_when_not_supplied(tmp_path, monkeypatch):
    session = tmp_path / "s.json"
    SessionStore(session).save(SessionState(base_url="http://127.0.0.1:4444", project_id="123"))
    seen = {}

    class RecordingBackend(FakeBackend):
        def get_rows(self, project_id, start=0, limit=10):
            seen["base_url"] = self.base_url
            return super().get_rows(project_id, start=start, limit=limit)

    monkeypatch.setattr(openrefine_cli, "OpenRefineBackend", RecordingBackend)
    result = CliRunner().invoke(cli, ["--json", "--session", str(session), "data", "rows"])
    assert result.exit_code == 0
    assert seen["base_url"] == "http://127.0.0.1:4444"


def test_cli_session_show_invalid_json_uses_json_error(tmp_path):
    session = tmp_path / "s.json"
    session.write_text("{bad", encoding="utf-8")
    result = CliRunner().invoke(cli, ["--json", "--session", str(session), "session", "show"])
    assert result.exit_code == 1
    assert json.loads(result.stderr)["ok"] is False


def test_cli_help_runs():
    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Agent-native CLI" in result.output


def test_cli_ops_text_transform_json(tmp_path):
    output = tmp_path / "ops.json"
    result = CliRunner().invoke(cli, ["--json", "ops", "text-transform", str(output), "--column", "Name", "--expression", "value.trim()"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["operations"][0]["op"] == "core/text-transform"
    assert output.exists()


def test_cli_ops_mass_edit_json(tmp_path):
    output = tmp_path / "ops.json"
    result = CliRunner().invoke(cli, ["--json", "ops", "mass-edit", str(output), "--column", "City", "--edit", "NYC=New York"])
    assert result.exit_code == 0
    assert json.loads(output.read_text(encoding="utf-8"))[0]["op"] == "core/mass-edit"


def test_cli_ops_mass_edit_bad_mapping(tmp_path):
    output = tmp_path / "ops.json"
    result = CliRunner().invoke(cli, ["ops", "mass-edit", str(output), "--column", "City", "--edit", "bad"])
    assert result.exit_code != 0


def test_cli_ops_mass_edit_bad_mapping_json_error(tmp_path):
    output = tmp_path / "ops.json"
    result = CliRunner().invoke(cli, ["--json", "ops", "mass-edit", str(output), "--column", "City", "--edit", "bad"])
    assert result.exit_code == 1
    assert json.loads(result.stderr) == {"error": "--edit must be in old=new form", "ok": False}


def test_cli_ops_add_column_json(tmp_path):
    output = tmp_path / "ops.json"
    result = CliRunner().invoke(cli, ["--json", "ops", "add-column", str(output), "--name", "slug", "--source-column", "Name", "--expression", "value"])
    assert result.exit_code == 0
    assert json.loads(result.output)["operations"][0]["newColumnName"] == "slug"


def test_cli_ops_remove_column_json(tmp_path):
    output = tmp_path / "ops.json"
    result = CliRunner().invoke(cli, ["--json", "ops", "remove-column", str(output), "--column", "unused"])
    assert result.exit_code == 0
    assert json.loads(result.output)["operations"][0]["columnName"] == "unused"


def test_cli_session_show_json_uses_custom_path(tmp_path):
    session = tmp_path / "s.json"
    result = CliRunner().invoke(cli, ["--json", "--session", str(session), "session", "show"])
    assert result.exit_code == 0
    assert json.loads(result.output)["base_url"].startswith("http")


def test_cli_default_enters_repl_and_exits():
    result = CliRunner().invoke(cli, input="exit\n")
    assert result.exit_code == 0
    assert "cli-anything" in result.output
    assert "Openrefine" in result.output


def test_openrefine_error_is_runtime_error():
    assert issubclass(OpenRefineError, RuntimeError)
