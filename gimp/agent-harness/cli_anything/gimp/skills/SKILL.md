---
name: >-
  cli-anything-gimp
description: >-
  Command-line interface for Gimp - A stateful command-line interface for image editing, built on Pillow. Designed for AI agents and pow...
---

# cli-anything-gimp

A stateful command-line interface for image editing, built on Pillow. Designed for AI agents and power users who need to create and manipulate images without a GUI.

## Installation

This CLI is installed as part of the cli-anything-gimp package:

```bash
pip install cli-anything-gimp
```

**Prerequisites:**
- Python 3.10+
- gimp must be installed on your system


## Usage

### Basic Commands

```bash
# Show help
cli-anything-gimp --help

# Start interactive REPL mode
cli-anything-gimp

# Create a new project
cli-anything-gimp project new -o project.json

# Run with JSON output (for agent consumption)
cli-anything-gimp --json project info -p project.json
```

### REPL Mode

When invoked without a subcommand, the CLI enters an interactive REPL session:

```bash
cli-anything-gimp
# Enter commands interactively with tab-completion and history
```


## Command Groups


### Project

Project management commands.

| Command | Description |
|---------|-------------|
| `new` | Create a new project |
| `open` | Open an existing project |
| `save` | Save the current project |
| `info` | Show project information |
| `profiles` | List available canvas profiles |
| `json` | Print raw project JSON |


### Layer

Layer management commands.

| Command | Description |
|---------|-------------|
| `new` | Create a new blank layer |
| `add-from-file` | Add a layer from an image file |
| `list` | List all layers |
| `remove` | Remove a layer by index |
| `duplicate` | Duplicate a layer |
| `move` | Move a layer to a new position |
| `set` | Set a layer property (name, opacity, visible, mode, offset_x, offset_y) |
| `flatten` | Flatten all visible layers |
| `merge-down` | Merge a layer with the one below it |


### Canvas

Canvas operations.

| Command | Description |
|---------|-------------|
| `info` | Show canvas information |
| `resize` | Resize the canvas (without scaling content) |
| `scale` | Scale the canvas and all content proportionally |
| `crop` | Crop the canvas to a rectangle |
| `mode` | Set the canvas color mode |
| `dpi` | Set the canvas DPI |


### Filter Group

Filter management commands.

| Command | Description |
|---------|-------------|
| `list-available` | List all available filters |
| `info` | Show details about a filter |
| `add` | Add a filter to a layer |
| `remove` | Remove a filter by index |
| `set` | Set a filter parameter |
| `list` | List filters on a layer |


### Media

Media file operations.

| Command | Description |
|---------|-------------|
| `probe` | Analyze an image file |
| `list` | List media files referenced in the project |
| `check` | Check that all referenced media files exist |
| `histogram` | Show histogram analysis of an image |


### Export Group

Export/render commands.

| Command | Description |
|---------|-------------|
| `presets` | List export presets |
| `preset-info` | Show preset details |
| `render` | Render the project to an image file |


### Session

Session management commands.

| Command | Description |
|---------|-------------|
| `status` | Show session status |
| `undo` | Undo the last operation |
| `redo` | Redo the last undone operation |
| `history` | Show undo history |


### Draw

Drawing operations (applied at render time).

| Command | Description |
|---------|-------------|
| `text` | Draw text on a layer (by converting it to a text layer) |
| `rect` | Draw a rectangle (stored as drawing operation) |




## Examples


### Create a New Project

Create a new gimp project file.

```bash
cli-anything-gimp project new -o myproject.json
# Or with JSON output for programmatic use
cli-anything-gimp --json project new -o myproject.json
```


### Interactive REPL Session

Start an interactive session with undo/redo support.

```bash
cli-anything-gimp
# Enter commands interactively
# Use 'help' to see available commands
# Use 'undo' and 'redo' for history navigation
```


### Export Project

Export the project to a final output format.

```bash
cli-anything-gimp --project myproject.json export render output.pdf --overwrite
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
cli-anything-gimp project info -p project.json

# JSON output for agents
cli-anything-gimp --json project info -p project.json
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