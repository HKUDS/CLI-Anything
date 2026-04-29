# cli-anything-lldb

Command-line interface for LLDB debugger using LLDB Python API.

## Installation

```bash
cd lldb/agent-harness
pip install -e .
```

## LLDB Prerequisites

Install LLDB:

```bash
# macOS
xcode-select --install

# Ubuntu
sudo apt install lldb python3-lldb

# Windows
winget install LLVM.LLVM
```

Ensure `lldb` is on `PATH`. The harness auto-discovers Python bindings via:

```bash
lldb -P
```

## Quick Start

```bash
# Show help
cli-anything-lldb --help

# Create a target
cli-anything-lldb --json target create --exe /path/to/executable

# Launch process
cli-anything-lldb --json process launch --arg foo --arg bar

# Set breakpoint by function
cli-anything-lldb --json breakpoint set --function main

# Continue and inspect
cli-anything-lldb --json process continue
cli-anything-lldb --json thread backtrace
cli-anything-lldb --json frame locals

# Evaluate expression
cli-anything-lldb --json expr "argc"

# Close the persistent session when you are done
cli-anything-lldb --json session close

# Start REPL (default mode)
cli-anything-lldb
```

Non-REPL commands share a persistent LLDB session automatically, so commands
such as `target create`, `breakpoint set`, `process launch`, and follow-up
inspection commands can run as separate CLI invocations against the same live
debugger state.

The persistent session daemon now speaks a localhost JSON socket protocol and
stores its session token in an owner-scoped state file. `memory find` scans in
64 KiB chunks and caps each request at 1 MiB.

## Command Groups

- `target`: `create`, `info`
- `process`: `launch`, `attach`, `continue`, `detach`, `info`
- `breakpoint`: `set`, `list`, `delete`, `enable`, `disable`
- `thread`: `list`, `select`, `backtrace`, `info`
- `frame`: `select`, `info`, `locals`
- `step`: `over`, `into`, `out`
- `expr`
- `memory`: `read`, `find`
- `core`: `load`
- `session`: `info`, `close`
- `repl`

## JSON Output

Use `--json` for all commands in agent workflows:

```bash
cli-anything-lldb --json process info
```

## Testing

```bash
cd lldb/agent-harness
pytest cli_anything/lldb/tests/test_core.py -v
pytest cli_anything/lldb/tests/test_full_e2e.py -v
```

E2E tests require:
- a working C compiler (`clang`, `gcc`, or `cc`) so the tests can build a small debug helper
- no extra env vars for the default suite; `LLDB_TEST_CORE` is optional if you want to point the negative-path core-load check at a specific local file
- `memory find` scans are chunked and capped at 1 MiB per invocation
