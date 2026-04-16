# Zoom CLI — Test Plan & Results

## Test Strategy

### Unit Tests (`test_core.py`)
- **No network calls** — all Zoom API calls are mocked
- **No Zoom account required** — tests run with synthetic data
- Tests cover: auth setup/login, meeting CRUD, participant management, recordings, JSON output, backend utilities

### E2E Tests (`test_full_e2e.py`)
- **Require real Zoom OAuth credentials** — tokens must be saved via `auth login`
- **Skipped by default** — set `CLI_ANYTHING_ZOOM_E2E=1` to enable
- Tests cover: auth status, full meeting lifecycle (create/read/update/delete), meeting listing, recording listing

## Running Tests

```bash
# Unit tests only (no Zoom account needed)
cd zoom/agent-harness
python3 -m pytest cli_anything/zoom/tests/test_core.py -v

# E2E tests (requires Zoom OAuth setup)
CLI_ANYTHING_ZOOM_E2E=1 python3 -m pytest cli_anything/zoom/tests/test_full_e2e.py -v

# All tests
python3 -m pytest cli_anything/zoom/tests/ -v
```

## Test Results

| Test Suite | Status | Notes |
|---|---|---|
| TestAuthSetup | PASS | Config save/load, custom redirect URI |
| TestAuthLogin | PASS | Login without config, login with code (mocked) |
| TestMeetingCommands | PASS | Create, list, info, update, delete |
| TestParticipantCommands | PASS | Add, list registrants |
| TestRecordingCommands | PASS | List, get files |
| TestJsonOutput | PASS | Valid JSON output for meeting list, auth status |
| TestBackend | PASS | Config/token round-trip, URL building |

## Coverage Notes

- Auth module: OAuth setup, browser login flow (mocked), manual code flow, status check, logout
- Meetings module: Full CRUD, join/start URL retrieval
- Participants module: Add single/batch, list, remove registrants, past participants
- Recordings module: List, get files, download (mocked), delete
