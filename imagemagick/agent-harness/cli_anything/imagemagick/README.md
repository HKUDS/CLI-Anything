# CLI-Anything · ImageMagick

A structured CLI harness wrapping ImageMagick `convert`/`magick` with JSON output, session management, and an interactive REPL.

## Installation

```bash
cd /tmp/CLI-Anything/imagemagick/agent-harness
pip install . --break-system-packages
```

## Usage

```bash
cli-anything-imagemagick --help
cli-anything-imagemagick repl
cli-anything-imagemagick info photo.jpg
cli-anything-imagemagick convert photo.jpg photo.png --width 800
```

## Commands

- `convert` — Convert/format images with options
- `info` — Image metadata
- `resize` — Resize with fit/fill modes
- `crop` — Crop images
- `thumbnail` — Create thumbnails
- `watermark` — Add text watermarks
- `border` — Add borders
- `montage` — Create montages
- `animate` — GIF animation info
- `compare` — Compare two images (RMSE)
- `batch` — Batch process multiple files
