# cli-anything-joplin

`cli-anything-joplin` is a stateful CLI harness that wraps the real `joplin`
terminal binary and exposes common Joplin workflows under a uniform JSON
command envelope.

It supports:

- harness project state with undo/redo
- notebook lifecycle (`list`, `create`, `use`, `remove`; list supports sort/reverse/long/json)
- note lifecycle (`list`, `create`, `set`, `get`, `remove`, `copy`, `move`, `rename`; list supports sort/reverse/type/long/json)
- to-do management (`create`, `toggle`, `clear`, `done`, `undone`, `list`)
- tag management (`list`, `add`, `remove`, `notetags`, `tagnotes`)
- search (best-effort; some Joplin CLI builds gate `search` behind GUI mode)
- sync (`sync run`, including `--target`, `--upgrade`, `--use-lock`)
- import / export (`jex`, `md`, `enex`, `raw`, `md_frontmatter`, plus import `--force` and `--output-format`)
- attachments (`attach add`)
- backend status and trash restore (`status show`, `status restore`)
- config get/set/list/export/import-file
- backend utilities (`version`, `dump`, `keymap`, `geoloc`, `export-sync-status`)
- API server controls (`server status/start/stop`)
- E2EE utilities (`status`, `target-status`, `decrypt`, `decrypt-file`)
- session controls (`status`, `undo`, `redo`, `history`)
- REPL mode and one-shot command mode

## Requirements

- Python 3.10+
- Joplin terminal CLI installed and available in `PATH` as `joplin`
- Optional: pass `--profile` to target a specific Joplin profile

## Install

```bash
cd joplin/agent-harness
pip install -e .
```

## Usage

```bash
# REPL mode (default)
cli-anything-joplin

# Machine-readable one-shot command
cli-anything-joplin --json notebooks list

# Stateful project
cli-anything-joplin project new --name demo -o ./demo.joplin-harness.json
cli-anything-joplin --project ./demo.joplin-harness.json notes create "Meeting note"

# Dry run (no auto-save)
cli-anything-joplin --json --dry-run --project ./demo.joplin-harness.json notes create temp
```

## JSON output contract

When `--json` is enabled, every command returns:

- `ok`: boolean
- `command`: stable command identifier (e.g. `notes.list`, `todos.toggle`)
- `data`: command payload
- `error`: `null` on success, or `{ type, message }` on failure

Success and failure share the same `command` identifier (e.g. `config.import_file`,
`backend.export_sync_status`). Multi-word subcommands use one dot between the
group and subcommand name.

## Backend behavior

- `run_joplin_command` returns verbatim `stdout`/`stderr` from the Joplin
  process. Benign Node.js deprecation warnings are filtered only when deciding
  whether a non-zero exit code is a real failure.
- `run_joplin_json` retries JSON parsing on a scrubbed copy of stdout when the
  raw stream contains a known warning prefix ahead of the JSON payload.

## Command groups

- `project`: `new`, `open`, `save`, `info`, `json`, `status`
- `notebooks`: `list`, `create`, `use`, `remove`
- `notes`: `list`, `create`, `set`, `get`, `remove`, `copy`, `move`, `rename`
- `todos`: `list`, `create`, `toggle`, `clear`, `done`, `undone`
- `tags`: `list`, `add`, `remove`, `notetags`, `tagnotes`
- `search`: `run`
- `sync`: `run`
- `interop`: `import`, `export`
- `config`: `get`, `set`, `list`, `export`, `import-file`
- `attach`: `add`
- `status`: `show`, `restore`
- `backend`: `version`, `dump`, `keymap`, `geoloc`, `export-sync-status`
- `server`: `status`, `start`, `stop`
- `e2ee`: `status`, `target-status`, `decrypt`, `decrypt-file`
- `session`: `status`, `undo`, `redo`, `history`

## Save behavior

- One-shot mutating commands auto-save when a project is loaded.
- `--dry-run` disables auto-save.
- REPL mode does not auto-save; the user saves explicitly with `project save`.
- Commands that don't deserve a dedicated undo snapshot (e.g. `sync run`,
  `interop export`) still mark the project as dirty via `Session.mark_dirty()`
  so that auto-save still captures the recorded history.

## Test workflow

```bash
# Quick feedback loop
python -m pytest -q cli_anything/joplin/tests/test_core.py
python -m pytest -q cli_anything/joplin/tests/test_full_e2e.py::TestCLISubprocess

# Real backend (requires joplin in PATH)
python -m pytest -v cli_anything/joplin/tests/test_full_e2e.py::TestBackendCommands
python -m pytest -v cli_anything/joplin/tests/test_full_e2e.py::TestBackendWorkflows
python -m pytest -v cli_anything/joplin/tests/test_full_e2e.py::TestBackendIntegration

# Full suite
python -m pytest -v --tb=no cli_anything/joplin/tests

# Verify the installed console script (as opposed to `python -m`)
CLI_ANYTHING_FORCE_INSTALLED=1 python -m pytest -v -s cli_anything/joplin/tests/test_full_e2e.py
```

Current validation baseline (Windows + Joplin CLI 3.6.2):

- `python -m pytest -q cli_anything/joplin/tests/test_core.py` -> `107 passed`
- `python -m pytest -q cli_anything/joplin/tests` -> `134 passed, 1 skipped`

See `cli_anything/joplin/tests/TEST.md` for the full test plan and
`cli_anything/joplin/WORKFLOWS.md` for the verified workflow inventory.
