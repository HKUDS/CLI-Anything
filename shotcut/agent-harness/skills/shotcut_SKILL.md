---
name: >-
  cli-anything-shotcut
description: >-
  Command-line interface for Shotcut - A stateful command-line interface for video editing, built on the MLT XML format. Designed for AI ag...
---

# cli-anything-shotcut

A stateful command-line interface for video editing, built on the MLT XML format. Designed for AI agents and power users who need to create and edit Shotcut projects without a GUI.

## Installation

This CLI is installed as part of the cli-anything-shotcut package:

```bash
pip install cli-anything-shotcut
```

**Prerequisites:**
- Python 3.10+
- shotcut must be installed on your system


## Usage

### Basic Commands

```bash
# Show help
cli-anything-shotcut --help

# Start interactive REPL mode
cli-anything-shotcut

# Create a new project
cli-anything-shotcut project new -o project.json

# Run with JSON output (for agent consumption)
cli-anything-shotcut --json project info -p project.json
```

### REPL Mode

When invoked without a subcommand, the CLI enters an interactive REPL session:

```bash
cli-anything-shotcut
# Enter commands interactively with tab-completion and history
```


## Command Groups


### Project

Project management: new, open, save, info.

| Command | Description |
|---------|-------------|



### Timeline

Timeline operations: tracks, clips, trimming.

| Command | Description |
|---------|-------------|



### Filter Group

Filter operations: add, remove, configure effects.

| Command | Description |
|---------|-------------|



### Media

Media operations: probe, list, check files.

| Command | Description |
|---------|-------------|



### Export

Export/render operations.

| Command | Description |
|---------|-------------|



### Transition Group

Transition operations: dissolve, wipe, and other transitions.

| Command | Description |
|---------|-------------|



### Composite Group

Compositing: blend modes, PIP, opacity.

| Command | Description |
|---------|-------------|



### Session

Session management: status, undo, redo.

| Command | Description |
|---------|-------------|




## Examples


### Create a New Project

Create a new shotcut project file.

```bash
cli-anything-shotcut project new -o myproject.json
# Or with JSON output for programmatic use
cli-anything-shotcut --json project new -o myproject.json
```


### Interactive REPL Session

Start an interactive session with undo/redo support.

```bash
cli-anything-shotcut
# Enter commands interactively
# Use 'help' to see available commands
# Use 'undo' and 'redo' for history navigation
```


### Export Project

Export the project to a final output format.

```bash
cli-anything-shotcut --project myproject.json export render output.pdf --overwrite
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
cli-anything-shotcut project info -p project.json

# JSON output for agents
cli-anything-shotcut --json project info -p project.json
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