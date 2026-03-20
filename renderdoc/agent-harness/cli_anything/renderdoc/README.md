# cli-anything-renderdoc

Command-line interface for [RenderDoc](https://renderdoc.org/) graphics debugger.

Provides headless, scriptable analysis of GPU frame captures (`.rdc` files)
without requiring the RenderDoc GUI.

## Installation

```bash
cd renderdoc/agent-harness
pip install -e .
```

**Prerequisites**: RenderDoc must be installed and its Python module must be
importable. Add the RenderDoc Python directory to `PYTHONPATH`:

```bash
# Windows (typical)
set PYTHONPATH=C:\Program Files\RenderDoc
# Linux (typical)
export PYTHONPATH=/opt/renderdoc/lib
```

## Quick Start

```bash
# Show capture info
cli-anything-renderdoc --capture frame.rdc capture info

# List all draw calls
cli-anything-renderdoc -c frame.rdc actions list --draws-only

# Get action summary
cli-anything-renderdoc -c frame.rdc actions summary

# Save a texture as PNG
cli-anything-renderdoc -c frame.rdc textures save <resourceId> -o output.png

# Pick a pixel
cli-anything-renderdoc -c frame.rdc textures pick <resourceId> 100 200

# Get pipeline state at a draw call
cli-anything-renderdoc -c frame.rdc pipeline state 42

# Get shader disassembly
cli-anything-renderdoc -c frame.rdc pipeline disasm 42 --stage Fragment

# List GPU counters
cli-anything-renderdoc -c frame.rdc counters list

# Read buffer data
cli-anything-renderdoc -c frame.rdc resources read-buffer <resourceId> --format float32

# JSON output for all commands
cli-anything-renderdoc -c frame.rdc --json actions list
```

## Command Reference

### Global Options

| Option       | Description                          |
|-------------|--------------------------------------|
| `--capture`  | Path to `.rdc` capture file         |
| `--json`     | JSON output mode                    |
| `--debug`    | Show error tracebacks               |
| `--version`  | Show version                        |

### Commands

| Group        | Command         | Description                                |
|-------------|----------------|--------------------------------------------|
| `capture`   | `info`          | Show metadata and sections                |
| `capture`   | `thumb`         | Extract thumbnail image                   |
| `capture`   | `convert`       | Convert capture format                    |
| `actions`   | `list`          | List all actions / draw calls             |
| `actions`   | `summary`       | Count actions by type                     |
| `actions`   | `find`          | Search actions by name                    |
| `actions`   | `get`           | Get single action details                 |
| `textures`  | `list`          | List all textures                         |
| `textures`  | `get`           | Get texture details                       |
| `textures`  | `save`          | Export texture to image file              |
| `textures`  | `save-outputs`  | Save all render targets at an event       |
| `textures`  | `pick`          | Read pixel value                          |
| `pipeline`  | `state`         | Full pipeline state at event              |
| `pipeline`  | `disasm`        | Shader disassembly                        |
| `pipeline`  | `cbuffer`       | Constant buffer contents                  |
| `resources` | `list`          | List all resources                        |
| `resources` | `buffers`       | List buffer resources                     |
| `resources` | `read-buffer`   | Read raw buffer data                      |
| `mesh`      | `inputs`        | Vertex shader input data                  |
| `mesh`      | `outputs`       | Post-VS output data                       |
| `counters`  | `list`          | Available GPU counters                    |
| `counters`  | `fetch`         | Fetch counter results                     |

## Environment Variables

| Variable           | Description                    |
|-------------------|--------------------------------|
| `RENDERDOC_CAPTURE` | Default capture file path     |
| `PYTHONPATH`        | Must include RenderDoc Python |
