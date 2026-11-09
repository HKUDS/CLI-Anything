"""Real native Turso, installed CLI and piped REPL workflows. No backend skips."""
import csv
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys
import time

import pytest
import turso

from cli_anything.turso.utils.turso_backend import Database, create_database


def _resolve_cli(name):
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1":
        raise RuntimeError(f"{name} not in PATH. Install with pip install -e .")
    return [sys.executable, "-m", "cli_anything.turso.turso_cli"]


CLI = _resolve_cli("cli-anything-turso")


def run(*args, code=0, input=None):
    result = subprocess.run(CLI + ["--json", *map(str, args)], input=input,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == code, (result.stdout, result.stderr)
    return result


def data(*args, code=0):
    result = run(*args, code=code)
    assert not (result.stderr if code == 0 else result.stdout), (result.stdout, result.stderr)
    return json.loads(result.stdout if code == 0 else result.stderr)


@pytest.fixture
def fixture_db(tmp_path):
    path = tmp_path / "native database with spaces.db"
    assert not path.exists()
    out = data("db", "create", path)
    assert out["database"] == str(path.resolve())
    assert isinstance(out["rows"][0][0], str) and out["rows"][0][0]
    data("--database", path, "sql", 'CREATE TABLE items (id INTEGER PRIMARY KEY, label TEXT UNIQUE, note TEXT, raw BLOB)')
    print(f"\n  Native Turso fixture: {path}")
    return path


def test_help_and_native_dependency():
    import cli_anything.turso
    required_root = os.environ.get("CLI_ANYTHING_REQUIRE_INSTALLED_ROOT")
    if required_root:
        assert Path(cli_anything.turso.__file__).is_relative_to(Path(required_root))
    result = subprocess.run(CLI + ["--help"], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and "transaction" in result.stdout
    info = data("doctor")
    assert info["backend"] == "pyturso" and info["sdk_version"] == "0.8.3"
    assert info["native_extensions"]
    assert all(Path(p["path"]).is_file() and len(p["sha256"]) == 64 for p in info["native_extensions"])


def test_database_selection_schema_and_no_overwrite(fixture_db, tmp_path):
    db = fixture_db
    session = tmp_path / "selected db.json"
    selected = data("--session", session, "db", "open", db)
    assert selected["database"] == str(db)
    assert data("--session", session, "table", "list")["rows"] == [["items"]]
    assert [row[1] for row in data("--session", session, "table", "describe", "items")["rows"]] == ["id", "label", "note", "raw"]
    assert any(row[1] == "items" for row in data("--session", session, "schema")["rows"])
    assert data("db", "create", db, code=1)["ok"] is False
    assert data("--session", session, "db", "close")["database"] is None
    assert data("--session", session, "schema", code=1)["ok"] is False


def test_crud_binds_escaping_and_null(fixture_db):
    db = fixture_db
    text = 'O\'Brien | "quoted"\n雪\t\\end'
    values = {"id": 1, "label": text, "note": None, "raw": {"$blob": "00ff22"}}
    assert data("--database", db, "table", "insert", "items", "--values", json.dumps(values))["rows_affected"] == 1
    rows = data("--database", db, "table", "rows", "items", "--where", '{"note":null}')["rows"]
    assert rows == [[1, text, None, {"$blob": "00ff22"}]]
    assert data("--database", db, "sql", "SELECT :word, ?2", "--params", '["named",3]')["rows"] == [["named", 3]]
    assert data("--database", db, "sql", "SELECT :word", "--params", '{"word":"bound"}')["rows"] == [["bound"]]
    data("--database", db, "table", "update", "items", "--where", '{"id":1}', "--values", '{"note":"updated"}')
    assert data("--database", db, "table", "rows", "items")["rows"][0][2] == "updated"
    assert data("--database", db, "table", "delete", "items", code=1)["ok"] is False
    data("--database", db, "table", "delete", "items", "--where", '{"id":1}')
    assert data("--database", db, "table", "rows", "items")["rows"] == []


def test_quoted_table_and_column_names(fixture_db):
    db = fixture_db
    table = 'odd" table;--'
    data("--database", db, "sql", 'CREATE TABLE "odd"" table;--" ("a""b" TEXT)')
    data("--database", db, "table", "insert", table, "--values", json.dumps({'a"b': "'); DROP TABLE items;--"}))
    assert data("--database", db, "table", "rows", table)["rows"] == [["'); DROP TABLE items;--"]]
    assert data("--database", db, "table", "rows", "items")["rows"] == []


def test_sql_row_cap_and_returning_are_durable(fixture_db):
    db = fixture_db
    result = data("--database", db, "sql", "INSERT INTO items(id,label) VALUES (1,'a'),(2,'b'),(3,'c') RETURNING id", "--limit", 1)
    assert len(result["rows"]) == 1 and result["truncated"] is True
    assert data("--database", db, "sql", "SELECT count(*) FROM items")["rows"] == [[3]]
    result = data("--database", db, "table", "rows", "items", "--limit", 2)
    assert result["row_count"] == 2 and result["truncated"] is True
    assert data("--database", db, "sql", "SELECT 1,2 UNION ALL SELECT 3,4", "--limit", 1)["rows"] == [[1, 2]]


def test_transaction_commit_and_constraint_rollback(fixture_db, tmp_path):
    db = fixture_db
    manifest = tmp_path / "operations with spaces.json"
    manifest.write_text(json.dumps([
        {"op": "insert", "table": "items", "values": {"id": 1, "label": "a"}},
        {"op": "insert", "table": "items", "values": {"id": 2, "label": "b"}},
    ]))
    assert data("--database", db, "transaction", "run", manifest)["committed"] is True
    assert data("--database", db, "sql", "SELECT id,label FROM items ORDER BY id")["rows"] == [[1, "a"], [2, "b"]]
    manifest.write_text(json.dumps([
        {"op": "update", "table": "items", "values": {"label": "changed"}, "where": {"id": 1}},
        {"op": "insert", "table": "items", "values": {"id": 3, "label": "b"}},
        {"op": "delete", "table": "items", "all": True},
    ]))
    error = data("--database", db, "transaction", "run", manifest, code=1)
    assert error["operation_index"] == 1
    assert data("--database", db, "sql", "SELECT id,label FROM items ORDER BY id")["rows"] == [[1, "a"], [2, "b"]]


def test_deferred_commit_failure_propagates_and_rolls_back(fixture_db):
    db = fixture_db
    data("--database", db, "sql", "CREATE TABLE parent(id INTEGER PRIMARY KEY)")
    data("--database", db, "sql", "CREATE TABLE child(id INTEGER PRIMARY KEY, parent_id INTEGER REFERENCES parent(id) DEFERRABLE INITIALLY DEFERRED)")
    error = data("--database", db, "sql", "INSERT INTO child VALUES(1,42)", code=1)
    assert "FOREIGN KEY" in error["error"].upper()
    assert data("--database", db, "sql", "SELECT * FROM child")["rows"] == []
    data("--database", db, "sql", "INSERT INTO parent VALUES(42)")
    data("--database", db, "sql", "INSERT INTO child VALUES(1,42)")
    assert data("--database", db, "sql", "SELECT * FROM child")["rows"] == [[1, 42]]


@pytest.mark.parametrize("sql,params", [
    ("SELEC bad", "[]"),
    ("SELECT 1; SELECT 2", "[]"),
    ("SELECT ?", "[]"),
    ("SELECT ?", "[9223372036854775808]"),
    ("SELECT ?", "[NaN]"),
])
def test_sql_failures_are_json(fixture_db, sql, params):
    error = data("--database", fixture_db, "sql", sql, "--params", params, code=1)
    assert error["ok"] is False and error["database"] == str(fixture_db)
    assert error["error"]


def test_missing_database_and_parent_never_created(tmp_path):
    absent = tmp_path / "absent.db"
    assert data("--database", absent, "status", code=1)["ok"] is False
    assert not absent.exists()
    assert data("db", "open", absent, code=1)["ok"] is False
    assert not absent.exists()
    assert data("db", "create", tmp_path / "missing" / "db", code=1)["ok"] is False


def test_json_and_csv_export_content(fixture_db, tmp_path):
    db = fixture_db
    values = {"id": 1, "label": 'comma, quote"\n雪', "raw": {"$blob": "00ff"}}
    data("--database", db, "table", "insert", "items", "--values", json.dumps(values))
    for fmt in ["json", "csv"]:
        path = tmp_path / f"export with spaces.{fmt}"
        exported = data("--database", db, "export", "items", "--output", path, "--format", fmt)
        assert exported["row_count"] == 1 and not exported["truncated"]
        assert path.stat().st_size > 0
        if fmt == "json":
            assert json.loads(path.read_text())["rows"] == [[1, values["label"], None, {"$blob": "00ff"}]]
        else:
            with path.open(newline="") as stream:
                rows = list(csv.reader(stream))
            assert rows == [["id", "label", "note", "raw"], ["1", values["label"], "", '{"$blob": "00ff"}']]
        before = path.read_bytes()
        assert data("--database", db, "export", "items", "--output", path, code=1)["ok"] is False
        assert path.read_bytes() == before
        print(f"\n  Native export: {path} ({path.stat().st_size} bytes)")


def test_default_repl_selection_persistence_and_recovery(tmp_path):
    a, b = tmp_path / "first db.db", tmp_path / "second db.db"
    session = tmp_path / "repl selection.json"
    commands = [
        ["db", "create", str(a)],
        ["sql", "CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT)"],
        ["sql", "INSERT INTO t VALUES(?,?)", "--params", json.dumps([1, 'pipe|\n"雪'])],
        ["sql", "bad sql"],
        ["table", "rows", "t"],
        ["db", "create", str(b)],
        ["status"],
        ["db", "open", str(a)],
        ["table", "rows", "t"],
        ["exit"],
    ]
    result = run("--session", session, input="\n".join(shlex.join(c) for c in commands) + "\n", code=1)
    outputs = [json.loads(line) for line in result.stdout.splitlines()]
    assert len(outputs) == 8
    assert outputs[3]["rows"] == [[1, 'pipe|\n"雪']]
    assert outputs[5]["database"] == str(b)
    assert outputs[-1]["rows"] == outputs[3]["rows"]
    assert json.loads(result.stderr)["ok"] is False
    assert data("--session", session, "table", "rows", "t")["rows"] == outputs[-1]["rows"]


def test_repl_success_and_usage_error(tmp_path):
    db = tmp_path / "repl.db"
    result = run(input=shlex.join(["db", "create", str(db)]) + '\nstatus\nexit\n')
    assert len([json.loads(line) for line in result.stdout.splitlines()]) == 2
    result = run(input='sql\nstatus\nexit\n', code=1)
    assert json.loads(result.stderr)["ok"] is False
    assert json.loads(result.stdout)["selected"] is False


def test_native_binary_independent_readback(fixture_db):
    path = os.environ.get("TURSODB_BIN") or shutil.which("tursodb")
    assert path, "Install native tursodb or set TURSODB_BIN"
    version = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=10)
    assert version.returncode == 0 and version.stdout.strip() == "Turso 0.8.3"
    data("--database", fixture_db, "sql", "INSERT INTO items(id,label) VALUES(7,'native')")
    result = subprocess.run([path, "--readonly", "-q", "-m", "list", str(fixture_db),
                             "SELECT turso_version(),id,label FROM items ORDER BY id"],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0
    sql_version, row_id, label = result.stdout.strip().split("|")
    assert sql_version and (row_id, label) == ("7", "native")


def test_held_native_lock_fails_promptly_and_recovers(fixture_db):
    # The only holder/contender target is this test's fresh synthetic database.
    conn = turso.connect(str(fixture_db))
    try:
        conn.execute("BEGIN IMMEDIATE").close()
        start = time.monotonic()
        error = data("--database", fixture_db, "sql", "INSERT INTO items(id,label) VALUES(1,'locked')", code=1)
        assert time.monotonic() - start < 5
        assert "lock" in error["error"].lower() or "busy" in error["error"].lower()
    finally:
        conn.rollback()
        conn.close()
        del conn  # SDK close alone can retain the native database owner.
    assert data("--database", fixture_db, "table", "rows", "items")["rows"] == []
    data("--database", fixture_db, "sql", "INSERT INTO items(id,label) VALUES(1,'released')")
    assert data("--database", fixture_db, "sql", "SELECT label FROM items")["rows"] == [["released"]]


def test_repl_releases_locks_after_success_and_failure(fixture_db):
    import select
    proc = subprocess.Popen(CLI + ["--json", "--database", str(fixture_db)],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)
    try:
        for sql, error in [("SELECT 1", False), ("SELECT * FROM absent_table", True)]:
            proc.stdin.write(shlex.join(["sql", sql]) + "\n")
            proc.stdin.flush()
            stream = proc.stderr if error else proc.stdout
            assert select.select([stream], [], [], 5)[0], "REPL failed to respond within five seconds"
            assert json.loads(stream.readline())["ok"] is not error
            # A separate process must open the fixture while the REPL is alive.
            assert data("--database", fixture_db, "sql", "SELECT 9")["rows"] == [[9]]
        proc.stdin.write("exit\n")
        proc.stdin.flush()
        proc.communicate(timeout=5)
        assert proc.returncode == 1
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.communicate(timeout=5)


def test_missing_sdk_in_separate_environment(tmp_path):
    import click
    import cli_anything.turso
    import venv
    env = tmp_path / "missing sdk environment"
    venv.EnvBuilder(with_pip=False).create(env)
    site = next((env / "lib").glob("python*/site-packages"))
    # Reuse only Click plus the harness source path, deliberately no pyturso.
    shutil.copytree(Path(click.__file__).parent, site / "click")
    namespace = site / "cli_anything"
    namespace.mkdir()
    shutil.copytree(Path(cli_anything.turso.__file__).parent, namespace / "turso",
                    ignore=shutil.ignore_patterns("__pycache__", "tests"))
    missing_python = env / "bin" / "python"
    destination = tmp_path / "must not be created.db"
    isolated_cli = [str(missing_python), CLI[0]] if len(CLI) == 1 else [
        str(missing_python), "-m", "cli_anything.turso.turso_cli"]
    for args in [["doctor"], ["db", "create", str(destination)]]:
        result = subprocess.run([*isolated_cli, "--json", *args],
                                capture_output=True, text=True, timeout=10)
        assert result.returncode == 1 and not result.stdout
        assert "pyturso==0.8.3" in json.loads(result.stderr)["error"]
    assert not destination.exists()


def test_session_lock_refusal_is_bounded(tmp_path):
    import fcntl
    path = tmp_path / "session.json"
    path.write_text('{"version":1,"database":null}')
    with path.open("r+") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        start = time.monotonic()
        assert data("--session", path, "status", code=1)["ok"] is False
        assert time.monotonic() - start < 5
    assert data("--session", path, "status")["selected"] is False


def test_named_prefixes_missing_binds_and_literal_escaping(fixture_db):
    db = fixture_db
    assert data("--database", db, "sql", "SELECT :x,?1", "--params", '{"x":7}')["rows"] == [[7, 7]]
    assert data("--database", db, "sql", "SELECT :x,@x,$x,':ignored' /* ? */", "--params", '{"x":"same"}')["rows"] == [["same", "same", "same", ":ignored"]]
    for statement, params in [("SELECT :x,:y", '{"x":1}'), ("SELECT ?,?", '[1]')]:
        assert data("--database", db, "sql", statement, "--params", params, code=1)["ok"] is False


def test_all_command_help_and_version():
    from cli_anything.turso.turso_cli import cli
    import click
    def visit(command, path=()):
        for switch in ["--help"]:
            result = subprocess.run(CLI + [*path, switch], capture_output=True, text=True, timeout=5)
            assert result.returncode == 0 and "Usage:" in result.stdout and not result.stderr
        if isinstance(command, click.Group):
            for name, child in command.commands.items():
                visit(child, (*path, name))
    visit(cli)
    result = subprocess.run(CLI + ["--version"], capture_output=True, text=True, timeout=5)
    assert result.returncode == 0 and "0.1.0" in result.stdout
    assert data("status")["selected"] is False
    result = subprocess.run(CLI + ["status"], capture_output=True, text=True, timeout=5)
    assert result.returncode == 0 and json.loads(result.stdout)["selected"] is False


def test_session_override_collision_and_invalid_state(fixture_db, tmp_path):
    db = fixture_db
    session = tmp_path / "selection.json"
    other = tmp_path / "other.db"
    data("--session", session, "db", "open", db)
    data("db", "create", other)
    before = session.read_bytes()
    assert data("--session", session, "--database", other, "status")["database"] == str(other)
    assert session.read_bytes() == before
    assert data("--session", session, "status")["database"] == str(db)
    collision = tmp_path / "same-path.json"
    assert data("--session", collision, "db", "create", collision, code=1)["ok"] is False
    assert not collision.exists()
    missing_parent = tmp_path / "missing" / "session.json"
    new_db = tmp_path / "not-created.db"
    assert data("--session", missing_parent, "db", "create", new_db, code=1)["ok"] is False
    assert not new_db.exists()
    session.write_text('not session JSON')
    assert data("--session", session, "status", code=1)["ok"] is False
    assert session.read_text() == 'not session JSON'
    assert data("--database", db, "table", "describe", "absent", code=1)["ok"] is False


def test_actual_all_row_crud_and_filter_validation(fixture_db):
    db = fixture_db
    for i in [1, 2]:
        data("--database", db, "table", "insert", "items", "--values", json.dumps({"id": i, "label": str(i)}))
    data("--database", db, "table", "update", "items", "--all", "--values", '{"note":"all"}')
    assert data("--database", db, "sql", "SELECT count(*) FROM items WHERE note='all'")["rows"] == [[2]]
    assert len(data("--database", db, "table", "rows", "items", "--where", '{"id":1,"note":"all"}')["rows"]) == 1
    assert data("--database", db, "table", "update", "items", "--all", "--where", '{"id":1}', "--values", '{"note":"bad"}', code=1)["ok"] is False
    for values in ['{}', '[]', '{"note":[]}']:
        assert data("--database", db, "table", "insert", "items", "--values", values, code=1)["ok"] is False
    data("--database", db, "table", "delete", "items", "--all")
    assert data("--database", db, "table", "rows", "items", "--limit", 10000)["rows"] == []


def test_transaction_commit_failure_and_validation(fixture_db, tmp_path):
    db = fixture_db
    data("--database", db, "sql", "CREATE TABLE p(id INTEGER PRIMARY KEY)")
    data("--database", db, "sql", "CREATE TABLE c(id INTEGER PRIMARY KEY, p INTEGER REFERENCES p(id) DEFERRABLE INITIALLY DEFERRED)")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps([
        {"op": "insert", "table": "items", "values": {"id": 1, "label": "must rollback"}},
        {"op": "insert", "table": "c", "values": {"id": 1, "p": 99}},
    ]))
    error = data("--database", db, "transaction", "run", manifest, code=1)
    assert "FOREIGN KEY" in error["error"].upper()
    assert data("--database", db, "table", "rows", "items")["rows"] == []
    assert data("--database", db, "table", "rows", "c")["rows"] == []
    for invalid in [[], {}, [{"op": "sql", "sql": "COMMIT"}], [{"op": "delete", "table": "items"}]]:
        manifest.write_text(json.dumps(invalid))
        assert data("--database", db, "transaction", "run", manifest, code=1)["ok"] is False
    manifest.write_text('not JSON')
    assert data("--database", db, "transaction", "run", manifest, code=1)["ok"] is False
    assert data("--database", db, "transaction", "run", tmp_path / "missing.json", code=1)["ok"] is False


def test_native_bind_boundaries_and_nonfinite_output(fixture_db):
    db = fixture_db
    assert data("--database", db, "sql", "SELECT 1", "--limit", 10000)["rows"] == [[1]]
    values = [-(2**63), 2**63 - 1, 1.25, True, False, None, {"$blob": ""}]
    assert data("--database", db, "sql", "SELECT ?,?,?,?,?,?,?", "--params", json.dumps(values))["rows"] == [[-(2**63), 2**63 - 1, 1.25, 1, 0, None, {"$blob": ""}]]
    assert data("--database", db, "sql", "SELECT 1e999")["rows"] == [[{"$float": "inf"}]]
    assert data("--database", db, "sql", "SELECT ?2,?1", "--params", '{"1":"one","2":"two","extra":"ignored"}')["rows"] == [["two", "one"]]
    for params in ['{"$blob":"zz"}', '[{"$blob":"zz"}]', '"wrong shape"', '[-9223372036854775809]']:
        assert data("--database", db, "sql", "SELECT ?", "--params", params, code=1)["ok"] is False


@pytest.mark.parametrize("command,limit", [
    ("sql", "0"), ("sql", "10001"), ("table", "0"), ("table", "10001"),
    ("export", "0"), ("export", "10001"),
])
def test_invalid_output_limits(fixture_db, tmp_path, command, limit):
    if command == "sql":
        args = ["sql", "SELECT 1"]
    elif command == "table":
        args = ["table", "rows", "items"]
    else:
        args = ["export", "items", "--output", str(tmp_path / "never.json")]
    assert data("--database", fixture_db, *args, "--limit", limit, code=2)["ok"] is False


def test_export_truncation_and_invalid_output(fixture_db, tmp_path):
    db = fixture_db
    data("--database", db, "sql", "INSERT INTO items(id,label) VALUES(1,'a'),(2,'b'),(3,'c')")
    for fmt in ["json", "csv"]:
        out = tmp_path / f"capped.{fmt}"
        result = data("--database", db, "export", "items", "--output", out, "--format", fmt, "--limit", 1)
        assert result["truncated"] is True and result["row_count"] == 1
        if fmt == "json":
            assert len(json.loads(out.read_text())["rows"]) == 1
            assert json.loads(out.read_text())["truncated"] is True
        else:
            with out.open(newline="") as stream:
                assert len(list(csv.reader(stream))) == 2
    out = tmp_path / "not-created.json"
    complete = data("--database", db, "export", "items", "--output", tmp_path / "complete.json", "--limit", 10000)
    assert complete["row_count"] == 3 and complete["truncated"] is False
    assert data("--database", db, "export", "absent", "--output", out, code=1)["ok"] is False
    assert not out.exists()
    assert data("--database", db, "export", "items", "--output", out, "--format", "sql", code=2)["ok"] is False
    assert not out.exists()
    assert data("--database", db, "export", "items", "--output", tmp_path / "missing" / "out.json", code=1)["ok"] is False


def test_repl_help_quit_eof_parse_and_nested_paths():
    result = run("repl", input="help\nstatus\nquit\n")
    outputs = [json.loads(line) for line in result.stdout.splitlines()]
    assert "sql" in outputs[0]["commands"] and outputs[1]["selected"] is False
    assert run(input="").stdout == ""
    result = run(input='"unterminated\nrepl\n--json repl\nstatus\nexit\n', code=1)
    errors = [json.loads(line) for line in result.stderr.splitlines()]
    assert len(errors) == 3 and all(error["ok"] is False for error in errors)
    assert json.loads(result.stdout)["selected"] is False


ENDLESS_ROWS = 'WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c) SELECT x FROM c'


def _interrupt_while_db_open(proc, db):
    fd_dir = Path(f"/proc/{proc.pid}/fd")
    deadline = time.monotonic() + 10
    while True:
        assert proc.poll() is None and time.monotonic() < deadline
        opened = []
        for fd in fd_dir.iterdir():
            try:
                opened.append(os.readlink(fd))
            except OSError:
                pass
        if str(Path(db).resolve()) in opened:
            break
        time.sleep(0.02)
    time.sleep(0.3)
    proc.send_signal(signal.SIGINT)


def _json_lines(text):
    return [json.loads(line) for line in text.splitlines() if line.strip()]


@pytest.mark.skipif(not Path("/proc/self/fd").is_dir(), reason="needs /proc fd introspection")
def test_one_shot_interrupt_reports_and_releases(fixture_db):
    data("--database", fixture_db, "sql", "INSERT INTO items (label) VALUES ('kept')")
    proc = subprocess.Popen(CLI + ["--json", "--database", str(fixture_db), "sql", ENDLESS_ROWS],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        _interrupt_while_db_open(proc, fixture_db)
        stdout, stderr = proc.communicate(timeout=10)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
    assert proc.returncode == 130, (stdout, stderr)
    assert stdout == "" and "Traceback" not in stderr
    errors = _json_lines(stderr)
    assert errors == [{"ok": False, "database": str(fixture_db.resolve()), "error": "interrupted"}]
    data("--database", fixture_db, "sql", "INSERT INTO items (label) VALUES ('after')")
    rows = data("--database", fixture_db, "sql", "SELECT label FROM items ORDER BY id")["rows"]
    assert rows == [["kept"], ["after"]]


@pytest.mark.skipif(not Path("/proc/self/fd").is_dir(), reason="needs /proc fd introspection")
def test_repl_interrupt_recovers_and_releases(fixture_db):
    proc = subprocess.Popen(CLI + ["--json", "--database", str(fixture_db)],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)
    try:
        proc.stdin.write(f"sql {shlex.quote(ENDLESS_ROWS)}\n")
        proc.stdin.flush()
        _interrupt_while_db_open(proc, fixture_db)
        proc.stdin.write("sql \"INSERT INTO items (label) VALUES ('after')\"\n"
                         "sql \"SELECT label FROM items\"\nquit\n")
        stdout, stderr = proc.communicate(timeout=10)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
    assert proc.returncode == 1, (stdout, stderr)
    assert "Traceback" not in stderr
    assert [e["error"] for e in _json_lines(stderr)] == ["interrupted"]
    outputs = _json_lines(stdout)
    assert outputs[0]["rows_affected"] == 1 and outputs[1]["rows"] == [["after"]]
    assert data("--database", fixture_db, "sql", "SELECT count(*) FROM items")["rows"] == [[1]]


@pytest.mark.parametrize("ending", [b"exit\n", b"\x03", b"\x04"], ids=["exit", "interrupt", "eof"])
def test_pseudo_tty_repl_smoke(fixture_db, tmp_path, ending):
    import pty
    import select
    import termios
    master, slave = pty.openpty()
    env = os.environ.copy()
    env.update({"TERM": "dumb", "NO_COLOR": "1", "PROMPT_TOOLKIT_NO_CPR": "1"})
    controlling_terminal = (
        "import fcntl,os,sys,termios;"
        "os.setsid();fcntl.ioctl(0,termios.TIOCSCTTY,0);"
        "os.tcsetpgrp(0,os.getpgrp());"
        "assert os.tcgetpgrp(0)==os.getpgrp();"
        "os.execvpe(sys.argv[1],sys.argv[1:],os.environ)"
    )
    proc = subprocess.Popen([sys.executable, "-c", controlling_terminal, *CLI,
                             "--database", str(fixture_db)],
                            stdin=slave, stdout=slave, stderr=slave,
                            env=env)
    os.close(slave)
    transcript = bytearray()
    pending = bytearray()
    def until(needle):
        deadline = time.monotonic() + 5
        while needle not in pending:
            remaining = deadline - time.monotonic()
            assert remaining > 0, bytes(transcript).decode(errors="replace")
            assert select.select([master], [], [], remaining)[0], bytes(transcript)
            chunk = os.read(master, 65536)
            assert chunk, bytes(transcript)
            transcript.extend(chunk)
            pending.extend(chunk)
        pos = pending.index(needle) + len(needle)
        del pending[:pos]
    try:
        until(b"Turso")
        os.write(master, b'status\n')
        until(b'"row_count"')
        os.write(master, b'sql "SELECT 17 AS proof"\n')
        until(b'"proof"')
        until(b'17')
        os.write(master, b'sql "malformed SQL"\n')
        until(b'"ok": false')
        os.write(master, b'help\n')
        until(b'Commands:')
        os.write(master, b'status\n')
        until(b'"row_count"')
        until("❯ ".encode())  # Synchronize with the new prompt, not echoed text.
        # TERM=dumb prints its prompt before Application enters raw mode.
        # A canonical Ctrl-D sent in that gap is not a raw input key event.
        deadline = time.monotonic() + 2
        while termios.tcgetattr(master)[3] & termios.ICANON:
            assert time.monotonic() < deadline, "Prompt never entered raw input mode"
            time.sleep(0.01)
        os.write(master, ending)
        proc.wait(timeout=5)
        assert proc.returncode == 1  # Sticky failed-command status.
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
        os.close(master)
        path = tmp_path / "pseudo-tty-transcript.txt"
        path.write_bytes(transcript)
        print(f"\n  Bounded pseudo-TTY transcript: {path}")
