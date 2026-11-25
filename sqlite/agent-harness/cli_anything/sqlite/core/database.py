"""Inspection and atomic data workflows using SQLite, not a database emulation."""

import csv
from pathlib import Path
import sqlite3
import time

from cli_anything.sqlite.utils.sqlite_backend import (
    connection, identifier, new_file, parameters, result, user_sql,
)


def create(path):
    with new_file(path) as target:
        with connection(target, write=True) as conn:
            conn.execute("PRAGMA user_version = 0")
    return {"path": str(target), "sqlite_version": sqlite3.sqlite_version}


def info(path, timeout=5.0):
    with connection(path, timeout=timeout) as conn:
        values = {key: conn.execute(f"PRAGMA {key}").fetchone()[0] for key in (
            "page_size", "page_count", "freelist_count", "user_version", "journal_mode",
        )}
        values["schema_objects"] = conn.execute(
            "SELECT count(*) FROM sqlite_schema WHERE name NOT GLOB 'sqlite_*'"
        ).fetchone()[0]
    return {"path": str(Path(path).expanduser().resolve()),
            "sqlite_version": sqlite3.sqlite_version, **values}


def check(path, full=False, timeout=5.0):
    with connection(path, timeout=timeout) as conn:
        checks = [row[0] for row in conn.execute(
            "PRAGMA integrity_check" if full else "PRAGMA quick_check"
        )]
        violations = [list(row) for row in conn.execute("PRAGMA foreign_key_check")]
    return {"ok": checks == ["ok"] and not violations, "integrity": checks,
            "foreign_key_violations": violations}


def schema(path, name=None, timeout=5.0):
    with connection(path, timeout=timeout) as conn:
        if name is None:
            return {"objects": [dict(zip(("type", "name", "table", "sql"), row)) for row in conn.execute(
                "SELECT type, name, tbl_name, sql FROM sqlite_schema "
                "WHERE name NOT GLOB 'sqlite_*' ORDER BY type, name"
            )]}
        record = conn.execute(
            "SELECT type, sql FROM sqlite_schema WHERE name = ? AND type IN ('table', 'view')",
            (name,),
        ).fetchone()
        if record is None:
            raise ValueError(f"No table or view named {name!r}.")
        columns = [dict(zip(("cid", "name", "type", "notnull", "default", "pk", "hidden"), row))
                   for row in conn.execute("SELECT * FROM pragma_table_xinfo(?)", (name,))]
        indexes = [dict(zip(("seq", "name", "unique", "origin", "partial"), row))
                   for row in conn.execute("SELECT * FROM pragma_index_list(?)", (name,))]
        for index in indexes:
            index["columns"] = [row[2] for row in conn.execute(
                "SELECT * FROM pragma_index_info(?)", (index["name"],))]
        foreign_keys = [dict(zip(("id", "seq", "table", "from", "to", "on_update", "on_delete", "match"), row))
                        for row in conn.execute("SELECT * FROM pragma_foreign_key_list(?)", (name,))]
    return {"name": name, "type": record[0], "sql": record[1], "columns": columns,
            "indexes": indexes, "foreign_keys": foreign_keys}


def query(path, sql, params=None, limit=1000, timeout=5.0):
    bound = parameters([] if params is None else params)
    with connection(path, timeout=timeout) as conn, user_sql(conn):
        cursor = conn.execute(sql, bound)
        try:
            return result(cursor, limit)
        finally:
            cursor.close()


