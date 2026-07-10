# cli-anything-unrealinsights

Command-line interface for Unreal Insights trace capture and export workflows.

This harness wraps the real Unreal Engine tools:

- `UnrealInsights.exe` for headless `.utrace` analysis and exporters
- a traced UE/Game executable for file-mode capture generation

## Installation

```bash
cd unrealinsights/agent-harness
pip install -e .
```

## Prerequisites

- Windows with Unreal Engine tools installed
- verified with UE 5.5; the headless timing exporters include legacy handling for
  UE 5.3-style command parsing where possible
- optional `UnrealTraceServer.exe` for backend reporting

You can point the harness at explicit binaries:

```powershell
$env:UNREALINSIGHTS_EXE='D:\Program Files\Epic Games\UE_5.5\Engine\Binaries\Win64\UnrealInsights.exe'
$env:UNREAL_TRACE_SERVER_EXE='D:\Program Files\Epic Games\UE_5.5\Engine\Binaries\Win64\UnrealTraceServer.exe'
```

If those are not set, the harness auto-discovers common UE installs under
`<drive>:\Program Files\Epic Games\UE_*`.

## Quick Start

```powershell
# Inspect resolved backend binaries
cli-anything-unrealinsights --json backend info

# Inspect the local Trace Store and select the latest trace
cli-anything-unrealinsights --json store info
cli-anything-unrealinsights --json store latest --set-current

# Find or build UnrealInsights.exe for a custom engine root
cli-anything-unrealinsights --json backend ensure-insights `
  --engine-root 'D:\code\D5\d5render-ue5_3'

# Bind a trace file for the current session
cli-anything-unrealinsights trace set D:\captures\session.utrace

# Start a background capture session and keep it running
cli-anything-unrealinsights --json capture start `
  --project 'D:\Projects\MyGame\MyGame.uproject' `
  --engine-root 'D:\Program Files\Epic Games\UE_5.5' `
  --output-trace D:\captures\live_session.utrace

# If a tracked capture is already running, replace it explicitly
cli-anything-unrealinsights --json capture start --replace `
  --project 'D:\Projects\MyGame\MyGame.uproject' `
  --engine-root 'D:\Program Files\Epic Games\UE_5.5' `
  --output-trace D:\captures\replacement_session.utrace

# Check current capture status
cli-anything-unrealinsights --json capture status

# Create a best-effort snapshot without ending the session
cli-anything-unrealinsights --json capture snapshot D:\captures\live_snapshot.utrace

# Stop the tracked capture session
cli-anything-unrealinsights --json capture stop

# List live UE processes and query live trace status through a configured backend
$env:UNREALINSIGHTS_LIVE_EXEC='ushell-wrapper --pid {pid} --cmd "{cmd}"'
cli-anything-unrealinsights --json live processes
cli-anything-unrealinsights --json live trace-status --pid 1234

# Open Unreal Insights GUI and keep it running
cli-anything-unrealinsights --json gui open-latest

# Export threads
cli-anything-unrealinsights --json -t D:\captures\session.utrace export threads D:\out\threads.csv

# Export timer statistics for a region
cli-anything-unrealinsights --json -t D:\captures\session.utrace export timer-stats `
  D:\out\timer_stats.csv --threads=GameThread --timers=* --region=EXPORT_CAPTURE

# Execute a response file
cli-anything-unrealinsights --json -t D:\captures\session.utrace batch run-rsp D:\out\export.rsp

# Export and summarize timing/counter hotspots
cli-anything-unrealinsights --json -t D:\captures\session.utrace analyze summary --out D:\out\summary

# Launch a traced UE target and wait for completion
cli-anything-unrealinsights --json capture run `
  --project 'D:\Projects\MyGame\MyGame.uproject' `
  --engine-root 'D:\Program Files\Epic Games\UE_5.5' `
  --output-trace D:\captures\editor_boot.utrace `
  --channels "default,bookmark" `
  --exec-cmd "Trace.Bookmark BootStart" `
  --wait --timeout 300

# Start REPL (default behavior)
cli-anything-unrealinsights
```

## Command Groups

- `backend`
  - `info`
  - `ensure-insights`
- `trace`
  - `set`
  - `info`
- `store`
  - `info`
  - `list`
  - `latest`
