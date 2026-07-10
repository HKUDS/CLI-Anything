# LLDB.md - LLDB Backend Notes for CLI-Anything

## Why LLDB Python API

This harness follows the CLI-Anything principle:

> Direct integration with actual software backends — full professional capabilities, zero compromises.

Using `import lldb` is the native backend integration route and avoids fragile
text parsing from `lldb -b -o ...` subprocess output.

## Integration Strategy

1. Try `import lldb`
2. On failure, run `lldb -P` to discover LLDB Python module directory
3. Prepend discovered path to `sys.path`
4. Retry import

This is implemented in `utils/lldb_backend.py`.

## Session Lifecycle

- Initialize LLDB debugger (`SBDebugger.Initialize`, `SBDebugger.Create`)
- Keep one process-level session object during command/repl lifetime
- Use synchronous mode (`SetAsync(False)`) for deterministic command behavior
- Destroy debugger cleanly on session close

## Data Model

All core operations return plain dictionaries:
- process info (`pid`, `state`, `num_threads`)
- stop info (`reason`, `description`, `module`, `function`, `frame`)
- frame info (`function`, `file`, `line`, `address`)
- breakpoints (`id`, `locations`, `condition`)
- expression result (`type`, `value`, `summary`, `error`)

This maps directly to `--json` output mode.

## Current Limitations

- No advanced watchpoint support yet
- Memory search is a naive byte scan over fetched range
- Multi-target workflows are not implemented yet (single active target/session)
