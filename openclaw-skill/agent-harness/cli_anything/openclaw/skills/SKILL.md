---
name: cli-anything-openclaw
description: >
  Use when the agent wants to define, list, inspect, or execute GUI macros
  via the OpenClaw Macro System CLI. Macros are parameterized, CLI-callable
  workflows — the agent invokes `macro run <name>` and the system handles
  backend routing (plugin, file transform, accessibility, compiled GUI replay).
---

# OpenClaw Macro System CLI

## What It Is

The OpenClaw Macro System converts valuable GUI workflows into parameterized,
CLI-callable macros. Agents **never touch the GUI directly** — they call macros
through this stable CLI, and the runtime routes execution to the best available
backend (native plugin/API, file transformation, semantic UI control, or
precompiled GUI macro replay).

## Installation

```bash
cd openclaw-skill/agent-harness
pip install -e .
```

**Requirements:** Python 3.10+, PyYAML, click, prompt-toolkit.

## Quick Start (for agents)

```bash
# 1. See what macros are available
cli-anything-openclaw macro list --json

# 2. Inspect a macro's parameters
cli-anything-openclaw macro info export_file --json

# 3. Dry-run to check params without side effects
cli-anything-openclaw --dry-run macro run export_file \
    --param output=/tmp/test.txt --json

# 4. Execute a macro
cli-anything-openclaw macro run export_file \
    --param output=/tmp/result.txt --json

# 5. See what backends are available
cli-anything-openclaw backends --json
```

## Command Reference

### Global Flags

| Flag | Description |
|------|-------------|
| `--json` | Machine-readable JSON output on stdout |
| `--dry-run` | Simulate all steps, skip side effects |
| `--session-id <id>` | Resume or create a named session |

### `macro` group

| Command | Description |
|---------|-------------|
| `macro list` | List all available macros |
| `macro info <name>` | Show macro schema (parameters, steps, conditions) |
| `macro run <name> --param k=v` | Execute a macro |
| `macro dry-run <name> --param k=v` | Simulate without side effects |
| `macro validate [name]` | Structural validation |
| `macro define <name>` | Scaffold a new macro YAML |

### `session` group

| Command | Description |
|---------|-------------|
| `session status` | Show session statistics |
| `session history` | Show recent run history |
| `session save` | Persist session to disk |
| `session list` | List all saved sessions |

### `backends`

```bash
cli-anything-openclaw backends --json
# Shows: native_api, file_transform, semantic_ui, gui_macro, recovery
# and whether each is available in the current environment.
```

## Macro Parameters

Pass parameters with `--param key=value`. Repeat for multiple:

```bash
cli-anything-openclaw macro run transform_json \
    --param file=/path/to/data.json \
    --param key=settings.theme \
    --param value=dark \
    --json
```

## Output Format (--json)

All commands output JSON when `--json` is set:

```json
{
  "success": true,
  "macro_name": "export_file",
  "output": {
    "exported_file": "/tmp/result.txt"
  },
  "error": "",
  "telemetry": {
    "duration_ms": 312,
    "steps_total": 2,
    "steps_run": 2,
    "backends_used": ["native_api"],
    "dry_run": false
  }
}
```

On failure (`"success": false`), read the `"error"` field for the reason.
Exit code is 1 on failure.

## Execution Backends

Backends are selected automatically based on the macro step definition:

| Backend | Triggered by | Use case |
|---------|-------------|----------|
| `native_api` | `backend: native_api` | Subprocess / shell command |
| `file_transform` | `backend: file_transform` | XML, JSON, text file editing |
| `semantic_ui` | `backend: semantic_ui` | Accessibility / keyboard shortcuts |
| `gui_macro` | `backend: gui_macro` | Precompiled coordinate replay |
| `recovery` | `backend: recovery` | Retry / fallback orchestration |

## Writing Macros

Macros are YAML files in `cli_anything/openclaw/macro_definitions/`.
Scaffold one with:

```bash
cli-anything-openclaw macro define my_macro --output \
    cli_anything/openclaw/macro_definitions/examples/my_macro.yaml
```

Minimal schema:

```yaml
name: my_macro
version: "1.0"
description: What this macro does.

parameters:
  output:
    type: string
    required: true
    description: Where to write results.
    example: /tmp/result.txt

preconditions:
  - file_exists: /path/to/input

steps:
  - id: step1
    backend: native_api
    action: run_command
    params:
      command: [my-app, --export, "${output}"]
    timeout_ms: 30000
    on_failure: fail  # or: skip, continue

postconditions:
  - file_exists: ${output}
  - file_size_gt: [${output}, 100]

outputs:
  - name: result_file
    path: ${output}

agent_hints:
  danger_level: safe  # safe | moderate | dangerous
  side_effects: [creates_file]
  reversible: true
```

## Agent Usage Rules

1. **Always use `--json`** for programmatic output.
2. **Use `--dry-run` to validate params** before executing side-effectful macros.
3. **Check `success` field** — do not assume success from exit code alone.
4. **Read `error` field** when `success` is false — it explains what failed.
5. **Use `macro info <name>` to discover params** before calling `macro run`.
6. **Use absolute paths** for all file parameters.

## Example Workflow

```bash
# Step 1: What's available?
cli-anything-openclaw macro list --json

# Step 2: What params does transform_json need?
cli-anything-openclaw macro info transform_json --json

# Step 3: Test safely
cli-anything-openclaw --dry-run macro run transform_json \
    --param file=/tmp/config.json \
    --param key=theme \
    --param value=dark --json

# Step 4: Execute for real
cli-anything-openclaw macro run transform_json \
    --param file=/tmp/config.json \
    --param key=theme \
    --param value=dark --json
```

## Version

1.0.0
