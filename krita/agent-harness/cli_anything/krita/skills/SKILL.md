---
name: >-
  cli-anything-krita
description: >-
  Command-line interface for Krita — Digital art and painting via krita CLI and ZIP-based .kra parsing...
---

# cli-anything-krita

A command-line interface for digital art and painting via Krita CLI. Designed for AI agents and power users.

## Installation

```bash
pip install cli-anything-krita
```

**Prerequisites:**
- Python 3.10+
- `krita` must be installed: `apt install krita`

## Usage

```bash
cli-anything-krita info artwork.kra
cli-anything-krita export artwork.kra output.png
cli-anything-krita layer list artwork.kra
cli-anything-krita layer export artwork.kra --index 0 --output layer.png
cli-anything-krita create --width 1920 --height 1080 --output canvas.png
cli-anything-krita filter apply input.png output.png --filter blur
cli-anything-krita colorspace convert input.png output.png --space SRGB
```

## Command Reference

| Command | Description |
|---------|-------------|
| `info` | Get KRA file info (layers, dimensions) |
| `export` | Export KRA to PNG/JPEG/TIFF |
| `batch` | Batch export KRA files |
| `layer list` | List layers |
| `layer export` | Export specific layer |
| `flatten` | Flatten and export |
| `resize` | Resize canvas |
| `filter apply` | Apply a filter |
| `colorspace convert` | Convert color space |
| `create` | Create new canvas |

## Version

1.0.0
