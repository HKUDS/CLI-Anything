# HARNESS.md – Nsight Graphics CLI Harness Specification

## Overview

This harness wraps the official **NVIDIA Nsight Graphics** command-line tools
into a Click-based CLI named `cli-anything-nsight-graphics`.

V1 is intentionally **orchestration-focused**:

- installation and capability probing
- detached launch and PID attach via `ngfx.exe`
- Graphics Capture / OpenGL Frame Debugger capture
- GPU Trace capture and auto-export
- replay metadata/log/screenshot/perf-report analysis for existing captures
- Generate C++ Capture

Replay analysis uses official `ngfx-replay` outputs. It does **not** attempt
RenderDoc-style offline object inspection of pipeline state, shaders, textures,
or resources.

## Architecture

```text
agent-harness/
├── HARNESS.md
├── NSIGHT_GRAPHICS.md
├── setup.py
└── cli_anything/
    └── nsight_graphics/
        ├── __init__.py
        ├── __main__.py
        ├── README.md
        ├── nsight_graphics_cli.py
        ├── core/
        │   ├── doctor.py
        │   ├── launch.py
        │   ├── frame.py
        │   ├── gpu_trace.py
        │   ├── replay.py
        │   └── cpp_capture.py
        ├── utils/
        │   ├── nsight_graphics_backend.py
        │   ├── output.py
        │   ├── errors.py
        │   └── repl_skin.py
        ├── skills/
        │   └── SKILL.md
        └── tests/
            ├── TEST.md
            ├── test_core.py
            └── test_full_e2e.py
```

## Command Groups

| Group | Commands |
|-------|----------|
| `doctor` | `info` |
| `launch` | `detached`, `attach` |
| `frame` | `capture` |
| `gpu-trace` | `capture`, `summarize` |
| `replay` | `analyze` |
| `cpp` | `capture` |

## Backend Strategy

1. Resolve Nsight executables from `NSIGHT_GRAPHICS_PATH`, `PATH`, then common
   Windows install directories.
2. Detect compatibility mode:
   - `unified`: legacy `ngfx.exe` activity-driven CLI
   - `split`: modern `ngfx-capture` / `ngfx-replay` present
   - `unified+split`: both tool families are present
3. Prefer `ngfx.exe` when available, because it covers launch, attach,
   GPU Trace, and Generate C++ Capture.
4. Create explicit output directories before invoking `ngfx.exe`, then use
   version-tolerant artifact discovery by diffing the output directory before
   and after a command instead of depending on one filename.
5. Use `ngfx-replay` for analysis of existing `.ngfx-capture` files. Accept
   `.ngfx-gputrace` inputs only to report clear compatibility diagnostics,
   because `ngfx-replay` documents its filename input as a Graphics Capture file
   and can reject standalone GPU Trace files with `Invalid file header`.

## Testing Strategy

- `test_core.py`: mock-based unit tests for discovery, parsing, command
  construction, output directory preparation, GPU Trace summary parsing, error
  handling, and CLI help.
- `test_full_e2e.py`: conditional tests using a real Nsight installation and a
  user-supplied test executable via environment variables.

## Notes

- V1 is Windows-first and only claims verified support on Windows hosts.
- Replay helpers are metadata/log/perf oriented and do not claim deep
  shader/pipeline/texture/resource inspection.
