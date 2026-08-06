---
name: cli-anything-test
description: Run CLI-Anything harness tests against the real backend and update TEST.md with passing results
---

# cli-anything-test Command

Run and document tests for an existing harness.

**Target software**: local path argument (required).

## CRITICAL: Resolve PLUGIN_ROOT (absolute paths only)

1. Read `~/.cursor/cli-anything-generator.root` / `%USERPROFILE%\.cursor\cli-anything-generator.root`
2. Else install dir `PLUGIN_ROOT.txt` / default `.../plugins/local/cli-anything`
3. Read `{PLUGIN_ROOT}/references/HARNESS.md` and `{PLUGIN_ROOT}/references/commands/test.md` via absolute paths

## Cursor Tool Bindings

| Cursor tool | Role |
|-------------|------|
| Shell | `pytest`, installed `cli-anything-<software>`, environment checks |
| Read / Grep | Locate tests, parse failures, update TEST.md |
| Write / StrReplace | Fix tests or harness bugs uncovered by failures |

## Phase Gates and Resume (hard gate)

Progress: `{software-root}/agent-harness/.cli-anything-progress.json` with `"mode": "test"`.

- Track unit / e2e / installed-CLI / TEST.md update steps; do not skip ahead without marking completion.
- Resume if interrupted; only append **passing** evidence to `TEST.md`.
- Prefer `CLI_ANYTHING_FORCE_INSTALLED=1` for release-style installed-command checks when documented by HARNESS / test command.

## Test checklist

- Run unit + E2E suites
- Verify installed `cli-anything-<software>` via subprocess / `_resolve_cli`
- Update `TEST.md` only with passing results

## What This Command Does

Follow `{PLUGIN_ROOT}/references/commands/test.md`.
