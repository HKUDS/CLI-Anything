# cli-anything-godot

A stateful command-line interface for game engine operations, built on Godot. Designed for AI agents and developers who need to manage projects, export builds, analyze scenes, and validate scripts without opening the Godot editor.

## Features

- **Project Info** — Read project.godot metadata (name, version, renderer)
- **Project Validation** — Check for errors and warnings
- **Export Presets** — List and run export presets
- **Build Export** — Export projects for all platforms
- **Scene Analysis** — List and analyze .tscn/.scn files
- **Script Listing** — List all GDScript files
- **Syntax Checking** — Check GDScript for syntax errors
- **Resource Cataloging** — List textures, sounds, meshes
- **Re-import** — Force re-import of all resources
- **Debug Mode** — Run with remote debug on a port
- **JSON output** — Machine-readable output with `--json` flag
- **REPL** — Interactive session with undo/redo history

## Installation

```bash
cd agent-harness
pip install -e .
```

## Quick Start

```bash
# Get project info
cli-anything-godot project info /path/to/game

# List export presets
cli-anything-godot export presets /path/to/game

# Export for Linux
cli-anything-godot export run /path/to/game --preset Linux --output build/game

# List scenes
cli-anything-godot scene list /path/to/game

# Check a script
cli-anything-godot script check player.gd

# List resources
cli-anything-godot resource list /path/to/game
```
