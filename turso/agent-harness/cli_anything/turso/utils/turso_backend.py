"""Real native pyturso backend. There is deliberately no sqlite3 fallback."""
import contextlib
import csv
import hashlib
import importlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import sys

from ..core.session import database_path
from ..core.values import TursoError, compile_operation, identifier, json_value, predicate, sql_parameters

SDK_VERSION = "0.8.3"
MAX_ROWS = 10000


def load_sdk():
    try:
        version = importlib.metadata.version("pyturso")
        if version != SDK_VERSION:
            raise TursoError(f"Unsupported pyturso {version}; this harness requires pyturso=={SDK_VERSION}")
        return importlib.import_module("turso")
    except (ImportError, importlib.metadata.PackageNotFoundError) as exc:
        raise TursoError(f"Native backend missing. Install into this Python environment: {sys.executable} -m pip install pyturso=={SDK_VERSION}") from exc


def dependency_info():
    sdk = load_sdk()
    root = Path(sdk.__file__).resolve().parent
    native = sorted(root.rglob("*.so")) + sorted(root.rglob("*.pyd"))
    if not native:
        raise TursoError(f"No native Turso extension found under {root}; reinstall pyturso=={SDK_VERSION}")
    return {"backend": "pyturso", "sdk_version": SDK_VERSION, "python": sys.executable,
            "module": str(root), "native_extensions": [
                {"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in native],
            "tursodb": shutil.which("tursodb"),
            "scope": "local native engine; Cloud, libSQL, AgentFS and MCP are separate interfaces"}


def row_limit(limit):
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_ROWS:
        raise TursoError(f"Row limit must be between 1 and {MAX_ROWS}")
    return limit


class Database:
    def __init__(self, path):
        self.path = database_path(path)

    def _connect(self):
        sdk = load_sdk()
        conn = sdk.connect(self.path)
        try:
            conn.execute("PRAGMA foreign_keys=ON").close()
            cur = conn.execute("PRAGMA foreign_keys")
            enabled = cur.fetchone()
            cur.close()
            if enabled != (1,):
                raise TursoError("Native engine did not enable foreign_keys")
            return conn
        except Exception:
            conn.close()
            raise

    @staticmethod
    def _result(conn, sql, params, limit):
        cur = conn.execute(sql, params)
        try:
            columns = [d[0] for d in cur.description] if cur.description else []
            rows = cur.fetchmany(limit + 1) if columns else []
            truncated = len(rows) > limit
            # Complete row-producing mutations (RETURNING) before COMMIT. The
            # cap bounds retained/output rows, not SQL execution cost or time.
            while columns and cur.fetchmany(256):
                pass
            return {"columns": columns, "rows": json_value(rows[:limit]),
                    "row_count": min(len(rows), limit), "truncated": truncated,
                    "rows_affected": cur.rowcount if cur.rowcount >= 0 else None}
        except KeyboardInterrupt:
            with contextlib.suppress(Exception):
                conn.interrupt()
            raise
        finally:
            cur.close()

    def _run(self, work):
        conn = None
        failure = None
        result = None
        try:
            conn = self._connect()
            result = work(conn)
            conn.commit()  # Explicit: SDK context manager can swallow failure.
        except Exception as exc:
            rollback_error = None
            if conn is not None:
                try:
                    conn.rollback()
                except Exception as failure:
                    rollback_error = str(failure)
            suffix = f"; rollback also failed: {rollback_error}" if rollback_error else ""
            # Translate after leaving this exception handler. Retaining the
            # native exception traceback also retains closed connection objects
            # and their file locks inside a long-lived REPL.
            failure = TursoError(f"{exc}{suffix}", operation_index=getattr(exc, "operation_index", None))
        except KeyboardInterrupt:
            if conn is not None:
                with contextlib.suppress(Exception):
                    conn.rollback()
            raise
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception as exc:
                    failure = TursoError(f"{failure or 'Operation completed'}; close failed: {exc}")
                conn = None
        if failure:
            raise failure
        return {"database": self.path, **result}

    def sql(self, sql, params=(), limit=100):
        row_limit(limit)
        if not isinstance(sql, str) or not sql.strip():
            raise TursoError("SQL must be nonempty text")
        bound = sql_parameters(sql, params)
        return self._run(lambda conn: self._result(conn, sql, bound, limit))

    def info(self):
        return self.sql("SELECT turso_version() AS turso_version, sqlite_version() AS sqlite_version")

    def schema(self):
        return self.sql("SELECT type, name, tbl_name, sql FROM sqlite_schema ORDER BY type, name", limit=MAX_ROWS)

    def tables(self):
        return self.sql("SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name", limit=MAX_ROWS)

    def describe(self, table):
        result = self.sql(f"PRAGMA table_info({identifier(table)})", limit=MAX_ROWS)
        if not result["rows"]:
            raise TursoError(f"Table does not exist: {table}")
        return result

    def rows(self, table, where=None, limit=100):
        row_limit(limit)
        suffix, params = predicate({} if where is None else where)
        return self.sql(f"SELECT * FROM {identifier(table)}{suffix} LIMIT ?", params + [limit + 1], limit)

    def mutate(self, operation):
        sql, params = compile_operation(operation)
        return self.sql(sql, params)

    def transaction(self, operations):
        if not isinstance(operations, list) or not 1 <= len(operations) <= 1000:
            raise TursoError("Transaction file must be an array of 1..1000 CRUD operations")
        compiled = [compile_operation(op) for op in operations]

        def work(conn):
            conn.execute("BEGIN IMMEDIATE").close()
            results = []
            for i, (sql, params) in enumerate(compiled):
                try:
                    results.append(self._result(conn, sql, params, 1))
                except Exception as exc:
                    raise TursoError(str(exc), operation_index=i) from exc
            return {"committed": True, "operations": results}

        return self._run(work)

    def export(self, table, output, fmt="json", limit=100):
        if fmt not in {"json", "csv"}:
            raise TursoError("Export format must be json or csv")
        result = self.rows(table, limit=limit)
        target = Path(output).expanduser().resolve()
        with target.open("x", encoding="utf-8", newline="") as stream:
            if fmt == "json":
                json.dump(result, stream, ensure_ascii=True, allow_nan=False, indent=2)
                stream.write("\n")
            else:
                writer = csv.writer(stream)
                writer.writerow(result["columns"])
                writer.writerows([
                    [json.dumps(v, ensure_ascii=True) if isinstance(v, dict) else v for v in row]
                    for row in result["rows"]])
        return {"database": self.path, "output": str(target), "format": fmt,
                "row_count": result["row_count"], "truncated": result["truncated"]}


def create_database(path):
    load_sdk()  # Check dependency before reserving the path.
    target = Path(database_path(path, exists=False))
    with target.open("xb"):
        pass
    return Database(str(target)).info()