- `capture`
  - `run`
  - `start`
  - `status`
  - `stop`
  - `snapshot`
- `live`
  - `processes`
  - `exec`
  - `trace-status`
  - `bookmark`
  - `screenshot`
  - `snapshot`
  - `stop-trace`
- `gui`
  - `status`
  - `open`
  - `open-latest`
- `export`
  - `threads`
  - `timers`
  - `timing-events`
  - `timer-stats`
  - `timer-callees`
  - `counters`
  - `counter-values`
- `batch`
  - `run-rsp`
- `analyze`
  - `summary`
- `repl`

## Global Options

- `--json`: machine-readable output
- `--debug`: include traceback details in errors
- `--trace/-t`: current `.utrace` file
- `--insights-exe`: explicit `UnrealInsights.exe` path
- `--trace-server-exe`: explicit `UnrealTraceServer.exe` path

## Engine-Matched Insights

If you need an `UnrealInsights.exe` matching a custom source engine, use:

```powershell
cli-anything-unrealinsights --json backend ensure-insights `
  --engine-root 'D:\code\D5\d5render-ue5_3'
```

Behavior:

- looks for `Engine\Binaries\Win64\UnrealInsights.exe` under the given engine root
- if missing, runs that engine's `Engine\Build\BatchFiles\Build.bat UnrealInsights Win64 Development -WaitMutex`
- returns the resolved path plus the build log path when a build was attempted

## Capture Convenience Layer

`capture run` supports two launch styles:

```powershell
# 1. Convenience mode: infer UnrealEditor.exe from engine root
cli-anything-unrealinsights capture run `
  --project 'D:\Projects\MyGame\MyGame.uproject' `
  --engine-root 'D:\Program Files\Epic Games\UE_5.5'

# 2. Explicit mode: provide the exact executable yourself
cli-anything-unrealinsights capture run `
  'D:\Program Files\Epic Games\UE_5.5\Engine\Binaries\Win64\UnrealEditor.exe' `
  --target-arg 'D:\Projects\MyGame\MyGame.uproject'
