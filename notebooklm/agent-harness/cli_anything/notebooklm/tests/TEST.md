# NotebookLM Harness - Test Documentation

## Test Inventory

| File | Focus |
| --- | --- |
| `test_core.py` | backend discovery, command building, session persistence, packaging fixtures |
| `test_cli_smoke.py` | help output and command group exposure |
| `test_manual_e2e.md` | authenticated local smoke-test checklist |

## Coverage Notes

This harness has three validation layers:

- unit tests for backend helpers and session state
- smoke tests for CLI help and command registration
- manual authenticated end-to-end verification

Because NotebookLM depends on a live Google account session and an installed
community CLI, full authenticated E2E coverage is not run in public CI.

## Local Verification

Verified on 2026-03-17 in the notebooklm harness worktree.

### Commands Run

```bash
python3 -m pytest cli_anything/notebooklm/tests/test_core.py -q
python3 -m pytest cli_anything/notebooklm/tests/test_cli_smoke.py -q
python3 -m cli_anything.notebooklm.notebooklm_cli --help
```

### Results

- `test_core.py`: 9 passed
- `test_cli_smoke.py`: 5 passed
- `python3 -m cli_anything.notebooklm.notebooklm_cli --help`: exit code 0, help text rendered correctly

### Notes

- Added a regression test for module execution so `python -m cli_anything.notebooklm.notebooklm_cli --help` is covered, not just Click's in-process `CliRunner`.
- The authenticated `notebooklm` backend remains intentionally manual for end-to-end verification because it depends on a local Google session.

## PR Polish Verification

Verified on 2026-03-17 after README, SKILL, and subprocess smoke coverage upgrades.

### Commands Run

```bash
python3 -m pytest cli_anything/notebooklm/tests -q
python3 -m cli_anything.notebooklm.notebooklm_cli --help
```

### Results

- Full NotebookLM harness suite: 17 passed
- Module help command: exit code 0, rendered command groups correctly

### Notes

- Added doc-level assertions so the package README and skill file now explicitly cover installation, tests, safety boundaries, and unofficial Google attribution.
- Added `_resolve_cli`-style subprocess smoke coverage so the CLI can be exercised through a resolved command path, not only through Click's in-process test runner.

## Review Fix Verification

Verified on 2026-03-17 after addressing PR review feedback about JSON passthrough and auth command semantics.

### Commands Run

```bash
python3 -m pytest cli_anything/notebooklm/tests/test_core.py -q
python3 -m pytest cli_anything/notebooklm/tests/test_cli_smoke.py -q
python3 -m pytest cli_anything/notebooklm/tests -q
python3 -m cli_anything.notebooklm.notebooklm_cli --json auth login
```

### Results

- targeted backend tests: pass
- targeted CLI routing tests: pass
- full NotebookLM harness suite: pass
- `--json auth login`: fails fast with a structured JSON error instead of passing an invalid `--json` flag through to upstream login

### Notes

- `auth status` now wraps upstream `notebooklm auth check`, which matches authentication semantics.
- JSON passthrough is now limited to wrapper commands whose upstream `notebooklm` command has verified `--json` support.
