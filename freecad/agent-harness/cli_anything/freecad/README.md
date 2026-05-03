# cli-anything-freecad

CLI harness for **FreeCAD** parametric 3D CAD modeler. Create, modify, and export
3D models from the command line or via AI agents — no GUI needed.

## Prerequisites

**FreeCAD >= 1.0.2** must be installed on your system. The CLI generates FreeCAD
Python macros and executes them headlessly via `freecadcmd`.  FreeCAD 1.1+ is
recommended for the full feature set.

- **Windows**: Download from [freecad.org](https://www.freecad.org/downloads.php)
- **Linux**: `sudo apt install freecad` or `snap install freecad`
- **macOS**: `brew install --cask freecad`

Verify installation:
```bash
freecadcmd --version
```

### Version Compatibility

The harness auto-detects the installed FreeCAD version.  Commands that require
FreeCAD 1.1 (e.g., `body local-coordinate-system`, `cam add-tapping`,
`fem add-tie`) will produce a clear error on older versions.

## Installation

```bash
cd freecad/agent-harness
pip install -e .
```

Verify:
```bash
cli-anything-freecad --help
```

## Quick Start

### One-shot commands
```bash
# Create a new document
cli-anything-freecad document new --name "MyPart" -o project.json

# Add a box
cli-anything-freecad -p project.json part add box --name "Base" -P length=20 -P width=15 -P height=5

# Add a cylinder
cli-anything-freecad -p project.json part add cylinder --name "Hole" -P radius=3 -P height=10 --position 10,7.5,0

# Boolean cut (subtract cylinder from box)
cli-anything-freecad -p project.json part boolean cut 0 1 --name "BaseWithHole"

# Export to STEP
cli-anything-freecad -p project.json export render output.step --preset step
```

### Interactive REPL
```bash
cli-anything-freecad
# or with a project:
cli-anything-freecad -p project.json
```

### JSON output for agents
```bash
cli-anything-freecad --json document new --name "AgentProject" -o project.json
cli-anything-freecad --json -p project.json part add box
cli-anything-freecad --json -p project.json export render output.step
```

## Preview and Motion

FreeCAD supports both truthful preview bundles and final motion rendering.

```bash
# Capture a real 4-view preview bundle
cli-anything-freecad --json -p project.json preview capture --recipe quick

# Start poll-mode live preview
cli-anything-freecad --json -p project.json preview live start --recipe quick --mode poll --source-poll-ms 500

# Query current live status without rendering
cli-anything-freecad --json -p project.json preview live status --recipe quick

# Render a final motion sequence
cli-anything-freecad --json -p project.json motion render-video spin output.mp4
```

The preview side publishes `session.json`, immutable bundle dirs, and
`trajectory.json`. The default bundle includes `hero.png`, `front.png`,
`top.png`, and `right.png`.

Inspect/open the published previews with:

```bash
cli-hub previews inspect /path/to/bundle-or-session
cli-hub previews html /path/to/bundle-or-session -o page.html
cli-hub previews watch /path/to/session --open
cli-hub previews open /path/to/bundle-or-session
```

## Command Groups

| Group | Description |
|-------|-------------|
| `document` | Create, open, save, inspect documents |
| `part` | Add/remove 3D primitives, transform, boolean ops |
| `sketch` | Create 2D sketches with lines, circles, arcs, constraints |
| `body` | PartDesign bodies — pad, pocket, fillet, chamfer, revolution |
| `material` | Create and assign PBR materials |
| `export` | Export to STEP, IGES, STL, OBJ, BREP, FCStd |
| `session` | Undo/redo, status, history |

## Supported Primitives

Box, Cylinder, Sphere, Cone, Torus, Wedge

## Supported Export Formats

| Preset | Format | Description |
|--------|--------|-------------|
| `step` | .step | STEP AP214 (ISO 10303) — standard CAD exchange |
| `iges` | .iges | IGES format |
| `stl` | .stl | STL mesh (3D printing) |
| `stl_fine` | .stl | Fine-mesh STL |
| `obj` | .obj | Wavefront OBJ |
| `brep` | .brep | OpenCASCADE BREP |
| `fcstd` | .FCStd | Native FreeCAD document |

## Running Tests

```bash
cd freecad/agent-harness
python -m pytest cli_anything/freecad/tests/ -v -s
```

Force installed command testing:
```bash
CLI_ANYTHING_FORCE_INSTALLED=1 python -m pytest cli_anything/freecad/tests/ -v -s
```
