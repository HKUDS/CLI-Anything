# TEST.md - Unreal Insights CLI Test Plan

## Test Inventory Plan

- `test_core.py`: 70 unit tests planned
- `test_full_e2e.py`: 15 E2E/smoke tests planned

## Unit Test Plan

### `utils/unrealinsights_backend.py`

- Validate binary discovery precedence: explicit path, env var, then Windows auto-discovery
- Validate missing explicit and env paths fail loudly
- Validate Unreal Insights headless command construction
- Validate engine-root binary resolution and build orchestration

### `core/capture.py`

- Validate output trace path normalization
- Validate traced target command construction
- Validate `-ExecCmds=` joining semantics
- Validate `--project + --engine-root` convenience resolution
- Validate tracked capture status, snapshot, and stop flows

### `core/export.py`

- Validate exporter command strings for all supported Timing Insights exporters
- Validate response-file parsing and output inference
- Validate UnrealInsights-safe filename normalization for direct and response-file exports
- Validate placeholder-aware output collection
- Validate legacy UnrealInsights 5.3 export command compatibility
- Validate exporter output classification for `ok`, `no_output`, and hard-error cases

### `core/store.py`

- Validate Trace Store directory resolution
- Validate `.utrace` and `.ucache` enumeration
- Validate latest-trace selection and live-candidate metadata
- Validate Trace Server/store info payloads

### `core/live.py`

- Validate Unreal-related process discovery and role classification
- Validate explicit failure when no live command backend is configured
- Validate configured backend command-template execution

### `core/gui.py`

- Validate GUI command lines omit `-NoUI` and `-AutoQuit`
- Validate GUI launch keeps Unreal Insights running
- Validate GUI status process reporting

### `core/analyze.py`

- Validate synthetic CSV parsing for top timers, focused threads, wait timers, and counter peaks
- Validate standard exporter bundle orchestration
- Validate `--skip-export` summary mode for existing CSV outputs
- Validate `export_status` propagation and diagnostics status counts

### `unrealinsights_cli.py`

- Validate root and group help, including `store`, `live`, `gui`, and `analyze`
- Validate JSON error payloads when trace/backend requirements are missing
- Validate REPL session trace state
- Validate capture convenience-layer argument handling
- Validate JSON command surfaces for the added command groups

## E2E Test Plan

### Prerequisites

- Windows with Unreal Engine tools installed
- Optional trace file via `UNREALINSIGHTS_TEST_TRACE`
- If not set, tests auto-discover the UE sample `example_trace.decomp.utrace` when installed locally
- Optional UE/Game executable via `UNREALINSIGHTS_TEST_TARGET_EXE`

### Workflows to validate

- `backend info` against the local UE install
- `store list/latest` against a synthetic Trace Store
- `gui status` without requiring a running GUI
- `live exec` backend-unavailable JSON boundary
- `analyze summary --skip-export` against synthetic CSV exports
- Export threads/timers/timing-events/timer-stats/timer-callees/counters/counter-values from a real `.utrace`
- Execute a generated response file containing multiple exporter commands
- Launch a traced target executable in file mode and verify `.utrace` creation
- Run `analyze summary` against a real `.utrace` when supplied

## Test Results

### Commands run

```bash
python -m pip install -e .
python -m pytest cli_anything/unrealinsights/tests/test_core.py -q
python -m pytest cli_anything/unrealinsights/tests/test_full_e2e.py -q -s --tb=short
```

### Result summary

- `test_core.py`: 70 passed
- `test_full_e2e.py`: 14 passed, 1 skipped
- Remaining skipped E2E coverage requires `UNREALINSIGHTS_TEST_TARGET_EXE`

### Latest pytest output

```text
......................................................................   [100%]
70 passed in 0.58s

[_resolve_cli] Using installed command: C:\Users\aimidi\AppData\Local\Programs\Python\Python311\Scripts\cli-anything-unrealinsights.EXE
[_resolve_cli] Using installed command: C:\Users\aimidi\AppData\Local\Programs\Python\Python311\Scripts\cli-anything-unrealinsights.EXE
[_resolve_cli] Using installed command: C:\Users\aimidi\AppData\Local\Programs\Python\Python311\Scripts\cli-anything-unrealinsights.EXE
..............s
14 passed, 1 skipped in 80.60s
```

## Coverage Notes

- Real export E2E scenarios run automatically when the UE sample trace is present, or when `UNREALINSIGHTS_TEST_TRACE` is set.
- The local UE sample trace passed threads, timers, timing-events, timer-stats, timer-callees, counters, counter-values, batch, and analyze flows.
- `counter-values` required unquoted simple filter tokens such as `-counter=*`; quoted wildcards were parsed by UnrealInsights as a literal backslash escape and matched zero counters.
- Real capture E2E scenarios remain env-gated because they require a user-supplied target executable.
- Live command delivery is intentionally tested through an external command-template boundary; without `UNREALINSIGHTS_LIVE_EXEC`, live commands fail loudly.
- `analyze summary` currently covers timing/counter CSVs. Memory, Networking, Slate, Asset Loading, and Cooking analysis are documented as uncovered domains.