def batch(path, statements, timeout=5.0):
    if not isinstance(statements, list) or not 1 <= len(statements) <= 1000:
        raise ValueError("A batch must contain between 1 and 1000 statement objects.")
    prepared = []
    for item in statements:
        if not isinstance(item, dict) or set(item) - {"sql", "params"}:
            raise ValueError("Each statement accepts only sql and params fields.")
        if not isinstance(item.get("sql"), str) or not item["sql"].strip():
            raise ValueError("Each statement requires nonempty sql.")
        prepared.append((item["sql"], parameters(item.get("params", []))))
    results = []
    deadline = time.monotonic() + timeout
    with connection(path, write=True, timeout=timeout) as conn, user_sql(conn, write=True):
        for sql, bound in prepared:
            if time.monotonic() >= deadline:
                raise TimeoutError("Batch exceeded the timeout; transaction rolled back.")
            previous_changes = conn.total_changes
            cursor = conn.execute(sql, bound)
            try:
                entry = result(cursor)
            finally:
                cursor.close()
            entry["changes"] = conn.total_changes - previous_changes
            results.append(entry)
    return {"committed": True, "statements": results,
            "changes": sum(entry["changes"] for entry in results)}


def execute(path, sql, params=None, timeout=5.0):
    return batch(path, [{"sql": sql, "params": [] if params is None else params}], timeout)


def import_csv(path, table, source, timeout=5.0):
    table_sql = identifier(table)
    count = 0
    processed = 0
    with open(source, encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream, strict=True)
        header = next(reader, None)
        # SQLite folds ASCII identifier case, including in an INSERT column list.
        folded = [name.translate(str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"))
                  for name in header or []]
        if not header or any(not name for name in header) or len(set(folded)) != len(header):
            raise ValueError("CSV requires a nonempty header with unique, nonempty column names.")
        columns = ", ".join(identifier(name) for name in header)
        placeholders = ", ".join("?" for _ in header)
        sql = f"INSERT INTO {table_sql} ({columns}) VALUES ({placeholders})"
        deadline = time.monotonic() + timeout
        with connection(path, write=True, timeout=timeout) as conn, user_sql(conn, write=True):
            # Compile and validate the target even for a header-only CSV.
            conn.execute(f"EXPLAIN {sql}", [None] * len(header)).close()
            for row in reader:
                if time.monotonic() >= deadline:
                    raise TimeoutError("CSV import exceeded the timeout; transaction rolled back.")
                if len(row) != len(header):
                    raise ValueError(f"CSV record ending at line {reader.line_num} has {len(row)} fields; "
                                     f"expected {len(header)}.")
                cursor = conn.execute(sql, row)
                count += cursor.rowcount
                processed += 1
                cursor.close()
    return {"table": table, "processed_rows": processed, "inserted_rows": count, "committed": True}


def export_csv(path, sql, destination, params=None, timeout=5.0):
    bound = parameters([] if params is None else params)
    count = 0
    deadline = time.monotonic() + timeout
    with connection(path, timeout=timeout) as conn, user_sql(conn):
        cursor = conn.execute(sql, bound)
        try:
            if cursor.description is None:
                raise ValueError("CSV export requires a query returning columns.")
            with new_file(destination) as target:
                with target.open("w", encoding="utf-8", newline="") as stream:
                    writer = csv.writer(stream)
                    writer.writerow([column[0] for column in cursor.description])
                    for row in cursor:
                        if time.monotonic() >= deadline:
                            raise TimeoutError("CSV export exceeded the timeout.")
                        if any(isinstance(value, bytes) for value in row):
                            raise ValueError("CSV cannot preserve BLOBs; select hex(column) or use query --json.")
                        writer.writerow(row)
                        count += 1
        finally:
            cursor.close()
    return {"path": str(target), "exported_rows": count}


def backup(path, destination, timeout=5.0):
    deadline = time.monotonic() + timeout

    def progress(status, remaining, total):
        if time.monotonic() >= deadline:
            raise TimeoutError("Backup exceeded the timeout.")

    with connection(path, timeout=timeout) as source:
        # Force SQLite to validate the source before creating an output file.
        source.execute("SELECT count(*) FROM sqlite_schema").fetchone()
        with new_file(destination) as target:
            target_conn = sqlite3.connect(str(target))
            try:
                source.backup(target_conn, pages=128, progress=progress, sleep=0.05)
            finally:
                target_conn.close()
    return {"path": str(target), "bytes": target.stat().st_size, "method": "sqlite-online-backup"}
