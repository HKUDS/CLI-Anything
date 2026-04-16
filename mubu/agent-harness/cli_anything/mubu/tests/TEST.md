# Mubu Live Bridge Test Plan And Results

This file follows the CLI-Anything habit of keeping the test plan and the executed results in one place.

## Test Inventory Plan

- `test_mubu_probe.py`: 26 unit / light integration tests planned
- `test_core.py`: 35 pure-logic contract tests planned
- `test_cli_entrypoint.py`: 13 subprocess / entrypoint tests planned
- `test_full_e2e.py`: 11 local-data end-to-end tests planned
- `test_agent_harness.py`: 11 packaging / harness-layout tests planned

Current status:

- `test_mubu_probe.py` exists and passes
- `test_core.py` exists and passes
- `test_cli_entrypoint.py` exists and passes
- `test_full_e2e.py` exists and passes when local Mubu data is available
- `test_agent_harness.py` exists and passes
- canonical harness test modules now also exist under `agent-harness/cli_anything/mubu/tests/`
- no separate `test_live_api.py` exists yet; local-data live coverage currently lives in `test_full_e2e.py` with skip guards and dry-run-first mutation checks

## Unit Test Plan

### Module: `mubu_probe.py`

Functions and behaviors covered now:

- `extract_plain_text`
  - HTML stripping
  - segment-list flattening
- `load_latest_backups`
  - newest snapshot selection per document
- `search_documents`
  - text and note hit detection
- `parse_client_sync_line`
  - `CHANGE` request parsing from sync logs
- `normalize_folder_record`
  - parent/child refs and timestamps
- `normalize_document_meta_record`
  - title/folder/timestamp normalization
- `extract_doc_links`
  - Mubu mention link extraction
- `folder_documents`
  - full folder path resolution
  - ambiguous folder-name detection
- `resolve_document_reference`
  - full document path resolution
  - ambiguous title detection
- `show_document_by_reference`
  - path-aware document open
- `looks_like_daily_title`
  - daily-title detection and template exclusion
- `choose_current_daily_document`
  - current daily selection logic
- `list_document_nodes`
  - live-node flattening for agent targeting
  - depth and query filtering
- `normalize_user_record`
  - token/user normalization
- `latest_doc_member_context`
  - newest member context selection
- `build_api_headers`
  - desktop header shape
- `build_text_update_request`
  - `/v3/api/colla/events` payload construction
- `node_path_to_api_path`
  - conversion from simplified node paths to canonical API paths
- `build_create_child_request`
  - create-event payload construction

Edge cases covered now:

- ambiguous folder names
- ambiguous document titles
- nested node paths
- query filtering on flattened nodes
- header normalization and request shape correctness
- insert-path expansion for child creation
- daily-title filtering and template exclusion

Expected unit count:

- 26 tests

### Module: `test_cli_entrypoint.py`

Behaviors covered now:

- installed-or-module entrypoint resolution
- root help rendering
- REPL help rendering
- default no-arg REPL startup and clean exit
- default REPL banner includes the packaged canonical `SKILL.md` path
- REPL in-memory current-document state
- REPL persisted current-document state across processes
- REPL in-memory current-node state
- REPL persisted current-node state across processes
- REPL alias expansion for both `@doc` and `@node`
- persisted clear-doc behavior across processes
- persisted clear-node behavior across processes
- grouped `discover daily-current` respects the root `--json` flag
- `session status --json` exposes persisted state for agent recovery

Expected subprocess count:

- 13 tests

### Module: `test_core.py`

Behaviors covered now:

- pure helper and transformation contracts
- plain-text and rich-text HTML conversion
- node id generation
- node iteration and path conversion
- folder index construction
- daily-title classification
- normalization helpers and revision parsing
- timestamp parsing and formatting
- default local-path discovery
- ambiguity message formatting
- document metadata enrichment and record deduplication

Expected pure-logic count:

- 35 tests

### Module: `test_full_e2e.py`

Behaviors covered now:

- live local-data discovery commands
- current-daily resolution with `MUBU_DAILY_FOLDER`
- live node listing from the current daily note
- `session use-daily` persisted state
- REPL `use-daily` plus follow-on inspection
- dry-run `update-text`, `create-child`, and `delete-node`

Expected local-data E2E count:

- 11 tests

### Module: `test_agent_harness.py`

Behaviors covered now:

- harness packaging files exist
- canonical source tree exists under `agent-harness/cli_anything/mubu/...`
- canonical test modules exist under `agent-harness/cli_anything/mubu/tests/...`
- harness `setup.py --name` reports the expected package name
- harness `setup.py --version` reports the expected version
- root `setup.py` targets the canonical `agent-harness` source tree
- both setup files declare the `click>=8.0` runtime dependency
- harness skill-generator assets exist
- harness skill generator can regenerate the packaged `SKILL.md`

Expected packaging count:

- 11 tests

## E2E Test Plan

These workflows are currently verified manually against the real local Mubu session instead of an automated live test file. The reason is safety: this bridge can mutate a real personal workspace, so execute-path automation should stay opt-in.

Planned live scenarios:

1. read recent documents from the local desktop profile
2. resolve `<daily-folder-ref>` and identify the current daily note
3. enumerate live nodes inside the current daily note
4. dry-run a text update and inspect the exact outgoing payload
5. execute one same-text live update to validate auth/member/version wiring
6. re-fetch and verify `baseVersion` plus node text after mutation
7. dry-run one child creation to validate canonical create payload generation
8. resolve the current daily note in one step with a date-title-aware selector
9. enumerate live nodes from the current daily note in one step
10. dry-run one node deletion to validate canonical delete payload generation
11. execute a reversible scratch create-then-delete cycle to verify live cleanup

What should be verified in later automated live tests:

- active local auth can be loaded from the Mubu desktop profile
- `document/get` returns a live definition for the resolved document
- `daily-current` resolves the right daily note instead of templates or helper docs
- `daily-nodes` resolves the current daily note and returns live nodes in one pass
- `doc-nodes` returns stable node ids and paths
- `update-text --json` builds a correct dry-run payload
- `update-text --execute --json` returns success and verification data
- document version changes are observed after execution
- `create-child --json` builds a correct canonical `create` event payload
- `delete-node --json` builds a correct canonical `delete` event payload
- reversible scratch create/delete execution works end-to-end

## Realistic Workflow Scenarios

### Workflow 1: Daily Note Discovery

- Simulates: an agent entering a configured daily-note workspace
- Operations chained:
  - `recent`
  - `path-docs '<daily-folder-ref>'`
- Verified:
  - folder path resolution
  - correct daily-note document ids
  - usable timestamps and recency data

### Workflow 2: Inspect Before Mutate

- Simulates: Codex locating the exact node to edit before sending any write
- Operations chained:
  - `open-path '<doc-ref>'`
  - `doc-nodes '<doc-ref>' --query '<anchor>'`
- Verified:
  - live document lookup
  - correct node id
  - correct update-target path

### Workflow 2.5: Current Daily Resolution

- Simulates: Codex jumping directly to the user's current daily note
- Operations chained:
  - `daily-current '<daily-folder-ref>' --json`
  - `daily-current --json` with `MUBU_DAILY_FOLDER='<daily-folder-ref>'`
- Verified:
  - date-like title filtering
  - template exclusion
  - latest-updated selection among daily-note candidates

### Workflow 2.6: Current Daily Live Node Inspection

- Simulates: Codex looking for an anchor inside today's daily note without manually resolving the path first
- Operations chained:
  - `daily-nodes '<daily-folder-ref>' --query '<anchor>'`
  - `daily-nodes --query '<anchor>'` with `MUBU_DAILY_FOLDER='<daily-folder-ref>'`
- Verified:
  - current daily-note resolution
  - live document fetch
  - node listing and query filtering in one step

### Workflow 3: Atomic Text Update

- Simulates: one safe, minimal live edit against the user's real workspace
- Operations chained:
  - `update-text ... --json`
  - `update-text ... --execute --json`
  - live re-fetch verification
- Verified:
  - auth loading
  - member-context selection
  - current `baseVersion` usage
  - accepted `/v3/api/colla/events` payload
  - visible post-write verification data

### Workflow 4: Atomic Child Creation

- Simulates: Codex adding one new child item under an existing outline node
- Operations chained:
  - `doc-nodes ...`
  - `create-child ... --json`
- Verified:
  - parent node targeting
  - child insertion index calculation
  - canonical `children` path generation
  - create-event payload shape

### Workflow 5: Atomic Delete And Cleanup

- Simulates: Codex removing one exact node after inspecting it or after a scratch verification create
- Operations chained:
  - `delete-node ... --json`
  - `create-child ... --execute --json`
  - `delete-node ... --execute --json`
- Verified:
  - parent id and delete index calculation
  - canonical delete-event payload shape
  - live create verification
  - live delete verification
  - post-delete absence of the scratch node

## Test Results

### Automated Unit Results

Command:

