---
name: >-
  cli-anything-kdenlive
description: >-
  Command-line interface for Kdenlive - A stateful command-line interface for video editing, following the same patterns as the Blender CLI ...
---

# cli-anything-kdenlive

A stateful command-line interface for video editing, following the same patterns as the Blender CLI harness. Uses a JSON project format with MLT XML generation for Kdenlive/melt.

## Installation

This CLI is installed as part of the cli-anything-kdenlive package:

```bash
pip install cli-anything-kdenlive
```

**Prerequisites:**
- Python 3.10+
- kdenlive must be installed on your system


## Usage

### Basic Commands

```bash
# Show help
cli-anything-kdenlive --help

# Start interactive REPL mode
cli-anything-kdenlive

# Create a new project
cli-anything-kdenlive project new -o project.json

# Run with JSON output (for agent consumption)
cli-anything-kdenlive --json project info -p project.json
```

### REPL Mode

When invoked without a subcommand, the CLI enters an interactive REPL session:

```bash
cli-anything-kdenlive
# Enter commands interactively with tab-completion and history
```


## Command Groups


### Project

Project management commands.

| Command | Description |
|---------|-------------|



### Bin Group

Media bin management commands.

| Command | Description |
|---------|-------------|



### Timeline

Timeline management commands.

| Command | Description |
|---------|-------------|



### Filter Group

Filter/effect management commands.

| Command | Description |
|---------|-------------|



### Transition

Transition management commands.

| Command | Description |
|---------|-------------|



### Guide

Guide/marker management commands.

| Command | Description |
|---------|-------------|



### Export

Export and render commands.

| Command | Description |
|---------|-------------|



### Session

Session management commands.

| Command | Description |
|---------|-------------|




## Examples


### Create a New Project

Create a new kdenlive project file.

```bash
cli-anything-kdenlive project new -o myproject.json
# Or with JSON output for programmatic use
cli-anything-kdenlive --json project new -o myproject.json
```


### Interactive REPL Session

Start an interactive session with undo/redo support.

```bash
cli-anything-kdenlive
# Enter commands interactively
# Use 'help' to see available commands
# Use 'undo' and 'redo' for history navigation
```


### Export Project

Export the project to a final output format.

```bash
cli-anything-kdenlive --project myproject.json export render output.pdf --overwrite
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
cli-anything-kdenlive project info -p project.json

# JSON output for agents
cli-anything-kdenlive --json project info -p project.json
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