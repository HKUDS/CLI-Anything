---
name: "cli-anything-universal-image-converter"
description: >-
  Command-line interface for Universal Image Converter — batch image format conversion via Pillow. Convert images between PNG, JPEG, Web...
---

# cli-anything-universal-image-converter

A command-line interface for batch image format conversion, built on Pillow. Designed for AI agents and power users who need to convert images between formats without a GUI.

## Installation

This CLI is installed as part of the cli-anything-universal-image-converter package:

```bash
pip install cli-anything-universal-image-converter
```

**Prerequisites:**
- Python 3.10+
- Pillow (installed automatically)


## Usage

### Basic Commands

```bash
# Show help
cli-anything-universal-image-converter --help

# Start interactive REPL mode
cli-anything-universal-image-converter

# Convert an image
cli-anything-universal-image-converter convert -i photo.jpg -o output/ -f png

# Run with JSON output (for agent consumption)
cli-anything-universal-image-converter --json convert -i photo.jpg -o output/ -f png
```

### REPL Mode

When invoked without a subcommand, the CLI enters an interactive REPL session:

```bash
cli-anything-universal-image-converter
# Enter commands interactively with tab-completion and history
```


## Command Groups


### Convert

Image format conversion commands.

| Command | Description |
|---------|-------------|
| `convert` | Convert images between formats (single or batch) |


### Info

Image metadata commands.

| Command | Description |
|---------|-------------|
| `info` | Show detailed information about an image file |


### Formats

Format listing commands.

| Command | Description |
|---------|-------------|
| `formats` | List supported input or output formats |
| `format-info` | Show details about a specific output format |


### Quality

Quality management commands.

| Command | Description |
|---------|-------------|
| `quality-presets` | List available quality presets |


### Resize

Image resizing commands.

| Command | Description |
|---------|-------------|
| `resize` | Resize an image, optionally converting format |


## Examples


### Convert a Single Image

Convert a photo from JPEG to PNG.

```bash
cli-anything-universal-image-converter convert -i photo.jpg -o output/ -f png
# Or with JSON for programmatic use
cli-anything-universal-image-converter --json convert -i photo.jpg -o output/ -f png
```


### Batch Convert a Directory

Convert all images in a directory to WebP.

```bash
cli-anything-universal-image-converter convert -d ./photos -o ./webp_output -f webp -q high --overwrite
```


### Resize and Convert

Resize images while converting format.

```bash
cli-anything-universal-image-converter convert -d ./originals -o ./thumbnails -f jpg -w 800 -h 600 -q medium
```


### Get Image Info

Inspect image metadata.

```bash
cli-anything-universal-image-converter info photo.jpg
cli-anything-universal-image-converter --json info photo.jpg
```


## Supported Formats

| Format | Input | Output | Notes |
|--------|-------|--------|-------|
| PNG | Yes | Yes | Lossless, supports alpha |
| JPEG | Yes | Yes | Lossy, no alpha |
| WebP | Yes | Yes | Both lossy/lossless |
| TIFF | Yes | Yes | Professional format |
| BMP | Yes | Yes | Uncompressed |
| ICO | Yes | Yes | Icon format |
| GIF | Yes | Yes | 256 colors max |
| HEIC | Yes | No | Requires pillow-heif |

## Quality Presets

| Preset | Description |
|--------|-------------|
| `lossless` | Maximum quality, no compression |
| `high` | High quality, moderate compression |
| `medium` | Good balance of quality and size |
| `low` | Small file size, visible quality loss |

## Output Formats

All commands support dual output modes:

- **Human-readable** (default): Tables, colors, formatted text
- **Machine-readable** (`--json` flag): Structured JSON for agent consumption

## For AI Agents

When using this CLI programmatically:

1. **Always use `--json` flag** for parseable output
2. **Check return codes** — 0 for success, non-zero for errors
3. **Parse stderr** for error messages on failure
4. **Use absolute paths** for all file operations
5. **Verify outputs exist** after conversion operations
6. **Use `--overwrite` flag** when re-running conversions on same output paths

## More Information

- Full documentation: See README.md in the package
- Test coverage: See TEST.md in the package

## Version

1.0.0
