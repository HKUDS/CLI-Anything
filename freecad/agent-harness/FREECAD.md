# FreeCAD CLI Harness — Standard Operating Procedure

## Software Overview

**FreeCAD** is an open-source parametric 3D CAD modeler built on OpenCASCADE (OCCT).
It supports Part design, Sketcher, Assembly, TechDraw, Mesh, and many other workbenches.

**This harness targets FreeCAD 1.1** (released March 2026) with 258 commands across 18 workbench groups.

- **Backend engine**: OpenCASCADE Technology (OCCT)
- **Native format**: `.FCStd` (ZIP containing `Document.xml` + BREP geometry files)
- **Python API**: `FreeCAD` (`App`) module — full document/object manipulation
- **Headless mode**: `freecadcmd` or `freecad -c` — runs without GUI
- **Macro execution**: `freecadcmd script.py` — executes Python macro headlessly
- **Export formats**: STEP, IGES, STL, OBJ, DXF, SVG, PDF (via TechDraw)

## Architecture

```
┌──────────────────────────────────────────────────────┐
│  cli-anything-freecad (CLI + REPL)                   │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │ document.py   │  │ parts.py     │  │ sketch.py  │ │
│  │ create/save   │  │ primitives   │  │ 2D shapes  │ │
│  └──────────────┘  └──────────────┘  └────────────┘ │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │ body.py       │  │ materials.py │  │ export.py  │ │
│  │ pad/pocket    │  │ PBR mats     │  │ STEP/STL   │ │
│  └──────────────┘  └──────────────┘  └────────────┘ │
│  ┌──────────────┐                                    │
│  │ session.py    │  ← undo/redo, state management    │
│  └──────────────┘                                    │
├──────────────────────────────────────────────────────┤
│  freecad_macro_gen.py — generates FreeCAD macros     │
│  freecad_backend.py   — invokes FreeCAD headless     │
├──────────────────────────────────────────────────────┤
│  FreeCAD (freecadcmd) — the REAL software            │
│  OpenCASCADE — geometry kernel                       │
└──────────────────────────────────────────────────────┘
```

## Data Model

The CLI maintains project state as a JSON document:

```json
{
    "version": "1.0",
    "name": "my_project",
    "units": "mm",
    "parts": [
        {
            "id": 0,
            "name": "Box",
            "type": "box",
            "params": {"length": 10, "width": 10, "height": 10},
            "placement": {"position": [0, 0, 0], "rotation": [0, 0, 0]},
            "material_index": null,
            "visible": true
        }
    ],
    "sketches": [],
    "bodies": [],
    "materials": [],
    "metadata": {
        "created": "2026-03-22T...",
        "modified": "2026-03-22T...",
        "software": "cli-anything-freecad 1.1.0"
    }
}
```

## Command Groups

| Group      | Commands                                              |
|------------|-------------------------------------------------------|
| `document` | new, open, save, info, profiles                       |
| `part`     | add, remove, list, get, transform, boolean            |
| `sketch`   | new, add-line, add-circle, add-rect, constrain, close |
| `body`     | new, pad, pocket, fillet, chamfer, list                |
| `material` | create, assign, list, set                             |
| `export`   | render, info, presets                                  |
| `session`  | undo, redo, status, history                           |
| `draft`    | wire, rectangle, circle, polygon, fillet-2d, shapestring, ... |
| `assembly` | new, add-part, constrain, solve, insert-part, create-simulation, ... |
| `techdraw` | new-page, add-view, add-annotation, export-pdf, ... |
| `mesh`     | import, from-shape, export, repair, decimate, ... |
| `fem`      | new-analysis, mesh-generate, solve, add-beam-section, add-tie, ... |
| `cam`      | new-job, add-profile, add-tapping, set-tool, generate-gcode, ... |
| `measure`  | distance, length, angle, area, volume, check-geometry, ... |
| `import`   | auto, step, iges, stl, obj, dxf, brep, 3mf, ... |
| `surface`  | filling, sections, extend, blend-curve, sew, cut |
| `spread`   | new, set-cell, get-cell, set-alias, import-csv, export-csv |

## FreeCAD 1.1 Changes

### Breaking: Datum/Origin Redesign
FreeCAD 1.1 replaces the legacy `Origin` object with `LocalCoordinateSystem`.
Use `body local-coordinate-system` to create configurable coordinate systems
with cross-workbench attachment support. Datum planes, lines, and points now
support `--attachment-mode` and `--attachment-refs` for flexible positioning.

**Note:** Files created with FreeCAD 1.1 are NOT backward-compatible with 1.0.

### New Features by Workbench
- **PartDesign**: Whitworth threads (BSW/BSF/BSP/NPT), tapered holes, feature freeze toggle
- **Assembly**: Inline part insertion, joint motion simulation
- **CAM**: G84/G74 tapping, multi-pass profiles, new tool library system
- **FEM**: Netgen refinement, beam sections (box/elliptical), tie constraints, result purging
- **Sketcher**: Projection/reference modes, plane intersection, face-based external geometry
- **Draft**: Edge-selective fillet, relative font paths
- **TechDraw**: Area annotations with hole accounting, shape validation
- **Measure**: Enhanced check-geometry with valid entries, additive measurements

## Rendering Pipeline

1. **Build JSON state** via CLI commands (document, part, sketch, body, material)
2. **Generate FreeCAD macro** from JSON state (`freecad_macro_gen.py`)
3. **Execute macro headlessly** via `freecadcmd script.py`
4. **Export output** (STEP, IGES, STL, OBJ) from the generated `.FCStd` document
5. **Verify output** (file exists, size > 0, correct format magic bytes)

## FreeCAD Python API Reference

```python
import FreeCAD
import Part

# Document management
doc = FreeCAD.newDocument("MyProject")
doc.saveAs("/path/to/project.FCStd")

# Primitives
box = doc.addObject("Part::Box", "MyBox")
box.Length = 10
box.Width = 10
box.Height = 10

cyl = doc.addObject("Part::Cylinder", "MyCylinder")
cyl.Radius = 5
cyl.Height = 20

sphere = doc.addObject("Part::Sphere", "MySphere")
sphere.Radius = 10

cone = doc.addObject("Part::Cone", "MyCone")
cone.Radius1 = 10
cone.Radius2 = 5
cone.Height = 15

torus = doc.addObject("Part::Torus", "MyTorus")
torus.Radius1 = 10
torus.Radius2 = 3

# Boolean operations
cut = doc.addObject("Part::Cut", "Cut")
cut.Base = box
cut.Tool = cyl

fuse = doc.addObject("Part::Fuse", "Fuse")
fuse.Base = box
fuse.Tool = cyl

common = doc.addObject("Part::Common", "Common")
common.Base = box
common.Tool = cyl

# Placement
import FreeCAD
box.Placement = FreeCAD.Placement(
    FreeCAD.Vector(x, y, z),
    FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), angle_degrees)
)

# Export
Part.export([box, cyl], "/path/to/output.step")
Part.export([box], "/path/to/output.stl")

# Recompute
doc.recompute()
```

## Dependencies

- **FreeCAD** (system package) — HARD DEPENDENCY
  - Windows: Download from freecad.org
  - Linux: `apt install freecad` or `snap install freecad`
  - macOS: `brew install --cask freecad`
- **Python 3.10+**
- **click** >= 8.0 (CLI framework)
- **prompt-toolkit** >= 3.0 (REPL)
