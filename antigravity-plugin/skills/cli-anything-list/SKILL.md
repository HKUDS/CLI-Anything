---
name: cli-anything-list
description: >-
  List all installed and locally generated CLI-Anything harnesses with status,
  version, executable path, and source directory in table or JSON format.
  Invoked via /cli-anything-list [--path <dir>] [--depth <n>] [--json].
---

# `/cli-anything-list` — Discover Installed & Generated Harnesses

List every installed `cli-anything-*` package in the active Python environment
and every local `agent-harness/cli_anything/*` directory under the target path.

## 1. Resolve `PLUGIN_ROOT`

Resolve `PLUGIN_ROOT` (two levels up from this `SKILL.md`, or discovery pointer
`~/.gemini/cli-anything-generator.root`, or `~/.gemini/config/plugins/cli-anything`).

Reference spec: `{PLUGIN_ROOT}/references/commands/list.md`.

## 2. Run the Bundled Discovery Script

Execute `list_harnesses.py` via `run_command` rather than hand-writing ad-hoc
shell loops:

```bash
python "{PLUGIN_ROOT}/scripts/list_harnesses.py" [--path "<dir>"] [--depth <n>] [--json] [--include-hub]
```

Options:
- `--path <directory>` — root directory to scan for generated `agent-harness/` trees (default: `.`).
- `--depth <n>` — maximum directory depth to recurse (default: unlimited).
- `--json` — emit machine-readable JSON matching `commands/list.md` (`tools`, `total`, `installed`, `generated_only`).
- `--include-hub` — also include the `cli-anything-hub` package manager in the output.

List mode is read-only and does not create `.cli-anything-progress.json`.