```

Notes:

- `--project` prepends the `.uproject` path to the target command line.
- `--engine-root` accepts either the UE install root or its `Engine` subdirectory.
- If `target_exe` is omitted, `capture run` resolves `UnrealEditor.exe` from `--engine-root`.
- The original explicit `target_exe` path remains supported.

## Continuous AI-Driven Capture

For longer-running sessions, prefer this loop:

```powershell
cli-anything-unrealinsights --json capture start --project ... --engine-root ...
cli-anything-unrealinsights --json capture status
cli-anything-unrealinsights --json capture snapshot
cli-anything-unrealinsights --json capture stop
```

Behavior:

- `capture start` launches the target in the background and persists the tracked PID/trace/session metadata
- `capture start` refuses to overwrite a still-running tracked session unless you pass `--replace`
- `capture status` reads the persisted session state and reports whether the process is still running and how large the trace has grown
- `capture snapshot` creates a best-effort copy of the current `.utrace` without requiring you to end the session first
- `capture stop` performs a best-effort stop of the tracked process tree launched by the harness
- `live stop-trace` is the non-killing trace-control path for already-running UE processes when a live backend is configured

## Trace Store, Live, and GUI Workflows

Trace Store helpers:

```powershell
cli-anything-unrealinsights --json store info
cli-anything-unrealinsights --json store list --live-only
cli-anything-unrealinsights --json store latest --set-current
```

Live process helpers:

```powershell
$env:UNREALINSIGHTS_LIVE_EXEC='ushell-wrapper --pid {pid} --cmd "{cmd}"'
cli-anything-unrealinsights --json live processes
cli-anything-unrealinsights --json live bookmark --pid 1234 "BeforeExport"
cli-anything-unrealinsights --json live snapshot --pid 1234 D:\captures\snapshot.utrace
cli-anything-unrealinsights --json live stop-trace --pid 1234
```

`UNREALINSIGHTS_LIVE_EXEC` is a pluggable command template. It must accept
`{pid}` and `{cmd}` placeholders and should route the command to UE through a
SessionServices/ushell-style backend. If it is not configured, live command
commands fail loudly with a JSON error instead of pretending to control UE.

GUI helpers:

```powershell
cli-anything-unrealinsights --json gui status
cli-anything-unrealinsights --json gui open --trace D:\captures\session.utrace
cli-anything-unrealinsights --json gui open-latest
```

These commands intentionally omit `-NoUI` and `-AutoQuit`, so the Unreal Insights
GUI remains available for human + AI co-analysis.

## Analyze Summary

```powershell
cli-anything-unrealinsights --json -t D:\captures\session.utrace analyze summary --out D:\out\summary
```

`analyze summary` runs the standard timing/counter exporter bundle, then parses
the generated CSV files for top timers, GameThread/RenderThread/RHIThread
hotspots, wait/task-related timers, and counter peaks. For offline parsing of
existing CSV files:

```powershell
cli-anything-unrealinsights --json analyze summary --skip-export --out D:\out\summary
```

Deep Memory, Networking, Slate, Asset Loading, and Cooking analysis are reported
as uncovered domains in the summary until dedicated parsers are added.

The JSON response includes `export_status` and
`summary.diagnostics.export_status_counts`. This makes exporter behavior
machine-readable: `ok` means files were produced, while `no_output` means
Unreal Insights completed successfully but the trace/filter combination did not
materialize data for that exporter.

## Human + AI Workflow

When a human is directing an AI agent, the best requests usually specify:

1. engine root
2. project path or target executable
3. whether the focus is startup or runtime behavior
4. the artifact or summary you want back

Example prompts:

```text
Use D:\code\D5\d5render-ue5_3 to analyze startup performance for
D:\code\D5\FusionEffectBuild.
First ensure a matching UnrealInsights.exe exists, then capture a startup trace,
export timer-stats, and summarize the top 20 hotspots.
```

```text
Use D:\code\D5\d5render-ue5_3 and D:\code\D5\FusionEffectBuild
to start a background performance capture.
Do not block and do not exit the project immediately.
Tell me the trace path and current status first.
When I say "stop", stop the capture, make a snapshot, export timer-stats and
timing-events, then summarize the results.
```

```text
Start a background trace for this project, let me interact with the scene
manually, and wait.
When I say "stop now", export timer-stats and timing-events and focus on
GameThread, RenderThread, and task-system waits.
```

Useful phrases in prompts:

- `ensure matching UnrealInsights`
- `background continuous capture`
- `wait until I say stop`
- `make a snapshot`
- `export timer-stats`
- `export timing-events`
- `summarize top hotspots`
- `look at GameThread / RenderThread / WaitForTasks`

## Export Filters

`timing-events` and `timer-stats` support:

- `--columns`
- `--threads`
- `--timers`
- `--start-time`
- `--end-time`
- `--region`

`counter-values` supports:

- `--counter`
- `--columns`
- `--start-time`
- `--end-time`
- `--region`

For wildcard filters in scripts and tests, prefer the equals form
`--threads=GameThread --timers=* --counter=*`. The harness emits simple
UnrealInsights filter values without inner quotes so `FParse::Token` receives
the wildcard instead of a literal escape character.

## Export Status

Exporter and batch JSON responses include:

- `output_status`
- `status_message`
- `output_files`
- `warnings`
- `errors`
- `succeeded`

`succeeded` is true only when `output_status` is `ok` and at least one expected
file was materialized. `no_output` is a data boundary, not a process crash; it
usually means the trace lacks that event/counter stream or the selected filters
matched nothing. `exporter_error`, `process_failed`, and `timed_out` classify
hard failures for agent retry/debug decisions.

## Testing

```bash
cd unrealinsights/agent-harness
pytest cli_anything/unrealinsights/tests/test_core.py -v
pytest cli_anything/unrealinsights/tests/test_full_e2e.py -v -s
```

Optional environment variables for E2E coverage:

- `UNREALINSIGHTS_TEST_TRACE`
- `UNREALINSIGHTS_TEST_TARGET_EXE`

If `UNREALINSIGHTS_TEST_TRACE` is not set, the E2E suite tries to discover the
UE sample trace at:

```text
<drive>:\Program Files\Epic Games\UE_*\Engine\Source\Programs\Shared\EpicGames.Tracing.Tests\UnrealInsights\example_trace.decomp.utrace
```

That sample trace is not vendored into this repository.
