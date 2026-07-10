# PR 189 MiniMax Harness Fix Notes

## Changes

- Added CLI subprocess smoke coverage in `test_full_e2e.py`.
- Added no-backend smoke tests for `--help`, `session status`, `models`, and `voices`.
- Added CLI-level missing `MINIMAX_API_KEY` validation.
- Added CLI-level invalid `MINIMAX_API_KEY` validation through a local HTTP fake.
- Added a local MiniMax-compatible fake server for API-mocked chat and TTS subprocess workflows.
- Fixed the `tts` command by renaming the Click callback parameter from `output` to `output_path`; the previous name shadowed the module-level `output()` helper and crashed the CLI TTS path.

## Commands Run

```bash
cd minimax/agent-harness
python3 -m py_compile \
  cli_anything/minimax/minimax_cli.py \
  cli_anything/minimax/core/session.py \
  cli_anything/minimax/utils/minimax_backend.py \
  cli_anything/minimax/tests/test_core.py \
  cli_anything/minimax/tests/test_full_e2e.py
python3 -m pytest cli_anything/minimax/tests/test_core.py cli_anything/minimax/tests/test_full_e2e.py -v
python3 -m pip install -e .
CLI_ANYTHING_FORCE_INSTALLED=1 python3 -m pytest \
  cli_anything/minimax/tests/test_full_e2e.py::TestCLISubprocessSmoke -v -s
```

## Results

- `py_compile`: passed.
- Full MiniMax unit/E2E suite: `25 passed in 2.82s`.
- Force-installed CLI smoke suite: `5 passed in 3.90s`, using `/root/miniconda3/bin/cli-anything-minimax`.

## Real Backend Validation

`MINIMAX_API_KEY` was unset in this environment, so real API validation was not executed. To validate against MiniMax:

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
