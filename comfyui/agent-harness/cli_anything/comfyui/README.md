# cli-anything-comfyui

CLI harness for **ComfyUI** — manage AI image generation workflows, queue prompts, inspect models, and download outputs from the command line via the ComfyUI REST API.

## Installation

```bash
pip install cli-anything-comfyui
# or from source:
cd comfyui/agent-harness && pip install -e .
```

## Prerequisites

1. [ComfyUI](https://github.com/comfyanonymous/ComfyUI) installed and running
2. ComfyUI server accessible at `http://localhost:8188` (default)
3. At least one checkpoint model installed in ComfyUI's `models/checkpoints/` directory

## Quick Start

```bash
# Check server status
cli-anything-comfyui system stats

# List available models
cli-anything-comfyui models checkpoints

# List workflows
cli-anything-comfyui workflow list

# Queue a workflow from a JSON file
cli-anything-comfyui queue prompt --workflow my_workflow.json

# Check queue status
cli-anything-comfyui queue status

# List output images
cli-anything-comfyui images list --prompt-id <prompt_id>

# Download an output image
cli-anything-comfyui images download --filename ComfyUI_00001_.png --output ./output.png

# Interactive mode
cli-anything-comfyui repl
```

## Commands

| Group | Commands |
|---|---|
| `workflow` | `list`, `load`, `validate` |
| `queue` | `prompt`, `status`, `clear`, `history`, `interrupt` |
| `models` | `checkpoints`, `loras`, `vaes`, `controlnets`, `node-info`, `list-nodes` |
| `images` | `list`, `download`, `download-all` |
| `system` | `stats`, `info` |

## Agent Usage (JSON mode)

All commands support `--json` for machine-readable output:

```bash
cli-anything-comfyui --json models checkpoints
cli-anything-comfyui --json queue status
cli-anything-comfyui --json queue history
```

## Custom Server URL

```bash
cli-anything-comfyui --url http://192.168.1.100:8188 system stats
```

## Workflow JSON Format

ComfyUI workflows use a node graph format. Export them from the ComfyUI web UI via **Save (API Format)**:

```json
{
  "3": {
    "class_type": "KSampler",
    "inputs": {
      "cfg": 7,
      "denoise": 1,
      "model": ["4", 0],
      "positive": ["6", 0],
      "negative": ["7", 0],
      "latent_image": ["5", 0],
      "sampler_name": "euler",
      "scheduler": "normal",
      "seed": 42,
      "steps": 20
    }
  }
}
```
