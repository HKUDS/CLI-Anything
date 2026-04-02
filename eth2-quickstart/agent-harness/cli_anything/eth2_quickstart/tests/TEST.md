# cli-anything-eth2-quickstart Test Plan

## Unit

- repo root detection from explicit path and environment
- config file upsert behavior
- CLI help and JSON output
- phase 2 command construction
- validator guidance generation
- status and health aggregation with mocked subprocess results

## E2E

- skip automatically when no real `eth2-quickstart` checkout is configured
- verify wrapper discovery
- verify read-only commands (`help`, `health-check`) against a real checkout

## Latest Pytest Results

### Unit

```text
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-7.4.4, pluggy-1.4.0 -- /usr/bin/python3
cachedir: .pytest_cache
rootdir: /root/.openclaw/workspace/dev/CLI-Anything/eth2-quickstart/agent-harness
plugins: anyio-4.12.1
collecting ... collected 14 items

eth2-quickstart/agent-harness/cli_anything/eth2_quickstart/tests/test_core.py::TestProjectHelpers::test_find_repo_root_from_explicit_path PASSED [  9%]
eth2-quickstart/agent-harness/cli_anything/eth2_quickstart/tests/test_core.py::TestProjectHelpers::test_find_repo_root_from_env PASSED [ 14%]
eth2-quickstart/agent-harness/cli_anything/eth2_quickstart/tests/test_core.py::TestProjectHelpers::test_upsert_user_config PASSED [ 21%]
eth2-quickstart/agent-harness/cli_anything/eth2_quickstart/tests/test_core.py::TestValidatorPlan::test_prysm_plan PASSED [ 28%]
eth2-quickstart/agent-harness/cli_anything/eth2_quickstart/tests/test_core.py::TestValidatorPlan::test_invalid_client PASSED [ 35%]
eth2-quickstart/agent-harness/cli_anything/eth2_quickstart/tests/test_core.py::TestCLI::test_help PASSED [ 42%]
eth2-quickstart/agent-harness/cli_anything/eth2_quickstart/tests/test_core.py::TestCLI::test_missing_repo_root_returns_clean_json_error PASSED [ 50%]
eth2-quickstart/agent-harness/cli_anything/eth2_quickstart/tests/test_core.py::TestCLI::test_health_check_json PASSED [ 57%]
eth2-quickstart/agent-harness/cli_anything/eth2_quickstart/tests/test_core.py::TestCLI::test_install_clients_json PASSED [ 64%]
eth2-quickstart/agent-harness/cli_anything/eth2_quickstart/tests/test_core.py::TestCLI::test_start_rpc_requires_confirm PASSED [ 71%]
eth2-quickstart/agent-harness/cli_anything/eth2_quickstart/tests/test_core.py::TestCLI::test_configure_validator_json PASSED [ 78%]
eth2-quickstart/agent-harness/cli_anything/eth2_quickstart/tests/test_core.py::TestCLI::test_status_json PASSED [ 85%]
eth2-quickstart/agent-harness/cli_anything/eth2_quickstart/tests/test_core.py::TestBackendErrors::test_run_handles_missing_wrapper PASSED [ 92%]
eth2-quickstart/agent-harness/cli_anything/eth2_quickstart/tests/test_core.py::TestBackendErrors::test_run_handles_permission_error PASSED [100%]

============================== 14 passed in 0.06s ==============================
```

### E2E

```text
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-7.4.4, pluggy-1.4.0 -- /usr/bin/python3
cachedir: .pytest_cache
rootdir: /root/.openclaw/workspace/dev/CLI-Anything/eth2-quickstart/agent-harness
plugins: anyio-4.12.1
collecting ... collected 3 items

eth2-quickstart/agent-harness/cli_anything/eth2_quickstart/tests/test_full_e2e.py::TestRealCheckoutE2E::test_help SKIPPED [ 33%]
eth2-quickstart/agent-harness/cli_anything/eth2_quickstart/tests/test_full_e2e.py::TestRealCheckoutE2E::test_health_check_json SKIPPED [ 66%]
eth2-quickstart/agent-harness/cli_anything/eth2_quickstart/tests/test_full_e2e.py::TestRealCheckoutE2E::test_status_json SKIPPED [100%]

============================== 3 skipped in 0.02s ==============================
```
