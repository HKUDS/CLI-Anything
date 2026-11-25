"""Behavioral tests using temporary databases and the actual SQLite engine."""

import base64
import csv
import json
from pathlib import Path
import sqlite3

import pytest

from cli_anything.sqlite.core import database as db
from cli_anything.sqlite.utils.sqlite_backend import identifier, parameters


@pytest.fixture
def path(tmp_path):
    path = tmp_path / "inventory.db"
    db.create(path)
    db.execute(path, "CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, quantity INTEGER)")
    return path


def test_create_real_database_and_refuse_overwrite(tmp_path):
    path = tmp_path / "new.db"
    data = db.create(path)
    assert data["sqlite_version"] == sqlite3.sqlite_version
    assert path.read_bytes().startswith(b"SQLite format 3\x00")
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        db.create(path)
    assert path.read_bytes() == original


@pytest.mark.parametrize("command", [db.info, db.check, db.schema,
                                    lambda path: db.query(path, "SELECT 1"),
                                    lambda path: db.execute(path, "CREATE TABLE t(x)")])
def test_missing_database_is_not_created(tmp_path, command):
    path = tmp_path / "missing.db"
    with pytest.raises(ValueError, match="does not exist"):
        command(path)
    assert not path.exists()


def test_uri_special_characters(tmp_path):
    path = tmp_path / "data ?mode=ro#資料.db"
    db.create(path)
    db.execute(path, "CREATE TABLE t(x)")
    db.execute(path, "INSERT INTO t VALUES (?)", ["works"])
    assert db.query(path, "SELECT * FROM t")["rows"] == [["works"]]


def test_named_and_positional_parameters_prevent_sql_interpolation(path):
    value = "O'Reilly'); DROP TABLE items; --\n資料"
    db.execute(path, "INSERT INTO items(name, quantity) VALUES (:name, :quantity)",
               {"name": value, "quantity": 3})
    assert db.query(path, "SELECT name FROM items WHERE quantity > ?", [2])["rows"] == [[value]]


def test_blobs_nulls_and_duplicate_column_names(path):
    blob = {"$base64": base64.b64encode(b"\x00\xff\n").decode()}
    data = db.query(path, "SELECT ? AS value, NULL AS value, ? AS value", [blob, True])
    assert data["columns"] == ["value", "value", "value"]
    assert data["rows"] == [[blob, None, 1]]
    json.dumps(data, allow_nan=False)


def test_nonfinite_database_value_is_json_safe(path):
    data = db.query(path, "SELECT 1e999, -1e999")
    assert data["rows"] == [[{"$float": "inf"}, {"$float": "-inf"}]]
    json.dumps(data, allow_nan=False)


@pytest.mark.parametrize("value", [None, "x", 1, [[1]], [{"nested": 1}], [float("nan")],
                                  [float("inf")], [2**63], [{"$base64": "!!"}],
                                  [{"$base64": 123}], {1: "value"}])
def test_invalid_parameters_rejected(value):
    with pytest.raises(ValueError):
        parameters(value)


@pytest.mark.parametrize("sql", [
    "DELETE FROM items", "INSERT INTO items(name) VALUES ('bad')",
    "CREATE TABLE bad(x)", "WITH c(x) AS (VALUES ('bad')) INSERT INTO items(name) SELECT x FROM c",
])
def test_query_is_always_read_only(path, sql):
    with pytest.raises(sqlite3.DatabaseError):
        db.query(path, sql)
    assert db.query(path, "SELECT * FROM items")["rows"] == []
    assert [obj["name"] for obj in db.schema(path)["objects"]] == ["items"]


@pytest.mark.parametrize("sql", ["COMMIT", "ROLLBACK", "BEGIN", "SAVEPOINT escape",
                                  "PRAGMA user_version=7", "ATTACH DATABASE ':memory:' AS other",
                                  "SELECT load_extension('anything')"])
