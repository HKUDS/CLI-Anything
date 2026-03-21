# Krita CLI

Digital art and painting from the command line via `krita --export` and ZIP-based `.kra` parsing.

## Prerequisites

- Python 3.10+
- `krita` (apt install krita)
- `Pillow` (for canvas creation and filters)
- `click` (CLI framework)

## Install

```bash
pip install click prompt_toolkit Pillow
```

## Commands

```bash
# Get KRA file info
krita_cli info artwork.kra

# Export KRA to PNG
krita_cli export artwork.kra output.png

# List layers
krita_cli layer list artwork.kra

# Export specific layer
krita_cli layer export artwork.kra --index 0 --output layer.png

# Create canvas
krita_cli create --width 1920 --height 1080 --output canvas.png

# Apply filter
krita_cli filter apply input.png output.png --filter blur

# Convert colorspace
krita_cli colorspace convert input.png output.png --space SRGB

# Batch export
krita_cli batch *.kra --output-dir ./exports --format png

# REPL
krita_cli repl
```

## Running Tests

```bash
cd agent-harness
python3 -m pytest cli_anything/krita/tests/ -v
```
