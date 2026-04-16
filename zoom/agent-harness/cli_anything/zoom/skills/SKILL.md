---
name: >-
  cli-anything-zoom
description: >-
  Command-line interface for Zoom - CLI harness for **Zoom** — manage meetings, participants, and recordings from the command line via t...
---

# cli-anything-zoom

CLI harness for **Zoom** — manage meetings, participants, and recordings from the command line via the Zoom REST API.

## Installation

This CLI is installed as part of the cli-anything-zoom package:

```bash
pip install cli-anything-zoom
```

**Prerequisites:**
- Python 3.10+
- zoom must be installed on your system


## Usage

### Basic Commands

```bash
# Show help
cli-anything-zoom --help

# Start interactive REPL mode
cli-anything-zoom

# Create a new project
cli-anything-zoom project new -o project.json

# Run with JSON output (for agent consumption)
cli-anything-zoom --json project info -p project.json
```

### REPL Mode

When invoked without a subcommand, the CLI enters an interactive REPL session:

```bash
cli-anything-zoom
# Enter commands interactively with tab-completion and history
```


## Command Groups


### Auth

Authentication and OAuth2 setup.

| Command | Description |
|---------|-------------|
| `setup` | Configure OAuth app credentials |
| `login` | Login via OAuth2 browser flow |
| `status` | Check authentication status |
| `logout` | Remove saved tokens |


### Meeting

Meeting management commands.

| Command | Description |
|---------|-------------|
| `create` | Create a new Zoom meeting |
| `list` | List meetings |
| `info` | Get meeting details |
| `update` | Update a meeting |
| `delete` | Delete a meeting |
| `join` | Open meeting join URL in browser |
| `start` | Open meeting start URL in browser (host only) |


### Participant

Participant management commands.

| Command | Description |
|---------|-------------|
| `add` | Register a participant for a meeting |
| `add-batch` | Batch register participants from a CSV file |
| `list` | List registered participants |
| `remove` | Cancel a participant's registration |
| `attended` | List participants who attended a past meeting |


### Recording

Cloud recording management.

| Command | Description |
|---------|-------------|
| `list` | List cloud recordings |
| `files` | List recording files for a specific meeting |
| `download` | Download a recording file |
| `delete` | Delete all recordings for a meeting |




## Examples


### Create a New Project

Create a new zoom project file.

```bash
cli-anything-zoom project new -o myproject.json
# Or with JSON output for programmatic use
cli-anything-zoom --json project new -o myproject.json
```


### Interactive REPL Session

Start an interactive session with undo/redo support.

```bash
cli-anything-zoom
# Enter commands interactively
# Use 'help' to see available commands
# Use 'undo' and 'redo' for history navigation
```


## State Management

The CLI maintains session state with:

- **Undo/Redo**: Up to 50 levels of history
- **Project persistence**: Save/load project state as JSON
- **Session tracking**: Track modifications and changes

## Output Formats

All commands support dual output modes:

- **Human-readable** (default): Tables, colors, formatted text
- **Machine-readable** (`--json` flag): Structured JSON for agent consumption

```bash
# Human output
cli-anything-zoom project info -p project.json

# JSON output for agents
cli-anything-zoom --json project info -p project.json
```

## For AI Agents

When using this CLI programmatically:

1. **Always use `--json` flag** for parseable output
2. **Check return codes** - 0 for success, non-zero for errors
3. **Parse stderr** for error messages on failure
4. **Use absolute paths** for all file operations
5. **Verify outputs exist** after export operations

## More Information

- Full documentation: See README.md in the package
- Test coverage: See TEST.md in the package
- Methodology: See HARNESS.md in the cli-anything-plugin

## Version

1.0.0