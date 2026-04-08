# Dify Workflow Harness Test Documentation

## Test Inventory Plan

- `test_core.py`: backend discovery, command construction, packaging fixture checks
- `test_full_e2e.py`: wrapper subprocess smoke tests and workflow lifecycle forwarding

## Unit Test Plan

### utils/dify_workflow_backend.py

- resolve the upstream `dify-workflow` executable from PATH
- fall back to `python -m dify_workflow.cli` when only the Python package exists
- raise clear install guidance when neither exists
- build the final subprocess command correctly

### Packaging fixtures

- README documents two-step installation
- SKILL.md documents wrapper semantics and installation
- wrapper CLI exposes the expected top-level commands

## E2E Test Plan

- verify `--help` on the wrapper command
- create a minimal workflow through the wrapper when the upstream CLI is installed
- validate the created workflow through the wrapper
- inspect the workflow as JSON through the wrapper

## Notes

This harness wraps an external open-source CLI rather than shipping the workflow
engine itself. Full E2E tests therefore require the upstream Dify workflow CLI
to be installed locally before the suite is run. If the upstream CLI is missing
or broken, the E2E suite now fails explicitly instead of being skipped.

## Test Results

Verified on 2026-04-07 in the local CLI-Anything worktree.

### Commands Run

```bash
uv run --with pytest --with click --with prompt-toolkit --with-editable "c:\Users\lishun\py_ws\提交pr\dify-workflow-cli" python -m pytest cli_anything/dify_workflow/tests -vv -s
```

### Results

- total collected: 11
- passed: 11

### Notes

- Full forwarding tests were rerun with the upstream `dify-workflow` package installed editable from the local `dify-workflow-cli` repository.
- The wrapper suite now exercises `help`, `create`, `validate`, and `inspect -j` end-to-end against the real upstream CLI.
