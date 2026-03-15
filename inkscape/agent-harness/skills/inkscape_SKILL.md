---
name: >-
  cli-anything-inkscape
description: >-
  Command-line interface for Inkscape - A stateful command-line interface for vector graphics editing, following the same patterns as the GI...
---

# cli-anything-inkscape

A stateful command-line interface for vector graphics editing, following the same patterns as the GIMP and Blender CLI harnesses. Directly manipulates SVG (XML) documents with a JSON project format for state tracking.

## Installation

This CLI is installed as part of the cli-anything-inkscape package:

```bash
pip install cli-anything-inkscape
```

**Prerequisites:**
- Python 3.10+
- inkscape must be installed on your system


## Usage

### Basic Commands

```bash
# Show help
cli-anything-inkscape --help

# Start interactive REPL mode
cli-anything-inkscape

# Create a new project
cli-anything-inkscape project new -o project.json

# Run with JSON output (for agent consumption)
cli-anything-inkscape --json project info -p project.json
```

### REPL Mode

When invoked without a subcommand, the CLI enters an interactive REPL session:

```bash
cli-anything-inkscape
# Enter commands interactively with tab-completion and history
```


## Command Groups


### Document

Document management commands.

| Command | Description |
|---------|-------------|



### Shape

Shape management commands.

| Command | Description |
|---------|-------------|



### Text

Text management commands.

| Command | Description |
|---------|-------------|



### Style

Style management commands.

| Command | Description |
|---------|-------------|



### Transform

Transform operations (translate, rotate, scale, skew).

| Command | Description |
|---------|-------------|



### Layer

Layer management commands.

| Command | Description |
|---------|-------------|



### Path Group

Path boolean operations.

| Command | Description |
|---------|-------------|



### Gradient

Gradient management commands.

| Command | Description |
|---------|-------------|



### Export Group

Export/render commands.

| Command | Description |
|---------|-------------|



### Session

Session management commands.

| Command | Description |
|---------|-------------|




## Examples


### Create a New Project

Create a new inkscape project file.

```bash
cli-anything-inkscape project new -o myproject.json
# Or with JSON output for programmatic use
cli-anything-inkscape --json project new -o myproject.json
```


### Interactive REPL Session

Start an interactive session with undo/redo support.

```bash
cli-anything-inkscape
# Enter commands interactively
# Use 'help' to see available commands
# Use 'undo' and 'redo' for history navigation
```


### Export Project

Export the project to a final output format.

```bash
cli-anything-inkscape --project myproject.json export render output.pdf --overwrite
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
cli-anything-inkscape project info -p project.json

# JSON output for agents
cli-anything-inkscape --json project info -p project.json
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