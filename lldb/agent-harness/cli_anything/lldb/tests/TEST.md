# TEST.md - LLDB CLI Test Plan

## Test Inventory Plan

- `test_core.py`: persistent session + lifecycle unit tests
- `test_full_e2e.py`: persistent workflow / attach cleanup / optional core-load E2E tests

## Unit Test Plan

### `utils/lldb_backend.py`
- Validate import fallback behavior using mocked `subprocess.run`
- Validate error path when `lldb` binary is not found
- Validate invalid `lldb -P` output handling
- Planned tests: 4

### `utils/output.py`
- Validate JSON emission and newline termination
- Validate simple table rendering and empty table behavior
- Planned tests: 3

### `utils/errors.py`
- Validate structured error dict
- Validate debug traceback inclusion
- Planned tests: 2

### `core/session.py`
- Validate target/process guards and high-level wrappers with mocked LLDB objects
- Validate breakpoint set/list/delete/enable operations
- Validate step/continue/backtrace/locals/evaluate return schemas
- Validate thread/frame select logic
- Validate cleanup semantics for attached vs launched inferiors

### `lldb_cli.py`
- Validate `--help` for root and command groups
- Validate JSON error behavior when no target/process exists
- Validate subprocess invocation entrypoint
- Validate persistent session command surface (`session info` / `session close`)

## E2E Test Plan

### Prerequisites
- LLDB installed and available in PATH
- A C compiler (`clang`, `gcc`, or `cc`) so the tests can build a small debug helper
- optional `LLDB_TEST_CORE` to override the placeholder file used for the core-load negative-path check

### Workflows to validate
- Create target in one command, read target info in a later command via the same persisted session
- Set breakpoint -> launch -> inspect threads/backtrace/locals -> evaluate expression -> read/find memory -> step -> continue
- Attach to a live process, then close the LLDB session without killing the attached process
- Load core dump negative path without a target selected, using either a provided `LLDB_TEST_CORE` path or an auto-generated placeholder file

### Output validation
- All command responses parse as valid JSON in `--json` mode
- Required keys exist (`pid`, `state`, `breakpoints`, `threads`, `frames`, etc.)
- Commands fail with structured error payloads when prerequisites are missing

## Realistic Workflow Scenarios

### Workflow name: `persistent_probe_session`
- Simulates: a CLI agent running multi-step debugger commands as separate invocations
- Operations chained:
  1. `target create`
  2. `target info`
  3. `breakpoint set`
  4. `process launch`
  5. `thread backtrace`
  6. `frame locals`
  7. `expr`
  8. `memory read`
  9. `memory find`
  10. `step over`
- Verified:
  - session persistence across non-REPL commands
  - breakpoint hit and stopped-state inspection
  - backtrace frame list shape
  - expression result object shape

### Workflow name: `attach_cleanup_session`
- Simulates: attaching to a live process and then shutting down the LLDB session
- Operations chained:
  1. `target create`
  2. `process attach --pid <pid>`
  3. `session close`
- Verified:
  - attached process remains alive after the debugger session closes

## Test Results

### Commands run

```bash
python -m pytest cli_anything/lldb/tests/test_core.py -v
python -m pytest cli_anything/lldb/tests/test_full_e2e.py -v -s
python -m pytest cli_anything/lldb/tests -q
```

### Result summary

- `test_core.py`: 23 passed
- `test_full_e2e.py`: 4 passed
- combined: 27 passed

### Notes

- Verified the installed `cli-anything-lldb` entrypoint on Windows after editable install
- The core-load negative-path test now auto-generates a placeholder file, so no extra env var is required for the default E2E suite
- Fixed REPL fallback behavior for non-interactive subprocess execution on Windows
- Fixed Windows REPL command parsing so quoted paths and inherited `--json` mode work correctly
- Added a persistent background LLDB session so non-REPL commands can share debugger state
- Switched the session daemon to a localhost JSON socket protocol with owner-scoped state file permissions
- `memory find` now uses a chunked scan capped at 1 MiB per call
- Fixed cleanup to detach attached inferiors instead of killing them on session shutdown
