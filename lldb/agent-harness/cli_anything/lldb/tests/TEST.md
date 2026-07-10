# TEST.md - LLDB CLI Test Plan

## Test Inventory Plan

- `test_core.py`: DAP framing, daemon security, persistent session, breakpoint semantics, pause/interrupt, and lifecycle unit tests
- `test_full_e2e.py`: persistent CLI workflow, DAP workflow, attach cleanup, and optional core-load E2E tests

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
- Validate unresolved breakpoints fail by default and explicit pending breakpoints report `resolved=false`
- Validate step/continue/backtrace/locals/evaluate return schemas
- Validate thread/frame select logic
- Validate cleanup semantics for attached vs launched inferiors
- Validate interrupt maps to `SBProcess.Stop()`

### `utils/session_server.py`
- Validate session state files are written with restrictive permissions where the platform supports them
- Validate the persistent daemon rejects methods outside the explicit RPC allowlist

### `dap.py`
- Validate DAP `Content-Length` framing and malformed-frame errors
- Validate initialize capabilities and `initialized` event emission
- Validate frame/variable references are cleared on resume
- Validate EOF cleanup destroys the LLDB session
- Validate running-state execution events emit `continued`, not a false `stopped`
- Validate DAP `pause` calls the async interrupt path and emits a pause stop event
- Validate DAP breakpoint mutation during an active continue requests async interrupt and waits for stopped state
- Validate DAP breakpoint mutation reports a clear timeout when the target does not stop
- Validate DAP auto-continues known internal JIT/startup breakpoint stops when explicitly enabled
- Validate structured DAP stop rules can match by module/function/reason/regex and classify internal traps
- Validate external DAP stop-rule profile files inject target-specific auto-continue rules
- Validate DAP stopped events distinguish manual pauses, internal traps, and ordinary debuggee stops
- Validate DAP transcript response/event ordering for initialize, launch, breakpoint setup, and configuration completion
- Validate DAP `modules` and `exceptionInfo` response shapes
- Validate DAP `readMemory` base64 encoding and expandable variable references

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
- Run DAP initialize -> launch -> setFunctionBreakpoints -> configurationDone -> stopped -> threads -> stackTrace -> scopes -> variables -> setVariable -> evaluate -> source -> loadedSources -> readMemory -> modules -> exceptionInfo -> disassemble -> step/continue
- Run DAP `setBreakpoints` with a real source line and verify the breakpoint resolves and stops
- Run DAP stop-on-entry and verify the stopped event reports `reason=entry`
- Attach to a live process, then close the LLDB session without killing the attached process
- Load core dump negative path without a target selected, using either a provided `LLDB_TEST_CORE` path or an auto-generated placeholder file

### Output validation
- All command responses parse as valid JSON in `--json` mode
- DAP stdout contains only DAP frames, even when the debuggee writes stdout
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

### Workflow name: `dap_probe_session`
- Simulates: an AI debug client driving LLDB through DAP instead of shell commands
- Operations chained:
  1. `initialize`
  2. `launch`
  3. `setFunctionBreakpoints`
  4. `configurationDone`
  5. `threads`
  6. `stackTrace`
  7. `scopes`
  8. `variables`
  9. `setVariable`
  10. `evaluate`
  11. `source`
  12. `loadedSources`
  13. `readMemory`
  14. `modules`
  15. `exceptionInfo`
  16. `disassemble`
  17. `next`
  18. `continue`
- Verified:
  - DAP lifecycle events and stopped reasons
  - locals and expression evaluation through DAP frame ids
  - struct child expansion and stopped-frame variable assignment
  - source/disassembly inspection
  - DAP memory reads, loaded source discovery, module listing, and exception info
  - no debuggee stdout contamination of DAP stdout

### Workflow name: `dap_source_line_breakpoint`
- Simulates: an editor or AI debug client setting a source file/line breakpoint
- Operations chained:
  1. `initialize`
  2. `launch`
  3. `setBreakpoints`
  4. `configurationDone`
- Verified:
  - source line breakpoint resolves to `verified=true`
  - process stops for the breakpoint through DAP

## Test Results

### Commands run

```bash
python -m pytest cli_anything/lldb/tests/test_core.py -v
python -m pytest cli_anything/lldb/tests/test_full_e2e.py -v -s
python -m pytest cli_anything/lldb/tests -q
```

### Result summary

- `test_core.py`: 46 passed
- `test_full_e2e.py`: 7 passed, 2 warnings from LLDB SWIG bindings
- combined default run: 53 passed, 2 warnings from LLDB SWIG bindings
- skip situation: 0 skipped in the current local run; older runs could skip the optional core-load negative-path scenario when `LLDB_TEST_CORE` was unset, but the fixture now creates a local placeholder core path for that negative-path test

### Notes

- Verified the installed `cli-anything-lldb` entrypoint on Windows after editable install
- The core-load negative-path test auto-generates a placeholder file, so no extra env var is required for the default E2E suite
- Fixed REPL fallback behavior for non-interactive subprocess execution on Windows
- Fixed Windows REPL command parsing so quoted paths and inherited `--json` mode work correctly
- Added a persistent background LLDB session so non-REPL commands can share debugger state
- Switched the session daemon to a localhost JSON socket protocol with owner-scoped state file permissions
- `memory find` now uses a chunked scan capped at 1 MiB per call
- Fixed cleanup to detach attached inferiors instead of killing them on session shutdown
- Hardened the persistent daemon state file and RPC method surface
- Added honest breakpoint resolution reporting and explicit pending breakpoint opt-in
- Added a stdio DAP adapter with stop-at-entry, breakpoint, stack, locals, expression, source, disassembly, step, and continue coverage
- Added DAP/CLI interrupt support and tightened DAP lifecycle cleanup/running-state event behavior
- Added a real DAP source-line breakpoint E2E scenario
- Added DAP `loadedSources` and `readMemory` coverage while keeping the harness at version 1.0.0
- Added DAP variable child expansion, `setVariable`, `modules`, `exceptionInfo`, and transcript ordering coverage while keeping the harness at version 1.0.0
- Added non-blocking DAP continue, async pause, guarded running-state breakpoint mutation, and internal breakpoint auto-continue coverage
- Added DAP structured stop-rule profile coverage and `cliAnythingStop` stopped-event metadata for manual pause vs internal trap classification
