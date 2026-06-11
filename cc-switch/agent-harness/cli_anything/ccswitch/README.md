# CC Switch CLI - Agent Harness

A CLI interface for CC Switch, a desktop app that manages AI coding
tool configurations across Claude Code, Codex, Gemini CLI, OpenCode, OpenClaw,
and Hermes. Reads directly from the live CC Switch SQLite database.

## Installation

```bash
pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=cc-switch/agent-harness
```

Or for local development:

```bash
cd cc-switch/agent-harness
pip install -e .
```

Requires CC Switch installed with an active database at `~/.cc-switch/cc-switch.db`.

## Quick Start

```bash
# Status overview
cli-anything-ccswitch
cli-anything-ccswitch status

# List all providers
cli-anything-ccswitch providers list

# Filter by app
cli-anything-ccswitch providers list --app claude

# Switch active provider
cli-anything-ccswitch providers set-current <provider-id> --app claude

# Check proxy status
cli-anything-ccswitch proxy status --app claude

# View usage stats (7 days)
cli-anything-ccswitch usage stats --days 7

# Recent request logs
cli-anything-ccswitch usage logs --limit 10

# List skills
cli-anything-ccswitch skills list

# List MCP servers
cli-anything-ccswitch mcp list

# Manage settings
cli-anything-ccswitch settings list
cli-anything-ccswitch settings get <key>

# Session logs
cli-anything-ccswitch sessions list --app claude
```

## JSON Output Mode

All commands support `--json` for machine-readable output. Place it before the subcommand:

```bash
cli-anything-ccswitch --json providers list
cli-anything-ccswitch --json usage stats --days 30
cli-anything-ccswitch --json providers get <id> --app claude
```

## Command Groups

| Group | Description |
|-------|-------------|
| `status` | Show a quick database overview |
| `providers` | Manage AI provider configurations (list, get, set-current) |
| `proxy` | Manage the local HTTP proxy server (status, config) |
| `mcp` | Manage MCP servers (list, enable) |
| `skills` | Manage installed skills (list, repos) |
| `usage` | View API usage and cost statistics (stats, logs) |
| `settings` | View and manage settings (list, get, set) |
| `sessions` | Browse AI conversation sessions (list) |

## Running Tests

```bash
# All tests
python3 -m pytest cli_anything/ccswitch/tests/ -v

# Unit tests (no CC Switch needed)
python3 -m pytest cli_anything/ccswitch/tests/test_core.py -v

# E2E tests (requires live CC Switch database)
python3 -m pytest cli_anything/ccswitch/tests/test_full_e2e.py -v
```

## Architecture

```
cli_anything/ccswitch/
├── __init__.py
├── __main__.py              # python3 -m cli_anything.ccswitch
├── ccswitch_cli.py          # Main Click CLI (7 command groups)
├── utils/
│   ├── __init__.py
│   └── db.py                # SQLite database utilities
├── skills/
│   └── SKILL.md             # Packaged AI skill definition
└── tests/
    ├── TEST.md              # Test plan and results
    ├── test_core.py         # 30 unit tests
    └── test_full_e2e.py     # 20 E2E tests
```

## Database

Reads directly from `~/.cc-switch/cc-switch.db`. Read operations are safe;
write operations (`providers set-current`, `proxy config`, `mcp enable`,
`settings set`) modify the database and write live config to app settings files.
