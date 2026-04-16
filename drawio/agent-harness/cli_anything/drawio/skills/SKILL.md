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
| `new` | Create a new blank diagram |
| `open` | Open an existing .drawio project file |
| `save` | Save the current project |
| `info` | Show detailed project information |
| `xml` | Print the raw XML of the current project |
| `presets` | List available page size presets |


### Shape

Shape operations: add, remove, move, resize, style.

| Command | Description |
|---------|-------------|
| `add` | Add a shape to the diagram |
| `remove` | Remove a shape by ID |
| `list` | List all shapes on a page |
| `label` | Update a shape's label text |
| `move` | Move a shape to new coordinates |
| `resize` | Resize a shape |
| `style` | Set a style property on a shape |
| `info` | Show detailed info about a shape |
| `types` | List all available shape types |


### Connect

Connector operations: add, remove, style.

| Command | Description |
|---------|-------------|
| `add` | Add a connector between two shapes |
| `remove` | Remove a connector by ID |
| `label` | Update a connector's label |
| `style` | Set a style property on a connector |
| `list` | List all connectors on a page |
| `styles` | List available edge styles |


### Page

Page operations: add, remove, rename, list.

| Command | Description |
|---------|-------------|
| `add` | Add a new page |
| `remove` | Remove a page by index |
| `rename` | Rename a page |
| `list` | List all pages |


### Export

Export operations: render to PNG, PDF, SVG.

| Command | Description |
|---------|-------------|
| `render` | Export the diagram to a file |
| `formats` | List available export formats |


### Session

Session management: status, undo, redo.

| Command | Description |
|---------|-------------|
| `status` | Show current session status |
| `undo` | Undo the last operation |
| `redo` | Redo the last undone operation |
| `save-state` | Save session state to disk |
| `list` | List all saved sessions |




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