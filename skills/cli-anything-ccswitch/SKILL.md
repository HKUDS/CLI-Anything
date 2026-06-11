---
name: "cli-anything-ccswitch"
description: "CLI interface for CC Switch — manage AI coding tool configurations from the terminal"
---

# CC Switch CLI

CLI harness for CC Switch, a desktop app that manages AI coding tool (Claude Code,
Codex, Gemini CLI, OpenCode, OpenClaw, Hermes) configurations. Built with Click
and the CLI-Anything methodology.

## Prerequisites

- Python 3.10+
- CC Switch installed with an active database at `~/.cc-switch/cc-switch.db`

## Installation

```bash
pip install -e .
```

After installation, the command `cli-anything-ccswitch` is available.

## Command Groups

| Group | Description |
|-------|-------------|
| `status` | Show a quick database overview |
| `providers` | Manage AI provider configurations (list, get, set-current) |
| `proxy` | Manage the local HTTP proxy server (status, config) |
| `mcp` | Manage MCP (Model Context Protocol) servers (list, enable) |
| `skills` | Manage installed skills (list, repos) |
| `usage` | View API usage and cost statistics (stats, logs) |
| `settings` | View and manage CC Switch settings (list, get, set) |
| `sessions` | Browse and search AI conversation sessions (list) |

## Global Options

- `--json` — Output in machine-readable JSON format (recommended for agent use)
- `--db PATH` — Override the database path

## Agent-Specific Guidance

### JSON Output

Always use `--json` for programmatic consumption. Place it **before** the
subcommand:

```bash
cli-anything-ccswitch --json providers list
cli-anything-ccswitch --json usage stats --days 30
cli-anything-ccswitch --json providers get <id> --app claude
```

### Sensitive Values

API tokens, keys, and secrets are masked in all output. The `settings_config`
field in provider details shows masked values (e.g., `sk-bc089...5cbb`).

### Exit Codes

- `0` — Success
- `1` — Error (e.g., resource not found, invalid app type)

### App Types

Valid app types: `claude`, `codex`, `gemini`, `opencode`, `openclaw`, `hermes`.

## Examples

### List all providers

```bash
cli-anything-ccswitch providers list
cli-anything-ccswitch --json providers list --app claude
```

### Switch active provider

```bash
cli-anything-ccswitch providers set-current <provider-id> --app claude
```

### Check proxy status

```bash
cli-anything-ccswitch proxy status --app claude
cli-anything-ccswitch proxy config --app claude --set-port 8080
```

### View usage stats

```bash
cli-anything-ccswitch usage stats --days 7
cli-anything-ccswitch --json usage stats --days 30 --app claude
cli-anything-ccswitch usage logs --limit 10
```

### List skills

```bash
cli-anything-ccswitch skills list
cli-anything-ccswitch skills repos
```

### MCP servers

```bash
cli-anything-ccswitch mcp list
cli-anything-ccswitch mcp enable <server-id> --app claude --on
```

### Settings

```bash
cli-anything-ccswitch settings list
cli-anything-ccswitch settings get <key>
cli-anything-ccswitch settings set <key> <value>
```

### Sessions

```bash
cli-anything-ccswitch sessions list --app claude --limit 10
```

### Status overview

```bash
cli-anything-ccswitch status
cli-anything-ccswitch
cli-anything-ccswitch --json
```

## Error Handling

When a resource is not found, the CLI prints an error message to stderr and
exits with code 1. Agents should check the exit code before parsing output.

## Database

The CLI reads from the live CC Switch SQLite database. All read operations
are safe and do not modify the database. Write operations (`providers
set-current`, `proxy config`, `mcp enable`, `settings set`) modify the
database directly.
