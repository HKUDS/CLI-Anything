---
name: "cli-anything-lldb"
description: Stateful LLDB debugging via LLDB Python API
version: 0.1.0
command: cli-anything-lldb
install: pip install cli-anything-lldb
requires:
  - lldb (Python bindings)
  - click>=8.0
  - prompt-toolkit>=3.0
categories:
  - debugging
  - native
  - lldb
---

# LLDB CLI Skill

Use this CLI to run structured LLDB debugging workflows with JSON output.

## Capabilities

- Create debug target from executable path
- Launch process or attach by pid/name
- Manage breakpoints (set/list/delete/enable/disable)
- Inspect threads, frames, locals, and backtrace
- Evaluate expressions in current frame
- Read/find process memory
- Load core dumps
- Interactive REPL with persistent session state

## Quick Commands

```bash
cli-anything-lldb --json target create --exe /path/to/exe
cli-anything-lldb --json process launch --arg foo --arg bar
cli-anything-lldb --json breakpoint set --function main
cli-anything-lldb --json process continue
cli-anything-lldb --json thread backtrace --limit 20
cli-anything-lldb --json frame locals
cli-anything-lldb --json expr "myVar"
cli-anything-lldb --json memory read --address 0x1000 --size 64
```

## Command Groups

### target
```bash
cli-anything-lldb --json target create --exe /path/to/exe [--arch x86_64]
cli-anything-lldb --json target info
```

### process
```bash
cli-anything-lldb --json process launch [--arg ARG ...] [--env KEY=VALUE ...] [--cwd DIR]
cli-anything-lldb --json process attach --pid 1234
cli-anything-lldb --json process attach --name myapp --wait-for
cli-anything-lldb --json process continue
cli-anything-lldb --json process detach
cli-anything-lldb --json process info
```

### breakpoint
```bash
cli-anything-lldb --json breakpoint set --function main
cli-anything-lldb --json breakpoint set --file main.c --line 42 --condition "i > 10"
cli-anything-lldb --json breakpoint list
cli-anything-lldb --json breakpoint delete --id 1
cli-anything-lldb --json breakpoint enable --id 1
cli-anything-lldb --json breakpoint disable --id 1
```

### thread / frame / step
```bash
cli-anything-lldb --json thread list
cli-anything-lldb --json thread select --id 11111
cli-anything-lldb --json thread backtrace --limit 50
cli-anything-lldb --json frame select --index 0
cli-anything-lldb --json frame info
cli-anything-lldb --json frame locals
cli-anything-lldb --json step over
cli-anything-lldb --json step into
cli-anything-lldb --json step out
```

### expr / memory / core
```bash
cli-anything-lldb --json expr "argc"
cli-anything-lldb --json memory read --address 0x1000 --size 128
cli-anything-lldb --json memory find "needle" --start 0x1000 --size 4096
cli-anything-lldb --json core load --path /path/to/core
```

## Agent Usage Notes

- Prefer `--json` for all automated flows.
- Non-REPL commands share state across separate invocations through the persistent session daemon until you run `session close` or the idle timeout expires.
- Use REPL when you want an interactive long-running debugger session:
  - run `cli-anything-lldb`
  - execute multi-step commands in one session
- `memory find` uses a chunked scan capped at 1 MiB per call.
- Call `target create` before process or core commands.
- Expect structured errors: `{"error": "...", "type": "..."}`
