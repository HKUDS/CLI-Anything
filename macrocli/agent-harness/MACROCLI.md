# MacroCLI — Agent Harness SOP

## What Is This?

**MacroCLI** is a layered CLI that turns valuable GUI workflows into
parameterized, agent-callable macros. The agent sends one command:

```bash
cli-anything-macrocli macro run export_png --param output=/tmp/out.png --json
```

The system handles everything else: parameter validation, precondition checks,
backend selection, step execution, postcondition verification, and structured
result output. The agent never touches the GUI directly.

## Architecture

```
Agent
  └─▶  cli-anything-macrocli macro run <name> --param k=v --json   (L6: CLI)
             │
        MacroRuntime                                                  (L5)
             │  1. Validate params against MacroDefinition schema
             │  2. Check preconditions (file_exists, process_running, …)
             │  3. For each step:
             │       RoutingEngine → select backend by priority       (L3)
             │       Backend.execute(step, resolved_params)           (L2)
             │  4. Check postconditions
             │  5. Collect declared outputs
             │  6. Record telemetry in ExecutionSession
             └─▶  { success, output, error, telemetry }
```

## Layer Mapping

| Layer | Name | Implementation |
|-------|------|---------------|
| L7 | Agent Task Interface | Caller (any AI agent) |
| L6 | Unified CLI Entry | `macrocli_cli.py` — Click CLI |
| L5 | Macro Execution Runtime | `core/runtime.py` |
| L4 | Parameterized Macro Model | `core/macro_model.py` + `macro_definitions/*.yaml` |
| L3 | Backend Routing Engine | `core/routing.py` |
| L2 | Execution Backends | `backends/` (5 backends) |
| L1 | Target Application | Any GUI-first or closed-source app |

## Execution Backends

| Backend | Priority | Trigger | Use case |
|---------|----------|---------|----------|
| `native_api` | 100 | `backend: native_api` | subprocess / shell commands |
| `gui_macro` | 80 | `backend: gui_macro` | precompiled coordinate replay (pyautogui) |
| `file_transform` | 70 | `backend: file_transform` | XML, JSON, text file editing |
| `semantic_ui` | 50 | `backend: semantic_ui` | accessibility API + keyboard (xdotool) |
| `recovery` | 10 | `backend: recovery` | retry + fallback orchestration |

The RoutingEngine respects the step's explicit `backend:` field; if that backend
is unavailable it walks down the priority list.

## Macro Definition Format

Macros live in `cli_anything/macrocli/macro_definitions/` as YAML files:

```yaml
name: export_png
version: "1.0"
description: Export the active diagram to PNG.

parameters:
  output:
    type: string
    required: true
    example: /tmp/diagram.png

preconditions:
  - process_running: draw.io
  - file_exists: /path/to/input.drawio

steps:
  - id: export
    backend: native_api
    action: run_command
    params:
      command: [draw.io, --export, --output, "${output}", input.drawio]
    timeout_ms: 30000
    on_failure: fail     # or: skip | continue

postconditions:
  - file_exists: ${output}
  - file_size_gt:
      - ${output}
      - 100

outputs:
  - name: exported_file
    path: ${output}

agent_hints:
  danger_level: safe
  side_effects: [creates_file]
  reversible: true
```

### Supported Condition Types

| Type | Args | Checks |
|------|------|--------|
| `file_exists` | path | `os.path.exists(path)` |
| `file_size_gt` | [path, min_bytes] | `os.stat(path).st_size > min_bytes` |
| `process_running` | name | `pgrep -x name` or psutil |
| `env_var` | name | `name in os.environ` |
| `always` | true/false | constant pass/fail |

## Package Layout

```
macrocli/
└── agent-harness/
    ├── setup.py                           entry_point: cli-anything-macrocli
    └── cli_anything/macrocli/
        ├── macrocli_cli.py                Main Click CLI
        ├── macro_definitions/             YAML macro registry
        │   ├── manifest.yaml
        │   └── examples/
        │       ├── export_file.yaml
        │       ├── transform_json.yaml
        │       └── undo_last.yaml
        ├── core/
        │   ├── macro_model.py             MacroDefinition + YAML loader
        │   ├── registry.py               MacroRegistry
        │   ├── routing.py                RoutingEngine
        │   ├── runtime.py                MacroRuntime (full lifecycle)
        │   └── session.py               ExecutionSession + telemetry
        ├── backends/
        │   ├── base.py                   Backend ABC + StepResult
        │   ├── native_api.py             subprocess backend
        │   ├── file_transform.py         XML/JSON/text backend
        │   ├── semantic_ui.py            accessibility backend
        │   ├── gui_macro.py              compiled replay backend
        │   └── recovery.py              retry/fallback backend
        ├── skills/SKILL.md               Agent-readable skill definition
        ├── utils/repl_skin.py            Unified REPL skin (cli-anything standard)
        └── tests/
            ├── test_core.py              Unit tests (49 tests, no external deps)
            └── test_full_e2e.py          E2E + CLI subprocess tests (15 tests)
```

## Installation

```bash
cd macrocli/agent-harness
pip install -e .
```

**Runtime dependencies:** Python 3.10+, PyYAML, click, prompt-toolkit.

**Optional (for specific backends):**
- `xdotool` — semantic_ui backend on Linux
- `pyautogui` — gui_macro backend
- `psutil` — richer process_running checks

## Running Tests

```bash
cd macrocli/agent-harness
python3 -m pytest cli_anything/macrocli/tests/ -v -s
# 64 passed
```

## Key Design Decisions

**Why YAML macros, not Python?** YAML macros are readable by agents without
running code, inspectable via `macro info`, and editable without touching the
harness source.

**Why 5 backends?** Real GUI applications expose many different control
surfaces. The routing engine picks the most reliable one available — the agent
doesn't need to know which one ran.

**Why preconditions and postconditions?** Agents operate in environments where
state is uncertain. Failing loudly before execution (preconditions) and
verifying after (postconditions) catches problems the agent can act on.

**Why `on_failure: skip | continue`?** Some macro steps are best-effort (e.g.,
confirming a dialog that may or may not appear). Skipping lets the macro
continue to the real work.
