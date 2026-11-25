"""Connections to the real SQLite engine provided by Python's sqlite3 binding."""

import base64
from contextlib import contextmanager
import math
import os
from pathlib import Path
import sqlite3
import time


def identifier(name: str) -> str:
    if not isinstance(name, str) or not name or "\x00" in name:
        raise ValueError("An identifier must be a nonempty string without NUL.")
    return '"' + name.replace('"', '""') + '"'


def parameters(value):
    """Accept scalar JSON parameters, with an explicit lossless BLOB encoding."""
    if not isinstance(value, (list, dict)):
        raise ValueError("Parameters must be a JSON array or object.")

    def scalar(item):
        if isinstance(item, dict) and set(item) == {"$base64"}:
            try:
                return base64.b64decode(item["$base64"], validate=True)
            except (ValueError, TypeError) as exc:
                raise ValueError("Invalid $base64 parameter.") from exc
        if item is None or isinstance(item, (str, bool)):
            return item
        if isinstance(item, int) and -(2**63) <= item < 2**63:
            return item
        if isinstance(item, float) and math.isfinite(item):
            return item
        raise ValueError("Parameters must be SQLite scalars or {$base64: ...} BLOBs.")

    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise ValueError("Named parameter keys must be strings.")
        return {key: scalar(item) for key, item in value.items()}
    return tuple(scalar(item) for item in value)


def json_value(value):
    if isinstance(value, bytes):
        return {"$base64": base64.b64encode(value).decode("ascii")}
    if isinstance(value, float) and not math.isfinite(value):
        return {"$float": str(value)}
    return value


@contextmanager
def connection(path, *, write=False, timeout=5.0):
    if sqlite3.sqlite_version_info < (3, 35, 0):
        raise ValueError("SQLite 3.35 or newer is required; use a Python build with a newer SQLite library.")
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Timeout must be a finite positive number of seconds.")
    target = Path(path).expanduser().resolve()
    if not target.is_file():
        raise ValueError(f"Database does not exist: {target}. Use database create first.")
    # URI encoding protects literal '?' and '#' in database filenames.
    uri = target.as_uri() + ("?mode=rw" if write else "?mode=ro")
    conn = sqlite3.connect(uri, uri=True, timeout=timeout, isolation_level=None)
    deadline = time.monotonic() + timeout
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        if not write:
            conn.execute("PRAGMA query_only = ON")
        conn.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
        yield conn
    finally:
        conn.close()


def _authorize(action, arg1, arg2, database, source):
    # Transactions belong to the harness. SQL cannot commit a batch early or
    # create/change another database via ATTACH, VACUUM INTO, or PRAGMA.
    if action in (sqlite3.SQLITE_TRANSACTION, sqlite3.SQLITE_SAVEPOINT,
                  sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH, sqlite3.SQLITE_PRAGMA):
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_FUNCTION and (arg2 or "").lower() == "load_extension":
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def _allow_internal(*args):
    # Python 3.10 cannot disable an authorizer with set_authorizer(None).
    return sqlite3.SQLITE_OK


@contextmanager
def user_sql(conn, *, write=False):
    if write:
        conn.execute("BEGIN IMMEDIATE")
    conn.set_authorizer(_authorize)
    try:
        yield
        conn.set_authorizer(_allow_internal)
        if write:
            conn.commit()
    except BaseException:
        conn.set_authorizer(_allow_internal)
        conn.set_progress_handler(None, 0)
        if write:
            conn.rollback()
        raise
    finally:
        conn.set_authorizer(_allow_internal)


@contextmanager
def new_file(path):
    """Reserve a new owner-only destination; remove incomplete output on failure."""
    target = Path(path).expanduser().absolute()
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    try:
        yield target
    except BaseException:
        target.unlink(missing_ok=True)
        raise


def result(cursor, limit=1000):
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 10000:
        raise ValueError("Limit must be an integer between 1 and 10000.")
    columns = [column[0] for column in cursor.description or []]
    rows = cursor.fetchmany(limit + 1) if columns else []
    return {
        "columns": columns,
        "rows": [[json_value(value) for value in row] for row in rows[:limit]],
        "row_count": min(len(rows), limit),
        "truncated": len(rows) > limit,
    }
