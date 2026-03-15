---
name: >-
  cli-anything-audacity
description: >-
  Command-line interface for Audacity - A stateful command-line interface for audio editing, following the same patterns as the GIMP and Ble...
---

# cli-anything-audacity

A stateful command-line interface for audio editing, following the same patterns as the GIMP and Blender CLIs in this repo.

## Installation

This CLI is installed as part of the cli-anything-audacity package:

```bash
pip install cli-anything-audacity
```

**Prerequisites:**
- Python 3.10+
- audacity must be installed on your system


## Usage

### Basic Commands

```bash
# Show help
cli-anything-audacity --help

# Start interactive REPL mode
cli-anything-audacity

# Create a new project
cli-anything-audacity project new -o project.json

# Run with JSON output (for agent consumption)
cli-anything-audacity --json project info -p project.json
```

### REPL Mode

When invoked without a subcommand, the CLI enters an interactive REPL session:

```bash
cli-anything-audacity
# Enter commands interactively with tab-completion and history
```


## Command Groups


### Project

Project management commands.

| Command | Description |
|---------|-------------|



### Track

Track management commands.

| Command | Description |
|---------|-------------|



### Clip

Clip management commands.

| Command | Description |
|---------|-------------|



### Effect Group

Effect management commands.

| Command | Description |
|---------|-------------|



### Selection

Selection management commands.

| Command | Description |
|---------|-------------|



### Label

Label/marker management commands.

| Command | Description |
|---------|-------------|



### Media

Media file operations.

| Command | Description |
|---------|-------------|



### Export Group

Export/render commands.

| Command | Description |
|---------|-------------|



### Session Group

Session management commands.

| Command | Description |
|---------|-------------|




## Examples


### Create a New Project

Create a new audacity project file.

```bash
cli-anything-audacity project new -o myproject.json
# Or with JSON output for programmatic use
cli-anything-audacity --json project new -o myproject.json
```


### Interactive REPL Session

Start an interactive session with undo/redo support.

```bash
cli-anything-audacity
# Enter commands interactively
# Use 'help' to see available commands
# Use 'undo' and 'redo' for history navigation
```


### Export Project

Export the project to a final output format.

```bash
cli-anything-audacity --project myproject.json export render output.pdf --overwrite
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
cli-anything-audacity project info -p project.json

# JSON output for agents
cli-anything-audacity --json project info -p project.json
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