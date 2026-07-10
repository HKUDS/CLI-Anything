# OpenRefine CLI-Anything Harness

This harness exposes OpenRefine's documented local HTTP API as a stateful, agent-friendly Click CLI.
It does not reimplement OpenRefine data cleaning. Project creation, row reads, operation application,
export, and undo/redo are delegated to a running OpenRefine backend.

## Backend Boundary

- Default backend URL: `http://127.0.0.1:3333`
- Override with `OPENREFINE_URL` or `--base-url`
- Expected backend: OpenRefine 3.10.x or newer
- Startup example: `openrefine -i 127.0.0.1 -p 3333`

The backend wrapper lives at `cli_anything/openrefine/utils/openrefine_backend.py`.
It wraps these OpenRefine surfaces:

- `/command/core/get-version`
- `/command/core/get-all-project-metadata`
- `/command/core/get-project-metadata`
- `/command/core/create-project-from-upload`
- `/command/core/get-rows`
- `/command/core/apply-operations`
- `/command/core/export-rows`
- `/command/core/get-history`
- `/command/core/get-csrf-token`
- `/command/core/undo-redo`
- `/command/core/delete-project`

## CLI Model

The entry point is `cli-anything-openrefine`.

Running the command with no subcommand enters the default REPL. One-shot commands are grouped by domain:

- `server`: backend start and ping helpers
- `project`: list, open, and import OpenRefine projects
- `data`: inspect rows, apply operation histories, export rows
- `ops`: generate reusable OpenRefine operation-history JSON
- `session`: show state and call undo/redo

All commands accept global `--json` for machine-readable output.

## State Model

Session state is JSON and defaults to `~/.cli-anything-openrefine/session.json`.
Use `--session <path>` for isolated automation runs.

The session stores:

- backend URL
- selected project id and name
- last export path
- local action history
- redo stack

Undo/redo uses OpenRefine's backend undo-redo endpoint when a project is selected. If no backend project is selected,
the session store can still undo/redo local action history.

## Operation Histories

The harness passes OpenRefine operation JSON through to the backend. It also provides small builders for common operations:

```bash
cli-anything-openrefine ops text-transform ops.json --column Name --expression 'value.trim()'
cli-anything-openrefine ops mass-edit ops.json --column City --edit NYC='New York'
cli-anything-openrefine data apply ops.json --project-id 123456789
```

Agents can also provide existing OpenRefine operation-history JSON exported from the UI.

## Install

```bash
cd openrefine/agent-harness
python -m pip install -e .
```

## Test

Backend-free unit tests:

```bash
python -m pytest cli_anything/openrefine/tests/test_core.py -v
```

Real backend E2E tests:

```bash
openrefine -i 127.0.0.1 -p 3333
python -m pytest cli_anything/openrefine/tests/test_full_e2e.py -v
```

## Limitations

- The OpenRefine HTTP API is documented as subject to change. This harness targets OpenRefine 3.10.x API behavior.
- Reconciliation-specific commands are not first-class yet; agents can still apply exported reconciliation operation histories.
- Long-running operations are synchronous from the harness perspective and rely on backend HTTP completion.
