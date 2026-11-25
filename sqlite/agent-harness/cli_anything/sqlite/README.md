# SQLite CLI

## Install

From `sqlite/agent-harness`, run `python3 -m pip install -e .`. Python 3.10+ must
be linked to SQLite 3.35+. Check with:

```bash
python3 -c 'import sqlite3; print(sqlite3.sqlite_version)'
cli-anything-sqlite --help
```

Python's binding calls the real embedded SQLite engine. A server, credentials,
and the native `sqlite3` executable are not required to use the harness.

## Create, inspect, and query

Global options precede the command. Each one-shot invocation needs `--database`
unless it creates or opens a database. Without a command, the CLI starts a REPL.

```bash
cli-anything-sqlite --json database create inventory.db
cli-anything-sqlite --json --database inventory.db execute \
  'CREATE TABLE items(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, quantity INTEGER)'
cli-anything-sqlite --json --database inventory.db execute \
  'INSERT INTO items(name,quantity) VALUES (:name,:quantity)' \
  --params '{"name":"coffee","quantity":12}'
cli-anything-sqlite --json --database inventory.db schema list
cli-anything-sqlite --json --database inventory.db schema describe items
cli-anything-sqlite --json --database inventory.db query \
  'SELECT name,quantity FROM items WHERE quantity > ? ORDER BY name' --params '[5]' --limit 100
cli-anything-sqlite --json --database inventory.db database check --full
```

`query` is read-only, even for SQL beginning with `WITH`. `execute` is an explicit
write-capable command. Bind values with `--params`; use `schema describe` to
discover column names. One SQL statement is accepted per query/execute call.

## Atomic migrations and CSV workflows

Save the following as `migration.json`, then run
`cli-anything-sqlite --json --database inventory.db batch migration.json`:

```json
[
  {"sql":"CREATE TABLE stock_events(item_id INTEGER REFERENCES items(id), delta INTEGER)"},
  {"sql":"UPDATE items SET quantity = quantity + ? WHERE name = ?", "params":[3,"coffee"]},
  {"sql":"INSERT INTO stock_events SELECT id, ? FROM items WHERE name = ?", "params":[3,"coffee"]}
]
```

All statements commit together. Any SQL, binding, constraint, or timeout failure
rolls back earlier statements, including table creation. `changes` uses SQLite's
total-change counter, including trigger effects; it is not a count of matched
rows. Foreign keys are enabled. Each result contains at most 1,000 rows; truncating
`INSERT ... RETURNING` output does not truncate the write itself.

```bash
# CSV headers map to existing columns; omitted columns use their defaults.
cli-anything-sqlite --json --database inventory.db import-csv items incoming.csv
cli-anything-sqlite --json --database inventory.db export-csv \
  'SELECT name,quantity FROM items ORDER BY name' report.csv
cli-anything-sqlite --json --database inventory.db database backup inventory-backup.db
```

Import accepts UTF-8 CSV (optional BOM), a unique nonempty header, and consistent
record widths. It streams bound values in a single transaction. Empty fields are
empty strings; SQLite applies the target column's affinity. `processed_rows`
counts input records, and `inserted_rows` counts direct inserts (excluding ignored
records and trigger side effects). Existing constraints and conflict policies
apply. Duplicate ASCII-case column names are rejected.

Export streams UTF-8 CSV with a header. SQL NULL and empty strings both become
empty CSV fields, so CSV cannot losslessly round-trip that distinction. BLOB
columns cause export to fail and remove its partial output; select `hex(column)`
or use the JSON query format instead. Create, export, and backup require a new
destination; existing files and symlinks are never overwritten. Online backup
includes committed WAL data and excludes uncommitted transactions.

## JSON contract

Without `--json`, results are indented JSON and errors go to stderr. With `--json`,
each ordinary command emits one compact JSON document on stdout. `--help` and
`--version` remain text. A query returns:

```json
{"columns":["name","quantity"],"rows":[["coffee",15]],"row_count":1,"truncated":false}
```

Rows are arrays so duplicate column names remain unambiguous. `row_count` counts
returned rows, not the total matching rows. `--limit` accepts 1–10,000; the default
is 1,000. Use an explicit SQL ordering and filter/pagination for larger datasets,
or stream with `export-csv`. Limits count rows, not bytes.

Bound parameters are a JSON array for `?` placeholders or an object for named
placeholders (keys omit the `:`). Values may be strings, null, booleans, signed
64-bit integers, finite numbers, or `{"$base64":"AP8="}` for binary data. Query
BLOBs use the same Base64 representation. Nonfinite SQLite float results use
`{"$float":"inf"}` or `{"$float":"-inf"}`, preserving valid JSON.

Errors use `{"error":"message"}` and a nonzero exit status (normally 1; Click
usage errors use 2). A failed `database check` emits its integrity/foreign-key
report with `ok: false` and exits 1. `--timeout SECONDS` defaults to 5, controls
lock waiting and cooperative query/workflow deadlines, and must be finite and
positive. It is not a hard operating-system execution limit.

## REPL and scope

```text
$ cli-anything-sqlite
database open inventory.db
schema list
query "SELECT * FROM items" --limit 5
session status
session history
quit
```

The REPL retains the selected database and timeout. Each write command commits
independently. `session history` retains only the last 100 command names and exit
codes; interactive input history stays in memory. No history/config files are
written. `--json` suppresses prompts and banners for scripted sessions. Errors
leave the session running; inspect each response or history entry, since the
REPL process exits 0 on quit/EOF.

Use `database info`, `database check`, and `schema` for inspection: user SQL
PRAGMA, ATTACH/DETACH, transaction control, savepoints, and extension loading are
disabled. VACUUM and journal-mode management are outside this harness's scope.
There is no persistent undo, encryption support, remote server integration, or
permission sandbox for hostile SQL/database files. Before a migration requiring
manual recovery, create a backup.
