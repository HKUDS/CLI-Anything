# HARNESS.md - LLDB CLI Harness Specification

## Overview

This harness wraps the **LLDB Python API** into a Click-based CLI tool:
`cli-anything-lldb`.

It provides stateful debugging workflows for agent and script usage, with:
- direct `import lldb` integration
- structured dict outputs for JSON mode
- interactive REPL with persistent debug session

## Architecture

```
agent-harness/
├── HARNESS.md
├── LLDB.md
├── setup.py
└── cli_anything/
    └── lldb/
        ├── lldb_cli.py
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
- `--version`: show package version

## Command Groups

- `target`: create/show target
- `process`: launch/attach/continue/detach/info
- `breakpoint`: set/list/delete/enable/disable
- `thread`: list/select/backtrace/info
- `frame`: select/info/locals
- `step`: over/into/out
- `expr`: evaluate expression
- `memory`: read/find
- `core`: load core dump
- `repl`: interactive mode (default)

## Patterns

1. **Lazy import of LLDB**:
   LLDB bindings are imported only when a command actually needs a session.
2. **Session object**:
   `LLDBSession` owns debugger/target/process lifecycle.
3. **Dict-first API**:
   Core methods return JSON-serializable dict/list structures.
4. **Dual output mode**:
   `_output()` chooses JSON or human-friendly formatting.
5. **Boundary errors**:
   Command layer converts exceptions into structured error payloads.

## Dependency Model

LLDB is a required backend dependency:
- macOS: `xcode-select --install`
- Ubuntu: `sudo apt install lldb python3-lldb`
- Windows: `winget install LLVM.LLVM`

The harness auto-discovers LLDB Python bindings with `lldb -P`.
