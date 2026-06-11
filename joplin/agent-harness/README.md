# Joplin Agent Harness

`cli-anything-joplin` is a stateful CLI harness for the Joplin terminal
application. It wraps the real `joplin` binary for backend operations and is
designed for agent-driven workflows, command validation, and end-to-end
demonstrations.

## What it does

- wraps a Joplin project/session JSON state with undo/redo
- exposes notebook, note, to-do, tag, search, sync, import/export, attachment,
  status, config, backend utility, API server, and E2EE command groups
- emits a stable JSON envelope (`ok`/`command`/`data`/`error`) for machine
  parsing
- supports one-shot and REPL modes
- auto-saves the harness project on mutation; honors `--dry-run`

## Requirements

- Python 3.10+
- Joplin terminal CLI installed and available in `PATH` as `joplin`

## Usage

```bash
# REPL mode
cli-anything-joplin

# One-shot command mode
cli-anything-joplin --json notebooks list

# Use a saved project file
cli-anything-joplin --project ./demo.joplin-harness.json notes create "hello"

# Dry run (no auto-save)
cli-anything-joplin --dry-run --project ./demo.joplin-harness.json todos create temp
```

## Command groups

- `project`
- `notebooks`
- `notes`
- `todos`
- `tags`
- `search`
- `sync`
- `interop`
- `config`
- `attach`
- `status`
- `backend`
- `server`
- `e2ee`
- `session`

## Test structure

- pure unit + CLI-contract tests (no `joplin` binary required)
- CLI subprocess smoke tests
- isolated backend command tests
- short backend workflow tests (note lifecycle, organization, todos, tags,
  search, sync, export, import, attach, history)
- one full end-to-end roundtrip

Current validation baseline (Windows + Joplin CLI 3.6.2):

- `python -m pytest -q cli_anything/joplin/tests/test_core.py` -> `107 passed`
- `python -m pytest -q cli_anything/joplin/tests` -> `134 passed, 1 skipped`

See `cli_anything/joplin/tests/TEST.md` for the full plan (91 unit + 27 e2e,
2 skipped on Windows) and `cli_anything/joplin/WORKFLOWS.md` for the verified
workflow inventory.
