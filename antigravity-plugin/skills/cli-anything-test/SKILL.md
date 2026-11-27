---
name: cli-anything-test
description: >-
  Run unit, real-backend E2E, and installed-CLI subprocess tests for an
  existing CLI-Anything harness in Google Antigravity and append passing
  results to TEST.md. Invoked via /cli-anything-test <path-or-repo>.
---

# `/cli-anything-test` — Run Harness Tests & Update `TEST.md`

Execute the full test suite against the real backend and installed console
script, then record passing results in `TEST.md`.

## 1. Resolve `PLUGIN_ROOT` and Read Canonical Spec

Resolve `PLUGIN_ROOT` (two levels up from this `SKILL.md`, or discovery pointer
`~/.gemini/cli-anything-generator.root`, or `~/.gemini/config/plugins/cli-anything`
where `references/HARNESS.md` exists). In an uninstalled `CLI-Anything` source
checkout (`{REPO_ROOT}`), either bootstrap with `{REPO_ROOT}/antigravity-plugin/scripts/install.{sh,ps1}`
or read `{REPO_ROOT}/cli-anything-plugin/HARNESS.md` and `{REPO_ROOT}/cli-anything-plugin/commands/test.md` directly.

Read with absolute paths via `read_file`:
- `{PLUGIN_ROOT}/references/HARNESS.md`
- `{PLUGIN_ROOT}/references/commands/test.md`

## 2. Arguments

- `<software-path-or-repo>` — **Required.** Local path (derive `<software-root>/agent-harness/` directly — never hardcode `/root/cli-anything/`) or GitHub URL (clone first).

## 3. Execution Steps & Phase Gates

Track in `{software-root}/agent-harness/.cli-anything-progress.json` with `"mode": "test"`:

1. `locate` — verify `agent-harness/cli_anything/<software>/tests/` exists and confirm the package is installed (`pip show cli-anything-<software>`).
2. `unit_tests` — run `python -m pytest cli_anything/<software>/tests/test_core.py -v --tb=short`.
3. `e2e_and_subprocess` — run the complete suite with force-installed mode so `_resolve_cli` verifies the real PATH executable:
   - Windows (`pwsh`): `$env:CLI_ANYTHING_FORCE_INSTALLED = "1"; python -m pytest cli_anything/<software>/tests/ -v -s --tb=short`
   - macOS / Linux: `CLI_ANYTHING_FORCE_INSTALLED=1 python3 -m pytest cli_anything/<software>/tests/ -v -s --tb=short`
   Confirm `[_resolve_cli] Using installed command:` appears in stdout and no real-backend tests were silently skipped.
4. `update_test_md` — **only if 100% of tests pass**, append the `pytest -v --tb=no` output, timestamp, and summary to `tests/TEST.md` (UTF-8). If any test fails, do NOT overwrite passing results in `TEST.md`; report exact failures and propose fixes.

Mark `"terminal": true` when complete.
