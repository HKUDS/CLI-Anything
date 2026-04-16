# Agent Harness: GUI-to-CLI for Open Source Software

## Purpose

This harness provides a standard operating procedure (SOP) and toolkit for coding
agents (Claude Code, Codex, etc.) to build powerful, stateful CLI interfaces for
open-source GUI applications. The goal: let AI agents operate software that was
designed for humans, without needing a display or mouse.

## General SOP: Turning Any GUI App into an Agent-Usable CLI

### Phase 1: Codebase Analysis

1. **Identify the backend engine** — Most GUI apps separate presentation from logic.
   Find the core library/framework (e.g., MLT for Shotcut, ImageMagick for GIMP).
2. **Map GUI actions to API calls** — Every button click, drag, and menu item
   corresponds to a function call. Catalog these mappings.
3. **Identify the data model** — What file formats does it use? How is project state
   represented? (XML, JSON, binary, database?)
4. **Find existing CLI tools** — Many backends ship their own CLI (`melt`, `ffmpeg`,
   `convert`). These are building blocks.
5. **Catalog the command/undo system** — If the app has undo/redo, it likely uses a
   command pattern. These commands are your CLI operations.

### Phase 2: CLI Architecture Design

1. **Choose the interaction model**:
   - **Stateful REPL** for interactive sessions (agents that maintain context)
   - **Subcommand CLI** for one-shot operations (scripting, pipelines)
   - **Both** (recommended) — a CLI that works in both modes

