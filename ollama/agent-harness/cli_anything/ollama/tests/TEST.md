# Ollama CLI — Test Plan & Results

## Test Strategy

### Unit Tests (`test_core.py`)
These tests do NOT require Ollama to be running. They test:
- URL construction in the backend module
- Output formatting helpers
- CLI argument parsing via Click's test runner
- Session state management (host, last model, chat history)
- Error handling for connection failures

### E2E Tests (`test_full_e2e.py`)
These tests REQUIRE Ollama running at `http://localhost:11434`. They test:
- Listing models
- Pulling a small test model
- Generating text completions
- Chat completions
- Model info display
- Embedding generation
- Model deletion

## Running Tests

```bash
cd ollama/agent-harness

# Unit tests only (no Ollama needed)
python -m pytest cli_anything/ollama/tests/test_core.py -v

# E2E tests (requires Ollama running)
python -m pytest cli_anything/ollama/tests/test_full_e2e.py -v

# All tests
python -m pytest cli_anything/ollama/tests/ -v
```

## Test Results

| Test Suite | Status | Notes |
|-----------|--------|-------|
| test_core.py | Passed | 87/87 (run 2026-03-18) |
| test_full_e2e.py | Passed | 10 passed, 1 skipped (embed model), run 2026-03-19 with `tinyllama` |