```bash
CLI_ANYTHING_FORCE_INSTALLED=1 python3 -m pytest cli_anything/mubu/tests -q
```

Latest result:

```text
96 passed
```

### Syntax Verification

Command:

```bash
python3 -m py_compile mubu_probe.py cli_anything/mubu/mubu_cli.py cli_anything/mubu/__main__.py
python3 -m py_compile agent-harness/mubu_probe.py agent-harness/cli_anything/mubu/mubu_cli.py
python3 -m py_compile agent-harness/cli_anything/mubu/__main__.py agent-harness/setup.py
python3 -m py_compile tests/_canonical_loader.py tests/test_mubu_probe.py tests/test_cli_entrypoint.py tests/test_agent_harness.py
python3 -m py_compile agent-harness/cli_anything/mubu/tests/__init__.py
python3 -m py_compile agent-harness/cli_anything/mubu/tests/test_mubu_probe.py
python3 -m py_compile agent-harness/cli_anything/mubu/tests/test_cli_entrypoint.py
python3 -m py_compile agent-harness/cli_anything/mubu/tests/test_agent_harness.py
```

Latest result:

- exit code `0`

### Installed Entrypoint Verification

Commands:

```bash
.venv/bin/python -m pip install -e ./agent-harness
.venv/bin/python -m pip install -e .
.venv/bin/cli-anything-mubu --help
.venv/bin/cli-anything-mubu --json discover daily-current '<daily-folder-ref>'
.venv/bin/cli-anything-mubu --json discover daily-current
.venv/bin/cli-anything-mubu session status --json
tmpdir=$(mktemp -d)
printf 'exit\n' | env CLI_ANYTHING_MUBU_STATE_DIR="$tmpdir" .venv/bin/cli-anything-mubu
```

Latest result:

- both editable-install paths succeeded when run sequentially
- installed `--help` exposes grouped `discover` / `inspect` / `mutate` / `session` domains
- installed `discover daily-current '<daily-folder-ref>'` resolved the current daily note
- installed `discover daily-current` also works when `MUBU_DAILY_FOLDER` is configured
- installed `session status --json` returned persisted state successfully
- installed no-arg REPL started cleanly, displayed the packaged canonical skill path, and exited cleanly

### Wheel Verification

Commands:

```bash
tmpdir=$(mktemp -d)
.venv/bin/python -m pip wheel --no-deps --wheel-dir "$tmpdir" ./agent-harness
unzip -l "$tmpdir"/cli_anything_mubu-0.1.1-py3-none-any.whl
```

Latest result:

- wheel build succeeded
- wheel contains the packaged README, generated `skills/SKILL.md`, `tests/TEST.md`, canonical test modules, and `utils/repl_skin.py`

Latest result:

- pass

### Install Verification

Commands:

```bash
.venv/bin/python -m pip install -e agent-harness
.venv/bin/python -m pip install -e <repo-root>
```

Latest result:

- both editable installs passed

### Installed Entrypoint Verification

Commands:

```bash
.venv/bin/cli-anything-mubu discover daily-current '<daily-folder-ref>' --json
.venv/bin/cli-anything-mubu discover daily-current --json
printf 'exit\n' | env CLI_ANYTHING_MUBU_STATE_DIR="$(mktemp -d)" .venv/bin/cli-anything-mubu
```

Latest result:

- installed `discover daily-current '<daily-folder-ref>' --json` passed against the real local Mubu session
- installed no-arg `discover daily-current --json` passed when `MUBU_DAILY_FOLDER` was configured
- installed REPL banner pointed to `agent-harness/cli_anything/mubu/skills/SKILL.md`

### Wheel Packaging Verification

Command:

```bash
.venv/bin/python -m pip wheel --no-deps --wheel-dir <tmpdir> agent-harness
```

Latest result:

- built successfully
- wheel contents include `mubu_probe.py`, `cli_anything/mubu/README.md`, `cli_anything/mubu/skills/SKILL.md`, `cli_anything/mubu/tests/TEST.md`, and `cli_anything/mubu/utils/repl_skin.py`

### CLI Surface Verification

Commands:

```bash
python3 mubu_probe.py --help
python3 mubu_probe.py daily-current --help
python3 mubu_probe.py daily-nodes --help
python3 mubu_probe.py doc-nodes --help
python3 mubu_probe.py create-child --help
python3 mubu_probe.py delete-node --help
python3 mubu_probe.py update-text --help
```

Latest result:

- pass
- command list now includes `daily-current`, `daily-nodes`, `doc-nodes`, `create-child`, and `delete-node`
- help for `daily-current`, `daily-nodes`, `update-text`, `doc-nodes`, `create-child`, and `delete-node` renders correctly

