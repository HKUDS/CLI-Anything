---
name: >-
  cli-anything-blender
description: >-
  Command-line interface for Blender - A stateful command-line interface for 3D scene editing, following the same patterns as the GIMP CLI ...
---

# cli-anything-blender

A stateful command-line interface for 3D scene editing, following the same patterns as the GIMP CLI harness. Uses a JSON scene description format with bpy script generation for actual Blender rendering.

## Installation

This CLI is installed as part of the cli-anything-blender package:

```bash
pip install cli-anything-blender
```

**Prerequisites:**
- Python 3.10+
- blender must be installed on your system


## Usage

### Basic Commands

```bash
# Show help
cli-anything-blender --help

# Start interactive REPL mode
cli-anything-blender

# Create a new project
cli-anything-blender project new -o project.json

# Run with JSON output (for agent consumption)
cli-anything-blender --json project info -p project.json
```

### REPL Mode

When invoked without a subcommand, the CLI enters an interactive REPL session:

```bash
cli-anything-blender
# Enter commands interactively with tab-completion and history
```


## Command Groups


### Scene

Scene management commands.

| Command | Description |
|---------|-------------|



### Object Group

3D object management commands.

| Command | Description |
|---------|-------------|



### Material

Material management commands.

| Command | Description |
|---------|-------------|



### Modifier Group

Modifier management commands.

| Command | Description |
|---------|-------------|



### Camera

Camera management commands.

| Command | Description |
|---------|-------------|



### Light

Light management commands.

| Command | Description |
|---------|-------------|



### Animation

Animation and keyframe commands.

| Command | Description |
|---------|-------------|



### Render Group

Render settings and output commands.

| Command | Description |
|---------|-------------|



### Session

Session management commands.

| Command | Description |
|---------|-------------|




## Examples


### Create a New Project

Create a new blender project file.

```bash
cli-anything-blender project new -o myproject.json
# Or with JSON output for programmatic use
cli-anything-blender --json project new -o myproject.json
```


### Interactive REPL Session

Start an interactive session with undo/redo support.

```bash
cli-anything-blender
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
cli-anything-blender project info -p project.json

# JSON output for agents
cli-anything-blender --json project info -p project.json
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