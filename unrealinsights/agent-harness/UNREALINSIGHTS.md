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

Simple exporter filters are emitted without inner quotes, for example
`-threads=GameThread`, `-timers=*`, and `-counter=*`. This keeps Unreal's
`FParse::Token` from treating backslash-escaped quotes as literal filter text
inside `-ExecOnAnalysisCompleteCmd`.

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

This harness supports file-mode capture orchestration plus v1 helper surfaces
for Trace Store discovery, GUI co-pilot launch, pluggable live command delivery,
and basic timing/counter summaries.

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
| Trace Store browsing | `store info/list/latest` | v1 |
| List live UE processes | `live processes` | v1 |
| Send live console command | `live exec` | v1 backend boundary |
| Common trace control commands | `live trace-status/bookmark/screenshot/snapshot/stop-trace` | v1 backend boundary |
| Keep Unreal Insights GUI running | `gui status/open/open-latest` | v1 |
| Timing/counter summary | `analyze summary` | v1 |
| Export result classification | `output_status` / `export_status` JSON fields | v1 |

## Current Limitations

- Windows-first discovery only
- Live command delivery requires an external SessionServices/ushell-style backend
  configured through `UNREALINSIGHTS_LIVE_EXEC` or `--backend-command`
- Capture orchestration assumes the target executable accepts standard UE trace flags
- `capture stop` still stops the harness-launched process tree; use
  `live stop-trace` when the intent is to stop trace collection without killing UE
- Empty exporter output is classified as `no_output`; agents should treat that
  as a trace/filter data boundary unless UnrealInsights logs explicit errors
- Deep Memory, Networking, Slate, Asset Loading, and Cooking analysis are reported
  as uncovered domains by `analyze summary`
