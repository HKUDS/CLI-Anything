---
name: >-
  cli-anything-darktable
description: >-
  Command-line interface for Darktable — RAW photo processing and export from the command line...
---

# cli-anything-darktable

A command-line interface for RAW photo processing via darktable-cli. Designed for AI agents and power users who need to process RAW photos without a GUI.

## Installation

```bash
pip install cli-anything-darktable
```

**Prerequisites:**
- Python 3.10+
- `darktable` must be installed: `apt install darktable`

## Usage

### Basic Commands

```bash
cli-anything-darktable --help
cli-anything-darktable export input.cr2 output.jpg --quality 95
cli-anything-darktable info photo.nef
cli-anything-darktable batch *.cr2 --output-dir ./exports
cli-anything-darktable styles list
cli-anything-darktable xmp create photo.cr2
cli-anything-darktable xmp apply photo.cr2.xmp photo.cr2 output.jpg
```

### REPL Mode

```bash
cli-anything-darktable
```

## Command Reference

| Command | Description |
|---------|-------------|
| `export` | Export RAW to JPEG/PNG/TIFF |
| `info` | Get RAW file info (exif data) |
| `batch` | Batch export with options |
| `styles list` | List available darktable styles |
| `styles export` | Export with a specific style |
| `xmp create` | Create XMP sidecar file |
| `xmp apply` | Apply XMP edits to produce output |

## Version

1.0.0
