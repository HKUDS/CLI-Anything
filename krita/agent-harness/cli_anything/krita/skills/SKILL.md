---
name: "cli-anything-krita"
description: "CLI harness for Krita digital painting — manage projects, layers, filters, and export via command line. Use when automating Krita workflows, batch processing images, or operating Krita without a GUI."
---

# cli-anything-krita

CLI harness for **Krita**, the professional open-source digital painting application.

## Prerequisites

- **Krita** installed on the system
- **Python 3.10+**

Install the CLI:
```bash
cd krita/agent-harness && pip install -e .
```

## Command Reference

### Project Management
```bash
cli-anything-krita project new -n "My Art" -w 2048 -h 2048 -o project.json
cli-anything-krita project open project.json
cli-anything-krita --project project.json project save
cli-anything-krita --project project.json project info
```

### Layer Management
```bash
cli-anything-krita -p project.json layer add "Sketch" -t paintlayer
cli-anything-krita -p project.json layer add "Colors" --opacity 200
cli-anything-krita -p project.json layer add "Group" -t grouplayer
cli-anything-krita -p project.json layer remove "Sketch"
cli-anything-krita -p project.json layer list
cli-anything-krita -p project.json layer set "Colors" opacity 180
cli-anything-krita -p project.json layer set "Colors" visible false
cli-anything-krita -p project.json layer set "Colors" blending_mode multiply
```

Layer types: `paintlayer`, `grouplayer`, `vectorlayer`, `filterlayer`, `filllayer`, `clonelayer`, `filelayer`

### Filters
```bash
cli-anything-krita -p project.json filter apply blur -l "Background"
cli-anything-krita -p project.json filter apply sharpen
cli-anything-krita -p project.json filter apply levels -c '{"shadows": 10, "highlights": 240}'
cli-anything-krita filter list
```

Available: blur, sharpen, desaturate, levels, curves, brightness-contrast, hue-saturation, color-balance, unsharp-mask, posterize, threshold

### Canvas Operations
```bash
cli-anything-krita -p project.json canvas resize -w 4096 -h 4096
cli-anything-krita -p project.json canvas resize --resolution 600
cli-anything-krita -p project.json canvas info
```

### Export
```bash
cli-anything-krita -p project.json export render output.png -p png --overwrite
cli-anything-krita -p project.json export render output.jpg -p jpeg
cli-anything-krita -p project.json export render output.psd -p psd
cli-anything-krita -p project.json export animation ./frames/ -p png
cli-anything-krita export presets
cli-anything-krita export formats
```

Presets: png, png-web, jpeg, jpeg-web, jpeg-low, tiff, tiff-lzw, psd, pdf, svg, webp, gif, bmp

### Session (Undo/Redo)
```bash
cli-anything-krita session undo
cli-anything-krita session redo
cli-anything-krita session history
```

### Status
```bash
cli-anything-krita status
```

## Agent Usage (JSON Mode)

All commands support `--json` for machine-readable output:

```bash
cli-anything-krita --json -p project.json project info
cli-anything-krita --json -p project.json layer list
cli-anything-krita --json status
```

## Example Workflow

```bash
# 1. Create project
cli-anything-krita --json project new -n "Illustration" -w 3000 -h 4000 -o art.json

# 2. Set up layer stack
cli-anything-krita --json -p art.json layer add "Background" -t paintlayer
cli-anything-krita --json -p art.json layer add "Sketch" -t paintlayer --opacity 180
cli-anything-krita --json -p art.json layer add "Inking" -t paintlayer
cli-anything-krita --json -p art.json layer add "Colors" -t paintlayer
cli-anything-krita --json -p art.json layer add "Effects" -t paintlayer --opacity 128

# 3. Apply effects
cli-anything-krita --json -p art.json filter apply blur -l "Background"

# 4. Export
cli-anything-krita --json -p art.json export render final.png -p png --overwrite
```
