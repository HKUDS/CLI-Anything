# Blender CLI - Agent Harness

A stateful command-line interface for 3D scene editing, following the same
patterns as the GIMP CLI harness. Uses a JSON scene description format
with bpy script generation for actual Blender rendering.

## Installation

```bash
# From the agent-harness directory:
pip install click prompt_toolkit

# No Blender installation required for scene editing.
# Blender is only needed if you want to execute the generated render scripts.
```

## Quick Start

```bash
# Create a new scene
python3 -m cli.blender_cli scene new --name "MyScene" -o scene.json

# Add objects
python3 -m cli.blender_cli --project scene.json object add cube --name "Box"
python3 -m cli.blender_cli --project scene.json object add sphere --name "Ball" -l 3,0,1

# Create and assign materials
python3 -m cli.blender_cli --project scene.json material create --name "Red" --color 1,0,0,1
python3 -m cli.blender_cli --project scene.json material assign 0 0

# Add modifiers
python3 -m cli.blender_cli --project scene.json modifier add subdivision_surface -o 0 -p levels=2

# Add camera and light
python3 -m cli.blender_cli --project scene.json camera add -l 7,-6,5 -r 63,0,46 --active
python3 -m cli.blender_cli --project scene.json light add sun -r -45,0,30

# Save
python3 -m cli.blender_cli --project scene.json scene save

# Generate render script
python3 -m cli.blender_cli --project scene.json render execute render.png --overwrite

# Execute with Blender (if installed)
blender --background --python /path/to/_render_script.py
```

## JSON Output Mode

All commands support `--json` for machine-readable output:

```bash
python3 -m cli.blender_cli --json scene new -o scene.json
python3 -m cli.blender_cli --json --project scene.json object list
```

## Preview and Live Preview

Blender exposes real preview bundles through the `preview` command group.

```bash
# Capture a real preview bundle
cli-anything-blender --json --project scene.blend-cli.json preview capture --recipe quick

# Query the latest bundle
cli-anything-blender --json --project scene.blend-cli.json preview latest --recipe quick

# Start a poll-mode live preview session
cli-anything-blender --json --project scene.blend-cli.json preview live start --recipe quick --mode poll --source-poll-ms 500

# Query current live-session state
cli-anything-blender --json --project scene.blend-cli.json preview live status --recipe quick
```

The default `quick` recipe produces real Blender-rendered `hero.png` and
`workbench.png` artifacts. Live sessions persist:

- `session.json`
- immutable bundle directories
- `trajectory.json`

Inspect or open published preview state with:

```bash
cli-hub previews inspect /path/to/bundle-or-session
cli-hub previews html /path/to/bundle-or-session -o page.html
cli-hub previews watch /path/to/session --open
cli-hub previews open /path/to/bundle-or-session
```

## Interactive REPL

```bash
python3 -m cli.blender_cli repl
# or with existing project:
python3 -m cli.blender_cli repl --project scene.json
```

## Command Groups

### Scene Management
```
scene new      - Create a new scene
scene open     - Open an existing scene file
scene save     - Save the current scene
scene info     - Show scene information
scene profiles - List available scene profiles
scene json     - Print raw scene JSON
```

### Object Management
```
object add       - Add a primitive (cube, sphere, cylinder, cone, plane, torus, monkey, empty)
object remove    - Remove an object by index
object duplicate - Duplicate an object
object transform - Translate, rotate, or scale an object
object set       - Set an object property
object list      - List all objects
object get       - Get detailed object info
```

### Material Management
```
material create - Create a new Principled BSDF material
material assign - Assign a material to an object
material set    - Set a material property
material list   - List all materials
material get    - Get detailed material info
```

### Modifier Management
```
modifier list-available - List all available modifier types
modifier info           - Show modifier details
modifier add            - Add a modifier to an object
modifier remove         - Remove a modifier
modifier set            - Set a modifier parameter
modifier list           - List modifiers on an object
```

### Camera Management
```
camera add        - Add a camera
camera set        - Set a camera property
camera set-active - Set the active camera
camera list       - List all cameras
```

### Light Management
```
light add  - Add a light (point, sun, spot, area)
light set  - Set a light property
light list - List all lights
```

### Animation
```
animation keyframe        - Set a keyframe on an object
animation remove-keyframe - Remove a keyframe
animation frame-range     - Set the animation frame range
animation fps             - Set the FPS
animation list-keyframes  - List keyframes for an object
```

### Render
```
render settings - Configure render settings
render info     - Show current render settings
render presets  - List available render presets
render execute  - Render the scene (generates bpy script)
render script   - Generate bpy script to stdout
```

### Session
```
session status  - Show session status
session undo    - Undo the last operation
session redo    - Redo the last undone operation
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

# Run with coverage
python3 -m pytest cli/tests/ -v --tb=short
```

## Architecture

```
cli/
├── __init__.py
├── __main__.py           # python3 -m cli.blender_cli
├── blender_cli.py        # Main CLI entry point (Click + REPL)
├── core/
│   ├── __init__.py
│   ├── scene.py          # Scene create/open/save/info
│   ├── objects.py        # 3D object management
│   ├── materials.py      # Material management
│   ├── modifiers.py      # Modifier registry + add/remove/set
│   ├── lighting.py       # Camera and light management
│   ├── animation.py      # Keyframe and timeline management
│   ├── render.py         # Render settings and export
│   └── session.py        # Stateful session, undo/redo
├── utils/
│   ├── __init__.py
│   └── bpy_gen.py        # Blender Python script generation
└── tests/
    ├── __init__.py
    ├── test_core.py      # Unit tests (synthetic data, 100+ tests)
    └── test_full_e2e.py  # E2E tests (script gen, roundtrips, workflows)
```

## JSON Scene Format

The scene is stored as a JSON file with this structure:

```json
{
  "version": "1.0",
  "name": "scene_name",
  "scene": { "fps": 24, "frame_start": 1, "frame_end": 250, ... },
  "render": { "engine": "CYCLES", "resolution_x": 1920, "samples": 128, ... },
  "world": { "background_color": [0.05, 0.05, 0.05], ... },
  "objects": [ { "name": "Cube", "mesh_type": "cube", "location": [0,0,0], ... } ],
  "materials": [ { "name": "Material", "color": [0.8,0.8,0.8,1], ... } ],
  "cameras": [ { "name": "Camera", "focal_length": 50, ... } ],
  "lights": [ { "name": "Light", "type": "POINT", "power": 1000, ... } ],
  "collections": [ { "name": "Collection", "objects": [0, 1] } ],
  "metadata": { "created": "...", "modified": "...", "software": "blender-cli 1.0" }
}
```

## Rendering

Since Blender's `.blend` format is binary, this CLI uses a JSON scene format
and generates Blender Python (bpy) scripts for rendering. The workflow:

1. Edit the scene using CLI commands (creates/modifies JSON)
2. Generate a bpy script with `render execute` or `render script`
3. Run the script with `blender --background --python script.py`

The generated scripts reconstruct the entire scene in Blender and render it.
