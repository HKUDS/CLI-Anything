# Universal Image Converter CLI

A command-line interface for batch image format conversion, built on Pillow.
Designed for AI agents and power users who need to convert images between
formats without a GUI.

## Prerequisites

- Python 3.10+
- `Pillow` (image processing)
- `click` (CLI framework)

Optional (for interactive REPL):
- `prompt_toolkit`

Optional (for HEIC/HEIF support):
- `pillow-heif`

## Install Dependencies

```bash
pip install Pillow click
# Optional
pip install prompt_toolkit pillow-heif
```

## How to Run

All commands are run from the `agent-harness/` directory.

### One-shot commands

```bash
# Show help
python3 -m cli_anything.universal_image_converter.uic_cli --help

# Convert a single image
python3 -m cli_anything.universal_image_converter.uic_cli convert -i photo.jpg -o output/ -f png

# Batch convert a directory
python3 -m cli_anything.universal_image_converter.uic_cli convert -d ./images -o ./converted -f webp

# Get image info
python3 -m cli_anything.universal_image_converter.uic_cli info photo.jpg

# JSON output (for agent consumption)
python3 -m cli_anything.universal_image_converter.uic_cli --json convert -i photo.jpg -o out/ -f png
```

### Interactive REPL

```bash
python3 -m cli_anything.universal_image_converter.uic_cli repl
```

## Command Reference

### convert

```bash
convert -i <files...> | -d <directory> -o <output> -f <format> [-q quality] [-w width] [-h height] [--overwrite]
```

Convert images between formats. Supports single files, multiple files, and directory batch conversion.

Options:
- `-i, --input` — One or more input image file paths
- `-d, --input-dir` — Directory of images to convert
- `-o, --output` — Output directory (or single file path for single input)
- `-f, --format` — Target output format (png, jpg, webp, tiff, bmp, ico, gif)
- `-q, --quality` — Quality preset: lossless, high, medium, low
- `-w, --width` — Target width in pixels
- `-h, --height` — Target height in pixels
- `--no-aspect` — Don't maintain aspect ratio when resizing
- `--overwrite` — Overwrite existing files
- `--prefix` — Prefix for output filenames
- `--suffix` — Suffix for output filenames

### info

```bash
info <path>
```

Show detailed information about an image file (dimensions, format, mode, file size).

### formats

```bash
formats [--type input|output]
```

List supported image formats. Default shows output formats.

### format-info

```bash
format-info <format_name>
```

Show details about a specific output format.

### quality-presets

```bash
quality-presets
```

List available quality presets for conversion.

### resize

```bash
resize <path> -o <output> -w <width> -h <height> [--format <fmt>] [--overwrite]
```

Resize an image, optionally converting its format.

## Supported Formats

| Format | Input | Output | Lossless | Alpha |
|--------|-------|--------|----------|-------|
| PNG    | Yes   | Yes    | Yes      | Yes   |
| JPEG   | Yes   | Yes    | No       | No    |
| WebP   | Yes   | Yes    | Yes      | Yes   |
| TIFF   | Yes   | Yes    | Yes      | Yes   |
| BMP    | Yes   | Yes    | Yes      | No    |
| ICO    | Yes   | Yes    | Yes      | Yes   |
| GIF    | Yes   | Yes    | Yes      | Yes   |
| HEIC   | Yes   | No     | —        | —     |

## Quality Presets

| Preset    | JPEG Quality | PNG Compression | WebP Quality |
|-----------|-------------|-----------------|-------------|
| lossless  | 100         | 0               | lossless    |
| high      | 92          | 3               | 85          |
| medium    | 80          | 6               | 85          |
| low       | 50          | 9               | 85          |

## JSON Mode

Add `--json` before the subcommand for machine-readable output:

```bash
python3 -m cli_anything.universal_image_converter.uic_cli --json convert -i photo.jpg -o out/ -f png
```

## Running Tests

```bash
cd agent-harness
python3 -m pytest cli_anything/universal_image_converter/tests/test_core.py -v
python3 -m pytest cli_anything/universal_image_converter/tests/test_full_e2e.py -v
python3 -m pytest cli_anything/universal_image_converter/tests/ -v
```

## Example Workflows

### Convert a photo to WebP

```bash
python3 -m cli_anything.universal_image_converter.uic_cli convert -i photo.jpg -o ./webp/ -f webp -q high
```

### Batch resize and convert

```bash
python3 -m cli_anything.universal_image_converter.uic_cli convert -d ./originals -o ./thumbnails -f jpg -w 800 -h 600 -q medium --overwrite
```

### Probe image metadata

```bash
python3 -m cli_anything.universal_image_converter.uic_cli --json info photo.jpg
```
