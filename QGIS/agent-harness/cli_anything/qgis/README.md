# cli-anything-qgis

A stateful CLI harness for QGIS that uses the real QGIS runtime.

## What it does

- manages `.qgs` / `.qgz` projects with PyQGIS
- creates writable GeoPackage-backed vector layers
- adds and inspects features with WKT geometry
- authors simple print layouts
- exports layouts through `qgis_process --json`
- exposes generic QGIS processing discovery and execution
- supports machine-readable `--json` output for every command
- starts a stateful REPL when run without a subcommand

## Runtime model

This harness deliberately splits responsibilities:

- **PyQGIS** handles project, layer, feature, and layout authoring
- **`qgis_process --json`** handles generic processing and layout export algorithms

That keeps authoring stateful while still using QGIS' existing processing CLI for backend execution.

## Prerequisites

- QGIS installed with `qgis_process` on `PATH`
- PyQGIS importable from the same Python used to run this package
- Python 3.10+

Quick checks:

```bash
qgis_process --version
python3 -c "from qgis.core import QgsApplication; print('pyqgis-ok')"
```

## Installation

```bash
cd QGIS/agent-harness
python3 -m pip install -e .
```

If PyQGIS comes from your system packages, a plain virtual environment may not see the `qgis` Python module. In that case, create the environment with system site packages enabled before installing:

```bash
python3 -m venv --system-site-packages .venv
. .venv/bin/activate
python3 -m pip install -e .
```

Verify:

```bash
which cli-anything-qgis
cli-anything-qgis --help
cli-anything-qgis --json process help native:printlayouttopdf
```

## Agent guidance

Prefer `--json` unless a human-readable summary is specifically more useful.

## More docs

- architecture note: [`../../QGIS.md`](../../QGIS.md)
- Chinese walkthrough and real-data tutorial: [`../../TUTORIAL.md`](../../TUTORIAL.md)

## Usage

### One-shot commands

```bash
# Create a project
cli-anything-qgis --json project new -o demo.qgz --title "Demo" --crs EPSG:4326

# Create a writable layer in the project's sidecar GeoPackage
cli-anything-qgis --json --project demo.qgz layer create-vector \
  --name places \
  --geometry point \
  --field name:string \
  --field score:int

# Add features by WKT
cli-anything-qgis --json --project demo.qgz feature add \
  --layer places \
  --wkt "POINT(1 2)" \
  --attr name=HQ \
  --attr score=5

# Create a layout and add items
cli-anything-qgis --json --project demo.qgz layout create --name Main
# Auto extent should work even for point-only projects; pass --extent only when you want explicit framing.
cli-anything-qgis --json --project demo.qgz layout add-map --layout Main --x 10 --y 20 --width 180 --height 120
cli-anything-qgis --json --project demo.qgz layout add-label --layout Main --text "Demo map" --x 10 --y 8 --width 120 --height 10

# Export through the real QGIS backend
cli-anything-qgis --json --project demo.qgz export pdf output.pdf --layout Main --overwrite
cli-anything-qgis --json --project demo.qgz export image output.png --layout Main --overwrite

# Inspect processing algorithms
cli-anything-qgis --json process list
cli-anything-qgis --json process help native:buffer
cli-anything-qgis --json --project demo.qgz process run native:buffer \
  --param INPUT=places \
  --param DISTANCE=10 \
  --param SEGMENTS=8 \
  --param END_CAP_STYLE=0 \
  --param JOIN_STYLE=0 \
  --param MITER_LIMIT=2 \
  --param DISSOLVE=false \
  --param OUTPUT=/tmp/buffer.gpkg
```

### REPL

Run without arguments:

```bash
cli-anything-qgis
```

Example session:

```text
project new -o demo.qgz --title "Demo"
layer create-vector --name places --geometry point --field name:string
feature add --layer places --wkt "POINT(1 2)" --attr name=HQ
layout create --name Main
layout add-map --layout Main --x 10 --y 20 --width 180 --height 120
export pdf demo.pdf --layout Main --overwrite
session status
quit
```

## Command groups

### `project`
- `new` — create a new project and save it immediately
- `open` — open an existing project
- `save` — save the active project
- `info` — inspect the current project
- `set-crs` — change project CRS

### `layer`
- `create-vector` — create a GeoPackage-backed vector layer
- `list` — list project layers
- `info` — inspect one layer
- `remove` — remove a layer from the project

### `feature`
- `add` — add a feature with WKT geometry and `key=value` attrs
- `list` — inspect features from a layer

### `layout`
- `create` — create a print layout
- `list` — list layouts
- `info` — inspect one layout
- `remove` — remove a layout
- `add-map` — add a map item
- `add-label` — add a text label item

### `export`
- `presets` — list supported export modes
- `pdf` — export a layout as PDF
- `image` — export a layout as an image

### `process`
- `list` — list installed processing algorithms
- `help` — inspect algorithm parameters and outputs
- `run` — execute a processing algorithm with repeatable `--param KEY=VALUE`

### `session`
- `status` — inspect current session state
- `history` — inspect recent command history

## Testing

```bash
python3 -m pytest cli_anything/qgis/tests/test_core.py -v
python3 -m pytest cli_anything/qgis/tests/test_full_e2e.py -v -s
```
