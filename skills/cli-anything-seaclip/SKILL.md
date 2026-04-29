---
name: "cli-anything-seaclip"
description: >-
  Command-line interface for SeaClip-Lite - A stateless CLI for managing issues, pipelines, agents, schedules, and activity on the SeaClip-Lite project management board.
---

# cli-anything-seaclip

A stateless command-line interface for SeaClip-Lite project management.
Communicates via HTTP API and direct SQLite reads. No local state or session.

## Installation

```bash
pip install -e .
```

**Prerequisites:**
- Python 3.10+
- SeaClip-Lite backend running at localhost:5200

## Usage

### Basic Commands

```bash
# Show help
cli-anything-seaclip --help

# Start interactive REPL mode
cli-anything-seaclip

# Run with JSON output (for agent consumption)
cli-anything-seaclip --json server health
cli-anything-seaclip --json issue list
cli-anything-seaclip --json agent list
```

### REPL Mode

When invoked without a subcommand, the CLI enters an interactive REPL session:

```bash
cli-anything-seaclip
# Enter commands interactively with tab-completion and history
```

## Command Groups

### Issue

Issue management commands.

| Command | Description |
|---------|-------------|
| `list` | List issues (--status, --priority, --search, --limit) |
| `create` | Create a new issue (--title, --description, --priority) |
| `move` | Move issue to column (ISSUE_ID --column COL) |
| `status` | Update issue status (ISSUE_ID --set STATUS) |
| `delete` | Delete an issue (ISSUE_ID) |

### Agent

Pipeline agent commands.

| Command | Description |
|---------|-------------|
| `list` | List all pipeline agents |

### Pipeline

Pipeline control commands.

| Command | Description |
|---------|-------------|
| `start` | Start pipeline (--issue UUID --mode auto/manual) |
| `status` | Get pipeline status (--issue UUID) |
| `resume` | Resume paused pipeline (--issue UUID) |
| `stop` | Stop running pipeline (--issue UUID) |

### Scheduler

Schedule configuration commands.

| Command | Description |
|---------|-------------|
| `list` | List all schedule configs |
| `add` | Add schedule (--name, --cron, --repo) |
| `sync` | Trigger sync (SCHEDULE_ID) |

### Activity

Activity feed commands.

| Command | Description |
|---------|-------------|
| `list` | Recent activity (--limit N) |

### Server

Server utility commands.

| Command | Description |
|---------|-------------|
| `health` | Check backend health |

## Output Formats

All commands support dual output modes:

- **Human-readable** (default): Tables, colors, formatted text
- **Machine-readable** (`--json` flag): Structured JSON for agent consumption

```bash
# Human output
cli-anything-seaclip issue list

# JSON output for agents
cli-anything-seaclip --json issue list
```

## For AI Agents

When using this CLI programmatically:

1. **Always use `--json` flag** for parseable output
2. **Check return codes** - 0 for success, non-zero for errors
3. **Parse stderr** for error messages on failure
4. **Error responses** include `{"error": "message"}` in JSON mode

## Version

1.0.0
