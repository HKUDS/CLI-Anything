---
name: "cli-anything-comfyui"
description: >-
  Command-line interface for ComfyUI - AI image generation workflow management via ComfyUI REST API. Designed for AI agents and power users who need to queue workflows, manage models, download generated images, and monitor the generation queue without a GUI.
---

# cli-anything-comfyui

AI image generation workflow management via the ComfyUI REST API. Designed for AI agents and power users who need to queue workflows, manage models, download generated images, and monitor the generation queue without a GUI.

## Installation

This CLI is installed as part of the cli-anything-comfyui package:

```bash
pip install cli-anything-comfyui
```

**Prerequisites:**
- Python 3.10+
- ComfyUI must be installed and running at http://localhost:8188

## Usage

### Basic Commands

```bash
# Show help
cli-anything-comfyui --help

# Start interactive REPL mode
cli-anything-comfyui repl

# Check server stats
cli-anything-comfyui system stats

# Run with JSON output (for agent consumption)
cli-anything-comfyui --json system stats
```

### REPL Mode

Start an interactive session for exploratory use:

```bash
cli-anything-comfyui repl
# Enter commands interactively with tab-completion and history
```

## Command Groups

### Workflow

Workflow management commands.

| Command | Description |
|---------|-------------|
| `list` | List saved workflows |
| `load` | Load a workflow from a JSON file |
| `validate` | Validate a workflow JSON against the ComfyUI node graph |

### Queue

Generation queue management.

| Command | Description |
|---------|-------------|
| `prompt` | Queue a workflow for execution |
| `status` | Show current queue status (running and pending) |
| `clear` | Clear the generation queue |
| `history` | Show prompt execution history |
| `interrupt` | Interrupt the currently running generation |

### Models

Model discovery commands.

| Command | Description |
|---------|-------------|
| `checkpoints` | List available checkpoint models |
| `loras` | List available LoRA models |
| `vaes` | List available VAE models |
| `controlnets` | List available ControlNet models |
| `node-info` | Show detailed info for a specific node type |
| `list-nodes` | List all available node types |

### Images

Generated image management.

| Command | Description |
|---------|-------------|
| `list` | List generated images on the server |
| `download` | Download a specific generated image |
| `download-all` | Download all images from a prompt execution |

### System

Server status and information.

| Command | Description |
|---------|-------------|
| `stats` | Show ComfyUI system statistics (GPU, CPU, memory) |
| `info` | Show ComfyUI server info and extensions |

## Examples

### Check System Status

```bash
# Server stats
cli-anything-comfyui system stats

# Server info
cli-anything-comfyui system info
```

### Discover Available Models

```bash
# List checkpoints
cli-anything-comfyui models checkpoints

# List LoRAs
cli-anything-comfyui models loras

# List all node types
cli-anything-comfyui models list-nodes
```

### Queue and Monitor Generation

```bash
# Queue a workflow
cli-anything-comfyui queue prompt --workflow my_workflow.json

# Check queue status
cli-anything-comfyui queue status

# View execution history
cli-anything-comfyui --json queue history
```

### Download Generated Images

```bash
# List generated images
cli-anything-comfyui images list

# Download a specific image
cli-anything-comfyui images download --filename ComfyUI_00001_.png --output ./out.png

# Download all images from a prompt
cli-anything-comfyui images download-all --prompt-id <id> --output-dir ./outputs
```

## Output Formats

All commands support dual output modes:

- **Human-readable** (default): Tables, colors, formatted text
- **Machine-readable** (`--json` flag): Structured JSON for agent consumption

```bash
# Human output
cli-anything-comfyui system stats

# JSON output for agents
cli-anything-comfyui --json system stats
```

## For AI Agents

When using this CLI programmatically:

1. **Always use `--json` flag** for parseable output
2. **Check return codes** - 0 for success, non-zero for errors
3. **Parse stderr** for error messages on failure
4. **Use absolute paths** for all file operations
5. **Verify ComfyUI is running** with `system stats` before other commands

## More Information

- Full documentation: See README.md in the package
- Test coverage: See TEST.md in the package
- Methodology: See HARNESS.md in the cli-anything-plugin

## Version

1.0.0
