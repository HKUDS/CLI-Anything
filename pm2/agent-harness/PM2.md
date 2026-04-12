# Agent Harness SOP: PM2 Process Management

## Purpose

This harness provides a CLI-Anything interface for PM2 process management.
It wraps the PM2 CLI via subprocess calls and exposes process lifecycle, logs,
and system commands through a unified Click CLI with interactive REPL mode.

## Backend

- **Engine**: PM2 (Node.js process manager) via subprocess
- **Binary**: `pm2` resolved via `shutil.which()` with fallback paths
- **Protocol**: Subprocess execution with stdout/stderr capture
- **Data format**: PM2 outputs JSON via `pm2 jlist`; other commands return plain text

## Architecture

```
cli-anything-pm2 (Click CLI)
    |
    +-- pm2_cli.py          # Click groups + REPL dispatcher
    |
    +-- core/
    |   +-- processes.py     # list, describe, metrics
    |   +-- lifecycle.py     # start, stop, restart, delete
    |   +-- logs.py          # view, flush
    |   +-- system.py        # save, startup, version
    |
    +-- utils/
    |   +-- pm2_backend.py   # subprocess wrapper (_run_pm2, pm2_jlist, etc.)
    |   +-- repl_skin.py     # cli-anything branded REPL UI
    |
    +-- tests/
    |   +-- test_core.py     # Unit tests (mocked subprocess)
    |   +-- test_full_e2e.py # E2E tests (real pm2 binary)
    |   +-- TEST.md          # Test plan and results
    |
    +-- skills/
        +-- SKILL.md         # Agent skill definitions
```

## Command Groups

| Group       | Commands                     | Backend Calls                     |
|-------------|------------------------------|-----------------------------------|
| `process`   | list, describe, metrics      | `pm2 jlist` (JSON parse)          |
| `lifecycle` | start, stop, restart, delete | `pm2 start/stop/restart/delete`   |
| `logs`      | view, flush                  | `pm2 logs --nostream`, `pm2 flush`|
| `system`    | save, startup, version       | `pm2 save/startup/--version`      |

## State Model

**Stateless.** Every command queries PM2 fresh via subprocess. There is no
in-memory session state, no project files, and no undo/redo. The PM2 daemon
itself maintains process state; this harness is a read/write proxy.

## Output Modes

All commands support two output modes controlled by the `--json` flag:

- **Human mode** (default): Formatted tables, status messages with color
- **JSON mode** (`--json`): Machine-readable JSON for agent consumption

## Interaction Modes

1. **Subcommand CLI**: `cli-anything-pm2 [--json] <group> <command> [args]`
2. **Interactive REPL**: `cli-anything-pm2` (no subcommand) launches the REPL

## Key Design Decisions

- PM2 binary path is cached after first lookup (`_PM2_BIN` module-level)
- `pm2 jlist` is used instead of `pm2 describe` for JSON reliability
- Subprocess environment includes `/opt/homebrew/bin` for macOS compatibility
- Timeout defaults to 30 seconds per subprocess call
- JSON parsing has fallback extraction for non-JSON preamble in stdout

## Error Handling

| Scenario              | Behavior                                    |
|-----------------------|---------------------------------------------|
| pm2 not installed     | `RuntimeError` with install instructions     |
| pm2 binary vanishes   | `FileNotFoundError` caught, error dict returned |
| Command timeout       | `TimeoutExpired` caught, error dict returned |
| Invalid JSON output   | Fallback regex extraction, then `data: None` |
| Process not found     | Returns `None` or exit code 1                |

## Testing

- **Unit tests**: `test_core.py` -- all subprocess calls mocked, no pm2 required
- **E2E tests**: `test_full_e2e.py` -- calls real pm2 binary, requires pm2 installed

```bash
# Run all tests
python -m pytest cli_anything/pm2/tests/ -v

# Run only unit tests (no pm2 needed)
python -m pytest cli_anything/pm2/tests/test_core.py -v

# Run only E2E tests (pm2 must be installed and running)
python -m pytest cli_anything/pm2/tests/test_full_e2e.py -v
```
