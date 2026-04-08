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
- blender (>= 4.2) must be installed on your system


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
| `new` | Create a new scene |
| `open` | Open an existing scene |
| `save` | Save the current scene |
| `info` | Show scene information |
| `profiles` | List available scene profiles |
| `json` | Print raw scene JSON |


### Object Group

3D object management commands.

| Command | Description |
|---------|-------------|
| `add` | Add a 3D primitive object |
| `remove` | Remove an object by index |
| `duplicate` | Duplicate an object |
| `transform` | Transform an object (translate, rotate, scale) |
| `set` | Set an object property (name, visible, location, rotation, scale, parent) |
| `list` | List all objects |
| `get` | Get detailed info about an object |


### Material

Material management commands.

| Command | Description |
|---------|-------------|
| `create` | Create a new material |
| `assign` | Assign a material to an object |
| `set` | Set a material property (color, metallic, roughness, specular, alpha, etc.) |
| `list` | List all materials |
| `get` | Get detailed info about a material |


### Modifier Group

Modifier management commands.

| Command | Description |
|---------|-------------|
| `list-available` | List all available modifiers |
| `info` | Show details about a modifier |
| `add` | Add a modifier to an object |
| `remove` | Remove a modifier by index |
| `set` | Set a modifier parameter |
| `list` | List modifiers on an object |


### Camera

Camera management commands.

| Command | Description |
|---------|-------------|
| `add` | Add a camera to the scene |
| `set` | Set a camera property |
| `set-active` | Set the active camera |
| `list` | List all cameras |


### Light

Light management commands.

| Command | Description |
|---------|-------------|
| `add` | Add a light to the scene |
| `set` | Set a light property |
| `list` | List all lights |


### Animation

Animation and keyframe commands.

| Command | Description |
|---------|-------------|
| `keyframe` | Set a keyframe on an object |
| `remove-keyframe` | Remove a keyframe from an object |
| `frame-range` | Set the animation frame range |
| `fps` | Set the animation FPS |
| `list-keyframes` | List keyframes for an object |


### Render Group

Render settings and output commands.

| Command | Description |
|---------|-------------|
| `settings` | Configure render settings |
| `info` | Show current render settings |
| `presets` | List available render presets |
| `execute` | Render the scene (generates bpy script) |
| `script` | Generate bpy script without rendering |


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
4. **MANDATORY: Use absolute paths** for all file operations (rendering, project files). Relative paths are prone to failure in background execution.
5. **Verify outputs exist** after export operations

## More Information

- Full documentation: See README.md in the package
- Test coverage: See TEST.md in the package
- Methodology: See HARNESS.md in the cli-anything-plugin

## Version

1.0.0