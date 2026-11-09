"""Backend-independent validation of the public command inputs and session IO."""
import importlib.metadata
import json

import pytest

from cli_anything.turso.core.session import SessionStore, database_path
from cli_anything.turso.core.values import (
    TursoError, bind_value, compile_operation, identifier, json_value, parameters,
    parse_json, predicate,
)
from cli_anything.turso.turso_cli import Runtime, execute
from cli_anything.turso.utils import turso_backend


def test_parameter_types_and_blob_round_trip():
    values = [None, True, -(2**63), 2**63 - 1, 1.5, 'quote"|\n雪', {"$blob": "00ff"}]
    assert parameters(values) == values[:-1] + [b"\x00\xff"]
    assert parameters({"name": "a", "raw": {"$blob": "ff"}}) == {"name": "a", "raw": b"\xff"}
    assert json_value([b"\x00", float("inf")]) == [{"$blob": "00"}, {"$float": "inf"}]


@pytest.mark.parametrize("value", [2**63, -(2**63)-1, float("inf"), float("nan"), [], {}, {"$blob": "xyz"}])
def test_invalid_bound_values(value):
    with pytest.raises(TursoError):
        bind_value(value)


@pytest.mark.parametrize("text", ["NaN", "Infinity", "[1,]", "{"])
def test_invalid_json(text):
    with pytest.raises(TursoError):
        parse_json(text)


def test_bad_parameter_shape():
    with pytest.raises(TursoError):
        parameters("value")


def test_identifiers_and_predicates():
    assert identifier('x"; DROP TABLE t;--') == '"x""; DROP TABLE t;--"'
    assert predicate({"id": 1, "name": None}) == (' WHERE "id" = ? AND "name" IS NULL', [1])
    with pytest.raises(TursoError):
        identifier("bad\x00name")


def test_crud_compilation_binds_values():
    sql, params = compile_operation({"op": "insert", "table": 'odd"table', "values": {"name": "'); DROP TABLE t;--"}})
    assert sql == 'INSERT INTO "odd""table" ("name") VALUES (?)'
    assert params == ["'); DROP TABLE t;--"]
    sql, params = compile_operation({"op": "update", "table": "t", "values": {"v": 7}, "where": {"id": None}})
    assert sql == 'UPDATE "t" SET "v" = ? WHERE "id" IS NULL'
    assert params == [7]
    assert compile_operation({"op": "delete", "table": "t", "all": True}) == ('DELETE FROM "t"', [])


@pytest.mark.parametrize("op", [
    {"op": "delete", "table": "t"},
    {"op": "update", "table": "t", "values": {}},
    {"op": "delete", "table": "t", "where": {"id": 1}, "all": True},
    {"op": "delete", "table": "t", "all": "yes"},
    {"op": "commit", "table": "t"},
    {"op": "insert", "table": "t", "values": {"a": 1}, "sql": "COMMIT"},
])
def test_invalid_crud_operations(op):
    with pytest.raises(TursoError):
        compile_operation(op)


def test_session_round_trip_and_malformed_file_preservation(tmp_path):
    path = tmp_path / "selection.json"
    store = SessionStore(path)
    assert store.load() is None
    store.save("/private/new file.db")
    assert store.load() == "/private/new file.db"
    store.save(None)
    assert store.load() is None
    path.write_text("not JSON")
    with pytest.raises(TursoError):
        store.save("another")
    assert path.read_text() == "not JSON"


def test_no_implicit_creation(tmp_path):
    missing = tmp_path / "missing.db"
    with pytest.raises(TursoError, match="db create"):
        database_path(str(missing))
    assert not missing.exists()
    for value in [":memory:", "https://example.test/db", "file:other.db"]:
        with pytest.raises(TursoError):
            database_path(value)


def test_missing_dependency(monkeypatch):
    def missing(name):
        raise importlib.metadata.PackageNotFoundError(name)
    monkeypatch.setattr(importlib.metadata, "version", missing)
    with pytest.raises(TursoError, match="pyturso==0.8.3"):
        turso_backend.load_sdk()


def test_unsupported_dependency(monkeypatch):
    monkeypatch.setattr(importlib.metadata, "version", lambda name: "99.0.0")
    with pytest.raises(TursoError, match="Unsupported pyturso"):
        turso_backend.load_sdk()


def test_usage_error_is_structured(capsys):
    assert execute(["--json", "table", "insert"], Runtime()) == 2
    out = capsys.readouterr()
    assert not out.out
    assert json.loads(out.err)["ok"] is False


def test_missing_selection_is_structured(capsys):
    assert execute(["--json", "schema"], Runtime()) == 1
    out = capsys.readouterr()
    assert not out.out
    assert json.loads(out.err)["database"] is None


def test_sql_parameter_slots_ignore_literals_and_comments():
    from cli_anything.turso.core.values import sql_parameters
    sql = "SELECT '?', \"@column\", `:column`, [?:column], :x, @x, :x, ?4 /* ? */ -- :ignored\n"
    assert sql_parameters(sql, {"x": "bound", "4": 4}) == ["bound", "bound", None, 4]
    assert sql_parameters("SELECT ?2, ?", [None, 2, 3]) == [None, 2, 3]
    assert sql_parameters("SELECT :x, ?1", {"x": 7}) == [7]
    with pytest.raises(TursoError, match="Missing named"):
        sql_parameters("SELECT :x, :y", {"x": 1})
    with pytest.raises(TursoError, match="Expected 2"):
        sql_parameters("SELECT ?, ?", [1])
    with pytest.raises(TursoError, match="Extended"):
        sql_parameters("SELECT $x::suffix", {"x": 1})
