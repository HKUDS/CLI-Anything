# HARNESS.md - LLDB CLI Harness Specification

## Overview

This harness wraps the **LLDB Python API** into a Click-based CLI tool and
debug adapter:
- `cli-anything-lldb` for JSON CLI / REPL workflows
- `cli-anything-lldb-dap` for stdio Debug Adapter Protocol clients

It provides stateful debugging workflows for agent and script usage, with:
- direct `import lldb` integration
- structured dict outputs for JSON mode
- interactive REPL with persistent debug session
- a formal single-session DAP server for AI/editor debugging

## Architecture

```
agent-harness/
├── HARNESS.md
├── LLDB.md
├── setup.py
└── cli_anything/
    └── lldb/
        ├── lldb_cli.py
        ├── dap.py
        ├── core/
        │   ├── session.py
        │   ├── breakpoints.py
        │   ├── inspect.py
        │   └── threads.py
        ├── utils/
        │   ├── lldb_backend.py
        │   ├── output.py
        │   ├── errors.py
        │   └── repl_skin.py
        ├── skills/SKILL.md
        └── tests/
```

## Global Options

- `--json`: machine-readable output
- `--debug`: include traceback in errors
- `--session-file`: explicit persistent CLI session state path
- `--version`: show package version

## Command Groups

- `target`: create/show target
- `process`: launch/attach/continue/interrupt/detach/info
- `breakpoint`: set/list/delete/enable/disable
- `thread`: list/select/backtrace/info
- `frame`: select/info/locals
- `step`: over/into/out
- `expr`: evaluate expression
- `memory`: read/find
- `core`: load core dump
- `dap`: run stdio DAP server
- `session`: info/close persistent CLI session
- `repl`: interactive mode (default)

## Debug Adapter Protocol

`cli-anything-lldb-dap` is a stdio DAP server. It owns one in-process
`LLDBSession` and does not use the persistent CLI daemon. Stdout must contain
only DAP `Content-Length` frames; diagnostics go to stderr or `--log-file`.

Supported v1 requests:
- lifecycle: `initialize`, `launch`, `attach`, `configurationDone`, `disconnect`
- breakpoints: `setBreakpoints`, `setFunctionBreakpoints`
- inspection: `threads`, `stackTrace`, `scopes`, `variables`, `setVariable`, `evaluate`, `source`, `loadedSources`, `readMemory`, `modules`, `exceptionInfo`, `disassemble`
- execution: `continue`, `pause`, `next`, `stepIn`, `stepOut`

DAP uses protocol-native pending breakpoint semantics: unresolved breakpoints
return `verified: false`, and later resolution is reported with breakpoint
events.
Variable references are adapter-local and reset on resume. This keeps stopped
frame state honest for AI agents and avoids reusing stale LLDB `SBValue`
objects after execution continues.

## Patterns

1. **Lazy import of LLDB**:
   LLDB bindings are imported only when a command actually needs a session.
2. **Session object**:
   `LLDBSession` owns debugger/target/process lifecycle.
3. **Dict-first API**:
   Core methods return JSON-serializable dict/list structures.
4. **Honest breakpoint state**:
   Breakpoint payloads include `resolved` and `location_details`; CLI unresolved
   breakpoints fail unless `--allow-pending` is explicit.
5. **Dual output mode**:
   `_output()` chooses JSON or human-friendly formatting.
6. **Boundary errors**:
   Command layer converts exceptions into structured error payloads.
7. **Secure persistent daemon**:
   CLI session auth state is written under a per-user directory with restrictive
   permissions and RPC dispatch uses an explicit method allowlist.

## Dependency Model

LLDB is a required backend dependency:
- macOS: `xcode-select --install`
- Ubuntu: `sudo apt install lldb python3-lldb`
- Windows: `winget install LLVM.LLVM`

The harness auto-discovers LLDB Python bindings with `lldb -P`.