def test_sql_cannot_escape_transaction(path, sql):
    with pytest.raises(sqlite3.DatabaseError):
        db.batch(path, [{"sql": "INSERT INTO items(name) VALUES ('before')"}, {"sql": sql}])
    assert db.query(path, "SELECT * FROM items")["rows"] == []


def test_batch_rolls_back_ddl_and_data(path):
    with pytest.raises(sqlite3.IntegrityError):
        db.batch(path, [
            {"sql": "CREATE TABLE transient(value TEXT)"},
            {"sql": "INSERT INTO items(name) VALUES (?)", "params": ["duplicate"]},
            {"sql": "INSERT INTO items(name) VALUES (?)", "params": ["duplicate"]},
        ])
    assert db.query(path, "SELECT * FROM items")["rows"] == []
    assert "transient" not in [obj["name"] for obj in db.schema(path)["objects"]]


def test_batch_commits_and_reports_changes_including_trigger_effects(path):
    db.execute(path, "CREATE TABLE audit(value TEXT)")
    db.execute(path, "CREATE TRIGGER inserted AFTER INSERT ON items "
               "BEGIN INSERT INTO audit VALUES(new.name); END")
    report = db.batch(path, [{"sql": "INSERT INTO items(name) VALUES (?)", "params": ["one"]},
                            {"sql": "UPDATE items SET quantity = ?", "params": [5]}])
    assert report["committed"] is True
    assert report["changes"] == 3
    assert db.query(path, "SELECT * FROM audit")["rows"] == [["one"]]


@pytest.mark.parametrize("statements", [[], {}, ["SELECT 1"], [{"sql": ""}],
                                       [{"sql": "SELECT 1", "extra": 1}], [{"params": []}]])
def test_invalid_batch_contract(path, statements):
    with pytest.raises(ValueError):
        db.batch(path, statements)


def test_multiple_statements_cannot_bypass_batch(path):
    with pytest.raises((sqlite3.ProgrammingError, sqlite3.Warning)):
        db.execute(path, "INSERT INTO items(name) VALUES ('x'); DELETE FROM items;")
    assert db.query(path, "SELECT * FROM items")["rows"] == []


def test_results_are_bounded_but_returning_writes_complete(path):
    db.execute(path, "CREATE TABLE numbers(x INTEGER)")
    report = db.execute(path, "WITH RECURSIVE n(x) AS (VALUES(1) UNION ALL "
                        "SELECT x+1 FROM n WHERE x < 1100) INSERT INTO numbers SELECT x FROM n RETURNING x")
    assert report["changes"] == 1100
    assert report["statements"][0]["truncated"] is True
    assert len(report["statements"][0]["rows"]) == 1000
    result = db.query(path, "SELECT * FROM numbers ORDER BY x", limit=3)
    assert result == {"columns": ["x"], "rows": [[1], [2], [3]], "row_count": 3, "truncated": True}
    assert db.query(path, "SELECT * FROM numbers WHERE x < 4", limit=3)["truncated"] is False


def test_query_timeout_interrupts_actual_sqlite_work(path):
    with pytest.raises(sqlite3.OperationalError, match="interrupted"):
        db.query(path, "WITH RECURSIVE n(x) AS (VALUES(1) UNION ALL SELECT x+1 FROM n) SELECT sum(x) FROM n",
                 timeout=0.02)
    assert db.query(path, "SELECT 1")["rows"] == [[1]]


