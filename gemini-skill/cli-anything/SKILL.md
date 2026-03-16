---
name: cli-anything
description: Use when creating, testing, or maintaining Agent-Native CLIs for existing software following the HKUDS/CLI-Anything protocol. This is specifically for building harnesses that allow AI agents to control complex GUI software (Blender, GIMP, LibreOffice) via structured command-line interfaces.
---

# CLI-Anything: Agent Harness Standard Operating Procedure

## Core Vision & The Iron Law
CLI-Anything bridges the gap between AI agents and GUI software by creating a stateful, structured, and verifiable CLI.

> [!IMPORTANT]
> **THE IRON LAW (Rule #1):** The CLI MUST invoke the actual software for rendering and export. **DO NOT reimplement** the software's functionality (e.g., using Pillow to replace GIMP). The software is a **hard dependency**, not optional.

## Mandatory Directory Structure
All harnesses MUST follow this PEP 420 Namespace package structure:
```
<software>/
└── agent-harness/
    ├── <SOFTWARE>.md          # Project-specific analysis
    ├── setup.py               # Namespace package config (Phase 7)
    ├── cli_anything/          # NO __init__.py here (Namespace Package)
    │   └── <software>/        # Sub-package for this CLI (HAS __init__.py)
    │       ├── README.md      # Installation & usage — required
    │       ├── <software>_cli.py # Main entry (Click + REPL)
    │       ├── core/          # Domain modules (project.py, export.py, etc.)
    │       ├── utils/         # backend.py (wrappers), repl_skin.py
    │       └── tests/
    │           ├── TEST.md    # Test plan and results — required
    │           ├── test_core.py
    │           └── test_full_e2e.py
```

## The 7-Phase SOP

### Phase 1: Codebase Analysis
- Identify the backend engine (MLT, ImageMagick, bpy).
- Map GUI actions to API calls and identify the data model (XML, JSON, .blend).
- Find existing low-level CLI tools (`melt`, `ffmpeg`, `convert`).

### Phase 2: CLI Architecture Design
- **Interaction Model**: Support both **Stateful REPL** and **Subcommand CLI**.
- **JSON Output**: Every command MUST support `--json` for machine parsing.
- **State Model**: Define what persists (open project, selection) and how it serializes.

### Phase 3: Implementation
- **Data Layer**: Start with direct manipulation of project files (XML/JSON).
- **Backend Wrapper**: Create `utils/<software>_backend.py`. Use `shutil.which()` to find the executable and `subprocess.run()` to invoke it. Raise `RuntimeError` with clear install instructions if missing.
- **REPL Skin**: Copy `repl_skin.py` from the plugin source to `utils/`. Use the `ReplSkin` class for banner, help, and styled messages. **REPL MUST be the default behavior** when no subcommand is given.

### Phase 4: Test Planning (TEST.md Part 1 - BEFORE Code)
**REQUIRED:** Create `tests/TEST.md` containing:
1. **Test Inventory Plan**: List planned files and test counts.
2. **Unit Test Plan**: Map modules/functions/edge cases.
3. **E2E Test Plan**: Scenarios with real files and verified output properties.
4. **Workflow Scenarios**: Titles, simulations (e.g. "podcast mix"), and operations chained.

### Phase 5: Test Implementation
- **Unit Tests**: Isolated with synthetic data.
- **E2E True Backend**: MUST invoke the real software. Verify file exists, size > 0, and **magic bytes/format validation**.
- **Artifact Paths**: Tests MUST print the paths of generated artifacts (PDF, MP4) for manual inspection.
- **Subprocess Tests**: Use the `_resolve_cli` helper to test the *installed* command. Never hardcode `python -m`.

### Phase 6: Test Documentation (TEST.md Part 2 - AFTER Execution)
**REQUIRED:** Append to `tests/TEST.md`:
1. **Test Results**: Full `pytest -v` output.
2. **Summary Stats**: Total tests, pass rate, time.

### Phase 7: Packaging & Publishing
- Use `setuptools.find_namespace_packages(include=["cli_anything.*"])`.
- Package name convention: `cli-anything-<software>`.
- **Namespace rule**: The `cli_anything` directory must NOT contain an `__init__.py`.

## Key Principles & Rules
- **No Graceful Degradation**: If the software is missing, fail loudly with install instructions.
- **The Rendering Gap**: Ensure filters/effects added via CLI are actually applied during render (use native engines or translated filtergraphs).
- **Timecode Precision**: Use `round()`, not `int()`, for float-to-frame conversion to avoid drifting.
- **Verification**: "It ran without errors" is NOT enough. Programmatically verify magic bytes, ZIP structure, or frame probes.

## Implementation Patterns
See [patterns.md](file:///C:/Users/SZGF/.gemini/skills/cli-anything/patterns.md) for boilerplate code regarding:
- Backend wrappers with `shutil.which`.
- Subprocess test helpers (`_resolve_cli`).
- REPL Skin integration.
- Output artifact verification.

---
*Reference: HKUDS/CLI-Anything HARNESS.md standard.*
