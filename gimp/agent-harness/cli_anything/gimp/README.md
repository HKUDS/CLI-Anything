# GIMP CLI

A stateful command-line interface for image editing, built on Pillow.
Designed for AI agents and power users who need to create and manipulate
images without a GUI.

## Prerequisites

- Python 3.10+
- `Pillow` (image processing)
- `click` (CLI framework)
- `numpy` (blend modes, pixel analysis)

Optional (for interactive REPL):
- `prompt_toolkit`

## Install Dependencies

```bash
pip install Pillow click numpy prompt_toolkit
```

## How to Run

All commands are run from the `agent-harness/` directory.

### One-shot commands

```bash
# Show help
cli-anything-gimp --help

# Create a new project
cli-anything-gimp project new --width 1920 --height 1080 -o my_project.json

# Create with a profile
cli-anything-gimp project new --profile hd720p -o project.json

# Open a project and show info
cli-anything-gimp --project project.json project info

# JSON output (for agent consumption)
cli-anything-gimp --json --project project.json project info
```

### Interactive REPL

```bash
cli-anything-gimp repl
cli-anything-gimp repl --project my_project.json
```

Inside the REPL, type `help` for all available commands.

## Command Reference

### Project

```bash
project new [--width W] [--height H] [--mode RGB|RGBA|L|LA] [--profile P] [-o path]
project open <path>
project save [path]
project info
project profiles
project json
```

Available profiles: `hd1080p`, `hd720p`, `4k`, `square1080`, `a4_300dpi`, `a4_150dpi`,
`letter_300dpi`, `web_banner`, `instagram_post`, `instagram_story`, `twitter_header`,
`youtube_thumb`, `icon_256`, `icon_512`

### Layer

```bash
layer new [--name N] [--type image|text|solid] [--fill F] [--opacity O] [--mode M]
layer add-from-file <path> [--name N] [--position P] [--opacity O] [--mode M]
layer list
layer remove <index>
layer duplicate <index>
layer move <index> --to <position>
layer set <index> <property> <value>
layer flatten
layer merge-down <index>
```

Layer properties: `name`, `opacity` (0.0-1.0), `visible` (true/false),
`mode` (blend mode), `offset_x`, `offset_y`

### Canvas

```bash
canvas info
canvas resize --width W --height H [--anchor center|top-left|...]
canvas scale --width W --height H [--resample lanczos|bicubic|bilinear|nearest]
canvas crop --left L --top T --right R --bottom B
canvas mode <RGB|RGBA|L|LA|CMYK|P>
canvas dpi <value>
```

### Filters

```bash
filter list-available [--category adjustment|blur|stylize|transform]
filter info <name>
filter add <name> [--layer L] [--param key=value ...]
filter remove <index> [--layer L]
filter set <index> <param> <value> [--layer L]
filter list [--layer L]
```

Available filters:
- **Adjustments**: brightness, contrast, saturation, sharpness, autocontrast,
  equalize, invert, posterize, solarize, grayscale, sepia
- **Blur**: gaussian_blur, box_blur, unsharp_mask, smooth
- **Stylize**: find_edges, emboss, contour, detail
- **Transform**: rotate, flip_h, flip_v, resize, crop

### Media

```bash
media probe <file>
media list
media check
media histogram <file>
```

### Export

```bash
export presets
export preset-info <name>
export render <output> [--preset name] [--overwrite] [--quality Q] [--format F]
```

Available presets: `png`, `png-max`, `jpeg-high`, `jpeg-medium`, `jpeg-low`,
`webp`, `webp-lossless`, `tiff`, `tiff-none`, `bmp`, `gif`, `pdf`, `ico`

### Draw

```bash
draw text --layer L --text "Hello" [--x X] [--y Y] [--font F] [--size S] [--color C]
draw rect --layer L --x1 X --y1 Y --x2 X --y2 Y [--fill C] [--outline C]
```

### Session

```bash
session status
session undo
session redo
session history
```

## JSON Mode

Add `--json` before the subcommand for machine-readable output:

```bash
cli-anything-gimp --json --project p.json layer list
```

## Running Tests

```bash
cd agent-harness
python3 -m pytest cli/tests/test_core.py -v        # Unit tests (no images needed)
python3 -m pytest cli/tests/test_full_e2e.py -v     # E2E tests (creates test images)
python3 -m pytest cli/tests/ -v                      # All tests
```

## Example Workflow

```bash
# Create a project
cli-anything-gimp project new --width 1920 --height 1080 --profile hd1080p -o edit.json

# Add an image layer
cli-anything-gimp --project edit.json layer add-from-file photo.jpg --name "Background"

# Apply filters
cli-anything-gimp --project edit.json filter add brightness --layer 0 --param factor=1.2
cli-anything-gimp --project edit.json filter add contrast --layer 0 --param factor=1.1
cli-anything-gimp --project edit.json filter add saturation --layer 0 --param factor=1.3

# Add a text overlay
cli-anything-gimp --project edit.json layer new --type text --name "Title"
cli-anything-gimp --project edit.json draw text --layer 0 --text "My Photo" --size 48 --color "#ffffff"

# View the layer stack
cli-anything-gimp --project edit.json layer list

# Save and render
cli-anything-gimp --project edit.json project save
cli-anything-gimp --project edit.json export render output.jpg --preset jpeg-high --overwrite
```

## Blend Modes

Supported blend modes for layer compositing:
`normal`, `multiply`, `screen`, `overlay`, `soft_light`, `hard_light`,
`difference`, `darken`, `lighten`, `color_dodge`, `color_burn`,
`addition`, `subtract`, `grain_merge`, `grain_extract`
