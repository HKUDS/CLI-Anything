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
| `new` | Create a new document |
| `open` | Open an existing project |
| `save` | Save the current project |
| `info` | Show document information |
| `profiles` | List available document profiles |
| `canvas-size` | Set the canvas size |
| `units` | Set the document units |
| `json` | Print raw project JSON |


### Shape

Shape management commands.

| Command | Description |
|---------|-------------|
| `add-rect` | Add a rectangle |
| `add-circle` | Add a circle |
| `add-ellipse` | Add an ellipse |
| `add-line` | Add a line |
| `add-polygon` | Add a polygon |
| `add-path` | Add a path |
| `add-star` | Add a star |
| `remove` | Remove a shape by index |
| `duplicate` | Duplicate a shape |
| `list` | List all shapes/objects |
| `get` | Get detailed info about a shape |


### Text

Text management commands.

| Command | Description |
|---------|-------------|
| `add` | Add a text element |
| `set` | Set a text property (text, font-family, font-size, fill, etc.) |
| `list` | List all text objects |


### Style

Style management commands.

| Command | Description |
|---------|-------------|
| `set-fill` | Set the fill color of an object |
| `set-stroke` | Set the stroke color (and optionally width) of an object |
| `set-opacity` | Set the opacity of an object (0.0-1.0) |
| `set` | Set an arbitrary style property on an object |
| `get` | Get the style properties of an object |
| `list-properties` | List all available style properties |


### Transform

Transform operations (translate, rotate, scale, skew).

| Command | Description |
|---------|-------------|
| `translate` | Translate (move) an object |
| `rotate` | Rotate an object |
| `scale` | Scale an object |
| `skew-x` | Skew an object horizontally |
| `skew-y` | Skew an object vertically |
| `get` | Get the current transform of an object |
| `clear` | Clear all transforms from an object |


### Layer

Layer management commands.

| Command | Description |
|---------|-------------|
| `add` | Add a new layer |
| `remove` | Remove a layer by index |
| `move-object` | Move an object to a different layer |
| `set` | Set a layer property (name, visible, locked, opacity) |
| `list` | List all layers |
| `reorder` | Move a layer from one position to another |
| `get` | Get detailed info about a layer |


### Path Group

Path boolean operations.

| Command | Description |
|---------|-------------|
| `union` | Union of two objects |
| `intersection` | Intersection of two objects |
| `difference` | Difference of two objects (A minus B) |
| `exclusion` | Exclusion (XOR) of two objects |
| `convert` | Convert a shape to a path |
| `list-operations` | List available path boolean operations |


### Gradient

Gradient management commands.

| Command | Description |
|---------|-------------|
| `add-linear` | Add a linear gradient |
| `add-radial` | Add a radial gradient |
| `apply` | Apply a gradient to an object |
| `list` | List all gradients |


### Export Group

Export/render commands.

| Command | Description |
|---------|-------------|
| `png` | Render the document to PNG |
| `svg` | Export the document as SVG |
| `pdf` | Export the document as PDF (requires Inkscape) |
| `presets` | List export presets |


### Session

Session management commands.

| Command | Description |
|---------|-------------|
| `status` | Show session status |
| `undo` | Undo the last operation |
| `redo` | Redo the last undone operation |
| `history` | Show undo history |




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