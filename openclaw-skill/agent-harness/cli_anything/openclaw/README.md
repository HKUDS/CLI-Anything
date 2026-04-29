# OpenClaw Macro System

**OpenClaw Macro System** is a layered CLI that converts GUI workflows into
parameterized, agent-callable macros. Agents call `macro run <name>` through
a stable CLI; the system routes execution to the right backend (native plugin,
file transform, semantic UI, or compiled GUI replay) — invisible to the agent.

## Installation

```bash
pip install -e .
```

**Dependencies:** Python 3.10+, PyYAML, click, prompt-toolkit

## Usage

```bash
# List available macros
cli-anything-openclaw macro list --json

# Inspect a macro
cli-anything-openclaw macro info export_file --json

# Execute a macro
cli-anything-openclaw macro run transform_json \
    --param file=/tmp/config.json \
    --param key=theme --param value=dark --json

# Dry run
cli-anything-openclaw --dry-run macro run export_file \
    --param output=/tmp/out.txt --json

# Interactive REPL
cli-anything-openclaw
```

## Run Tests

```bash
cd openclaw-skill/agent-harness
pip install -e ".[dev]"
python -m pytest cli_anything/openclaw/tests/ -v -s
```

## Architecture

```
cli-anything-openclaw (CLI)
  └─▶ macro run <name> --param key=value
         │
    MacroRuntime
         │  validate params
         │  check preconditions
         │  for each step:
         │    RoutingEngine → select backend
         │    Backend.execute(step, params)
         │  check postconditions
         └─▶ ExecutionResult { success, output, telemetry }
```

**Backends:**
- `native_api` — subprocess / shell commands
- `file_transform` — XML, JSON, text file editing
- `semantic_ui` — accessibility controls + keyboard shortcuts
- `gui_macro` — precompiled coordinate-based replay
- `recovery` — retry + fallback orchestration

## Adding a Macro

1. Create `cli_anything/openclaw/macro_definitions/my_macro.yaml`
2. Add it to `macro_definitions/manifest.yaml`
3. Verify: `cli-anything-openclaw macro validate my_macro --json`

See `skills/SKILL.md` (installed with the package) for full macro YAML schema.
