# CC Switch CLI - Test Plan

## Test Inventory Plan

| Test File | Planned Tests | Type |
|-----------|--------------|------|
| `test_core.py` | 25+ | Unit tests (synthetic data) |
| `test_full_e2e.py` | 15+ | E2E tests (real database) |

## Unit Test Plan

### `test_core.py` — Unit Tests with Synthetic Data

**Database connection (`utils/db.py`)**
- `test_get_cc_switch_dir` — custom env var
- `test_get_db_path` — returns correct path
- `test_valid_app_types` — VALID_APP_TYPES contains expected values
- `test_connect_db_in_memory` — connects without error
- `test_resolve_app_valid` — valid app types pass
- `test_resolve_app_invalid` — raises on invalid
- `test_resolve_app_none` — None returns None

**Table formatting (`_table`)**
- `test_table_basic` — basic table output
- `test_table_empty` — empty rows returns "(empty)"
- `test_table_single` — single row

**Sensitive masking (`_mask_sensitive`)**
- `test_mask_api_token` — masks long token
- `test_mask_api_key` — masks key in name
- `test_mask_short_value` — short values still masked
- `test_mask_non_sensitive` — leaves normal values unmasked
- `test_mask_nested_dict` — recursively masks nested dict

**CLI invocation**
- `test_main_help` — `--help` returns 0
- `test_providers_help` — `providers --help` returns 0
- `test_usage_help` — `usage --help` returns 0
- `test_skills_help` — `skills --help` returns 0
- `test_has_commands` — all 6 command groups present

## E2E Test Plan

### `test_full_e2e.py` — Tests Against Real CC Switch Database

**Providers**
- `test_providers_list` — returns rows
- `test_providers_list_json` — valid JSON output
- `test_providers_list_filter_by_app` — filter works
- `test_providers_get_existing` — returns provider details
- `test_providers_get_masked` — API keys are masked in output (never exposed in plaintext)
- `test_providers_get_nonexistent` — exits with error

**Skills**
- `test_skills_list` — returns rows
- `test_skills_list_json` — valid JSON
- `test_skills_repos` — returns repos

**Usage**
- `test_usage_stats` — returns rows with cost
- `test_usage_stats_json` — valid JSON
- `test_usage_logs` — returns recent logs

**MCP**
- `test_mcp_list` — returns servers
- `test_mcp_list_json` — valid JSON

**Settings**
- `test_settings_list` — returns key-value pairs
- `test_settings_get_existing` — returns value

**Proxy**
- `test_proxy_status_claude` — returns proxy config

**Combined**
- `test_full_status` — default invocation shows overview
- `test_full_status_json` — JSON mode works for overview

## Realistic Workflow Scenarios

### Workflow 1: Provider Audit
- **Simulates**: Checking which providers are configured across all apps
- **Operations**: 1) List all providers 2) Get details for current providers 3) Check proxy status
- **Verified**: All apps have at least one provider, current providers are set

### Workflow 2: Cost Analysis
- **Simulates**: Monthly cost review
- **Operations**: 1) Get usage stats for last 30 days 2) Get recent logs 3) Check per-model costs
- **Verified**: Cost data is present, models are tracked

### Workflow 3: Skill Inventory
- **Simulates**: Auditing installed skills across apps
- **Operations**: 1) List all skills 2) Check registered repos 3) Verify skill enable status
- **Verified**: Skills are listed with source info

---

## Phase 6: Test Results

### Full pytest Output

