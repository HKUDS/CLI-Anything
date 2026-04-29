---
name: cli-anything-qgis
description: Stateful QGIS CLI for projects, writable layers, features, layouts, exports, and qgis_process operations using the real QGIS runtime.
---

# cli-anything-qgis

Use this skill when you need to inspect or modify QGIS projects from the terminal through the real QGIS runtime.

## Requirements

- QGIS installed with `qgis_process` on `PATH`
- PyQGIS importable from the Python environment running the CLI
- Python 3.10+

## Agent guidance

- Prefer `--json` for all machine-driven use.
- For one-shot commands, pass `--project <path>` when operating on an existing project.
- Running `cli-anything-qgis` with no subcommand starts a stateful REPL.
- Layout export is backed by real QGIS processing algorithms:
  - `native:printlayouttopdf`
  - `native:printlayouttoimage`

## What this CLI covers

- create, open, save, and inspect `.qgs` / `.qgz` projects
- create writable GeoPackage-backed vector layers
- add features via WKT geometry and typed `key=value` attributes
- create print layouts and add map/label items
- export layouts to PDF or image
- inspect and run generic `qgis_process` algorithms
- inspect session status and history

## Command groups

### `project`
- `new -o/--output [--title] [--crs]`
- `open PATH`
- `save [PATH]`
- `info`
- `set-crs CRS`

### `layer`
- `create-vector --name --geometry --crs [--field name:type ...]`
- `list`
- `info LAYER`
- `remove LAYER`

### `feature`
- `add --layer LAYER --wkt WKT [--attr key=value ...]`
- `list --layer LAYER [--limit N]`

### `layout`
- `create --name [--page-size] [--orientation]`
- `list`
- `info LAYOUT`
- `remove LAYOUT`
- `add-map --layout LAYOUT --x --y --width --height [--extent xmin,ymin,xmax,ymax]`
- `add-label --layout LAYOUT --text TEXT --x --y --width --height [--font-size N]`

### `export`
- `presets`
- `pdf OUTPUT --layout LAYOUT [--dpi] [--force-vector] [--force-raster] [--georeference/--no-georeference] [--overwrite]`
- `image OUTPUT --layout LAYOUT [--dpi] [--overwrite]`

### `process`
- `list`
- `help ALGORITHM_ID`
- `run ALGORITHM_ID [--param KEY=VALUE ...]`

### `session`
- `status`
- `history [--limit N]`

## Examples

### Create a project and add a writable layer

```bash
cli-anything-qgis --json project new -o demo.qgz --title "Demo" --crs EPSG:4326
cli-anything-qgis --json --project demo.qgz layer create-vector \
  --name places \
  --geometry point \
  --field name:string \
  --field score:int
```

### Add features and inspect them

```bash
cli-anything-qgis --json --project demo.qgz feature add \
  --layer places \
  --wkt "POINT(1 2)" \
  --attr name=HQ \
  --attr score=5

cli-anything-qgis --json --project demo.qgz feature list --layer places --limit 10
```

### Create and export a layout

```bash
cli-anything-qgis --json --project demo.qgz layout create --name Main
cli-anything-qgis --json --project demo.qgz layout add-map --layout Main --x 10 --y 20 --width 180 --height 120
cli-anything-qgis --json --project demo.qgz layout add-label --layout Main --text "Demo map" --x 10 --y 8 --width 100 --height 10
cli-anything-qgis --json --project demo.qgz export pdf output.pdf --layout Main --overwrite
```

### Inspect or run processing algorithms

```bash
cli-anything-qgis --json process help native:buffer
cli-anything-qgis --json --project demo.qgz process run native:buffer \
  --param INPUT=/tmp/demo_data.gpkg|layername=places \
  --param DISTANCE=1 \
  --param SEGMENTS=8 \
  --param END_CAP_STYLE=0 \
  --param JOIN_STYLE=0 \
  --param MITER_LIMIT=2 \
  --param DISSOLVE=false \
  --param OUTPUT=/tmp/buffer.geojson
```

### REPL

```bash
cli-anything-qgis
```

Example interactive flow:

```text
project new -o demo.qgz --title "Demo"
layer create-vector --name places --geometry point --field name:string
feature add --layer places --wkt "POINT(1 2)" --attr name=HQ
layout create --name Main
session status
quit
```
