# CLI-Anything Turso

A local native Turso database CLI using **pyturso 0.8.3** (Python module `turso`).
It supports one-shot commands and the default REPL, parameterized SQL, schema
inspection, table CRUD, atomic CRUD transactions, and bounded JSON/CSV exports.

This harness is a trusted local SQL tool. Opening a database uses a read-write
native connection. It does not provide read-only confinement, SQL sandboxing,
managed-writer ownership, or an administration interface for Turso Cloud, libSQL,
AgentFS, MCP or sync services. Use only files you are authorized to open/write.

## Installation and native dependency

Python 3.10+ and the native `pyturso==0.8.3` wheel are required; verified on Linux
x86_64. Install in a private virtual environment from this repository:

```bash
python3 -m venv /tmp/turso-harness-env
/tmp/turso-harness-env/bin/python -m pip install -e ./turso/agent-harness
/tmp/turso-harness-env/bin/cli-anything-turso --json doctor
```

No stdlib sqlite3 or libSQL fallback exists. Other SDK versions are refused until
qualified. `doctor` reports the Python/module paths, native-extension SHA-256,
SDK version, and optional `tursodb` executable discovered on PATH; it opens no DB.
The standalone `tursodb` binary is an independent native verification dependency
for the integration suite, not the runtime transport. Obtain version 0.8.3 from
[official releases](https://github.com/tursodatabase/turso/releases/tag/v0.8.3).
SQL `turso_version()` and `sqlite_version()` are diagnostic engine strings; they
can differ between SDK and shell builds. Distribution metadata and binary
`--version` identify the installed products.

## Command surface

Global options precede the command: `--json`, `--database PATH`, `--session PATH`.
No default database is opened. URLs and `:memory:` are unsupported. Database
selection reports a resolved absolute path in results and errors. Creation is
explicit and refuses existing destinations; all other commands require an
existing file. Parent directories must already exist.

| Command | Behavior |
| --- | --- |
| `doctor`, `status` | Dependency identity; selected database/native version |
| `db create PATH`, `db open PATH`, `db close` | Create/select/clear selection |
| `schema` | Ordered sqlite_schema objects, maximum 10000 |
| `table list`, `table describe NAME` | Tables and columns, maximum 10000 |
| `sql STATEMENT --params JSON --limit N` | Exactly one trusted SQL statement, explicit commit |
| `table rows NAME --where JSON --limit N` | Bound equality/NULL filters |
| `table insert NAME --values JSON` | Insert one row |
| `table update NAME --values JSON --where JSON` | Update matching rows |
| `table delete NAME --where JSON` | Delete matching rows |
| `transaction run FILE` | One atomic JSON array of 1..1000 CRUD operations |
| `export NAME --output PATH --format json\|csv --limit N` | New bounded table export |
| `repl` (also default with no command) | Same commands, selection held in memory |

Update/delete require nonempty `--where` or explicit `--all`. A predicate ANDs
column equality tests; NULL uses `IS NULL`. Identifiers are quoted and values are
bound separately. DDL, indexes and more complex predicates use `sql`.

```bash
# Use a new owned synthetic scratch directory.
mkdir -p /tmp/my-turso-fixtures
cli-anything-turso --json --session /tmp/my-turso-fixtures/selection.json db create '/tmp/my-turso-fixtures/example db.db'
cli-anything-turso --json --session /tmp/my-turso-fixtures/selection.json sql 'CREATE TABLE items(id INTEGER PRIMARY KEY, label TEXT UNIQUE)'
cli-anything-turso --json --session /tmp/my-turso-fixtures/selection.json table insert items --values '{"id":1,"label":"hello"}'
cli-anything-turso --json --session /tmp/my-turso-fixtures/selection.json sql 'SELECT id,label FROM items WHERE id=:id ORDER BY id' --params '{"id":1}' --limit 20
cli-anything-turso --json --session /tmp/my-turso-fixtures/selection.json export items --output /tmp/my-turso-fixtures/items.json
```

`--database` overrides a loaded session for that invocation. It does not save
selection by itself; `db create/open/close` save selection when `--session` is
supplied. Sessions store only a version and database path. Saves and reads use
nonblocking Unix flock; contention fails immediately rather than waiting.
Malformed existing state is not overwritten. No implicit home-directory session
or history is written.

## Parameters, output and errors

`--params` accepts a positional array or an object with unprefixed names. Supported
placeholders are `?`, `?NNN`, `:name`, `@name`, `$name` with simple alphanumeric/
underscore names. Mapping keys may include numeric strings for `?NNN`; anonymous
`?` requires an array. Missing binds and positional count mismatches are errors.
Extra mapping keys are ignored. Extended Tcl-style names are unsupported. The
placeholder scanner skips SQL strings, quoted identifiers and comments; it is
only parameter handling and does not restrict SQL authority.

Values are text, NULL, booleans (native integer 0/1), signed 64-bit integers,
finite floats, or `{"$blob":"00ff"}`. Nonfinite input and wider integers are
refused rather than silently converted. Output blobs use the same tagged object;
nonfinite SQL results use `{"$float":"inf"}` (or `-inf`/`nan`). Rows are arrays
with a separate `columns` array, preserving duplicate column names.

`--json` emits one JSON object on stdout per successful command. Errors emit one
JSON object on stderr, leave stdout empty, and exit 1; CLI usage errors exit 2.
Ctrl-C/SIGINT during a command reports `error: "interrupted"` and exits 130 (the
REPL records the failure and continues). Uncommitted work is rolled back and the
connection released. An interrupt that lands during or after the commit can report
`interrupted` for a command whose changes are already durable, so verify state
before retrying. Native work is only interrupted once control returns to Python,
so cancellation of arbitrary native SQL is not guaranteed.
`ok`, `database`, and `error` identify failures; transaction statement failures
also report a zero-based `operation_index`. Standard `--help`/`--version` retain
Click's text format. Without `--json`, results are formatted JSON for inspection.

The default result limit is 100, maximum 10000; `row_count` counts returned rows
and `truncated` reports omitted rows. `rows_affected` is NULL when the SDK does
not supply a count (including RETURNING). SQL results are drained before commit
so bounded RETURNING output still completes the mutation. The cap bounds retained
rows, **not cell size, query execution cost, memory inside the engine, or runtime**.
Use SQL LIMIT for work reduction and an external process timeout for trusted long
queries. Table row order is unspecified; use SQL ORDER BY for deterministic order.

## Transactions and REPL

Each command opens, explicitly commits/rolls back, and releases its connection.
Foreign keys are enabled and read back for each connection. The SDK connection
context manager is not used because 0.8.3 can swallow a failed COMMIT. A deferred
constraint failure returns an error and rolls back; no successful commit is
reported. Native lock conflicts fail without retry; no experimental multiprocess
or MVCC options are enabled. A closed SDK object can retain native file ownership;
the adapter releases its references, including exception tracebacks, between REPL
commands. This is not a multi-writer coordination service.

Create `operations.json` with this content, then run
`cli-anything-turso --json --database PATH transaction run operations.json`:

```json
[
  {"op":"insert","table":"items","values":{"id":2,"label":"second"}},
  {"op":"update","table":"items","values":{"label":"updated"},"where":{"id":1}},
  {"op":"delete","table":"items","where":{"id":2}}
]
```

The adapter validates the complete manifest, executes BEGIN IMMEDIATE, stops on
first failure, and explicitly commits or rolls back the whole transaction.
Transaction manifests cannot contain raw SQL or transaction-control statements.
`sql` accepts exactly one statement and commits that command; BEGIN/COMMIT cannot
span commands. SQL scripts, migrations, savepoints, nested transactions, undo/redo,
and raw SQL transaction batches are not exposed.

The REPL accepts the identical command syntax (quote SQL/JSON as shell arguments),
plus `help`, `exit`, `quit`. It retains selection without retaining a connection.
Interactive terminals use the shared ReplSkin. Redirected `--json` REPL input emits
JSON lines without banners/prompts/goodbyes; any failed command makes the final
exit code 1 while subsequent commands can recover. No REPL history is persisted.

## Exports and scope limits

JSON exports preserve typed rows and include database identity, columns and
truncation metadata. CSV uses standard quoting, empty cells for NULL, and JSON text
for tagged blobs/nonfinite values; CSV loses type distinctions. Export destinations
must be new. A truncated export succeeds with `truncated=true`; it is never a full
database dump or backup. Schema, triggers, indexes and PRAGMAs are not exported.

This version qualifies ordinary local tables and the tested SQL/transaction subset.
It does not qualify full SQLite compatibility, extensions, encryption, backup/
restore, concurrent writers, MVCC, FTS/vector behavior, remote URLs, Cloud account
administration, MCP, sync or AgentFS. Arbitrary trusted SQL retains the native
engine's file/extension capabilities. No service is started and no global setup
or managed database migration is performed.

## Tests

Install development dependencies into the private environment. Create a private
parent directory for pytest fixtures, then run with a new owned basetemp:

```bash
python -m pip install -e './turso/agent-harness[dev]'
mkdir -p /tmp/turso-private-test-parent
CLI_ANYTHING_FORCE_INSTALLED=1 TURSODB_BIN=/absolute/path/to/tursodb \
  timeout 120s python -m pytest turso/agent-harness/cli_anything/turso/tests -v \
  --basetemp=/tmp/turso-private-test-parent/run1
```

Unit tests need no native backend. Integration tests fail if the SDK or binary is
missing. All DBs are newly owned synthetic fixtures; subprocess probes use 5–10
second bounds. See `tests/TEST.md` for the test plan and recorded results, and
`tests/COVERAGE.md` for every command/option and meaningful REPL path. The Linux
pseudo-TTY checks exercise human output, error recovery, exit, Ctrl-C and Ctrl-D
with a controlling terminal and a raw-input readiness handshake.

Sources: [official CLI getting started](https://github.com/tursodatabase/turso/blob/main/docs/sql-reference/cli/getting-started.mdx)
and [native database manual](https://github.com/tursodatabase/turso/blob/main/docs/manual.md).
Mutable upstream docs describe more than the pinned, measured subset above.
