# Test Plan — cli-anything-cloudanalyzer

## Unit Tests (test_core.py) — No CloudAnalyzer required

- Project creation, loading, saving
- Session undo/redo
- Operation history recording
- Backend availability check

## E2E Tests (test_full_e2e.py) — Requires CloudAnalyzer + Open3D

- `evaluate run` with real PCD files
- `trajectory evaluate` with CSV trajectories
- `check init` + `check run` cycle
- `baseline save` + `baseline list` + `baseline decision` cycle
- `process downsample` with real PCD
- `info show` and `info version`
- `--json` flag produces valid JSON for all commands
- REPL startup and quit
