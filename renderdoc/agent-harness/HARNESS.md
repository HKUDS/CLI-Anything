# HARNESS.md – RenderDoc CLI Harness Specification

## Overview

This harness wraps the **RenderDoc** graphics debugger Python API into a Click-based
CLI tool called `cli-anything-renderdoc`. It enables headless, scriptable analysis
of GPU frame captures (`.rdc` files) without requiring the RenderDoc GUI.

## Architecture

```
agent-harness/
├── HARNESS.md              # This file
├── RENDERDOC.md            # Software-specific SOP
├── setup.py                # PEP 420 namespace package
└── cli_anything/           # NO __init__.py (namespace package)
    └── renderdoc/          # HAS __init__.py
        ├── renderdoc_cli.py        # Main CLI entry point (Click)
        ├── core/
        │   ├── capture.py          # Capture file open/close/metadata/convert
        │   ├── actions.py          # Draw call / action tree navigation
        │   ├── textures.py         # Texture listing, pixel picking, export
        │   ├── pipeline.py         # Pipeline state, shader export, diff, cbuffers
        │   ├── resources.py        # Buffer/resource enumeration and reading
        │   ├── mesh.py             # Vertex input/output decoding
        │   └── counters.py         # GPU performance counters
        ├── utils/
        │   ├── output.py           # JSON/table output formatting
        │   └── errors.py           # Error handling
        ├── skills/
        │   └── SKILL.md            # AI-discoverable skill definition
        └── tests/
            ├── TEST.md             # Test plan and results
            ├── test_core.py        # Unit tests (mock-based, no renderdoc dep)
            └── test_full_e2e.py    # E2E tests (requires renderdoc + .rdc files)
```

## Command Groups

| Group       | Commands                                          |
|-------------|--------------------------------------------------|
| `capture`   | `info`, `thumb`, `convert`                       |
| `actions`   | `list`, `summary`, `find`, `get`                 |
| `textures`  | `list`, `get`, `save`, `save-outputs`, `pick`    |
| `pipeline`  | `state`, `shader-export`, `cbuffer`, `diff`      |
| `resources` | `list`, `buffers`, `read-buffer`                 |
| `mesh`      | `inputs`, `outputs`                              |
| `counters`  | `list`, `fetch`                                  |

## Global Options

- `--capture / -c <path>`: Path to the `.rdc` capture file (or `$RENDERDOC_CAPTURE`)
- `--json`: Output in JSON format (machine-readable)
- `--debug`: Show tracebacks on errors
- `--version`: Show version

## Patterns

1. **Lazy loading**: `renderdoc` module is only imported when a command runs, not at
   CLI parse time. This allows `--help` to work without renderdoc installed.
2. **CaptureHandle**: Single context manager that owns the CaptureFile and
   ReplayController lifecycle.
3. **Dict-based returns**: Every core function returns plain `dict`/`list` for
   direct JSON serialisation.
4. **Dual output**: `_output()` helper picks JSON or human-readable based on `--json`.
5. **Error dicts**: Errors returned as `{"error": "message"}` rather than exceptions
   at the boundary layer.

## Testing Strategy

- **Unit tests** (`test_core.py`): Test all core module functions using mocks.
  No dependency on `renderdoc` module. Uses synthetic data.
- **E2E tests** (`test_full_e2e.py`): Require a real RenderDoc installation and
  at least one `.rdc` capture file. Test full CLI invocation via subprocess.
- **Subprocess tests**: Invoke the CLI with
  `python -m cli_anything.renderdoc.renderdoc_cli` from `agent-harness/` (see
  `test_core.py` / `test_full_e2e.py`).

## Dependencies

- **Required**: `click>=8.0`, `prompt-toolkit>=3.0`, `python>=3.10`
- **Optional** (runtime): `renderdoc` Python module (from RenderDoc installation)
- **Test**: `pytest>=7.0`
