---
name: >-
  cli-anything-freecad
description: >-
  Parametric 3D modeling CLI for AI Agents. Control FreeCAD via structured commands,
  sketches, part design operations, and headless rendering/export.
---

# cli-anything-freecad

A powerful, stateful command-line interface that brings FreeCAD's parametric 3D modeling 
capabilities to AI agents. It wraps FreeCAD's rich Python API into a structured, 
JSON-first CLI that supports complex CAD workflows.

## Installation

This CLI is installed as part of the cli-anything-freecad package:

```bash
pip install cli-anything-freecad
```

**Prerequisites:**
- Python 3.10+
- FreeCAD must be installed on your system

## Usage

### Basic Commands

```bash
# Show help
cli-anything-freecad --help

# Start interactive REPL mode
cli-anything-freecad

# Create a new project
cli-anything-freecad project new -o my_part.json

# Run with JSON output (for agent consumption)
cli-anything-freecad --json project info -p my_part.json
```

### REPL Mode

When invoked without a subcommand, the CLI enters an interactive REPL session:

```bash
cli-anything-freecad
# Enter commands interactively with tab-completion and history
```

## Command Groups

### project

Project management and state persistence.

| Command | Description |
|---------|-------------|
| `new` | Create a new project file |
| `info` | Show current project metadata |
| `save` | Save current project state |

### sketch

Sketcher workbench: 2D geometry with constraints.

| Command | Description |
|---------|-------------|
| `add-circle` | Add a circle to the sketch |
| `add-rectangle` | Add a rectangle to the sketch |
| `add-line` | Add a line segment |
| `constrain-radius` | Add a radius constraint |

### part

Part Design: 3D modeling operations.

| Command | Description |
|---------|-------------|
| `pad` | Extrude a sketch to create a 3D solid |
| `pocket` | Cut a pocket into a solid |
| `fillet` | Round edges of a solid |
| `chamfer` | Bevel edges of a solid |

### export

Rendering and file export.

| Command | Description |
|---------|-------------|
| `render` | Export the 3D model to STEP, STL, or OBJ |
| `capture` | Save a PNG screenshot of the 3D view |

## Examples

### Create a Simple Flange

```bash
# 1. Start project
cli-anything-freecad project new -o flange.json

# 2. Sketch base circle
cli-anything-freecad -p flange.json sketch add-circle --radius 50

# 3. Pad to create disk
cli-anything-freecad -p flange.json part pad --length 10

# 4. Export to STEP
cli-anything-freecad -p flange.json export render -o flange.step -f step
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
