---
name: "cli-anything-nsight-graphics"
description: Windows-first CLI harness for Nsight Graphics launch, frame capture, GPU Trace, and C++ Capture orchestration
version: 0.1.0
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
- Trigger Frame Debugger capture
- Trigger GPU Trace capture, auto-export, and summarize
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
cli-anything-nsight-graphics launch detached --activity "Frame Debugger" --exe "C:\Path\To\App.exe"
cli-anything-nsight-graphics launch attach --activity "Frame Debugger" --pid 12345
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
- Prefer `gpu-trace capture --auto-export --summarize` for one-step performance triage.
- Frame/GPU/C++ capture commands require a launch target through `--exe` or a
  preconfigured root-level `--project`.
- V1 is orchestration-focused; it does not expose shader, pipeline, or resource
  inspection commands.
