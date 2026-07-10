# MiniMax Harness Test Plan and Results

## Test Inventory

- `test_core.py`: 16 unit tests for API key resolution, config persistence, model/voice registries, mocked chat, streaming, TTS parsing, and full workflow helpers.
- `test_full_e2e.py`: 9 E2E tests covering installed-command smoke behavior, no-backend commands, missing/invalid API key failures, API-mocked CLI chat/TTS, and backend chat/stream/TTS paths.

## Unit Coverage

- `utils/minimax_backend.py`
  - API key priority: CLI argument, `MINIMAX_API_KEY`, config file, missing key.
  - Config read/write behavior with isolated config paths.
  - Chat request body, default temperature, MiniMax endpoint, and HTTP error wrapping.
  - Streaming SSE parsing and callback delivery.
  - TTS SSE parsing, hex audio decoding, endpoint selection, and API-level error handling.
  - `run_full_workflow` chat response and token metadata extraction.

## E2E and CLI Coverage

- Installed command resolution uses `_resolve_cli("cli-anything-minimax")`.
- `CLI_ANYTHING_FORCE_INSTALLED=1` requires the installed console script and fails if it is not on `PATH`.
- No-backend smoke tests verify `--help`, `session status`, `models`, and `voices` without `MINIMAX_API_KEY`.
- Missing-key CLI tests verify `chat` fails before making any network call and returns machine-readable JSON errors.
- Invalid-key CLI tests route through a local HTTP fake, return 401, and verify the CLI reports a MiniMax API error.
- API-mocked workflow tests run real CLI subprocesses against a local MiniMax-compatible fake server:
  - `chat` returns JSON content and usage.
  - `tts` writes MP3-like bytes to disk and reports output metadata.

## Real Backend Validation Steps

Run these from the repository root when a real MiniMax API key is available:

```bash
cd minimax/agent-harness
python3 -m pip install -e .
export MINIMAX_API_KEY="sk-your-real-key"
cli-anything-minimax --json test
cli-anything-minimax --json chat --prompt "Say ok only" --max-tokens 10
cli-anything-minimax stream --prompt "Say ok only" --max-tokens 10
cli-anything-minimax --json tts --text "MiniMax validation" --output /tmp/minimax-validation.mp3
test -s /tmp/minimax-validation.mp3
python3 -m pytest cli_anything/minimax/tests/test_full_e2e.py -v -s
```

Expected real-backend results:

- `test` returns JSON with `"status": "ok"`.
- `chat` returns non-empty assistant content.
- `stream` prints at least one streamed chunk.
- `tts` writes a non-empty `/tmp/minimax-validation.mp3`.
- `test_full_e2e.py` uses the real API for backend tests when `MINIMAX_API_KEY` is set.

## Local Validation Results

Environment note: `MINIMAX_API_KEY` was unset for this validation run, so real API calls used the mocked/no-backend test paths.

```text
$ python3 -m py_compile cli_anything/minimax/minimax_cli.py cli_anything/minimax/core/session.py cli_anything/minimax/utils/minimax_backend.py cli_anything/minimax/tests/test_core.py cli_anything/minimax/tests/test_full_e2e.py
# passed with exit code 0
```

```text
$ python3 -m pytest cli_anything/minimax/tests/test_core.py cli_anything/minimax/tests/test_full_e2e.py -v
25 passed in 2.82s
```

```text
$ CLI_ANYTHING_FORCE_INSTALLED=1 python3 -m pytest cli_anything/minimax/tests/test_full_e2e.py::TestCLISubprocessSmoke -v -s
[_resolve_cli] Using installed command: /root/miniconda3/bin/cli-anything-minimax
5 passed in 3.90s
```

## Coverage Gaps

- Real MiniMax backend validation still requires a live `MINIMAX_API_KEY`.
- The mocked TTS output verifies the CLI write path and MP3-like bytes, not perceptual audio quality.
