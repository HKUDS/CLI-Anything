# TEST.md — cli-anything-rms Test Plan

## Test Plan

### Test Inventory

| File | Type | Count |
|------|------|-------|
| test_core.py | Unit | ~40 tests |
| test_full_e2e.py | E2E | ~20 tests |

### Unit Tests (test_core.py)

Tests use `unittest.mock.patch` to mock `requests` calls. No RMS account needed.

**Backend tests:**
- `test_get_api_token_from_env` — reads from RMS_API_TOKEN env var
- `test_get_api_token_from_config` — reads from config file
- `test_require_api_token_missing` — raises RuntimeError with instructions
- `test_make_auth_headers` — returns correct Bearer header
- `test_api_get_success` — parses JSON response
- `test_api_get_error` — raises RuntimeError on HTTP error
- `test_api_get_rate_limited` — handles 429 response
- `test_api_post_success` — sends JSON body
- `test_api_put_success` — sends JSON body
- `test_api_delete_success` — returns response

**Core module tests (per resource):**
- `test_list_devices` — calls GET /devices with params
- `test_get_device` — calls GET /devices/{id}
- `test_list_companies` — calls GET /companies
- `test_list_tags` — calls GET /tags
- `test_create_tag` — calls POST /tags
- `test_list_alerts` — calls GET /device_alerts
- `test_get_location` — calls GET /device_location/{device_id}

**Session tests:**
- `test_session_create` — creates session file
- `test_session_save_load` — round-trip persistence
- `test_session_history` — tracks command history
- `test_session_clear` — resets state

### E2E Tests (test_full_e2e.py)

Require `RMS_API_TOKEN` environment variable. Skip if not set.

**Connectivity:**
- `test_api_connectivity` — GET /devices returns success

**Device workflows:**
- `test_list_devices` — returns device list with pagination
- `test_get_device` — returns device details (uses first device from list)

**Resource listing:**
- `test_list_companies` — returns company list
- `test_list_users` — returns user list
- `test_list_tags` — returns tag list

**CLI integration:**
- `test_cli_devices_list` — `cli-anything-rms --json devices list` returns valid JSON
- `test_cli_auth_test` — `cli-anything-rms auth test` succeeds

### Running Tests

**Important:** Use `python -m pytest` (not bare `pytest`) to avoid namespace package import errors with `cli_anything`:

```bash
cd rms/agent-harness
source .venv/bin/activate
export RMS_API_TOKEN=<your-pat>

# Unit tests (no token needed)
python -m pytest cli_anything/rms/tests/test_core.py -v

# E2E tests (requires RMS_API_TOKEN)
python -m pytest cli_anything/rms/tests/test_full_e2e.py -v
```

Bare `pytest` resolves the local `cli_anything/` directory instead of the installed namespace package, causing `ModuleNotFoundError` in tests that use direct imports. Subprocess-based tests (TestCLIIntegrationE2E) are unaffected.

### Realistic Workflows

1. **Device monitoring**: List devices → filter by status → get details → check location
2. **Alert management**: List alerts → view alert config → create new config
3. **User admin**: List users → invite user → update role

---

## Test Results

### Unit Tests — 76/76 passed (0.10s)


### E2E Tests — 9/9 passed (3.03s) — 2026-03-23

Validated against live Teltonika RMS API with a real PAT.

| Test | Result | Notes |
|------|--------|-------|
| `test_api_connectivity` | PASSED | GET /devices?limit=1 returns success |
| `test_auth_headers` | PASSED | Bearer token header constructed correctly |
| `test_list_devices` | PASSED | devices returned with pagination |
| `test_get_device` | PASSED | Single device detail fetch works |
| `test_list_companies` | PASSED | Company listing returns success |
| `test_list_users` | PASSED | User listing returns success |
| `test_list_tags` | PASSED | Tag listing returns success |
| `test_cli_devices_list` | PASSED | `--json devices list --limit 1` returns valid JSON |
| `test_cli_auth_test` | PASSED | `auth test` exits 0 |

### Manual CLI Validation — 2026-03-23

| Command | Result |
|---------|--------|
| `python -m cli_anything.rms auth test` | "API connection successful" |
| `python -m cli_anything.rms devices list` | all devices listed (human-readable) |
| `python -m cli_anything.rms --json devices list --limit 5` | Valid JSON, 5 devices, correct metadata |

**No endpoint path adjustments were needed** — all API paths matched the real Teltonika RMS API.
