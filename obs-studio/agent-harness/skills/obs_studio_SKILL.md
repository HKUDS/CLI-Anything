---
name: >-
  cli-anything-obs_studio
description: >-
  Command-line interface for Obs Studio - A stateful command-line interface for OBS Studio scene collection editing, following the same patter...
---

# cli-anything-obs_studio

A stateful command-line interface for OBS Studio scene collection editing, following the same patterns as the Blender CLI harness. Uses a JSON scene collection format. No OBS installation required for editing.

## Installation

This CLI is installed as part of the cli-anything-obs_studio package:

```bash
pip install cli-anything-obs_studio
```

**Prerequisites:**
- Python 3.10+
- obs_studio must be installed on your system


## Usage

### Basic Commands

```bash
# Show help
cli-anything-obs_studio --help

# Start interactive REPL mode
cli-anything-obs_studio

# Create a new project
cli-anything-obs_studio project new -o project.json

# Run with JSON output (for agent consumption)
cli-anything-obs_studio --json project info -p project.json
```

### REPL Mode

When invoked without a subcommand, the CLI enters an interactive REPL session:

```bash
cli-anything-obs_studio
# Enter commands interactively with tab-completion and history
```


## Command Groups


### Project

Project management commands.

| Command | Description |
|---------|-------------|



### Scene Group

Scene management commands.

| Command | Description |
|---------|-------------|



### Source Group

Source management commands.

| Command | Description |
|---------|-------------|



### Filter Group

Filter management commands.

| Command | Description |
|---------|-------------|



### Audio Group

Audio management commands.

| Command | Description |
|---------|-------------|



### Transition Group

Transition management commands.

| Command | Description |
|---------|-------------|



### Output Group

Output/streaming/recording configuration.

| Command | Description |
|---------|-------------|



### Session

Session management commands.

| Command | Description |
|---------|-------------|




## Examples


### Create a New Project

Create a new obs_studio project file.

```bash
cli-anything-obs_studio project new -o myproject.json
# Or with JSON output for programmatic use
cli-anything-obs_studio --json project new -o myproject.json
```


### Interactive REPL Session

Start an interactive session with undo/redo support.

```bash
cli-anything-obs_studio
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
cli-anything-obs_studio project info -p project.json

# JSON output for agents
cli-anything-obs_studio --json project info -p project.json
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