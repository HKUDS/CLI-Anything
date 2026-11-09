---
name: cli-anything-turso
description: Operate owned local native Turso database files with parameterized SQL, table CRUD, schema inspection, atomic CRUD transactions and bounded exports. Does not administer Turso Cloud, libSQL, AgentFS or managed database writers.
---

# Local native Turso

Install `turso/agent-harness` into a private Python 3.10+ environment. Required
backend: `pyturso==0.8.3` importing `turso`; no sqlite3 fallback. Run
`cli-anything-turso --json doctor` to see SDK/native extension identity.

Use global `--json --database PATH` before the command, or select via
`--session STATE.json db create/open PATH`. No implicit database creation, default
DB or home session exists. Creation refuses existing files. `--session` is Unix
only; selected paths are absolute and returned in output. Do not point this tool
at a managed writer's database without its owner's explicit authorization.

Commands:

- `db create PATH`, `db open PATH`, `db close`, `status`, `doctor`.
- `schema`, `table list`, `table describe NAME`.
- `sql 'SELECT id,label FROM items WHERE id=:id ORDER BY id' --params '{"id":1}' --limit 20`.
- `table rows items --where '{"label":null}' --limit 20`.
- `table insert items --values '{"id":1,"label":"hello"}'`.
- `table update items --where '{"id":1}' --values '{"label":"new"}'`.
- `table delete items --where '{"id":1}'`. Update/delete need where or explicit `--all`.
- `transaction run operations.json`: array of 1..1000 objects with `op`
  insert/update/delete, `table`, `values` (insert/update), `where` (update/delete)
  or `all:true`. Entire manifest commits or rolls back in BEGIN IMMEDIATE.
- `export items --output NEW.json --format json --limit 100` (also csv).

Create a new synthetic database and schema before inserting. Raw DDL uses `sql`.
SQL accepts one statement and commits per command. Bind arrays to `?`/`?NNN`,
objects with unprefixed keys to simple `:name`/`@name`/`$name`; missing binds are
errors. Text, NULL, bool, signed 64-bit integers, finite floats and
`{"$blob":"00ff"}` are accepted. Extended Tcl parameter names are unsupported.

JSON successes go to stdout; JSON errors go to stderr with `ok:false`, `error`,
`database`, exit 1 (usage 2). Transaction statement errors include zero-based
`operation_index`. Help/version retain text output. Results use `columns` and
array `rows`, `row_count`, `truncated`, `rows_affected` (NULL if unavailable).
Default output limit 100, maximum 10000. Truncation caps retained rows, not cell
size, native execution cost or runtime. Use external timeouts for long queries.
Exports are bounded table rows, not backup: CSV loses types; JSON preserves them.

No command enters a transaction that survives to the next command. Default with
no subcommand starts a REPL accepting the same shell-quoted commands, plus
help/exit/quit. Selection persists in memory, while native connections are released
between commands. Piped `--json` REPL output is JSON lines; any command error makes
the final exit status 1. Native and session lock contention fail without retry.

This is a trusted **read-write** local SQL tool. It does not enforce read-only
confinement or SQL sandboxing; SQL can use native file/extension capabilities.
No Cloud login, libSQL, AgentFS, MCP/sync, multi-writer coordination, full SQLite
compatibility, migrations, MVCC, FTS/vector qualification or backup/restore is
provided. Never infer feature support from current docs alone.
