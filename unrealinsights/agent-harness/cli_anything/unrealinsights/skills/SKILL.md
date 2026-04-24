---
name: "cli-anything-unrealinsights"
description: "Capture Unreal Engine traces, inspect Trace Store files, keep Unreal Insights GUI open, and export/summarize timing/counter data."
---

# cli-anything-unrealinsights

Use this CLI when you need agent-friendly access to Unreal Insights trace capture
and exporter workflows on Windows.

## Prerequisites

- Windows
- Unreal Engine tools installed with `UnrealInsights.exe`
- Verified with UE 5.5; headless timing exporters include compatibility handling
  for UE 5.3-style command parsing where possible
- Optional explicit env vars:
  - `UNREALINSIGHTS_EXE`
  - `UNREAL_TRACE_SERVER_EXE`
  - `UNREALINSIGHTS_TRACE`

## Core Commands

### Backend discovery

```powershell
cli-anything-unrealinsights --json backend info
```

To use a source-built engine's matching `UnrealInsights.exe`:

```powershell
cli-anything-unrealinsights --json backend ensure-insights `
  --engine-root 'D:\code\D5\d5render-ue5_3'
```

This first looks for `Engine\Binaries\Win64\UnrealInsights.exe` under the
specified engine root, then builds it with that engine's `Build.bat` if needed.

### Trace session state

```powershell
cli-anything-unrealinsights trace set D:\captures\session.utrace
cli-anything-unrealinsights --json trace info
```

### Trace Store discovery

```powershell
cli-anything-unrealinsights --json store info
cli-anything-unrealinsights --json store list --live-only
cli-anything-unrealinsights --json store latest --set-current
```

### Capture orchestration

```powershell
cli-anything-unrealinsights --json capture run `
  --project 'D:\Projects\MyGame\MyGame.uproject' `
  --engine-root 'D:\Program Files\Epic Games\UE_5.5' `
  --output-trace D:\captures\boot.utrace `
  --channels "default,bookmark" `
  --exec-cmd "Trace.Bookmark BootStart" `
  --wait --timeout 300
```

You can also keep using the explicit form:

```powershell
cli-anything-unrealinsights --json capture run `
  'D:\Program Files\Epic Games\UE_5.5\Engine\Binaries\Win64\UnrealEditor.exe' `
  --target-arg 'D:\Projects\MyGame\MyGame.uproject'
```

### Continuous capture session control

```powershell
cli-anything-unrealinsights --json capture start `
  --project 'D:\Projects\MyGame\MyGame.uproject' `
  --engine-root 'D:\Program Files\Epic Games\UE_5.5' `
  --output-trace D:\captures\live_session.utrace

cli-anything-unrealinsights --json capture status
cli-anything-unrealinsights --json capture snapshot D:\captures\live_snapshot.utrace
cli-anything-unrealinsights --json capture stop
```

This is the preferred flow when an agent needs to start profiling now and stop
or snapshot later in a follow-up turn.

If a tracked capture session is still running, `capture start` now requires
`--replace` so the previous process is stopped before a new one is launched.

### Live trace control backend

```powershell
$env:UNREALINSIGHTS_LIVE_EXEC='ushell-wrapper --pid {pid} --cmd "{cmd}"'
cli-anything-unrealinsights --json live processes
cli-anything-unrealinsights --json live trace-status --pid 1234
cli-anything-unrealinsights --json live bookmark --pid 1234 "BeforeExport"
cli-anything-unrealinsights --json live stop-trace --pid 1234
```

Live command delivery requires `UNREALINSIGHTS_LIVE_EXEC` or `--backend-command`.
If no backend is configured, live commands return a JSON error and do not claim
success. `live stop-trace` stops trace collection without killing the UE process;
`capture stop` still terminates the harness-launched process tree.

### GUI co-pilot

```powershell
cli-anything-unrealinsights --json gui status
cli-anything-unrealinsights --json gui open --trace D:\captures\session.utrace
cli-anything-unrealinsights --json gui open-latest
```

GUI commands omit `-NoUI` and `-AutoQuit` so Unreal Insights remains open.

### Offline exporters

```powershell
cli-anything-unrealinsights --json -t D:\captures\session.utrace export threads D:\out\threads.csv
cli-anything-unrealinsights --json -t D:\captures\session.utrace export timer-stats D:\out\stats.csv --region=EXPORT_CAPTURE
cli-anything-unrealinsights --json -t D:\captures\session.utrace export counter-values D:\out\counter_values.csv --counter=*
```

Prefer equals-form wildcard filters such as `--timers=*` and `--counter=*`.
The harness passes simple values to UnrealInsights without inner quotes so
wildcards remain usable inside `-ExecOnAnalysisCompleteCmd`.

### Batch response files

```powershell
cli-anything-unrealinsights --json -t D:\captures\session.utrace batch run-rsp D:\out\exports.rsp
```

### Analyze summaries

```powershell
cli-anything-unrealinsights --json -t D:\captures\session.utrace analyze summary --out D:\out\summary
cli-anything-unrealinsights --json analyze summary --skip-export --out D:\out\summary
```

The summary reports top timers, focused GameThread/RenderThread/RHIThread
hotspots, wait/task-related timers, counter peaks, and uncovered domains for
future Memory/Network/Slate/Asset/Cooking analysis.

`analyze summary` also returns `export_status` and
`summary.diagnostics.export_status_counts` so agents can distinguish successful
exports from trace/filter combinations that completed but produced no rows.

## JSON Output Guidance

- Prefer `--json` for agent workflows.
- Export commands return:
  - `trace_path`
  - `exec_command`
  - `output_files`
  - `output_status`
  - `status_message`
  - `log_path`
  - `exit_code`
  - `warnings`
  - `errors`
  - `succeeded`
- Capture returns:
  - `command`
  - `trace_path`
  - `trace_exists`
  - `trace_size`
  - `pid` or `exit_code`
- Continuous capture status returns:
  - `pid`
  - `running`
  - `target_exe`
  - `project_path`
  - `trace_path`
  - `trace_size`
  - `started_at`
- Trace Store commands return:
  - `store_dir`
  - `trace_count`
  - `traces`
  - `latest`
- Live commands return:
  - `pid`
  - `live_command`
  - `backend`
  - `exit_code`
  - `succeeded`
- Analyze summary returns:
  - `exports`
  - `export_status`
  - `summary.top_timers`
  - `summary.focus_threads`
  - `summary.wait_timers`
  - `summary.counter_peaks`
  - `summary.diagnostics`
  - `summary.uncovered_domains`

Treat `output_status == "ok"` as a materialized export. Treat
`output_status == "no_output"` as an empty trace/filter result, not a backend
crash. Use `exporter_error`, `process_failed`, and `timed_out` for retry or
debugging decisions.

## Notes

- v1 is Windows-first.
- v1 includes Trace Store browsing, GUI open/status, pluggable live command delivery,
  and timing/counter summaries.
- `capture stop` is a best-effort stop of the harness-launched process tree.
- `capture snapshot` is a best-effort filesystem snapshot of the active trace.
- Regression tests auto-discover the UE `example_trace.decomp.utrace` sample
  when present; the binary trace is not vendored.
