"""Installed-command workflows, with independent native sqlite3 readback."""

import csv
import json
import os
import shlex
import shutil
import sqlite3
import subprocess
import sys

import pytest


def _resolve_cli(name):
    """Prefer the installed entry point; require it for release validation."""
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1":
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    module = name.replace("cli-anything-", "cli_anything.") + "." + name.split("-")[-1] + "_cli"
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m {module}")
    return [sys.executable, "-m", module]


CLI_BASE = _resolve_cli("cli-anything-sqlite")


def run(*args, input=None, code=0):
    completed = subprocess.run(CLI_BASE + list(map(str, args)), input=input,
                               capture_output=True, text=True, timeout=20)
    assert completed.returncode == code, (completed.stdout, completed.stderr)
    return completed.stdout


def command(path, *args, code=0):
    output = run("--json", "--database", path, *args, code=code)
    return json.loads(output)


@pytest.fixture
def path(tmp_path):
    path = tmp_path / "inventory ?#資料.db"
    data = json.loads(run("--json", "database", "create", path))
    assert data["path"] == str(path)
    return path


def native(path, sql):
    executable = shutil.which("sqlite3")
    assert executable, "E2E readback requires the real sqlite3 executable on PATH."
    completed = subprocess.run([executable, "-json", str(path), sql],
                               capture_output=True, text=True, check=True, timeout=10)
    return json.loads(completed.stdout or "[]")


def test_help_and_version():
    assert "import-csv" in run("--help")
    assert "1.0.0" in run("--version")
    assert "--params" in run("query", "--help")


def test_inventory_csv_report_and_backup(path, tmp_path):
    migration = tmp_path / "schema.json"
    migration.write_text(json.dumps([
        {"sql": "CREATE TABLE items(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, quantity INTEGER)"},
        {"sql": "CREATE INDEX by_quantity ON items(quantity)"},
    ]))
    assert command(path, "batch", migration)["committed"] is True
    source = tmp_path / "items.csv"
    source.write_text('name,quantity\n"資料, first",3\nsecond,1\n', encoding="utf-8")
    assert command(path, "import-csv", "items", source)["inserted_rows"] == 2
    report = command(path, "query", "SELECT name, quantity FROM items WHERE quantity > :min",
                     "--params", '{"min":2}')
    assert report["rows"] == [["資料, first", 3]]
    assert command(path, "schema", "describe", "items")["indexes"][0]["name"] == "by_quantity"
    assert {obj["name"] for obj in command(path, "schema", "list")["objects"]} == {"items", "by_quantity"}
    output = tmp_path / "report.csv"
    assert command(path, "export-csv", "SELECT name,quantity FROM items ORDER BY id", output)["exported_rows"] == 2
    with output.open(encoding="utf-8", newline="") as stream:
        assert list(csv.reader(stream)) == [["name", "quantity"], ["資料, first", "3"], ["second", "1"]]
    copy = tmp_path / "backup.db"
    assert command(path, "database", "backup", copy)["method"] == "sqlite-online-backup"
    assert native(copy, "SELECT name,quantity FROM items ORDER BY id") == [
        {"name": "資料, first", "quantity": 3}, {"name": "second", "quantity": 1}]
    assert command(copy, "database", "check", "--full")["ok"] is True


def test_parameters_blobs_and_bounded_results(path):
    command(path, "execute", "CREATE TABLE data(value BLOB)")
    assert command(path, "execute", "INSERT INTO data VALUES (?)", "--params", '[{"$base64":"AP8="}]')["changes"] == 1
    assert command(path, "query", "SELECT value, NULL AS value FROM data")["rows"] == [[{"$base64": "AP8="}, None]]
    result = command(path, "query", "SELECT 1 AS x UNION ALL SELECT 2", "--limit", "1")
    assert result["rows"] == [[1]] and result["truncated"] is True


def test_failed_migration_leaves_no_schema_or_rows(path, tmp_path):
    command(path, "execute", "CREATE TABLE items(name TEXT UNIQUE)")
    batch = tmp_path / "failed.json"
    batch.write_text(json.dumps([
        {"sql": "CREATE TABLE transient(x)"},
        {"sql": "INSERT INTO items VALUES (?)", "params": ["same"]},
        {"sql": "INSERT INTO items VALUES (?)", "params": ["same"]},
    ]))
    assert "UNIQUE" in command(path, "batch", batch, code=1)["error"]
    assert native(path, "SELECT * FROM items") == []
    assert native(path, "SELECT name FROM sqlite_schema WHERE name='transient'") == []


