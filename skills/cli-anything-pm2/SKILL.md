---
name: "cli-anything-pm2"
description: >-
  Command-line interface for PM2 - A stateless CLI for Node.js process management via the PM2 CLI. List, start, stop, restart processes, view logs, and manage system configuration.
---

# cli-anything-pm2

A stateless command-line interface for PM2 process management.
Communicates via the PM2 CLI subprocess. No local state or session.

## Installation

```bash
pip install -e .
```

**Prerequisites:**
- Python 3.10+
- PM2 installed globally (`npm install -g pm2`)

## Usage

### Basic Commands

```bash
# Show help
cli-anything-pm2 --help

# Start interactive REPL mode
cli-anything-pm2

# Run with JSON output (for agent consumption)
cli-anything-pm2 --json process list
cli-anything-pm2 --json system version
```

### REPL Mode

When invoked without a subcommand, the CLI enters an interactive REPL session:

```bash
cli-anything-pm2
# Enter commands interactively with tab-completion and history
```

## Command Groups

### process
Process inspection commands.

| Command | Description |
|---------|-------------|
| `list` | List all PM2 processes |
| `describe <name>` | Get detailed info for a process |
| `metrics` | Get metrics for all processes |

### lifecycle
Process lifecycle commands.

| Command | Description |
|---------|-------------|
| `start <script> --name <name>` | Start a new process |
| `stop <name>` | Stop a process |
| `restart <name>` | Restart a process |
| `delete <name>` | Delete a process |

### logs
Log management commands.

| Command | Description |
|---------|-------------|
| `view <name> --lines 50` | View recent logs |
| `flush [name]` | Flush logs |

### system
System-level commands.

| Command | Description |
|---------|-------------|
| `save` | Save current process list |
| `startup` | Generate startup script |
| `version` | Get PM2 version |

## Output Formats

All commands support dual output modes:

- **Human-readable** (default): Tables, colors, formatted text
- **Machine-readable** (`--json` flag): Structured JSON for agent consumption

```bash
# Human output
cli-anything-pm2 process list

# JSON output for agents
cli-anything-pm2 --json process list
```

## For AI Agents

When using this CLI programmatically:

1. **Always use `--json` flag** for parseable output
2. **Check return codes** - 0 for success, non-zero for errors
3. **Parse stderr** for error messages on failure

## Version

1.0.0
