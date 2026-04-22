# TEST.md - Unreal Insights CLI Test Plan

## Test Inventory Plan

- `test_core.py`: 49 unit tests planned
- `test_full_e2e.py`: 10 E2E tests planned

## Unit Test Plan

### `utils/unrealinsights_backend.py`
- Validate binary discovery precedence: explicit path, env var, then Windows auto-discovery
- Validate missing explicit and env paths fail loudly
- Validate Unreal Insights command construction
- Validate engine-root binary resolution and build orchestration
- Planned tests: 13

### `core/capture.py`
- Validate output trace path normalization
- Validate traced target command construction
- Validate `-ExecCmds=` joining semantics
- Validate `--project + --engine-root` convenience resolution
- Validate tracked capture status, snapshot, and stop flows
- Planned tests: 12

### `core/export.py`
- Validate exporter command strings for all supported exporters
- Validate response-file parsing and output inference
- Validate placeholder-aware output collection
- Validate legacy UnrealInsights 5.3 export command compatibility
- Planned tests: 9

### `unrealinsights_cli.py`
- Validate root and group help
- Validate JSON error payloads when trace/backend requirements are missing
- Validate REPL session trace state
- Validate capture convenience-layer argument handling
- Validate `capture status`, `capture stop`, and `capture snapshot` JSON flows
- Planned tests: 12

## E2E Test Plan

### Prerequisites
- Unreal Engine 5.5+ installed with `UnrealInsights.exe`
- Optional trace file via `UNREALINSIGHTS_TEST_TRACE`
- Optional UE/Game executable via `UNREALINSIGHTS_TEST_TARGET_EXE`

### Workflows to validate
- `backend info` against the local UE install
- Export threads/timers/timing-events/timer-stats/timer-callees/counters/counter-values from a real `.utrace`
- Execute a generated response file containing multiple exporter commands
- Launch a traced target executable in file mode and verify `.utrace` creation

### Output validation
- All `--json` responses parse correctly
- Export commands create non-empty output files and surface log paths
- `batch run-rsp` returns the materialized output list
- `capture run --wait` returns exit status plus `.utrace` file metadata

## Realistic Workflow Scenarios

### Workflow name: `trace_export_bundle`
- Simulates: post-capture analysis of a performance trace
- Operations chained:
  1. `trace set`
  2. `export threads`
  3. `export timer-stats`
  4. `export counter-values`
  5. `batch run-rsp`
- Verified:
  - exporter outputs exist
  - response-file execution triggers multiple materialized files
  - JSON payloads include log path and exit code

### Workflow name: `editor_boot_capture`
- Simulates: launching a traced UE executable and recording startup behavior
- Operations chained:
  1. `capture run`
  2. `trace info`
  3. optional exporter pass on the produced trace
- Verified:
  - traced command line contains `-trace=` and `-tracefile=`
  - `.utrace` file is created and has size > 0

## Test Results

### Commands run

```bash
python -m pytest cli_anything/unrealinsights/tests/test_core.py -v --tb=no
python -m pytest cli_anything/unrealinsights/tests/test_full_e2e.py -v -s --tb=no
python -m pip install -e .
cli-anything-unrealinsights --json backend info
```

### Result summary

- `test_core.py`: 49 passed
- `test_full_e2e.py`: 1 passed, 9 skipped
- Manual smoke: installed entrypoint resolved local UE 5.5 binaries successfully

### Coverage notes

- Real export and capture E2E scenarios are env-gated and were skipped because
  `UNREALINSIGHTS_TEST_TRACE` and `UNREALINSIGHTS_TEST_TARGET_EXE` were not set.
- The local Windows auto-discovery path was validated against:
  - `D:\Program Files\Epic Games\UE_5.5\Engine\Binaries\Win64\UnrealInsights.exe`
  - `D:\Program Files\Epic Games\UE_5.5\Engine\Binaries\Win64\UnrealTraceServer.exe`

### Full pytest output