```
============================= test session starts =============================
platform win32 -- Python 3.13.9, pytest-8.4.2, pluggy-1.5.0
rootdir: D:\study\vibe-coding\cli-anything\cc-switch-3.15.0\agent-harness
plugins: anyio-4.10.0
collected 50 items

cli_anything/ccswitch/tests/test_core.py::test_get_cc_switch_dir_custom PASSED [  2%]
cli_anything/ccswitch/tests/test_core.py::test_get_db_path PASSED        [  4%]
cli_anything/ccswitch/tests/test_core.py::test_get_config_path PASSED    [  6%]
cli_anything/ccswitch/tests/test_core.py::test_get_settings_path PASSED  [  8%]
cli_anything/ccswitch/tests/test_core.py::test_valid_app_types PASSED    [ 10%]
cli_anything/ccswitch/tests/test_core.py::test_connect_db_in_memory PASSED [ 12%]
cli_anything/ccswitch/tests/test_core.py::test_load_config_missing PASSED [ 14%]
cli_anything/ccswitch/tests/test_core.py::test_save_and_load_config PASSED [ 16%]
cli_anything/ccswitch/tests/test_core.py::test_load_settings_missing PASSED [ 18%]
cli_anything/ccswitch/tests/test_core.py::test_resolve_app_valid PASSED  [ 20%]
cli_anything/ccswitch/tests/test_core.py::test_resolve_app_none PASSED   [ 22%]
cli_anything/ccswitch/tests/test_core.py::test_resolve_app_invalid PASSED [ 24%]
cli_anything/ccswitch/tests/test_core.py::test_table_basic PASSED        [ 26%]
cli_anything/ccswitch/tests/test_core.py::test_table_empty PASSED        [ 28%]
cli_anything/ccswitch/tests/test_core.py::test_table_single PASSED       [ 30%]
cli_anything/ccswitch/tests/test_core.py::test_mask_api_token PASSED     [ 32%]
cli_anything/ccswitch/tests/test_core.py::test_mask_api_key PASSED       [ 34%]
cli_anything/ccswitch/tests/test_core.py::test_mask_password PASSED      [ 36%]
cli_anything/ccswitch/tests/test_core.py::test_mask_short_value PASSED   [ 38%]
cli_anything/ccswitch/tests/test_core.py::test_mask_non_sensitive PASSED [ 40%]
cli_anything/ccswitch/tests/test_core.py::test_mask_nested_dict PASSED   [ 42%]
cli_anything/ccswitch/tests/test_core.py::test_main_help PASSED          [ 44%]
cli_anything/ccswitch/tests/test_core.py::test_providers_help PASSED     [ 46%]
cli_anything/ccswitch/tests/test_core.py::test_usage_help PASSED         [ 48%]
cli_anything/ccswitch/tests/test_core.py::test_skills_help PASSED        [ 50%]
cli_anything/ccswitch/tests/test_core.py::test_mcp_help PASSED           [ 52%]
cli_anything/ccswitch/tests/test_core.py::test_proxy_help PASSED         [ 54%]
cli_anything/ccswitch/tests/test_core.py::test_settings_help PASSED      [ 56%]
cli_anything/ccswitch/tests/test_core.py::test_sessions_help PASSED      [ 58%]
cli_anything/ccswitch/tests/test_core.py::test_all_command_groups PASSED [ 60%]
cli_anything/ccswitch/tests/test_full_e2e.py::TestCLISubprocess::test_help PASSED [ 62%]
cli_anything/ccswitch/tests/test_full_e2e.py::TestCLISubprocess::test_providers_help PASSED [ 64%]
cli_anything/ccswitch/tests/test_full_e2e.py::TestCLISubprocess::test_providers_list PASSED [ 66%]
cli_anything/ccswitch/tests/test_full_e2e.py::TestCLISubprocess::test_providers_list_json PASSED [ 68%]
cli_anything/ccswitch/tests/test_full_e2e.py::TestCLISubprocess::test_providers_list_filter_claude PASSED [ 70%]
cli_anything/ccswitch/tests/test_full_e2e.py::TestCLISubprocess::test_providers_get_nonexistent PASSED [ 72%]
cli_anything/ccswitch/tests/test_full_e2e.py::TestCLISubprocess::test_providers_get_no_api_key_leaked PASSED [ 74%]
cli_anything/ccswitch/tests/test_full_e2e.py::TestCLISubprocess::test_skills_list PASSED [ 76%]
cli_anything/ccswitch/tests/test_full_e2e.py::TestCLISubprocess::test_skills_list_json PASSED [ 78%]
cli_anything/ccswitch/tests/test_full_e2e.py::TestCLISubprocess::test_skills_repos PASSED [ 80%]
cli_anything/ccswitch/tests/test_full_e2e.py::TestCLISubprocess::test_usage_stats PASSED [ 82%]
cli_anything/ccswitch/tests/test_full_e2e.py::TestCLISubprocess::test_usage_stats_json PASSED [ 84%]
cli_anything/ccswitch/tests/test_full_e2e.py::TestCLISubprocess::test_usage_logs PASSED [ 86%]
cli_anything/ccswitch/tests/test_full_e2e.py::TestCLISubprocess::test_mcp_list PASSED [ 88%]
cli_anything/ccswitch/tests/test_full_e2e.py::TestCLISubprocess::test_mcp_list_json PASSED [ 90%]
cli_anything/ccswitch/tests/test_full_e2e.py::TestCLISubprocess::test_settings_list PASSED [ 92%]
cli_anything/ccswitch/tests/test_full_e2e.py::TestCLISubprocess::test_settings_list_json PASSED [ 94%]
cli_anything/ccswitch/tests/test_full_e2e.py::TestCLISubprocess::test_proxy_status PASSED [ 96%]
cli_anything/ccswitch/tests/test_full_e2e.py::TestCLISubprocess::test_full_status PASSED [ 98%]
cli_anything/ccswitch/tests/test_full_e2e.py::TestCLISubprocess::test_full_status_json PASSED [100%]

============================= 50 passed in 1.84s ==============================
```

### Summary Statistics

| Metric | Value |
|--------|-------|
| **Total tests** | 50 |
| **Passed** | 50 |
| **Failed** | 0 |
| **Pass rate** | 100% |
| **Execution time** | 1.84s |
| **Unit tests (test_core.py)** | 30 |
| **E2E tests (test_full_e2e.py)** | 20 |

### Coverage Notes

- **DB path resolution**: Covered with custom `CCSWITCH_HOME` env var
- **Config load/save**: Covered including empty-file edge case
- **App resolution**: Covered valid, invalid, and None inputs
- **Table formatting**: Covered basic, empty, and single-row cases
- **Sensitive masking**: Covered tokens, keys, passwords, short values, non-sensitive keys, and nested dicts
- **CLI help commands**: All 7 command groups tested via Click CliRunner
- **E2E providers**: List, JSON output, filtering, nonexistent lookup, API key leak prevention
- **E2E skills**: List, JSON output, repos listing
- **E2E usage**: Stats, JSON stats, logs
- **E2E MCP**: List, JSON output
- **E2E settings**: List, JSON output
- **E2E proxy**: Status check
- **E2E combined**: Default overview and JSON overview
- **Not covered**: Write operations (providers add/remove, settings set, proxy start/stop, sessions kill) — these are destructive and require a disposable test environment; recommended for manual testing only
