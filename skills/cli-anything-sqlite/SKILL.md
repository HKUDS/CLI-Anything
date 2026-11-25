---
name: "cli-anything-sqlite"
description: "Inspect local SQLite schemas, run parameterized queries, apply atomic SQL batches, import or export CSV, and create online backups with cli-anything-sqlite."
---

# SQLite workflows

Use `cli-anything-sqlite --help` to confirm installation. Requires Python 3.10+
linked to SQLite 3.35+. From this repository, install with
`python3 -m pip install ./sqlite/agent-harness`.

## Inspect and plan

1. Select the target explicitly in each one-shot command:
   `cli-anything-sqlite --json --database PATH database info`.
   For a new database, use `--json database create PATH`; existing paths are refused.
2. Run `--json --database PATH schema list`, then `schema describe TABLE` for
   relevant columns, constraints, and indexes.
3. Inspect data with `query SQL --params JSON --limit N`. This command is read-only;
   bind values using JSON arrays for `?` or objects for `:name` placeholders.
   Check `truncated` before treating the returned rows as complete.

## Change and verify

- Use `execute SQL --params JSON` for one statement, or `batch FILE` for a JSON
  array of `{"sql":"...","params":[...]}` objects. A batch commits atomically;
  any failure rolls back the whole batch, including schema changes.
- Use `import-csv TABLE FILE` to append UTF-8 CSV records to an existing table.
  Headers select columns; values remain strings subject to SQLite affinity.
  Inspect `processed_rows` and `inserted_rows` for ignored records.
- Verify changes with a targeted `query`, then `database check` (or `--full`).
  Ordinary JSON errors contain `error` and exit nonzero; integrity failures
  contain `ok: false` and exit 1.

## Export and recovery

`export-csv SQL OUTPUT --params JSON` streams a read-only query to a new CSV.
NULL and empty strings both export as empty fields. Select `hex(column)` for
BLOBs; JSON queries preserve BLOBs as `{"$base64":"..."}`.

`database backup OUTPUT` makes a consistent online backup, including committed
WAL data. Use a new destination for each export or backup. Back up before changes
that may require manual recovery: there is no persistent undo.

## Command boundaries

Global `--json`, `--database`, and `--timeout` options precede the command. Without
a command, the CLI enters a REPL; `database open PATH` retains the selection until
`quit`. Writes commit per command. REPL failures do not end the process; inspect
each JSON response. Input history is in memory, and `session history` exposes
only command names and exit codes.

Use structured inspection commands for metadata. User SQL cannot run PRAGMA,
ATTACH/DETACH, savepoints, transaction control, or extension loading. Query limits
bound rows, not cell sizes; `--timeout` is a cooperative deadline. For complete
output contracts and supported scope, read the installed `cli_anything/sqlite/README.md`
or its copy under `sqlite/agent-harness/` in this repository.
