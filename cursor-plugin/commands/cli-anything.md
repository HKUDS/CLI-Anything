---
name: cli-anything
description: Build a complete CLI-Anything harness for any GUI application (all 7 phases)
---

# cli-anything Command

Build a complete, stateful CLI harness for any GUI application.

**Target software**: use the path or repo URL supplied with this command.

## CRITICAL: Resolve PLUGIN_ROOT (absolute paths only)

Cursor tools often resolve relative paths against the **workspace** root, not this plugin. Before anything else, resolve `PLUGIN_ROOT` using this order — stop at the first hit that contains `references/HARNESS.md`:

1. Read the discovery pointer (absolute path on one line):
   - Windows: `%USERPROFILE%\.cursor\cli-anything-generator.root`
   - Unix: `~/.cursor/cli-anything-generator.root`
   Then use that directory as `PLUGIN_ROOT`.
2. Else read `{candidate}/PLUGIN_ROOT.txt` where `candidate` is:
   - `%USERPROFILE%\.cursor\plugins\local\cli-anything` / `~/.cursor/plugins/local/cli-anything`
   - or `$CURSOR_PLUGINS_HOME/local/cli-anything` if the env var is set (Shell: printenv / `$env:CURSOR_PLUGINS_HOME`)
3. Else, if `candidate/references/HARNESS.md` exists, use `candidate`.
4. Else, if the workspace is a CLI-Anything checkout, use `{workspace}/cli-anything-plugin` for methodology (and still prefer an installed plugin when present).
5. Else clone `https://github.com/HKUDS/CLI-Anything` and use `cli-anything-plugin/`.

Always **Read** `{PLUGIN_ROOT}/references/HARNESS.md` with an absolute path. Also read `{PLUGIN_ROOT}/references/commands/cli-anything.md`. Use `{PLUGIN_ROOT}/references/guides/` on demand. Do not use workspace-relative `./HARNESS.md`.

## Cursor Tool Bindings

| Cursor tool | Role in harness workflow |
|-------------|--------------------------|
| Read | Read HARNESS, guides, target source, generated files |
| Grep / Glob | Map APIs, locate entry points, inventory coverage |
| Shell | Clone repos, run pytest, pip install, invoke CLIs |
| Write / StrReplace | Implement harness modules, tests, packaging, docs |
| Task | Optional parallel analysis subtasks |

## Arguments

- First argument is the **software path or repo URL** (required):
  - Local path (e.g. `/home/user/gimp`, `./blender`)
  - GitHub repository URL
  - Software names alone (e.g. `gimp`) are NOT accepted

If a GitHub URL is provided, clone locally first, then work on the local copy. Derive the software name from the directory name.

## Phase Gates and Resume (hard gate)

Progress file (create `agent-harness/` as soon as tracking starts, even before full implementation):

`{software-root}/agent-harness/.cli-anything-progress.json`

Schema:

```json
{
  "software": "<name>",
  "mode": "build",
  "target": "<absolute software path>",
  "phases": {
    "0": { "status": "completed", "updated_at": "<ISO-8601>" },
    "1": { "status": "in_progress", "updated_at": "<ISO-8601>" }
  },
  "terminal": false,
  "terminal_status": null
}
```

Rules:

- Phases: `0` source acquisition through `7` packaging/install (same as HARNESS / Claude plugin).
- **Do not start the next phase until the progress file records the previous phase as `completed`.**
- After finishing a phase, set it to `completed` and set the next to `in_progress`.
- On session start, if a non-terminal progress file exists for this target, **resume** from the first non-completed phase. Do not redo completed phases unless the user asks.
- Set `terminal: true` and `terminal_status` to `success` or `failed` only when the whole build mode finishes or aborts permanently.
- A terminal progress file is historical; start a new build only when the user requests a rebuild (then reset or replace the file).

## What This Command Does

Implements the complete cli-anything methodology. **All phases follow HARNESS.md.**

### Phase 0: Source Acquisition
- Clone URL targets if needed; verify local source exists; derive software name
- Create `agent-harness/` and initialize the progress file

### Phase 1: Codebase Analysis
- Backend/data model, GUI-to-API map, existing CLIs, architecture notes

### Phase 2: CLI Architecture Design
- Command groups, state model, output formats, software-specific SOP (`<SOFTWARE>.md`)

### Phase 3: Implementation
- `agent-harness/cli_anything/<software>/` with core, utils, Click CLI + REPL, `--json`
- Imports use `cli_anything.<software>.*`
- Copy `{PLUGIN_ROOT}/scripts/repl_skin.py` (and preview helpers when applicable)

### Phase 4: Test Planning
- `TEST.md` with unit, E2E, and workflow plans

### Phase 5: Test Implementation
- `test_core.py`, `test_full_e2e.py`, workflow tests, `_resolve_cli("cli-anything-<software>")`

### Phase 6: Test Documentation
- Run `pytest -v --tb=no`; append results to `TEST.md`

### Phase 7: Packaging and Installation
- `setup.py` with namespace packages; `cli-anything-<software>` console script
- `pip install -e .`; verify PATH; generate CLI-specific `SKILL.md` via `{PLUGIN_ROOT}/scripts/skill_generator.py`

## Quality Bar Checklist (do not skip)

- Real software backend preferred over reimplementation
- One-shot Click subcommands + default REPL
- `--json` machine-readable output
- Session state with undo/redo where supported; locked session writes; auto-save / `--dry-run` per guides
- Unit (`test_core.py`) + E2E (`test_full_e2e.py`) + installed-command subprocess coverage
- Namespace packaging: `cli_anything.<software>`, no top-level `cli_anything/__init__.py`
- Generate CLI-specific skills via vendored `skill_generator.py`

## Output Expectations

Report phases completed, harness path, test summary, install command, and resume state in `agent-harness/.cli-anything-progress.json`.