def test_busy_database_reports_failure_without_partial_write(path):
    conn = sqlite3.connect(path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            db.execute(path, "INSERT INTO items(name) VALUES ('x')", timeout=0.02)
    finally:
        conn.rollback()
        conn.close()
    assert db.query(path, "SELECT * FROM items")["rows"] == []


def test_batch_timeout_rolls_back_prior_schema_and_data(path):
    with pytest.raises((sqlite3.OperationalError, TimeoutError)):
        db.batch(path, [
            {"sql": "CREATE TABLE transient(x)"},
            {"sql": "INSERT INTO items(name) VALUES('before-timeout')"},
            {"sql": "WITH RECURSIVE n(x) AS (VALUES(1) UNION ALL SELECT x+1 FROM n) SELECT sum(x) FROM n"},
        ], timeout=0.02)
    assert db.query(path, "SELECT * FROM items")["rows"] == []
    assert "transient" not in [obj["name"] for obj in db.schema(path)["objects"]]


def test_deferred_foreign_key_failure_at_commit_rolls_back(path):
    db.execute(path, "CREATE TABLE child(parent REFERENCES items(id) DEFERRABLE INITIALLY DEFERRED)")
    with pytest.raises(sqlite3.IntegrityError):
        db.batch(path, [{"sql": "INSERT INTO items(id,name) VALUES(1,'valid')"},
                        {"sql": "INSERT INTO child VALUES(999)"}])
    assert db.query(path, "SELECT * FROM items")["rows"] == []
    assert db.query(path, "SELECT * FROM child")["rows"] == []


def test_schema_preserves_user_names_similar_to_sqlite_prefix(path):
    db.execute(path, "CREATE TABLE sqliteXdata(x)")
    assert {obj["name"] for obj in db.schema(path)["objects"]} == {"items", "sqliteXdata"}
    assert db.info(path)["schema_objects"] == 2


def test_schema_reports_generated_columns_indexes_foreign_keys_and_views(path):
    db.batch(path, [{"sql": "CREATE TABLE child(id INTEGER REFERENCES items(id), value TEXT, "
                    "upper_value TEXT GENERATED ALWAYS AS (upper(value)))"},
                   {"sql": "CREATE INDEX child_value ON child(value)"},
                   {"sql": "CREATE VIEW named_items AS SELECT name FROM items"}])
    described = db.schema(path, "child")
    assert described["columns"][2]["hidden"] == 2
    assert described["foreign_keys"][0]["table"] == "items"
    assert described["indexes"][0]["columns"] == ["value"]
    assert db.schema(path, "named_items")["type"] == "view"
    with pytest.raises(ValueError, match="No table or view"):
        db.schema(path, "absent")


def test_quoted_identifiers_are_not_sql(path):
    name = 'odd "table; DROP TABLE items;--'
    db.execute(path, f"CREATE TABLE {identifier(name)} ({identifier('a b')} TEXT)")
    assert db.schema(path, name)["columns"][0]["name"] == "a b"
    with pytest.raises(ValueError):
        identifier("nul\x00name")


def test_csv_round_trip_unicode_newlines_and_reordered_columns(path, tmp_path):
    source = tmp_path / "source.csv"
    source.write_text('quantity,name\n3,"資料, first\nsecond"\n4,"quote""text"\n', encoding="utf-8")
    assert db.import_csv(path, "items", source)["inserted_rows"] == 2
    output = tmp_path / "output.csv"
    assert db.export_csv(path, "SELECT quantity, name FROM items ORDER BY id", output)["exported_rows"] == 2
    with source.open(newline="") as before, output.open(newline="") as after:
        assert list(csv.reader(before)) == list(csv.reader(after))


@pytest.mark.parametrize("text", ["", "name,name\nx,y\n", "name,NAME\nx,y\n", ",name\nx,y\n", "name\nx\ny,z\n",
                                 'name\nx\n"unterminated', "name\nx\nx\n", "absent\nvalue\n"])
def test_invalid_csv_rolls_back_every_row(path, tmp_path, text):
    source = tmp_path / "bad.csv"
    source.write_text(text)
    with pytest.raises((ValueError, csv.Error, sqlite3.Error)):
        db.import_csv(path, "items", source)
    assert db.query(path, "SELECT * FROM items")["rows"] == []


def test_header_only_csv_validates_target(path, tmp_path):
    source = tmp_path / "empty.csv"
    source.write_text("name\n")
    assert db.import_csv(path, "items", source)["inserted_rows"] == 0
    with pytest.raises(sqlite3.Error):
        db.import_csv(path, "missing", source)
    source.write_text("missing_column\n")
    with pytest.raises(sqlite3.Error):
        db.import_csv(path, "items", source)


def test_csv_foreign_key_failure_rolls_back(path, tmp_path):
    db.execute(path, "INSERT INTO items(id,name) VALUES(1, 'parent')")
    db.execute(path, "CREATE TABLE child(parent INTEGER REFERENCES items(id))")
    source = tmp_path / "children.csv"
    source.write_text("parent\n1\n2\n")
    with pytest.raises(sqlite3.IntegrityError):
        db.import_csv(path, "child", source)
    assert db.query(path, "SELECT * FROM child")["rows"] == []


def test_csv_reports_ignored_rows_separately(path, tmp_path):
    db.execute(path, "CREATE TABLE ignored(name TEXT UNIQUE ON CONFLICT IGNORE)")
    source = tmp_path / "ignored.csv"
    source.write_text("name\nx\nx\n")
    report = db.import_csv(path, "ignored", source)
    assert report["processed_rows"] == 2
    assert report["inserted_rows"] == 1
    assert db.query(path, "SELECT * FROM ignored")["rows"] == [["x"]]


def test_export_refuses_existing_files_and_cleans_partial_output(path, tmp_path):
    output = tmp_path / "out.csv"
    output.write_text("keep")
    with pytest.raises(FileExistsError):
        db.export_csv(path, "SELECT 1", output)
    assert output.read_text() == "keep"
    output.unlink()
    with pytest.raises(ValueError, match="BLOB"):
        db.export_csv(path, "SELECT 'first' UNION ALL SELECT x'ff'", output)
    assert not output.exists()


def test_export_rejects_writes(path, tmp_path):
    output = tmp_path / "out.csv"
    with pytest.raises(sqlite3.DatabaseError):
        db.export_csv(path, "INSERT INTO items(name) VALUES('bad') RETURNING name", output)
    assert not output.exists()


def test_backup_includes_committed_wal_data_and_is_independently_readable(path, tmp_path):
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("INSERT INTO items(name, quantity) VALUES('wal-item', 42)")
        conn.commit()
        assert Path(str(path) + "-wal").exists()
        output = tmp_path / "copy.db"
        report = db.backup(path, output)
        assert report["bytes"] > 0
        copied = sqlite3.connect(output)
        try:
            assert copied.execute("SELECT name,quantity FROM items").fetchall() == [("wal-item", 42)]
        finally:
            copied.close()
        assert db.check(output)["ok"] is True
    finally:
        conn.close()


def test_backup_refuses_source_existing_file_and_symlink(path, tmp_path):
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        db.backup(path, path)
    link = tmp_path / "symlink.db"
    try:
        link.symlink_to(path)
    except OSError:
        pytest.skip("Symlink creation unavailable on this host")
    with pytest.raises(FileExistsError):
        db.backup(path, link)
    assert path.read_bytes() == original


def test_integrity_check_reports_foreign_key_violations(path):
    conn = sqlite3.connect(path)
    try:
        conn.execute("CREATE TABLE child(parent INTEGER REFERENCES items(id))")
        conn.execute("INSERT INTO child VALUES(999)")
        conn.commit()
    finally:
        conn.close()
    report = db.check(path, full=True)
    assert report["ok"] is False
    assert report["foreign_key_violations"][0][0] == "child"


def test_corrupt_source_does_not_leave_backup(tmp_path):
    source = tmp_path / "corrupt.db"
    source.write_text("not a sqlite database")
    output = tmp_path / "out.db"
    with pytest.raises(sqlite3.DatabaseError):
        db.backup(source, output)
    assert not output.exists()