@pytest.mark.parametrize("sql", ["DELETE FROM items", "COMMIT", "PRAGMA user_version=7",
                                  "ATTACH DATABASE ':memory:' AS external"])
def test_query_rejects_mutation_and_transaction_control(path, sql):
    command(path, "execute", "CREATE TABLE items(x)")
    command(path, "execute", "INSERT INTO items VALUES(42)")
    assert command(path, "query", sql, code=1)["error"]
    assert native(path, "SELECT * FROM items") == [{"x": 42}]


@pytest.mark.parametrize("args,code", [
    (["query", "SELECT ?", "--params", "{"], 1),
    (["query", "SELECT ?", "--params", "[[]]"], 1),
    (["query", "SELECT 1", "--limit", "0"], 2),
    (["query"], 2),
    (["missing-command"], 2),
    (["execute", "CREATE TABLE t(x); CREATE TABLE u(x)"], 1),
    (["batch", "/missing-sqlite-batch.json"], 2),
])
def test_errors_are_single_json_documents(path, args, code):
    assert command(path, *args, code=code)["error"]


def test_missing_database_does_not_create_file(tmp_path):
    path = tmp_path / "missing.db"
    assert "does not exist" in command(path, "query", "SELECT 1", code=1)["error"]
    assert not path.exists()
    assert json.loads(run("--json", "query", "SELECT 1", code=1))["error"]


def test_corrupt_database_and_existing_output(path, tmp_path):
    corrupt = tmp_path / "corrupt.db"
    corrupt.write_text("this is not sqlite")
    assert command(corrupt, "database", "info", code=1)["error"]
    before = path.read_bytes()
    assert json.loads(run("--json", "database", "create", path, code=1))["error"]
    assert command(path, "database", "backup", path, code=1)["error"]
    assert path.read_bytes() == before


def test_integrity_failure_has_report_and_nonzero_status(path):
    conn = sqlite3.connect(path)
    try:
        conn.executescript("CREATE TABLE parent(id INTEGER PRIMARY KEY);"
                           "CREATE TABLE child(parent REFERENCES parent(id)); INSERT INTO child VALUES(9);")
    finally:
        conn.close()
    report = command(path, "database", "check", code=1)
    assert report["ok"] is False
    assert report["foreign_key_violations"][0][0] == "child"


def test_online_backup_reads_committed_wal(path, tmp_path):
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE wal_data(value)")
        conn.execute("INSERT INTO wal_data VALUES('committed')")
        conn.commit()
        conn.execute("INSERT INTO wal_data VALUES('uncommitted')")
        output = tmp_path / "wal-copy.db"
        command(path, "database", "backup", output)
        assert native(output, "SELECT * FROM wal_data") == [{"value": "committed"}]
    finally:
        conn.close()


def test_scripted_repl_retains_session_and_continues_after_errors(path):
    lines = [shlex.join(["database", "open", str(path)]),
             'execute "CREATE TABLE t(value)"',
             'execute "INSERT INTO t VALUES (?)" --params \'["private-value"]\'',
             "", "--json", "--json repl", "query 'unterminated", "unknown-secret",
             'query "SELECT value FROM t"', "session status", "session history", "quit"]
    output = run("--json", input="\n".join(lines) + "\n")
    records = [json.loads(line) for line in output.splitlines()]
    assert records[0]["path"] == str(path)
    assert sum("error" in record for record in records) == 4
    assert records[-3]["rows"] == [["private-value"]]
    assert records[-2]["database"] == str(path)
    history = records[-1]["history"]
    assert {entry["exit_code"] for entry in history} == {0, 1, 2}
    assert "private-value" not in json.dumps(history)
    assert "unknown-secret" not in json.dumps(history)


def test_plain_scripted_repl_reports_parse_error_without_crashing():
    completed = subprocess.run(CLI_BASE + ["repl"], input="query 'unterminated\nsession status\nexit\n",
                               capture_output=True, text=True, timeout=10)
    assert completed.returncode == 0
    assert "No closing quotation" in completed.stderr
    assert json.loads(completed.stdout)["database"] is None


def test_packaged_skill_is_available():
    from importlib.resources import files

    skill = files("cli_anything.sqlite").joinpath("skills/SKILL.md").read_text(encoding="utf-8")
    assert 'name: "cli-anything-sqlite"' in skill
    assert "import-csv" in skill
