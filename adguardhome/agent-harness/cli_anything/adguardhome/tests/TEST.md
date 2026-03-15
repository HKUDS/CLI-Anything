# Test Plan - cli-anything-adguardhome

## Test Inventory Plan

- `test_core.py`: 20 unit tests (no real AdGuardHome needed)
- `test_full_e2e.py`: 12 E2E + subprocess tests (Docker AdGuardHome on port 3001)

## Unit Test Plan (test_core.py)

### AdGuardHomeClient (utils/adguardhome_backend.py)
- `test_client_init_default` - default host/port, no auth
- `test_client_init_with_auth` - auth set on session
- `test_client_url_construction` - base URL built correctly
- `test_get_success` - GET returns deserialized JSON
- `test_get_empty_response` - GET returns {} on empty body
- `test_post_json` - POST sends JSON body
- `test_post_empty` - POST with no data
- `test_connection_error_raises_runtime` - ConnectionError raises RuntimeError with instructions

### project.py
- `test_load_config_defaults` - returns localhost:3000 when no file/env
- `test_load_config_from_file` - loads from JSON file
- `test_load_config_env_override` - env vars override file
- `test_save_config` - writes JSON file correctly

### filtering.py
- `test_get_status` - calls GET /filtering/status
- `test_add_filter` - calls POST /filtering/add_url with correct body
- `test_remove_filter` - calls POST /filtering/remove_url
- `test_set_enabled` - calls POST /filtering/config

### blocking.py
- `test_parental_status` - calls GET /parental/status
- `test_parental_enable` - calls POST /parental/enable
- `test_safebrowsing_status` - calls GET /safebrowsing/status

### clients.py
- `test_list_clients` - calls GET /clients
- `test_add_client` - calls POST /clients/add with correct body

### rewrite.py
- `test_list_rewrites` - calls GET /rewrite/list
- `test_add_rewrite` - calls POST /rewrite/add

## E2E Test Plan (test_full_e2e.py)

### Setup
- Docker fixture starts `adguard/adguardhome` on port 3001 with pre-configured YAML
- Teardown removes the container

### Workflow: CLI subprocess tests (no real AdGuardHome)
- `test_help` - `cli-anything-adguardhome --help` exits 0
- `test_config_show_json` - `--json config show` returns valid JSON with host/port
- `test_server_version_json` - `--json server version` returns JSON (requires running instance)
- `test_filter_list_json` - `--json filter list` returns JSON

### Workflow: Full filter lifecycle (requires Docker AdGuardHome)
- `test_filter_list` - list filters on fresh instance
- `test_rewrite_add_and_list` - add rewrite, verify in list
- `test_rewrite_remove` - remove rewrite, verify gone

---

## Test Results

(appended after pytest run)

---

## Test Results

```
============================= test session starts ==============================
platform linux -- Python 3.13.5, pytest-9.0.2, pluggy-1.6.0
rootdir: /home/yoan/work/AdGuardHome/agent-harness

cli_anything/adguardhome/tests/test_core.py::TestAdGuardHomeClient::test_client_init_default PASSED
cli_anything/adguardhome/tests/test_core.py::TestAdGuardHomeClient::test_client_init_with_auth PASSED
cli_anything/adguardhome/tests/test_core.py::TestAdGuardHomeClient::test_client_init_no_auth PASSED
cli_anything/adguardhome/tests/test_core.py::TestAdGuardHomeClient::test_client_url_construction PASSED
cli_anything/adguardhome/tests/test_core.py::TestAdGuardHomeClient::test_get_success PASSED
cli_anything/adguardhome/tests/test_core.py::TestAdGuardHomeClient::test_get_empty_response PASSED
cli_anything/adguardhome/tests/test_core.py::TestAdGuardHomeClient::test_post_json PASSED
cli_anything/adguardhome/tests/test_core.py::TestAdGuardHomeClient::test_post_empty PASSED
cli_anything/adguardhome/tests/test_core.py::TestAdGuardHomeClient::test_connection_error_raises_runtime PASSED
cli_anything/adguardhome/tests/test_core.py::TestProject::test_load_config_defaults PASSED
cli_anything/adguardhome/tests/test_core.py::TestProject::test_load_config_from_file PASSED
cli_anything/adguardhome/tests/test_core.py::TestProject::test_load_config_env_override PASSED
cli_anything/adguardhome/tests/test_core.py::TestProject::test_save_config PASSED
cli_anything/adguardhome/tests/test_core.py::TestFiltering::test_get_status PASSED
cli_anything/adguardhome/tests/test_core.py::TestFiltering::test_add_filter PASSED
cli_anything/adguardhome/tests/test_core.py::TestFiltering::test_remove_filter PASSED
cli_anything/adguardhome/tests/test_core.py::TestFiltering::test_set_enabled PASSED
cli_anything/adguardhome/tests/test_core.py::TestBlocking::test_parental_status PASSED
cli_anything/adguardhome/tests/test_core.py::TestBlocking::test_parental_enable PASSED
cli_anything/adguardhome/tests/test_core.py::TestBlocking::test_safebrowsing_status PASSED
cli_anything/adguardhome/tests/test_core.py::TestClients::test_list_clients PASSED
cli_anything/adguardhome/tests/test_core.py::TestClients::test_add_client PASSED
cli_anything/adguardhome/tests/test_core.py::TestRewrite::test_list_rewrites PASSED
cli_anything/adguardhome/tests/test_core.py::TestRewrite::test_add_rewrite PASSED
cli_anything/adguardhome/tests/test_full_e2e.py::TestCLISubprocess::test_help PASSED
cli_anything/adguardhome/tests/test_full_e2e.py::TestCLISubprocess::test_config_show_json PASSED
cli_anything/adguardhome/tests/test_full_e2e.py::TestCLISubprocess::test_config_show_default_host PASSED
cli_anything/adguardhome/tests/test_full_e2e.py::TestCLISubprocess::test_help_subcommands_listed PASSED
cli_anything/adguardhome/tests/test_full_e2e.py::TestCLISubprocess::test_filter_help PASSED
cli_anything/adguardhome/tests/test_full_e2e.py::TestCLISubprocess::test_rewrite_help PASSED
cli_anything/adguardhome/tests/test_full_e2e.py::TestCLISubprocess::test_blocking_help PASSED
cli_anything/adguardhome/tests/test_full_e2e.py::TestDockerE2E::test_server_status_json PASSED
cli_anything/adguardhome/tests/test_full_e2e.py::TestDockerE2E::test_filter_list_json PASSED
cli_anything/adguardhome/tests/test_full_e2e.py::TestDockerE2E::test_rewrite_lifecycle PASSED
cli_anything/adguardhome/tests/test_full_e2e.py::TestDockerE2E::test_stats_show_json PASSED
cli_anything/adguardhome/tests/test_full_e2e.py::TestDockerE2E::test_config_test PASSED

============================== 36 passed in 6.57s ==============================
```

**36/36 passed (100%) — 2026-03-13**

- Unit tests: 24/24
- Subprocess tests (installed CLI): 7/7
- Docker E2E tests (real AdGuardHome v0.107.73): 5/5
