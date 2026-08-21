---
name: cli-anything-list
description: List installed and generated CLI-Anything tools (human or JSON)
---

# cli-anything-list Command

Discover installed and generated CLI-Anything tools.

## CRITICAL: Resolve PLUGIN_ROOT (absolute paths only)

1. Read `~/.cursor/cli-anything-generator.root` / `%USERPROFILE%\.cursor\cli-anything-generator.root`
2. Else install dir `PLUGIN_ROOT.txt` / default `.../plugins/local/cli-anything`
3. Read `{PLUGIN_ROOT}/references/commands/list.md` via absolute path (HARNESS optional for list)

## Cursor Tool Bindings

| Cursor tool | Role |
|-------------|------|
| Shell | `python` / `importlib.metadata`, `which` / `Get-Command`, directory scans |
| Glob / Grep | Find `agent-harness` trees under a search path |

## Options

Honor the same options as the canonical list command:

- `--path <directory>` search root (default: workspace / cwd)
- `--depth <n>` recursion limit
- `--json` machine-readable output

## What This Command Does

Follow `{PLUGIN_ROOT}/references/commands/list.md`:

1. List installed `cli-anything-*` packages and entry points.
2. Scan for generated `agent-harness` trees.
3. Present human-readable or JSON output as requested.

List mode does not require a progress file unless the user asks to persist results.
