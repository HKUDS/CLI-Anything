---
name: >-
  cli-anything-drawio
description: >-
  Command-line interface for Drawio - A CLI harness for **Draw.io** — create, edit, and export diagrams from the command line....
---

# cli-anything-drawio

A CLI harness for **Draw.io** — create, edit, and export diagrams from the command line.

## Installation

This CLI is installed as part of the cli-anything-drawio package:

```bash
pip install cli-anything-drawio
```

**Prerequisites:**
- Python 3.10+
- drawio must be installed on your system


## Usage

### Basic Commands

```bash
# Show help
cli-anything-drawio --help

# Start interactive REPL mode
cli-anything-drawio

# Create a new project
cli-anything-drawio project new -o project.json

# Run with JSON output (for agent consumption)
cli-anything-drawio --json project info -p project.json
```

### REPL Mode

When invoked without a subcommand, the CLI enters an interactive REPL session:

```bash
cli-anything-drawio
# Enter commands interactively with tab-completion and history
```


## Command Groups


### Project

Project management: new, open, save, info.

| Command | Description |
|---------|-------------|



### Shape

Shape operations: add, remove, move, resize, style.

| Command | Description |
|---------|-------------|



### Connect

Connector operations: add, remove, style.

| Command | Description |
|---------|-------------|



### Page

Page operations: add, remove, rename, list.

| Command | Description |
|---------|-------------|



### Export

Export operations: render to PNG, PDF, SVG.

| Command | Description |
|---------|-------------|



### Session

Session management: status, undo, redo.

| Command | Description |
|---------|-------------|




## Examples


### Create a New Project

Create a new drawio project file.

```bash
cli-anything-drawio project new -o myproject.json
# Or with JSON output for programmatic use
cli-anything-drawio --json project new -o myproject.json
```


### Interactive REPL Session

Start an interactive session with undo/redo support.

```bash
cli-anything-drawio
# Enter commands interactively
# Use 'help' to see available commands
# Use 'undo' and 'redo' for history navigation
```


### Export Project

Export the project to a final output format.

```bash
cli-anything-drawio --project myproject.json export render output.pdf --overwrite
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
cli-anything-drawio project info -p project.json

# JSON output for agents
cli-anything-drawio --json project info -p project.json
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