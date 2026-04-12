# PM2 CLI Tests

Test suites for the PM2 CLI-Anything harness.

## Test Files

| File              | Type   | Count | Dependencies         |
|-------------------|--------|-------|----------------------|
| `test_core.py`    | Unit   | 28    | None (mocked subprocess) |
| `test_full_e2e.py`| E2E    | 9     | pm2 installed, CLI on PATH |

## Running Tests

```bash
cd agent-harness
pip install -e .

# All tests
python -m pytest cli_anything/pm2/tests/ -v

# Unit tests only (no pm2 needed)
python -m pytest cli_anything/pm2/tests/test_core.py -v

# E2E tests only (requires pm2)
python -m pytest cli_anything/pm2/tests/test_full_e2e.py -v
```

## Test Plan

### Unit Tests (test_core.py)

- [x] `_find_pm2()` locates binary via shutil.which
- [x] `_find_pm2()` raises RuntimeError when pm2 missing
- [x] `run_pm2()` returns success dict on exit code 0
- [x] `run_pm2()` returns failure dict on exit code 1
- [x] `run_pm2()` parses JSON stdout with capture_json=True
- [x] `run_pm2()` extracts JSON from stdout with non-JSON preamble
- [x] `run_pm2()` handles subprocess timeout
- [x] `run_pm2()` handles FileNotFoundError for missing binary
- [x] `list_processes()` JSON mode returns raw list
- [x] `list_processes()` human mode returns formatted rows
- [x] `list_processes()` returns message when no processes
- [x] `describe_process()` returns details for known process
- [x] `describe_process()` returns None for unknown process
- [x] `get_metrics()` JSON mode returns metric dicts
- [x] `restart_process()` success message
- [x] `stop_process()` failure message
- [x] `start_process()` with name in JSON mode
- [x] `view_logs()` success with content
- [x] `flush_logs()` all processes
- [x] `version()` JSON mode
- [x] `save()` success message
- [x] `_output()` JSON string wrapping
- [x] `_output()` JSON dict passthrough
- [x] `_output()` human string echo
- [x] `_output()` human dict with [OK] prefix
- [x] `_output()` human dict with [ERROR] prefix
- [x] `_format_bytes()` zero bytes
- [x] `_format_bytes()` megabytes

### E2E Tests (test_full_e2e.py)

- [x] `--json process list` returns valid JSON array
- [x] `process list` exits with code 0
- [x] `--json process describe <name>` returns valid JSON dict
- [x] `process describe __nonexistent__` exits non-zero
- [x] `--json system version` returns JSON with version key
- [x] `system version` returns version string with digits
- [x] `--help` exits with code 0
- [x] `process --help` shows list and describe subcommands
- [x] `--json process metrics` returns JSON list

## Last Run Results

```
Platform: darwin (macOS)
Python:   3.14.3
pytest:   9.0.2
Date:     2026-03-23

37 passed in 1.53s
  - test_core.py:     28 passed
  - test_full_e2e.py:  9 passed
```
