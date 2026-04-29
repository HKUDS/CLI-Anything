---
name: "cli-anything-unrealinsights"
description: "Capture Unreal Engine traces to .utrace files and export Unreal Insights timing/counter data in headless mode."
---

# cli-anything-unrealinsights

Use this CLI when you need agent-friendly access to Unreal Insights trace capture
and exporter workflows on Windows.

## Prerequisites

- Unreal Engine 5.5+ installed with `UnrealInsights.exe`
- Windows
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

### Offline exporters

```powershell
cli-anything-unrealinsights --json -t D:\captures\session.utrace export threads D:\out\threads.csv
cli-anything-unrealinsights --json -t D:\captures\session.utrace export timer-stats D:\out\stats.csv --region "EXPORT_CAPTURE"
cli-anything-unrealinsights --json -t D:\captures\session.utrace export counter-values D:\out\counter_values.csv --counter "*"
```

### Batch response files

```powershell
cli-anything-unrealinsights --json -t D:\captures\session.utrace batch run-rsp D:\out\exports.rsp
```

## JSON Output Guidance

- Prefer `--json` for agent workflows.
- Export commands return:
  - `trace_path`
  - `exec_command`
  - `output_files`
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

## Notes

- v1 is Windows-first.
- v1 supports file-mode capture orchestration only.
- v1 does not control already-running UE instances or browse trace stores.
- `capture stop` is a best-effort stop of the harness-launched process tree.
- `capture snapshot` is a best-effort filesystem snapshot of the active trace.
