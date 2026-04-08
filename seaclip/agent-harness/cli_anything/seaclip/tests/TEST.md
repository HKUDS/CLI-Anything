# SeaClip CLI Harness - Test Documentation

## Test Inventory

| File | Test Classes | Test Count | Focus |
|------|-------------|------------|-------|
| `test_core.py` | 5 | 25 | Unit tests for backend, JSON output, human output, arg parsing, error handling |
| `test_full_e2e.py` | 1 | 10 | E2E subprocess tests against live backend + CLI binary |
| **Total** | **6** | **35** | |

## Unit Tests (`test_core.py`)

All unit tests mock HTTP and SQLite calls. No live backend required.

### TestBackendURLConstruction (4 tests)
- Default base URL is `http://127.0.0.1:5200`
- Custom base URL with trailing slash stripped
- URL helper concatenates path correctly
- `SEACLIP_URL` environment variable overrides default

### TestJSONOutput (6 tests)
- `server health` returns valid JSON with status field
- `issue list` returns JSON array with issue objects
- `issue create` returns JSON with new issue ID
- `agent list` returns JSON array with agent objects
- `scheduler list` returns JSON array
- `activity list --limit 5` returns JSON array

### TestHumanOutput (2 tests)
- `issue list` with results renders without error (table output)
- `issue list` with empty results renders info message

### TestCLIArgParsing (7 tests)
- `issue list` passes --status, --priority, --limit to backend
- `issue move` passes issue_id and --column to backend
- `issue move` without --column fails with non-zero exit
- `pipeline start` passes --issue and --mode to backend
- `pipeline start` with invalid --mode fails
- `activity list` uses default limit of 20
- `scheduler add` passes --name and --cron as config dict

### TestErrorHandling (6 tests)
- Connection error on `server health` produces `{"error": "..."}` and exit 1
- Exception on `issue list` produces JSON error object
- DB lock error on `agent list` produces JSON error with message
- Unknown subcommand exits non-zero
- `--version` flag prints version 1.0.0
- `--help` flag prints CLI description

## End-to-End Tests (`test_full_e2e.py`)

E2E tests shell out via `subprocess` to the installed `cli-anything-seaclip` binary.
Tests requiring the live backend are skipped gracefully if localhost:5200 is unreachable.

### TestCLISubprocess (10 tests)
- `server health` returns valid JSON from live API
- `issue list` returns JSON array from live API
- `issue list --limit 3` accepts limit parameter without error
- `issue list --status backlog` accepts status filter
- `agent list` returns JSON array (SQLite read)
- `scheduler list` returns JSON array (SQLite read)
- `activity list --limit 5` returns JSON array (SQLite read)
- `--version` subprocess prints version string
- `--help` subprocess prints CLI description
- Invalid subcommand exits non-zero

## Test Results

```
============================= test session starts ==============================
platform darwin -- Python 3.14.3, pytest-9.0.2, pluggy-1.6.0

test_core.py     25 passed
test_full_e2e.py 10 passed

============================= 35 passed in 1.17s ==============================
```
