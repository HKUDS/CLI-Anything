# cli-anything-godot

Agent-native CLI harness for the **Godot Engine** (4.x). Provides structured, JSON-capable commands for project management, scene editing, exporting, and GDScript execution — all accessible to AI agents.

## Installation

```bash
pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=godot/agent-harness
```

## Prerequisites

- **Godot 4.x** on PATH (or set `GODOT_BIN` environment variable)
- Python 3.10+

## Quick Start

```bash
# Check engine status
cli-anything-godot engine status

# Create a new project
cli-anything-godot project create ./my-game --name "My Game"

# List scenes in a project
cli-anything-godot --project ./my-game project scenes

# Create a scene
cli-anything-godot -p ./my-game scene create scenes/Main.tscn --root-type Node2D

# Add a node to a scene
cli-anything-godot -p ./my-game scene add-node scenes/Main.tscn --name Player --type CharacterBody2D

# Run a GDScript
cli-anything-godot -p ./my-game script run tools/generate_map.gd

# Run inline GDScript
cli-anything-godot -p ./my-game script inline 'print("Hello from Godot!")'

# Export the project
cli-anything-godot -p ./my-game export build --preset "Windows Desktop"

# JSON mode for agents
cli-anything-godot --json -p ./my-game project info

# Interactive REPL
cli-anything-godot -p ./my-game session
```

## Command Groups

| Group | Commands | Description |
|-------|----------|-------------|
| `project` | create, info, scenes, scripts, resources, reimport | Project management |
| `scene` | create, read, add-node | Scene file operations |
| `export` | build, presets | Platform export |
| `script` | run, inline, validate | GDScript execution |
| `engine` | version, status | Engine info |
| `session` | (REPL) | Interactive mode |

## Security Note

The `script inline` command writes user-provided GDScript to a temp file and executes it via Godot subprocess. This runs arbitrary code on the host — only use with trusted input.

## Version Compatibility

- `export build` without `--preset` uses `--export-all` (Godot 4.3+). For older 4.x, specify `--preset` explicitly.
- Set `GODOT_BIN` environment variable if your Godot binary has a non-standard name.
