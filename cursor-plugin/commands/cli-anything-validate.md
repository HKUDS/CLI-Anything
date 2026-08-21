---
name: cli-anything-validate
description: Validate a CLI-Anything harness against the full HARNESS checklist
---

# cli-anything-validate Command

Validate an existing harness against directory, implementation, test, docs, packaging, and code-quality requirements.

**Target software**: local path argument (required).

## CRITICAL: Resolve PLUGIN_ROOT (absolute paths only)

1. Read `~/.cursor/cli-anything-generator.root` / `%USERPROFILE%\.cursor\cli-anything-generator.root`
2. Else install dir `PLUGIN_ROOT.txt` / default `.../plugins/local/cli-anything`
3. Read `{PLUGIN_ROOT}/references/HARNESS.md` and `{PLUGIN_ROOT}/references/commands/validate.md` via absolute paths

## Cursor Tool Bindings

| Cursor tool | Role |
|-------------|------|
| Glob / Grep / Read | Checklist inventory of harness layout and APIs |
| Shell | Optional smoke tests, import checks, `pip show` / entry-point checks |
| Write | Only to record validation report if the user asks for a file |

## Phase Gates and Resume (hard gate)

Progress: `{software-root}/agent-harness/.cli-anything-progress.json` with `"mode": "validate"`.

- Walk checklist sections; mark each section completed before moving on.
- Resume incomplete validation; finish with a clear pass/fail summary and concrete gaps.

## Validate checklist (summary)

- Directory layout under `agent-harness/cli_anything/<software>/`
- Implementation: Click + REPL + `--json` + session patterns per HARNESS
- Tests: unit + E2E + installed CLI
- Docs: README, SOFTWARE.md, TEST.md, skills
- Packaging: namespace packages + console_scripts

## What This Command Does

Follow `{PLUGIN_ROOT}/references/commands/validate.md`. Do not silently lower the quality bar.
