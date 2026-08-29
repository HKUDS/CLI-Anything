---
name: cli-anything-refine
description: Refine an existing CLI-Anything harness to expand coverage and add missing capabilities
---

# cli-anything-refine Command

Refine an existing CLI harness after a successful `/cli-anything` build.

**Target software**: first argument (local path required).
**Focus area**: optional second argument / trailing natural-language focus.

## CRITICAL: Resolve PLUGIN_ROOT (absolute paths only)

Resolve `PLUGIN_ROOT` in this order (first hit with `references/HARNESS.md` wins):

1. Read `%USERPROFILE%\.cursor\cli-anything-generator.root` or `~/.cursor/cli-anything-generator.root`
2. Else `{default-or-$CURSOR_PLUGINS_HOME}/local/cli-anything/PLUGIN_ROOT.txt`
3. Else that candidate directory if `references/HARNESS.md` exists
4. Else workspace / cloned `cli-anything-plugin/`

Then read `{PLUGIN_ROOT}/references/HARNESS.md` and `{PLUGIN_ROOT}/references/commands/refine.md` with absolute paths.

## Cursor Tool Bindings

| Cursor tool | Role |
|-------------|------|
| Read / Grep / Glob | Inventory current CLI coverage and target APIs |
| Shell | Run existing tests; verify new commands |
| Write / StrReplace | Add commands, modules, and tests |

## Arguments

- Local software path only (same tree used for the original build). Clone first with `/cli-anything` if needed.
- Optional focus area narrows gap analysis (e.g. `"picture-in-picture features"`).

## Phase Gates and Resume (hard gate)

Progress: `{software-root}/agent-harness/.cli-anything-progress.json` with `"mode": "refine"`.

- Steps: inventory → capability scan → gap analysis → implement → test → document.
- Do not advance a step until the previous is `completed` in the progress file.
- Resume incomplete refine runs; do not remove existing commands unless the user requests a breaking change.
- Mark `terminal: true` when refine completes or is permanently aborted.

## Refine checklist

- Inventory current commands/tests before coding
- Prefer high-impact gaps and thin wrappers around real backend APIs
- Add matching unit/E2E coverage for every new command surface
- Keep HARNESS packaging and `--json` / REPL standards

## What This Command Does

Follow `{PLUGIN_ROOT}/references/commands/refine.md` for the full procedure.
