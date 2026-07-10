# EEZ Studio Harness Test Plan

## Test Inventory Plan

- `test_core.py`: 8 unit tests planned.
- `test_full_e2e.py`: 4 end-to-end tests planned.

## Unit Test Plan

### `core.project`

- Create a native LVGL `.eez-project` JSON document.
- Validate required EEZ Studio sections: `settings.general`, `settings.build`, `userPages`, `scpi`.
- Save/load round trip.
- Mutate general settings and build destination.
- Add pages and LVGL widgets.

### `core.scpi`

- Add SCPI subsystems, commands, and parameters.
- Preserve query response metadata for commands ending with `?`.

### `core.session`

- Track undo/redo snapshots across native project mutations.

### CLI JSON

- Use Click/subprocess execution to verify `--json project new` emits machine-readable output and creates a valid project.

## E2E Test Plan

### Native CLI Workflow

- Create a saved `.eez-project`.
- Add a label, button, SCPI subsystem, and SCPI query command through the installed CLI.
- Reload and validate JSON structure.

### Backend Status Probe

- Call `backend status --json` to verify the CLI reports backend availability as structured JSON.

### Real Backend Inspect

- Default run: call `lvgl backend-inspect` without `EEZ_STUDIO_SOURCE` and verify the CLI returns a structured unavailable-backend error with setup instructions.
- Opt-in live run: when `EEZ_STUDIO_RUN_LIVE_BACKEND=1` and `EEZ_STUDIO_SOURCE` points to a built checkout, call `lvgl backend-inspect` through the CLI and verify structured project info from EEZ Studio's built `docker-build-lib.js`.

### Simulator Output Verification

- Validate generated simulator output by checking `index.html`, `index.js`, and WebAssembly magic bytes for `index.wasm`.

## Realistic Workflow Scenarios

**Embedded panel scaffold**

- Simulates: embedded GUI developer scaffolding a panel project.
- Operations chained: create project, add LVGL widgets, save, validate.
- Verified: native JSON structure, page/widget counts, output file presence.

**SCPI instrument command model**

- Simulates: test engineer adding a measurable instrument command surface.
- Operations chained: add subsystem, add query, add parameter when applicable.
- Verified: subsystem and command arrays match EEZ Studio SCPI model.

**Backend LVGL project inspection**

- Simulates: build automation reading EEZ project settings before a manufacturing/test export.
- Operations chained: prepare destination directory, verify default unavailable-backend behavior, optionally invoke real EEZ Studio Node backend.
- Verified: structured unavailable-backend error by default; backend exit code and structured project info from `docker-build-lib.js` when opted in.

## Test Results

Commands run from `eez-studio/agent-harness`:

```bash
python3 -m json.tool ../../registry.json
python3 -m compileall cli_anything/eez_studio
python3 -m pip install -e .
python3 -m pytest cli_anything/eez_studio/tests/test_core.py -v
env -u EEZ_STUDIO_SOURCE -u EEZ_STUDIO_RUN_LIVE_BACKEND python3 -m pytest cli_anything/eez_studio/tests/test_full_e2e.py -v
```

Unit test result:

```text
cli_anything/eez_studio/tests/test_core.py::test_create_project_has_native_sections PASSED
cli_anything/eez_studio/tests/test_core.py::test_save_load_round_trip PASSED
cli_anything/eez_studio/tests/test_core.py::test_set_general_and_destination PASSED
cli_anything/eez_studio/tests/test_core.py::test_add_page_and_widgets PASSED
cli_anything/eez_studio/tests/test_core.py::test_scpi_subsystem_command_parameter PASSED
cli_anything/eez_studio/tests/test_core.py::test_session_undo_redo PASSED
cli_anything/eez_studio/tests/test_core.py::test_cli_json_project_new PASSED
cli_anything/eez_studio/tests/test_core.py::test_cli_json_mutation_autosaves PASSED
cli_anything/eez_studio/tests/test_core.py::test_repl_dispatch_preserves_open_session_mutation_and_undo PASSED
cli_anything/eez_studio/tests/test_core.py::test_custom_build_command_uses_shlex_for_quoted_args PASSED

10 passed in 0.11s
```

Full E2E result:

```text
cli_anything/eez_studio/tests/test_full_e2e.py::TestCLISubprocessE2E::test_help PASSED
cli_anything/eez_studio/tests/test_full_e2e.py::TestCLISubprocessE2E::test_native_project_scpi_workflow PASSED
cli_anything/eez_studio/tests/test_full_e2e.py::TestCLISubprocessE2E::test_backend_status_json PASSED
cli_anything/eez_studio/tests/test_full_e2e.py::TestCLISubprocessE2E::test_backend_inspect_reports_unavailable_without_source PASSED
cli_anything/eez_studio/tests/test_full_e2e.py::TestCLISubprocessE2E::test_real_backend_inspect_required SKIPPED

4 passed, 1 skipped in 1.12s
```

Unavailable backend evidence:

```text
stderr:
{
  "error": "EEZ Studio backend is not available.\n\nInstall/build the real target software and point this harness at it:\n  git clone https://github.com/eez-open/studio.git\n  cd studio\n  npm install\n  npm run build\n  export EEZ_STUDIO_SOURCE=/absolute/path/to/studio\n\nFor full LVGL simulator builds, Docker must also be installed and running.\n",
  "type": "RuntimeError"
}
```

## Summary Statistics

- Unit tests: 10 passed, 0 failed.
- Full E2E tests: 4 passed, 1 skipped by default because live backend inspection is opt-in.
- Registry JSON validation: passed.
- Python compile validation: passed.
- Editable install: passed.

## Coverage Notes

The native `.eez-project` editing path, REPL session reuse, session undo/redo, SCPI model edits, CLI subprocess execution, JSON output, unavailable-backend handling, and quoted custom build command parsing are covered. The real EEZ Studio backend path is implemented as an opt-in E2E gate for environments with `EEZ_STUDIO_RUN_LIVE_BACKEND=1` and a built `EEZ_STUDIO_SOURCE`.