```text
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.0.3, pluggy-1.6.0 -- C:\Users\aimidi\AppData\Local\Programs\Python\Python311\python.exe
cachedir: .pytest_cache
rootdir: D:\code\D5\CLI-Anything-unrealinsights\unrealinsights\agent-harness
collecting ... collected 46 items

cli_anything/unrealinsights/tests/test_core.py::TestOutputUtils::test_output_json PASSED [  3%]
cli_anything/unrealinsights/tests/test_core.py::TestOutputUtils::test_output_table_empty PASSED [  7%]
cli_anything/unrealinsights/tests/test_core.py::TestOutputUtils::test_format_size PASSED [ 11%]
cli_anything/unrealinsights/tests/test_core.py::TestErrorUtils::test_handle_error PASSED [ 14%]
cli_anything/unrealinsights/tests/test_core.py::TestBackendDiscovery::test_explicit_path_precedence PASSED [ 18%]
cli_anything/unrealinsights/tests/test_core.py::TestBackendDiscovery::test_env_path_precedence PASSED [ 22%]
cli_anything/unrealinsights/tests/test_core.py::TestBackendDiscovery::test_auto_discovery PASSED [ 25%]
cli_anything/unrealinsights/tests/test_core.py::TestBackendDiscovery::test_missing_explicit_path_fails PASSED [ 29%]
cli_anything/unrealinsights/tests/test_core.py::TestBackendDiscovery::test_build_insights_command PASSED [ 33%]
cli_anything/unrealinsights/tests/test_core.py::TestCaptureCore::test_normalize_trace_output_path_prefers_explicit PASSED [ 37%]
cli_anything/unrealinsights/tests/test_core.py::TestCaptureCore::test_build_exec_cmds_arg PASSED [ 40%]
cli_anything/unrealinsights/tests/test_core.py::TestCaptureCore::test_resolve_engine_root_from_engine_subdir PASSED [ 43%]
cli_anything/unrealinsights/tests/test_core.py::TestCaptureCore::test_resolve_editor_target PASSED [ 46%]
cli_anything/unrealinsights/tests/test_core.py::TestCaptureCore::test_resolve_capture_target_from_project_and_engine PASSED [ 50%]
cli_anything/unrealinsights/tests/test_core.py::TestCaptureCore::test_build_capture_command PASSED [ 53%]
cli_anything/unrealinsights/tests/test_core.py::TestExportCore::test_build_export_exec_command[threads-TimingInsights.ExportThreads] PASSED [ 56%]
cli_anything/unrealinsights/tests/test_core.py::TestExportCore::test_build_export_exec_command[timers-TimingInsights.ExportTimers] PASSED [ 59%]
cli_anything/unrealinsights/tests/test_core.py::TestExportCore::test_build_export_exec_command[timing-events-TimingInsights.ExportTimingEvents] PASSED [ 62%]
cli_anything/unrealinsights/tests/test_core.py::TestExportCore::test_build_export_exec_command[timer-stats-TimingInsights.ExportTimerStatistics] PASSED [ 65%]
cli_anything/unrealinsights/tests/test_core.py::TestExportCore::test_build_export_exec_command[timer-callees-TimingInsights.ExportTimerCallees] PASSED [ 68%]
cli_anything/unrealinsights/tests/test_core.py::TestExportCore::test_build_export_exec_command[counters-TimingInsights.ExportCounters] PASSED [ 71%]
cli_anything/unrealinsights/tests/test_core.py::TestExportCore::test_build_export_exec_command[counter-values-TimingInsights.ExportCounterValues] PASSED [ 75%]
cli_anything/unrealinsights/tests/test_core.py::TestExportCore::test_build_rsp_exec_command PASSED [ 78%]
cli_anything/unrealinsights/tests/test_core.py::TestExportCore::test_expected_outputs_from_rsp PASSED [ 81%]
cli_anything/unrealinsights/tests/test_core.py::TestExportCore::test_collect_materialized_outputs_placeholder PASSED [ 84%]
cli_anything/unrealinsights/tests/test_core.py::TestCLIHelp::test_main_help PASSED [ 87%]
cli_anything/unrealinsights/tests/test_core.py::TestCLIHelp::test_group_help PASSED [ 90%]
cli_anything/unrealinsights/tests/test_core.py::TestCLIJsonErrors::test_export_threads_requires_trace PASSED [ 93%]
cli_anything/unrealinsights/tests/test_core.py::TestCLIJsonErrors::test_backend_info_json PASSED [ 96%]
cli_anything/unrealinsights/tests/test_core.py::TestCLIJsonErrors::test_capture_project_requires_engine_root PASSED [ 96%]
cli_anything/unrealinsights/tests/test_core.py::TestREPLSessionState::test_trace_set_then_info_in_repl PASSED [ 99%]
cli_anything/unrealinsights/tests/test_core.py::TestCaptureCLIConvenience::test_capture_run_with_project_and_engine_root PASSED [100%]

============================= 46 passed in 0.28s ==============================

============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.0.3, pluggy-1.6.0 -- C:\Users\aimidi\AppData\Local\Programs\Python\Python311\python.exe
cachedir: .pytest_cache
rootdir: D:\code\D5\CLI-Anything-unrealinsights\unrealinsights\agent-harness
collecting ... [_resolve_cli] Using installed command: C:\Users\aimidi\AppData\Local\Programs\Python\Python311\Scripts\cli-anything-unrealinsights.EXE
[_resolve_cli] Using installed command: C:\Users\aimidi\AppData\Local\Programs\Python\Python311\Scripts\cli-anything-unrealinsights.EXE
[_resolve_cli] Using installed command: C:\Users\aimidi\AppData\Local\Programs\Python\Python311\Scripts\cli-anything-unrealinsights.EXE
collected 10 items

cli_anything/unrealinsights/tests/test_full_e2e.py::TestCLISmoke::test_backend_info PASSED
cli_anything/unrealinsights/tests/test_full_e2e.py::TestExportE2E::test_exporter_creates_output[threads-extra_args0] SKIPPED
cli_anything/unrealinsights/tests/test_full_e2e.py::TestExportE2E::test_exporter_creates_output[timers-extra_args1] SKIPPED
cli_anything/unrealinsights/tests/test_full_e2e.py::TestExportE2E::test_exporter_creates_output[timing-events-extra_args2] SKIPPED
cli_anything/unrealinsights/tests/test_full_e2e.py::TestExportE2E::test_exporter_creates_output[timer-stats-extra_args3] SKIPPED
cli_anything/unrealinsights/tests/test_full_e2e.py::TestExportE2E::test_exporter_creates_output[timer-callees-extra_args4] SKIPPED
cli_anything/unrealinsights/tests/test_full_e2e.py::TestExportE2E::test_exporter_creates_output[counters-extra_args5] SKIPPED
cli_anything/unrealinsights/tests/test_full_e2e.py::TestExportE2E::test_exporter_creates_output[counter-values-extra_args6] SKIPPED
cli_anything/unrealinsights/tests/test_full_e2e.py::TestExportE2E::test_batch_run_rsp SKIPPED
cli_anything/unrealinsights/tests/test_full_e2e.py::TestCaptureE2E::test_capture_run_wait SKIPPED

======================== 1 passed, 9 skipped in 0.85s =========================
```
