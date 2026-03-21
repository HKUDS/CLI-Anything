---
name: >-
  cli-anything-godot
description: >-
  Command-line interface for Godot - Project management, export, scene analysis,
  script validation, and resource cataloging via godot headless...
---

# cli-anything-godot

A stateful command-line interface for game engine operations, built on Godot. Designed for AI agents and developers who need to manage projects, export builds, analyze scenes, and validate scripts.

## Installation

```bash
pip install cli-anything-godot
```

**Prerequisites:**
- Python 3.10+
- Godot 4+ must be installed (`apt install godot`)

## Command Groups

### Project

| Command | Description |
|---------|-------------|
| `info` | Get project.godot info (name, version, renderer) |
| `run` | Run the project headless |
| `validate` | Validate project (check for errors) |

### Export

| Command | Description |
|---------|-------------|
| `presets` | List export presets |
| `run` | Run an export preset |
| `all` | Export all presets |

### Scene

| Command | Description |
|---------|-------------|
| `list` | List all .tscn/.scn files |
| `info` | Get scene info (nodes, resources) |

### Script

| Command | Description |
|---------|-------------|
| `list` | List all .gd scripts |
| `check` | Check GDScript for syntax errors |

### Resource

| Command | Description |
|---------|-------------|
| `list` | List resources (textures, sounds, meshes) |

### Import

| Command | Description |
|---------|-------------|
| `reimport` | Re-import all resources |

### Debug

| Command | Description |
|---------|-------------|
| `run` | Run with remote debug |

### Build

| Command | Description |
|---------|-------------|
| `build` | Build/export the project |

### Session

| Command | Description |
|---------|-------------|
| `status` | Show session status |
| `undo` | Undo last operation |
| `redo` | Redo last undone operation |
| `history` | Show undo history |

## Examples

```bash
# Get project info
cli-anything-godot --json project info /path/to/game

# List export presets
cli-anything-godot export presets /path/to/game

# Export for Linux
cli-anything-godot export run /path/to/game --preset Linux --output build/game

# Export all presets
cli-anything-godot export all /path/to/game --output-dir builds/

# List scenes
cli-anything-godot scene list /path/to/game

# Get scene info
cli-anything-godot scene info main.tscn

# Check a script
cli-anything-godot script check player.gd

# List resources
cli-anything-godot resource list /path/to/game

# Build project
cli-anything-godot build /path/to/game --export-preset Linux --output build/game
```

## Version

1.0.0
