# SQLite harness: architecture and operating procedure

## Backend boundary

SQLite is an embedded database engine. Python's standard-library `sqlite3` module
links directly to that engine and provides its SQL compiler, storage, transaction,
locking, and online-backup APIs. The harness uses those APIs for every database
operation; it does not parse SQL into a substitute storage model. The native
`sqlite3` executable is used for independent E2E artifact verification, and is not
a runtime dependency.

The supported runtime is Python 3.10+ with SQLite 3.35+ (including `RETURNING`).
`database info` reports the engine actually linked to Python, which can differ
from the command-line executable's version.

```text
sqlite_cli.py                 Click commands, JSON errors, REPL session
  core/database.py            Inspection, transactions, streaming CSV, backup
    utils/sqlite_backend.py   Connections, authorizer, binding, output encoding
      Python sqlite3         Actual SQLite engine and on-disk databases
  utils/repl_skin.py          Unmodified shared terminal skin
```

## Workflow

1. Run `database create PATH` for a new file or `--database PATH database info`
   for an existing one. All other database operations require an existing file.
2. Inspect `schema list` and `schema describe NAME` before preparing SQL. Use
   `query SQL --params JSON` for bounded read-only inspection.
3. For changes, choose `execute SQL`, `batch FILE`, or `import-csv TABLE FILE`.
   Each command owns one transaction with foreign-key enforcement. A failed
   statement or CSV record rolls the entire operation back, including DDL.
4. Verify the result with `query` and `database check`. For durable artifacts,
   stream `export-csv SQL OUTPUT` or create `database backup OUTPUT`.

## State and transaction ownership

One-shot commands open and close their own connections. REPL state consists of
the database path, timeout, and up to 100 command-name/exit-code records. SQL text
and parameters are excluded from that status history. Interactive line editing
uses in-memory history; the harness writes no persistent history or configuration.
Transactions never span REPL commands. There is no persistent undo/redo: use a
backup before a migration that may need to be reversed later.

`query` and `export-csv` use URI `mode=ro` plus `query_only`. Writes use `mode=rw`
and `BEGIN IMMEDIATE`. Both modes reject user transaction control, savepoints,
ATTACH/DETACH, PRAGMA, and extension loading through an SQLite authorizer.
Internal inspection and transaction completion run with a permissive callback;
this also supports Python 3.10, which cannot clear a callback with `None`.

The authorizer preserves transaction ownership; this CLI is not an isolation
boundary for hostile database files or arbitrary untrusted SQL. The user's own
database constraints and triggers remain active.

## Files, limits, and failures

Database paths are URI-encoded to preserve literal `?`, `#`, and Unicode names.
Create, export, and backup reserve their destination with exclusive creation;
existing files and symlinks are rejected. Incomplete outputs are removed on
failure. Backup uses SQLite's online backup API, including committed WAL pages,
instead of copying the main file alone.

Queries return at most 10,000 rows (1,000 by default), plus a truncation flag.
Each batch accepts 1–1,000 statements and bounds each statement's result to 1,000
rows. These are row limits, not limits on individual cell sizes. CSV operations
stream records, subject to Python's CSV field-size limit. Cooperative SQLite
progress callbacks, lock timeouts, and Python loop checks bound work; they are
not a hard process or memory limit.

Ordinary failures return a nonzero status and `{"error":"..."}` in JSON mode.
A failed integrity check returns its structured report and status 1. REPL command
failures are recorded and the session continues; terminating the REPL returns 0.

## Validation procedure

Install `.[dev]` and provide the native `sqlite3` executable on PATH. Run:

```bash
CLI_ANYTHING_FORCE_INSTALLED=1 python3 -m pytest cli_anything/sqlite/tests -v --tb=no
```

Core tests use temporary real SQLite files with no separate service or executable.
Subprocess tests invoke the installed entry point, produce real DB/CSV artifacts,
and read database artifacts with the native CLI. See `tests/TEST.md` for outcomes
and coverage boundaries.