### Installed Entrypoint Verification

Commands:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/cli-anything-mubu --help
.venv/bin/cli-anything-mubu repl --help
tmpdir=$(mktemp -d) && env CLI_ANYTHING_MUBU_STATE_DIR="$tmpdir" /usr/bin/zsh -lc "printf 'exit\n' | .venv/bin/cli-anything-mubu"
.venv/bin/cli-anything-mubu discover daily-current '<daily-folder-ref>' --json
.venv/bin/cli-anything-mubu discover daily-current --json
.venv/bin/python -m pip install -e ./agent-harness
python3 agent-harness/setup.py --name
python3 agent-harness/setup.py --version
```

Latest result:

- editable install succeeded in project-local `.venv`
- `cli-anything-mubu --help` renders wrapper + subcommand help
- `cli-anything-mubu repl --help` renders REPL help
- no-arg `cli-anything-mubu` enters the REPL, exposes app/skill/history banner context, and exits cleanly on `exit`
- REPL can store and report the current document reference during a session
- REPL can persist `current-doc` across independent processes when given the same state directory
- REPL can store and report the current node reference during a session
- REPL can persist `current-node` across independent processes when given the same state directory
- REPL can expand both `@doc` and `@node` into a real dry-run command
- installed console script can resolve the current daily note from an explicit folder reference
- installed console script also supports no-arg daily resolution when `MUBU_DAILY_FOLDER` is set
- `agent-harness/` now works as a real editable-install root
- harness setup metadata reports the correct package identity

### Real Local Session Checks

Commands executed on the real machine:

```bash
python3 mubu_probe.py path-docs '<daily-folder-ref>' --limit 5 --json
python3 mubu_probe.py daily-current '<daily-folder-ref>' --json
MUBU_DAILY_FOLDER='<daily-folder-ref>' python3 mubu_probe.py daily-current --json
python3 mubu_probe.py daily-nodes '<daily-folder-ref>' --query '<anchor>' --json
MUBU_DAILY_FOLDER='<daily-folder-ref>' python3 mubu_probe.py daily-nodes --query '<anchor>' --json
python3 mubu_probe.py doc-nodes '<doc-ref>' --query '<anchor>' --json
python3 mubu_probe.py create-child '<doc-ref>' --parent-node-id <node-id> --text 'CLI bridge dry run child' --note 'not executed' --json
python3 mubu_probe.py delete-node '<doc-ref>' --node-id <node-id> --json
python3 mubu_probe.py update-text '<doc-ref>' --node-id <node-id> --text '<replacement-text>' --json
python3 mubu_probe.py update-text '<doc-ref>' --match-text '<anchor>' --text '<replacement-text>' --execute --json
python3 - <<'PY'
# create-child --execute scratch node, then delete-node --execute that exact node id
PY
```

Observed results:

- `path-docs` resolved the configured daily folder successfully
- `daily-current` resolved the same current daily note with both the explicit folder argument and `MUBU_DAILY_FOLDER`
- `daily-nodes` resolved the same current daily note and returned the targeted live node
- `doc-nodes` returned a stable node id plus both simplified and API paths for the target node
- `create-child` dry-run resolved the parent node, child insert index, and canonical child path
- `delete-node` dry-run resolved the parent id, delete index, and canonical API path
- dry-run update produced the expected `CHANGE` payload
- real execute returned success
- live document version advanced after execution
- post-fetch verification confirmed the target node text matched the requested value
- reversible scratch create/delete advanced live version on each execute call
- the scratch node was present after create and absent after delete

## Summary Statistics

- automated tests: 96 / 96 pass
- syntax check: pass
- help/CLI surface checks: pass
- isolated install / entrypoint checks: pass
- targeted real-session checks: pass

## Coverage Notes

Strong coverage:

- local parsing and normalization logic
- path resolution
- live request header construction
- live text-update payload construction
- inspect-before-mutate node targeting
- canonical create-child payload construction
- canonical delete-node payload construction
- current-daily selection logic
- packaged entrypoint and default REPL behavior
- REPL persisted current-document context
- REPL persisted current-node context
- REPL skill-path/history banner context
- harness install-root metadata and install path

Current gaps:

- no automated live execute suite yet
- no rollback/undo tests yet
- no move primitive yet
- no direct `daily-open` shortcut yet

Conclusion:

- the current bridge is verified enough for careful interactive use by Codex
- it is not yet at full CLI-Anything packaged-harness maturity
