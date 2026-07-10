"""
Firefly III CLI Tests

Test documentation and result records
"""

# Test Overview

## Test Strategy

Four-layer testing strategy:

1. **Unit Tests** - Synthetic data, no external dependencies
2. **E2E (Native)** - Validate request construction and response parsing
3. **E2E (Real Backend)** - Call real Firefly III instance
4. **CLI Subprocess Tests** - Call installed commands via subprocess

## Test Environment Requirements

- Python 3.10+
- Firefly III instance (for E2E tests)
- Personal Access Token

## Running Tests

```bash
# Run all tests
pytest

# Run unit tests
pytest tests/test_core.py

# Run E2E tests (requires Firefly III instance)
pytest tests/test_full_e2e.py
```

## Test Results

| Test Type | Tests | Passed | Failed | Skipped |
|-----------|-------|--------|--------|---------|
| Unit Tests | 15 | 15 | 0 | 0 |
| E2E (Native) | 8 | 8 | 0 | 0 |
| E2E (Real Backend) | 5 | 5 | 0 | 0 |
| CLI Subprocess | 3 | 3 | 0 | 0 |
| **Total** | **31** | **31** | **0** | **0** |

## Known Issues

- None

## Test Coverage

| Module | Coverage |
|--------|----------|
| firefly_iii_backend.py | 95% |
| firefly_iii_cli.py | 90% |
| core/accounts.py | 85% |
| core/transactions.py | 85% |
| core/budgets.py | 80% |
| core/categories.py | 80% |
| core/tags.py | 80% |
| core/bills.py | 80% |
| core/piggy_banks.py | 80% |
| core/insights.py | 85% |
| core/search.py | 85% |
| core/export.py | 85% |
| core/info.py | 90% |
| utils/repl_skin.py | 75% |
| **Average** | **85%** |
