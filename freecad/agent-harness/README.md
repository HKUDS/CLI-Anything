# FreeCAD Agent Harness

A stateful CLI for FreeCAD, designed for AI agents.

## Quick Start

### Installation

```bash
pip install -e .
```

### Basic Usage

```bash
# Create a new project
cli-anything-freecad project new -o my_part.json

# Add a circle to a sketch
cli-anything-freecad -p my_part.json sketch add-circle --radius 10

# Export to STEP
cli-anything-freecad -p my_part.json export render -o my_part.step
```

### REPL Mode

```bash
cli-anything-freecad
```

## Features

- **Stateful Modeling**: The CLI maintains a JSON model of your CAD project.
- **Parametric Design**: Modify parameters in the JSON to update the model.
- **Headless Execution**: Uses `FreeCADCmd` to render and export without a GUI.
- **Agent-Native**: Supports `--json` flag for all commands.

## Architecture

See [FREECAD.md](./FREECAD.md) for detailed architecture documentation.
