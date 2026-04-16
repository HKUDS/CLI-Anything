# ComfyUI Harness Test Guide

## Requirements

No ComfyUI installation required — all tests use mocked HTTP responses.

```bash
pip install pytest pytest-cov
# or install the harness with dev extras:
pip install -e ".[dev]"
```

## Running Tests

```bash
# From the agent-harness directory:
python -m pytest cli_anything/comfyui/tests/ -v

# Unit tests only:
python -m pytest cli_anything/comfyui/tests/test_core.py -v

# E2E simulation tests:
python -m pytest cli_anything/comfyui/tests/test_full_e2e.py -v

# With coverage:
python -m pytest cli_anything/comfyui/tests/ --cov=cli_anything.comfyui --cov-report=term-missing
```

## Test Structure

| File | Coverage |
|---|---|
| `test_core.py` | Unit tests for all core modules + backend + CLI commands |
| `test_full_e2e.py` | Simulated end-to-end generation workflows |

## What Is Tested

- **Workflow:** load, save, list, validate (valid + invalid cases)
- **Queue:** submit prompt, check status, clear, history, interrupt
- **Models:** checkpoints, LoRAs, VAEs, ControlNets, node info, all node classes
- **Images:** list outputs, download single image, download all for prompt
- **Backend:** GET/POST/DELETE/raw byte wrappers, connection errors, timeouts
- **CLI:** all command groups in both human and `--json` output modes
- **Errors:** connection refused, server rejects workflow, file not found, overwrite protection

## Mock Patterns

All tests use `unittest.mock.patch` to intercept HTTP calls at the backend layer:

```python
from unittest.mock import patch

with patch("cli_anything.comfyui.core.queue.api_post", return_value={"prompt_id": "abc"}):
    result = queue_mod.queue_prompt("http://localhost:8188", workflow)
```

For CLI tests, use Click's `CliRunner`:

```python
from click.testing import CliRunner
from cli_anything.comfyui.comfyui_cli import cli

runner = CliRunner()
result = runner.invoke(cli, ["--json", "queue", "status"])
assert result.exit_code == 0
```
