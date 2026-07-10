# JOPLIN Harness SOP

## Overview

`cli-anything-joplin` is a stateful CLI harness for Joplin automation backed by
the real `joplin` terminal binary. It is intended for command-driven
workflows, real-backend validation, and agent demo runs.

## Requirements

- Python 3.10+
- Joplin terminal CLI installed and available in `PATH` as `joplin`
- The harness package installed in editable mode for local development

Verify the backend with:

```bash
where joplin       # or `which joplin` on POSIX
joplin help
```

## Install

```bash
cd joplin/agent-harness
pip install -e .
```

## Usage

```bash
# REPL mode (default)
cli-anything-joplin

# One-shot command mode with JSON output
cli-anything-joplin --json notebooks list

# Use a project file
cli-anything-joplin --project ./demo.joplin-harness.json notes create "hello"

# Dry-run (no auto-save)
cli-anything-joplin --json --dry-run --project ./demo.joplin-harness.json notes create temp
```

## Command groups

- `project`: `new`, `open`, `save`, `info`, `json`, `status`
- `notebooks`: `list`, `create`, `use`, `remove`
- `notes`: `list`, `create`, `set`, `get`, `remove`, `copy`, `move`, `rename`
- `todos`: `list`, `create`, `toggle`, `clear`, `done`, `undone`
- `tags`: `list`, `add`, `remove`, `notetags`, `tagnotes`
- `search`: `run`
- `sync`: `run` (`--target`, `--upgrade`, `--use-lock`)
- `interop`: `import`, `export`
- `config`: `get`, `set`, `list`, `export`, `import-file`
- `attach`: `add`
- `status`: `show`, `restore`
- `backend`: `version`, `dump`, `keymap`, `geoloc`, `export-sync-status`
- `server`: `status`, `start`, `stop`
- `e2ee`: `status`, `target-status`, `decrypt`, `decrypt-file`
- `session`: `status`, `undo`, `redo`, `history`

## State model

The harness project is JSON-based and stores:

- `name`
- `created_at`, `updated_at`
- backend settings such as `binary` and `profile`
- user context such as `current_notebook`
- `history` as an operations log

The session keeps in-memory project state plus undo/redo snapshots.

## Save behavior

- One-shot mutating commands auto-save when a project is loaded.
- `--dry-run` disables auto-save.
- REPL mode does not auto-save; the user saves explicitly with `project save`.
- Commands that should not produce an undo snapshot (e.g. `sync run`,
  `interop export`) still mark the project dirty via `Session.mark_dirty()`
  so the auto-save still persists their history entry.

## JSON output contract

When `--json` is enabled, commands return a stable envelope:

- `ok`: boolean
- `command`: command identifier such as `notes.list`, `todos.toggle`
- `data`: command payload
- `error`: `null` on success, or `{ type, message }` on failure

## Testing strategy

### 1. Unit / command tests (`test_core.py`)
Validate harness internals and CLI contract without any backend.

### 2. CLI subprocess tests (`TestCLISubprocess`)
Run the installed `cli-anything-joplin` (or `python -m`) entry point and
assert the externally visible JSON contract for non-mutating commands.

### 3. Real-backend command tests (`TestBackendCommands`)
Single-command checks against the real backend on a fresh profile.

### 4. Real-backend workflow tests (`TestBackendWorkflows`)
Short user-flow scripts covering note lifecycle, organization, todos,
tagging, search (best-effort), sync, export, import, attach, history.

### 5. End-to-end integration test (`TestBackendIntegration`)
Full demo flow used for regression and agent demonstrations; verifies that
the saved project history captures every action performed.

### Test commands

```bash
python -m pytest -q cli_anything/joplin/tests/test_core.py
python -m pytest -q cli_anything/joplin/tests/test_full_e2e.py::TestCLISubprocess
python -m pytest -v cli_anything/joplin/tests/test_full_e2e.py::TestBackendCommands
python -m pytest -v cli_anything/joplin/tests/test_full_e2e.py::TestBackendWorkflows
python -m pytest -v cli_anything/joplin/tests/test_full_e2e.py::TestBackendIntegration
python -m pytest -v --tb=no cli_anything/joplin/tests
```

For real backend runs, ensure `joplin` is installed and available in `PATH`.

Current validation baseline (Windows + Joplin CLI 3.6.2):

- `python -m pytest -q cli_anything/joplin/tests/test_core.py` -> `107 passed`
- `python -m pytest -q cli_anything/joplin/tests` -> `134 passed, 1 skipped`

## Development notes

- Prefer adding new coverage as a small command test first.
- Promote longer user journeys into workflow tests.
- Keep exactly one full integration flow for demonstration and regression.
- Preserve the JSON envelope and backend command naming conventions.
- Prefer Joplin's native `--format json` for list-style commands when the
  source command supports it (`ls` does; `tag list` does not).
- New mutating commands should either call `sess.snapshot(reason)` (creates an
  undo point) or `sess.mark_dirty()` (just marks the project as modified) so
  auto-save still persists the appended history entry.
- `utils/joplin_backend.py` returns raw `stdout`/`stderr` from Joplin. The
  benign-Node-warning filter is used only inside the non-zero exit decision
  (and once inside `run_joplin_json` when JSON parsing fails on stdout that
  may contain a warning prefix). Never rewrite caller-facing stdout.
- Error envelopes must use the same `command` string as success payloads.
  `handle_error` derives IDs with `func.__name__.replace("_", ".", 1)` so
  multi-word subcommands stay `config.import_file`, not `config.import.file`.

## Known limitations

- Some Joplin CLI builds reject `search` outside the REPL with
  `"only available in GUI mode"`. The harness surfaces this as a normal
  `ok=false` JSON envelope; agents should treat search as best-effort.
- Non-ASCII process arguments on Windows pass through `joplin.cmd` ? `cmd.exe`,
  which truncates them to the active code page. Harness JSON state handles
  unicode correctly; only argv-forwarded titles are affected. The unicode
  workflow test is skipped on Windows.
- `notes remove --permanent` / `notebooks remove --permanent` require Joplin
  terminal CLI >= 3.0. Older builds silently ignore unknown options, so the
  harness probes `joplin help rmnote` / `rmbook` once per binary and raises
  a clear `RuntimeError` rather than letting a "permanent" delete fall
  through to a soft trash move. The flag is forwarded as the long-form
  `--permanent` (and `--force` for force), never the short `-p` / `-f`.
- `server start --exit-early` / `--quiet` and `e2ee decrypt --force` are
  gated by the same `joplin help <command>` probe (see
  `_cli_supports_flag` in `core/backend.py`). They are real options of
  Joplin 3.x, but the same "silently ignored unknown option" behaviour
  means dropping them on older builds would either hang the harness on
  the server foreground loop or deadlock e2ee on an interactive
  master-password prompt. The probe raises a clear, actionable error in
  those cases.
