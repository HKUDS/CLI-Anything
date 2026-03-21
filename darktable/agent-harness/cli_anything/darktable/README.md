# Darktable CLI

RAW photo processing from the command line via `darktable-cli`.

## Prerequisites

- Python 3.10+
- `darktable` (apt install darktable)
- `click` (CLI framework)
- `prompt_toolkit` (optional, for REPL)

## Install

```bash
pip install click prompt_toolkit
```

## Commands

```bash
# Export RAW to JPEG
darktable_cli export input.cr2 output.jpg --quality 95

# Get file info
darktable_cli info photo.nef

# Batch export
darktable_cli batch *.cr2 --output-dir ./exports

# List styles
darktable_cli styles list

# Export with style
darktable_cli styles export input.cr2 output.jpg --style "My Style"

# XMP operations
darktable_cli xmp create photo.cr2
darktable_cli xmp apply photo.cr2.xmp photo.cr2 output.jpg

# REPL
darktable_cli repl
```

## Running Tests

```bash
cd agent-harness
python3 -m pytest cli_anything/darktable/tests/ -v
```
