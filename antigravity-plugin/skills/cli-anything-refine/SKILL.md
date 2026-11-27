---
name: cli-anything-refine
description: >-
  Refine an existing CLI-Anything harness in Google Antigravity to analyze
  capability gaps and incrementally add new commands, backend wrappers, and
  tests (with optional focus area). Invoked via /cli-anything-refine <path> [focus].
---

# `/cli-anything-refine` — Expand Coverage of an Existing Harness

Incrementally expand an already-built CLI harness after `/cli-anything`, either
broadly across the software or scoped to a specific `[focus]` area.

## 1. Resolve `PLUGIN_ROOT` and Read Canonical Spec

Resolve `PLUGIN_ROOT` (first location with `references/HARNESS.md` and `scripts/verify_harness.py` wins):
1. Two levels up from this `SKILL.md` (`.../plugins/cli-anything`).
2. Discovery pointer (`~/.gemini/cli-anything-generator.root` or `%USERPROFILE%\.gemini\cli-anything-generator.root`).
3. `{workspace}/.agents/plugins/cli-anything`, `$ANTIGRAVITY_PLUGINS_HOME/cli-anything`, or `~/.gemini/config/plugins/cli-anything`.
4. **Source checkout fallback (`{REPO_ROOT}`):** If running directly from an uninstalled `CLI-Anything` checkout (no vendored `references/` directory), either bootstrap via `{REPO_ROOT}/antigravity-plugin/scripts/install.{sh,ps1}` or read `{REPO_ROOT}/cli-anything-plugin/HARNESS.md` and `{REPO_ROOT}/cli-anything-plugin/commands/refine.md`, and run `{REPO_ROOT}/antigravity-plugin/scripts/verify_harness.py` and `{REPO_ROOT}/cli-anything-plugin/skill_generator.py`.

Read with absolute paths via `read_file`:
- `{PLUGIN_ROOT}/references/HARNESS.md`
- `{PLUGIN_ROOT}/references/commands/refine.md`

## 2. Arguments

- `<software-path>` — **Required.** Local source directory (same tree used for the original build).
- `[focus]` — **Optional.** Natural-language capability area to target (e.g., `"picture-in-picture compositing"`, `"batch Script-Fu filters"`).

## 3. Hard Phase Gates & Resume

Track progress in `{software-root}/agent-harness/.cli-anything-progress.json` with `"mode": "refine"` and mirror transitions with `update_steps`:

1. `inventory` — catalog existing CLI commands, core modules, and tests.
2. `capability_scan` — scan target software APIs/CLIs (narrowed to `[focus]` when given; use `research` subagent for large trees).
3. `gap_analysis` — rank missing high-impact / composable features and **present the gap report to the user to confirm priorities before coding**.
4. `implement` — add commands following `HARNESS.md` (Click groups, `--json`, session undo/redo, auto-save/`--dry-run`, real backend). Never remove existing commands unless explicitly requested.
5. `test` — expand `test_core.py` and `test_full_e2e.py`; run full regression suite (`pytest`) plus `python "{PLUGIN_ROOT}/scripts/verify_harness.py" "<software-root>/agent-harness"`.
6. `document` — update `README.md`, `TEST.md`, `<SOFTWARE>.md`, and refresh `SKILL.md` via `{PLUGIN_ROOT}/scripts/skill_generator.py`.

Set `"terminal": true` and `"terminal_status": "success"` only after all tests and verification pass.
