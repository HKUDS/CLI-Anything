---
name: >-
  cli-anything-ghidra
description: >-
  Command-line interface for Ghidra - import and analyze binaries headlessly, list functions, decompile to C, extract strings and imports, and trace cross-references. Designed for AI agents and reverse engineers who need structured, scriptable binary analysis without the GUI.
---

# cli-anything-ghidra

Headless reverse engineering with the real Ghidra (`analyzeHeadless`). Designed for AI agents and reverse engineers who need structured analysis of binaries without a GUI. The target binary is read and copied, never executed.

## Installation

```bash
pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=ghidra/agent-harness
```

**Prerequisites:** Ghidra 12.x unzipped, with `GHIDRA_INSTALL_DIR` pointing at it (the folder containing `support/`), and a JDK 25+ (set `GHIDRA_JAVA_HOME` if the default `JAVA_HOME` is older). See `cli_anything/ghidra/README.md`.

## Usage

Running with no subcommand starts the REPL. Add `--json` before the command for machine-readable output (errors become `{"error": "..."}` with exit code 1, or 2 for a usage error such as a missing argument).

```bash
cli-anything-ghidra --json analyze BINARY [--loader L --processor P --entry ADDR --timeout SEC --force]
cli-anything-ghidra --json info BINARY
cli-anything-ghidra --json functions BINARY [--filter TEXT] [--limit N]
cli-anything-ghidra --json decompile BINARY TARGET
cli-anything-ghidra --json strings BINARY [--min-length N] [--limit N]
cli-anything-ghidra --json imports BINARY
cli-anything-ghidra --json xrefs BINARY TARGET
```

## Command Groups

| Command | Purpose |
|---------|---------|
| `analyze` | Import and analyze once per binary (can take minutes); returns format, language, function count, `analysis_timed_out` and `cached` |
| `info` | Format, language, image base, function and symbol counts |
| `functions` | Name, address and size of every function |
| `decompile` | C pseudo-code for a function by name or address |
| `strings` | Defined strings with address and length |
| `imports` | External symbols per library |
| `xrefs` | References to a symbol or address, with the calling function |

## Agent Guidance

- Always run `analyze` first; the other commands fail with "has not been analyzed" otherwise. Analysis is cached by file content: running `analyze` again on the same bytes with the same `--loader/--processor/--entry` returns the stored result at once with `"cached": true`. Pass `--force` to re-import and re-analyze anyway (for example after changing nothing but wanting a fresh run).
- A typical triage: `info` -> `functions --filter` -> `decompile` of interesting functions -> `xrefs` to find callers -> `strings` / `imports` for behavior hints.
- Raw binaries (firmware, shellcode) need `--loader BinaryLoader --processor <lang id>` and `--entry <addr>`; without an entry no function exists to decompile.
- `TARGET`, `--loader`, `--processor` and `--entry` accept only a strict character set (names, hex addresses, language IDs). A rejection is deliberate (Windows `.bat` injection defense), not a bug.
- Each query takes about 10 seconds because Ghidra starts per call; batch your questions. Root options go before the command: `--json`, and `--query-timeout SEC` (default 300) for slow queries, which also sets the decompiler's own budget.
- If `analyze` returns `"analysis_timed_out": true`, Ghidra stopped at `--timeout` and the result is partial. Queries still work on it; re-run `analyze` with a larger `--timeout` for the full analysis.
- `analyze` on a file Ghidra does not recognize fails with a hint: raw firmware needs `--loader BinaryLoader --processor <language id>`.
- A query that fails with "busy" found the project locked by another run on the same binary; retry in a moment.
- `TARGET` may be a name, a hex address or an address-space address such as `ram:00401000`.
- Never execute the analyzed binary. Treat decompiler output as a hint, not ground truth.
