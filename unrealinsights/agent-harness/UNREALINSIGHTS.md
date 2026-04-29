# UNREALINSIGHTS.md - Software-Specific SOP

## About Unreal Insights

Unreal Insights is Epic's trace analysis tool for Unreal Engine performance,
profiling, timing, and counter data stored in `.utrace` files.

This harness follows the CLI-Anything rule of using the real backend:

- `UnrealInsights.exe` for headless analysis and CSV/TXT export
- a traced Unreal Engine target executable for capture generation

## Backend Model

### Analysis backend

`UnrealInsights.exe` accepts:

- `-OpenTraceFile=<path>`
- `-NoUI`
- `-AutoQuit`
- `-ABSLOG=<path>`
- `-ExecOnAnalysisCompleteCmd=<command>`

The command may be:

- a direct exporter command such as `TimingInsights.ExportThreads`
- `@=<response-file>` for batch execution

This harness can also ensure an engine-matched analysis backend for custom
source engines by locating or building `Engine/Binaries/Win64/UnrealInsights.exe`.

### Capture backend

UE targets can be launched with:

- `-trace=<channels>`
- `-tracefile=<path>`
- optional `-ExecCmds=<cmd1,cmd2,...>`

This harness supports two v1 launch shapes:

- explicit target executable path
- `--project + --engine-root` convenience mode, which resolves `UnrealEditor.exe`

This harness only supports file-mode capture orchestration in v1.

## CLI Coverage Map

| Feature | CLI Command | Status |
|--------|-------------|--------|
| Resolve Insights binaries | `backend info` | v1 |
| Set current trace | `trace set` | v1 |
| Inspect current trace | `trace info` | v1 |
| Launch traced target | `capture run` | v1 |
| Export threads | `export threads` | v1 |
| Export timers | `export timers` | v1 |
| Export timing events | `export timing-events` | v1 |
| Export timer statistics | `export timer-stats` | v1 |
| Export timer callees | `export timer-callees` | v1 |
| Export counter list | `export counters` | v1 |
| Export counter values | `export counter-values` | v1 |
| Batch response file | `batch run-rsp` | v1 |
| Control live instances | — | future |
| Trace store browsing | — | future |

## Current Limitations

- Windows-first discovery only
- No SessionServices control of already-running UE instances
- No trace store session enumeration
- Capture orchestration assumes the target executable accepts standard UE trace flags
