# Inkscape CLI - Agent Harness

A stateful command-line interface for vector graphics editing, following the same
patterns as the GIMP and Blender CLI harnesses. Directly manipulates SVG (XML)
documents with a JSON project format for state tracking.

## Installation

```bash
# From the agent-harness directory:
pip install click pillow

# No Inkscape installation required for SVG editing.
# Inkscape is only needed for PDF export and advanced rendering.
```

## Quick Start

```bash
# Create a new document
python3 -m cli.inkscape_cli document new --name "MyDrawing" -o drawing.json

# Add shapes
python3 -m cli.inkscape_cli --project drawing.json shape add-rect --x 100 --y 100 --width 200 --height 150
python3 -m cli.inkscape_cli --project drawing.json shape add-circle --cx 400 --cy 300 --r 80
python3 -m cli.inkscape_cli --project drawing.json shape add-star --cx 700 --cy 300 --points 5 --outer-r 100

# Style objects
python3 -m cli.inkscape_cli --project drawing.json style set-fill 0 "#ff0000"
python3 -m cli.inkscape_cli --project drawing.json style set-stroke 1 "#000000" --width 3

# Add text
python3 -m cli.inkscape_cli --project drawing.json text add --text "Hello World" --x 100 --y 50 --font-size 36

# Transform objects
python3 -m cli.inkscape_cli --project drawing.json transform translate 0 50 --ty 25
python3 -m cli.inkscape_cli --project drawing.json transform rotate 1 45

# Add gradients
python3 -m cli.inkscape_cli --project drawing.json gradient add-linear --color1 "#ff0000" --color2 "#0000ff"
python3 -m cli.inkscape_cli --project drawing.json gradient apply 0 0

# Export
python3 -m cli.inkscape_cli --project drawing.json export svg output.svg --overwrite
python3 -m cli.inkscape_cli --project drawing.json export png output.png --overwrite
```

## JSON Output Mode

All commands support `--json` for machine-readable output:

```bash
python3 -m cli.inkscape_cli --json document new -o doc.json
python3 -m cli.inkscape_cli --json --project doc.json shape list
```

## Interactive REPL

```bash
python3 -m cli.inkscape_cli repl
# or with existing project:
python3 -m cli.inkscape_cli repl --project doc.json
```

## Command Groups

### Document Management
```
document new         - Create a new document
document open        - Open an existing project file
document save        - Save the current project
document info        - Show document information
document profiles    - List available document profiles
document canvas-size - Set canvas dimensions
document units       - Set document units (px, mm, cm, in, pt, pc)
document json        - Print raw project JSON
```

### Shape Management
```
shape add-rect    - Add a rectangle
shape add-circle  - Add a circle
shape add-ellipse - Add an ellipse
shape add-line    - Add a line
shape add-polygon - Add a polygon
shape add-path    - Add an SVG path
shape add-star    - Add a star
shape remove      - Remove a shape by index
shape duplicate   - Duplicate a shape
shape list        - List all shapes
shape get         - Get detailed shape info
```

### Text Management
```
text add  - Add a text element
text set  - Set a text property
text list - List all text objects
```

### Style Management
```
style set-fill        - Set fill color
style set-stroke      - Set stroke color/width
style set-opacity     - Set overall opacity
style set             - Set any style property
style get             - Get an object's style
style list-properties - List available style properties
```

### Transform Operations
```
transform translate - Move an object
transform rotate    - Rotate an object
transform scale     - Scale an object
transform skew-x    - Horizontal skew
transform skew-y    - Vertical skew
transform get       - Get current transform
transform clear     - Clear all transforms
```

### Layer Management
```
layer add         - Add a new layer
layer remove      - Remove a layer
layer move-object - Move object to layer
layer set         - Set layer property
layer list        - List all layers
layer reorder     - Reorder layers
layer get         - Get layer details
```

### Path Operations
```
path union         - Boolean union of two shapes
path intersection  - Boolean intersection
path difference    - Boolean difference (A-B)
path exclusion     - Boolean exclusion (XOR)
path convert       - Convert shape to path
path list-operations - List available operations
```

### Gradient Management
```
gradient add-linear - Add linear gradient
gradient add-radial - Add radial gradient
gradient apply      - Apply gradient to object
gradient list       - List all gradients
```

### Export
```
export png     - Render to PNG (via Pillow)
export svg     - Export as SVG
export pdf     - Export as PDF (needs Inkscape)
export presets - List export presets
```

### Session Management
```
session status  - Show session status
session undo    - Undo last operation
session redo    - Redo last undone operation
session history - Show undo history
```

## Running Tests

```bash
# From the agent-harness directory:

# Run all tests
python3 -m pytest cli/tests/ -v

# Run unit tests only
python3 -m pytest cli/tests/test_core.py -v

# Run E2E tests only
python3 -m pytest cli/tests/test_full_e2e.py -v

# Run with short traceback
python3 -m pytest cli/tests/ -v --tb=short
```

## Architecture

```
cli/
├── __init__.py
├── __main__.py            # python3 -m cli.inkscape_cli
├── inkscape_cli.py        # Main CLI entry point (Click + REPL)
├── core/
│   ├── __init__.py
│   ├── document.py        # Document create/open/save/info, SVG generation
│   ├── shapes.py          # Shape operations (rect, circle, path, star, etc.)
│   ├── text.py            # Text element management
│   ├── styles.py          # CSS style management (fill, stroke, opacity)
│   ├── transforms.py      # Transform operations (translate, rotate, scale)
│   ├── layers.py          # Layer/group management
│   ├── paths.py           # Path boolean operations (union, diff, etc.)
│   ├── gradients.py       # Gradient management (linear, radial)
│   ├── export.py          # Export (PNG via Pillow, SVG, PDF)
│   └── session.py         # Stateful session with undo/redo
├── utils/
│   ├── __init__.py
│   └── svg_utils.py       # SVG XML helpers, namespace constants
└── tests/
    ├── __init__.py
    ├── test_core.py        # Unit tests (100+ tests, synthetic data)
    └── test_full_e2e.py    # E2E tests (SVG validation, workflows, CLI)
```

## Key Design: Direct SVG Manipulation

Since SVG is XML, we directly manipulate the document structure:

- **JSON project file** (.inkscape-cli.json) tracks all objects, layers, gradients,
  and metadata for state management and undo/redo.
- **SVG file** is generated from the project state on export, producing valid SVG
  that can be opened in Inkscape, browsers, or any SVG viewer.
- **Inkscape namespaces** (inkscape:, sodipodi:) are included for compatibility
  with Inkscape's layer system and other features.

This means no binary format parsing is needed -- everything is human-readable
XML and JSON.
