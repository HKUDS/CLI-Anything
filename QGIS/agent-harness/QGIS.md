# QGIS harness architecture notes

This harness targets the real QGIS runtime already present on the machine and follows the cli-anything harness model: keep authoring state inside a long-lived Python process, and use existing backend CLIs where QGIS already exposes them cleanly.

## Backend split

### PyQGIS for stateful authoring

Use PyQGIS for operations that mutate or inspect in-memory project state:

- project create/open/save
- project CRS/title updates
- writable vector layer creation
- feature insertion
- layout creation and item authoring
- project/layer/layout summaries for CLI output

Key APIs and source references:

- `QgsApplication`
  - `QGIS/src/core/qgsapplication.h`
  - `QGIS/src/core/qgsapplication.cpp`
- `QgsProject`
  - `QGIS/src/core/project/qgsproject.h`
  - `QGIS/src/core/project/qgsproject.cpp`
- `QgsPrintLayout` / layout items
  - runtime API surfaced via PyQGIS
- `QgsLayoutExporter`
  - `QGIS/src/core/layout/qgslayoutexporter.h`

### `qgis_process --json` for processing and export

Use `qgis_process --json` for operations that already exist as stable QGIS processing algorithms:

- algorithm discovery (`list`)
- algorithm help (`help <id>`)
- generic algorithm execution (`run <id>`)
- layout PDF export (`native:printlayouttopdf`)
- layout image export (`native:printlayouttoimage`)

Key references:

- process CLI entrypoint
  - `QGIS/src/process/main.cpp`
  - `QGIS/src/process/qgsprocess.cpp`
  - `QGIS/src/process/qgsprocess.h`
- layout export algorithms
  - `QGIS/src/analysis/processing/qgsalgorithmlayouttopdf.cpp`
  - `QGIS/src/analysis/processing/qgsalgorithmlayouttoimage.cpp`
- exporter tests/examples
  - `QGIS/tests/src/python/test_qgslayoutexporter.py`

## Why this split

PyQGIS is the right layer for commands that need live project state across multiple commands in a REPL. `qgis_process` is the right layer for processing algorithms because QGIS already ships a supported CLI contract, including JSON output and algorithm metadata.

This keeps the harness close to QGIS instead of reimplementing backend logic in Python.

## How the harness was surveyed

This harness was not generated automatically from `QGIS/src`. The command groups were chosen by surveying QGIS' stable runtime surfaces and then wrapping a narrow, testable subset.

- `project`, `layer`, `feature`, and `layout` wrap PyQGIS authoring surfaces that need live project state
- `export` and `process` wrap stable `qgis_process --json` surfaces instead of reimplementing algorithms in Python
- `session` is harness-local ergonomics for REPL/history tracking, not a native QGIS feature

This also explains the current boundaries:

- the harness intentionally exposes a small layout surface instead of the full desktop layout system
- the harness can run processing algorithms directly against shapefiles and other datasource paths
- the harness does not currently provide a first-class command to add an arbitrary existing shapefile into a project

## Data model choices

### Projects

Projects are saved immediately to `.qgz` or `.qgs` paths. The harness normalizes bare output names to `.qgz` by default.

### Writable layers

New vector layers are created as project-side GeoPackage layers instead of ephemeral memory layers. The default datastore is derived from the project path:

- `<project>.qgz` -> `<project>_data.gpkg`

This keeps authored data on disk and makes subsequent processing/export commands work against real datasets.

### Features

Feature insertion accepts:

- WKT geometry
- repeatable `--attr key=value`

Attributes are coerced against the declared QGIS field types so CLI input remains simple while the stored layer schema stays authoritative.

### Layouts

The harness only implements a narrow but useful layout surface in v1:

- create/remove/list layouts
- add map items
- add label items
- derive map extent from current project layers when no explicit extent is given

## Session model

The CLI maintains lightweight session state for:

- current project path
- modified flag reporting
- command history

The REPL is the default mode when no subcommand is passed. One-shot commands can still use `--project` to bind a command to a saved project path.

## Output model

Every command supports a stable JSON shape through `--json`. Human-readable output is intentionally secondary; agent-facing usage should prefer JSON.

## Testing strategy

The test suite should cover three layers:

1. direct module tests against PyQGIS helpers
2. real E2E flows against the actual QGIS runtime
3. subprocess tests against the installed `cli-anything-qgis` executable

That combination checks both the library layer and the packaging/runtime contract.
