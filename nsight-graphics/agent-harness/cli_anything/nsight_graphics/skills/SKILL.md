---
name: cli-anything-nsight-graphics
description: Windows-first CLI harness for Nsight Graphics capture, GPU Trace summary, and ngfx-replay analysis
version: 0.2.0
command: cli-anything-nsight-graphics
install: pip install cli-anything-nsight-graphics
requires:
  - NVIDIA Nsight Graphics installation
  - Windows host recommended
categories:
  - graphics
  - debugging
  - gpu
  - profiling
---

# Nsight Graphics CLI Skill

Command-line orchestration of official NVIDIA Nsight Graphics activities.

## Capabilities

- Probe installed Nsight binaries and compatibility mode
- Launch an application detached under Nsight
- Attach Nsight to a running PID
- Trigger Graphics Capture or OpenGL Frame Debugger capture
- Trigger GPU Trace capture, auto-export, and summarize
- Analyze existing `.ngfx-capture` files through `ngfx-replay`
- Report clear compatibility diagnostics for `.ngfx-gputrace` inputs
- Trigger Generate C++ Capture

## Commands

### doctor

```bash
cli-anything-nsight-graphics --json doctor info
cli-anything-nsight-graphics --json doctor versions
cli-anything-nsight-graphics --nsight-path "C:\Path\To\Nsight Graphics 2024.2\host\windows-desktop-nomad-x64" --json doctor info
```

### launch

```bash
cli-anything-nsight-graphics launch detached --activity "Graphics Capture" --exe "C:\Path\To\App.exe"
cli-anything-nsight-graphics launch attach --activity "Graphics Capture" --pid 12345
```

### frame capture

```bash
cli-anything-nsight-graphics --output-dir D:\captures frame capture ^
  --exe "C:\Path\To\App.exe" ^
  --wait-frames 10
```

### GPU Trace

```bash
cli-anything-nsight-graphics --output-dir D:\traces gpu-trace capture ^
  --exe "C:\Path\To\App.exe" ^
  --start-after-ms 1000 ^
  --limit-to-frames 1 ^
  --auto-export ^
  --summarize

cli-anything-nsight-graphics gpu-trace summarize ^
  --input-dir D:\traces
```

### Replay analysis

```bash
cli-anything-nsight-graphics --json replay analyze ^
  --capture-file D:\captures\frame.ngfx-capture ^
  --output-dir D:\analysis
```

### Generate C++ Capture

```bash
cli-anything-nsight-graphics --output-dir D:\cpp cpp capture ^
  --exe "C:\Path\To\App.exe" ^
  --wait-seconds 5
```

## Agent Notes

- Prefer `doctor info` first to discover the available compatibility mode.
- Use `doctor versions` to list detected installs when multiple Nsight Graphics versions exist.
- Use `--nsight-path` to force a specific install directory or `ngfx.exe`.
- Use `--json` for programmatic workflows.
- Prefer `gpu-trace capture --auto-export --summarize` for one-step performance
  triage. The summary includes exported table inventory, metric inventory,
  frame-budget classification, workload classification, throughput ranking,
  bottleneck hints, and warnings for empty event/regime tables.
- Use `replay analyze` when the input is an existing `.ngfx-capture` file. With
  no analysis switches it exports metadata, logs, captured log errors, and a
  replay performance report, then adds structured `analysis.highlights` /
  `analysis.warnings`.
- `ngfx-replay` documents its input as a Graphics Capture file. `.ngfx-gputrace`
  inputs are accepted for clear diagnostics, but on Nsight Graphics 2026.1.0
  they may report `Invalid file header`; use `gpu-trace summarize` for exported
  GPU Trace table analysis.
- `replay analyze` uses official `ngfx-replay` metadata/log/screenshot/perf-report
  outputs; it is not a RenderDoc-style shader, pipeline, texture, or resource inspector.
- Frame/GPU/C++ capture commands require a launch target through `--exe` or a
  preconfigured root-level `--project`.
- If a global `cli-anything-nsight-graphics` command points at an old worktree,
  reinstall from `nsight-graphics/agent-harness` with `python -m pip install -e .`.