2. **Define command groups** matching the app's logical domains:
   - Project management (new, open, save, close)
   - Core operations (the app's primary purpose)
   - Import/Export (file I/O, format conversion)
   - Configuration (settings, preferences, profiles)
   - Session/State management (undo, redo, history, status)

3. **Design the state model**:
   - What must persist between commands? (open project, cursor position, selection)
   - Where is state stored? (in-memory for REPL, file-based for CLI)
   - How does state serialize? (JSON session files)

4. **Plan the output format**:
   - Human-readable (tables, colors) for interactive use
   - Machine-readable (JSON) for agent consumption
   - Both, controlled by `--json` flag

### Phase 3: Implementation

1. **Start with the data layer** — XML/JSON manipulation of project files
2. **Add probe/info commands** — Let agents inspect before they modify
3. **Add mutation commands** — One command per logical operation
4. **Add rendering/export** — The output pipeline (see "The Rendering Gap" below)
5. **Add session management** — State persistence, undo/redo
6. **Add the REPL** — Interactive mode wrapping the subcommands

### Phase 4: Validation

1. **Unit tests** — Every core function tested in isolation with synthetic data
2. **E2E tests with real files** — Run the full CLI against real media/project files.
   This catches format assumptions that unit tests miss.
3. **Workflow tests** — Multi-step real-world scenarios (e.g., "cut 3 segments, apply
   effects, color grade, export"). These expose composition bugs.
4. **Output verification** — **Don't trust that export works just because it exits
   successfully.** Verify outputs programmatically:
   - Pixel-level analysis for video (probe frames, compare mean brightness/color)
   - Audio analysis (RMS levels, spectral comparison)
   - Duration/format checks against expected values
5. **Round-trip test** — Create project via CLI, open in GUI, verify correctness
6. **Agent test** — Have an AI agent complete a real task using only the CLI

## Critical Lessons Learned

### The Rendering Gap

**This is the #1 pitfall.** Most GUI apps apply effects at render time via their
engine. When you build a CLI that manipulates project files directly, you must also
handle rendering — and naive approaches will silently drop effects.

**The problem:** Your CLI adds filters/effects to the project file format. But when
rendering, if you use a simple tool (e.g., ffmpeg concat demuxer), it reads raw
media files and **ignores** all project-level effects. The output looks identical to
the input. Users can't tell anything happened.

**The solution — a filter translation layer:**
1. **Best case:** Use the app's native renderer (`melt` for MLT projects). It reads
   the project file and applies everything.
2. **Fallback:** Build a translation layer that converts project-format effects into
   the rendering tool's native syntax (e.g., MLT filters → ffmpeg `-filter_complex`).
3. **Last resort:** Generate a render script the user can run manually.

**Priority order for rendering:** native engine → translated filtergraph → script.

### Filter Translation Pitfalls

When translating effects between formats (e.g., MLT → ffmpeg), watch for:

- **Duplicate filter types:** Some tools (ffmpeg) don't allow the same filter twice
  in a chain. If your project has both `brightness` and `saturation` filters, and
  both map to ffmpeg's `eq=`, you must **merge** them into a single `eq=brightness=X:saturation=Y`.
- **Ordering constraints:** ffmpeg's `concat` filter requires **interleaved** stream
  ordering: `[v0][a0][v1][a1][v2][a2]`, NOT grouped `[v0][v1][v2][a0][a1][a2]`.
  The error message ("media type mismatch") is cryptic if you don't know this.
- **Parameter space differences:** Effect parameters often use different scales.
  MLT brightness `1.15` = +15%, but ffmpeg `eq=brightness=0.06` on a -1..1 scale.
  Document every mapping explicitly.
- **Unmappable effects:** Some effects have no equivalent in the render tool. Handle
  gracefully (warn, skip) rather than crash.

### Timecode Precision

Non-integer frame rates (29.97fps = 30000/1001) cause cumulative rounding errors:

- **Use `round()`, not `int()`** for float-to-frame conversion. `int(9000 * 29.97)`
  truncates and loses frames; `round()` gets the right answer.
- **Use integer arithmetic for timecode display.** Convert frames → total milliseconds
  via `round(frames * fps_den * 1000 / fps_num)`, then decompose with integer
  division. Avoid intermediate floats that drift over long durations.
- **Accept ±1 frame tolerance** in roundtrip tests at non-integer FPS. Exact equality
  is mathematically impossible.

### Output Verification Methodology

Never assume an export is correct just because it ran without errors. Verify:

```python
# Video: probe specific frames with ffmpeg
# Frame 0 for fade-in (should be near-black)
# Middle frames for color effects (compare brightness/saturation vs source)
# Last frame for fade-out (should be near-black)

# When comparing pixel values between different resolutions,
# exclude letterboxing/pillarboxing (black padding bars).
# A vertical video in a horizontal frame will have ~40% black pixels.

# Audio: check RMS levels at start/end for fades
# Compare spectral characteristics against source
```

### Testing Strategy

Two test suites with complementary purposes:

1. **Unit tests** (`test_core.py`): Synthetic data, no external dependencies. Tests
   every function in isolation. Fast, deterministic, good for CI.
2. **E2E tests** (`test_full_e2e.py`): Real media files. Tests the full pipeline
   including format parsing, codec handling, and actual rendering. Catches the
   real-world issues that unit tests can't.

Real-world workflow test scenarios should include:
- Multi-segment editing (YouTube-style cut/trim)
- Montage assembly (many short clips)
- Picture-in-picture compositing
- Color grading pipelines
- Audio mixing (podcast-style)
- Heavy undo/redo stress testing
- Save/load round-trips of complex projects
- Iterative refinement (add, modify, remove, re-add)

## Key Principles

- **Manipulate the native format directly** — Don't reimplement the engine. Parse and
  modify the app's native project files (MLT XML, PSD, etc.)
- **Leverage existing CLI tools** — Use `melt`, `ffmpeg`, `ffprobe` as subprocesses
  when available. Don't reinvent rendering.
- **But verify rendering applies your edits** — See "The Rendering Gap" above. This is
  the most common and most silent failure mode.
- **Fail loudly and clearly** — Agents need unambiguous error messages to self-correct.
- **Be idempotent where possible** — Running the same command twice should be safe.
- **Provide introspection** — `info`, `list`, `status` commands are critical for agents
  to understand current state before acting.
- **JSON output mode** — Every command should support `--json` for machine parsing.

## Rules

- **Every `cli/` directory MUST contain a `README.md`** that explains how to
  install dependencies, run the CLI, run tests, and shows basic usage examples.
  This is the first thing a user or agent reads. Without it, the CLI is unusable.
- **Every export/render function MUST be verified** with programmatic output analysis
  before being marked as working. "It ran without errors" is not sufficient.
- **Every filter/effect in the registry MUST have a corresponding render mapping**
  or be explicitly documented as "project-only (not rendered)".
- **Test suites MUST include real-file E2E tests**, not just unit tests with synthetic
  data. Format assumptions break constantly with real media.

## Directory Structure

```
agent-harness/
├── HARNESS.md              # This file — general SOP
├── SHOTCUT.md              # Project-specific analysis and SOP
├── cli/                    # The actual CLI implementation
│   ├── README.md           # HOW TO RUN — required
│   ├── __init__.py
│   ├── __main__.py         # python3 -m cli.shotcut_cli
│   ├── shotcut_cli.py      # Main CLI entry point (Click + REPL)
│   ├── core/               # Core modules (one per domain)
│   │   ├── __init__.py
│   │   ├── project.py      # Project create/open/save/info
│   │   ├── timeline.py     # Tracks, clips, trim, split, move
│   │   ├── filters.py      # Filter registry + add/remove/set
│   │   ├── media.py        # ffprobe wrapper, media inventory
│   │   ├── export.py       # Render pipeline + filter translation
│   │   └── session.py      # Stateful session, undo/redo
│   ├── utils/              # Shared utilities
│   │   ├── __init__.py
│   │   ├── mlt_xml.py      # MLT XML parsing/generation (lxml)
│   │   └── time.py         # Timecode ↔ frame conversion
│   └── tests/              # Test suites
│       ├── test_core.py    # Unit tests (65 tests, synthetic)
│       └── test_full_e2e.py # E2E tests (79 tests, real media)
├── examples/               # Example scripts and workflows
│   └── workflow_basic.sh
└── workflow_demo.py        # Full demo: 3-segment highlight reel
```

## Applying This to Other Software

This same SOP applies to any GUI application:

| Software | Backend | Native Format | Existing CLI | Rendering Gap Risk |
|----------|---------|---------------|-------------|-------------------|
| Shotcut | MLT | .mlt (XML) | melt, ffmpeg | **High** — must translate filters |
| GIMP | GEGL | .xcf | gimp -i (script-fu) | Medium — GEGL has CLI |
| Blender | bpy | .blend | blender --python | Low — bpy renders natively |
| Inkscape | librsvg | .svg (XML) | inkscape --actions | Low — SVG is the format |
| Audacity | PortAudio | .aup3 (SQLite) | — | **High** — no CLI renderer |
| LibreOffice | UNO | .odt (XML+ZIP) | soffice --macro | Low — UNO API works |
| OBS Studio | libobs | scene.json | obs-websocket | Medium — live only |
| Kdenlive | MLT | .kdenlive (XML) | melt | **High** — same as Shotcut |

The "Rendering Gap Risk" column indicates how likely it is that a naive export
approach will silently drop effects. **High** risk means you almost certainly need
a filter translation layer.

The pattern is always the same: find the data format, find the engine, build a
CLI that manipulates one and drives the other — and **verify the output**.
