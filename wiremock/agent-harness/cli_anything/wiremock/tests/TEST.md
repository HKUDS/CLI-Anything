# WireMock CLI Harness — Test Plan

## Overview

This document describes the testing strategy for the `cli-anything-wiremock` package. Tests live in this directory and cover both unit-level logic and end-to-end CLI invocation.

---

## Test Files

| File               | Type        | Description                                               |
|--------------------|-------------|-----------------------------------------------------------|
| `test_core.py`     | Unit        | Tests all core modules with mocked HTTP responses         |
| `test_full_e2e.py` | E2E / CLI   | Tests CLI subcommands via subprocess against a live server |

---

## Unit Tests (`test_core.py`)

Tests run entirely offline using `unittest.mock` to intercept `requests` calls.

### Coverage targets

| Module                         | Tests                                                                 |
|--------------------------------|-----------------------------------------------------------------------|
| `utils/client.py`              | `base_url()` construction, all HTTP verbs, `is_alive()` true/false    |
| `utils/output.py`              | `success()` JSON mode, `success()` human mode, `error()` exits        |
| `core/session.py`              | `from_env()` reads env vars, falls back to defaults                   |
| `core/stubs.py`                | `list()`, `get()`, `create()`, `delete()`, `reset()`, `quick_stub()`  |
| `core/requests_log.py`         | `list()`, `find()`, `count()`, `unmatched()`, `reset()`               |
| `core/scenarios.py`            | `list()`, `set_state()`, `reset_all()`                                |
| `core/recording.py`            | `start()` with and without headers, `stop()`, `status()`, `snapshot()`|
| `core/settings.py`             | `get()`, `get_version()`                                              |

### Running unit tests

```bash
cd /tmp/wiremock-src/agent-harness
pip install -e . pytest
pytest cli_anything/wiremock/tests/test_core.py -v
```

---

## E2E Tests (`test_full_e2e.py`)

CLI subcommand tests run via `subprocess`. They test argument parsing, flag handling, and output formatting.

Tests that require a live WireMock server are gated on the `WIREMOCK_URL` environment variable — they skip automatically when no server is available.

Tests that only invoke `--help` or check argument parsing do not require a live server.

### Running E2E tests (no server required for basic checks)

```bash
pytest cli_anything/wiremock/tests/test_full_e2e.py -v
```

### Running E2E tests with a live WireMock server

```bash
# Start WireMock first
java -jar wiremock-standalone.jar --port 8080 &

export WIREMOCK_URL=http://localhost:8080
pytest cli_anything/wiremock/tests/test_full_e2e.py -v
```

---

## Coverage Requirements

- Minimum 80% overall coverage
- All public methods in `core/` must have at least one unit test
- All CLI command groups must have at least one invocation test

```bash
pytest --cov=cli_anything.wiremock --cov-report=term-missing cli_anything/wiremock/tests/
```
