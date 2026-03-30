---
name: "cli-anything-freecad"
description: "Complete CLI harness for FreeCAD parametric 3D CAD modeler (258 commands). Covers ALL workbenches: Part (29 primitives + boolean + mirror + loft + sweep), Sketcher (26 cmds: geometry + constraints + editing), PartDesign (38 cmds: pad/pocket/groove/fillet/chamfer/patterns/hole/datum), Assembly (11 cmds), Mesh (16 cmds), TechDraw (15 cmds: views + dimensions + PDF/SVG), Draft (33 cmds: 2D shapes + arrays + transforms), FEM (12 cmds), CAM/CNC (10 cmds), Surface (6 cmds), Spreadsheet (7 cmds), Import (13 formats), Export (17 formats), Measure (12 cmds), Materials (21 presets). Headless FreeCAD export to STEP/IGES/STL/OBJ/DXF/PDF/glTF/3MF."
---

# cli-anything-freecad

Complete CLI harness for **FreeCAD** — 258 commands across 17 groups covering ALL workbenches.

## Prerequisites

FreeCAD >= 1.0.2 must be installed: `freecadcmd` must be in PATH.
FreeCAD 1.1+ recommended for full feature set (LocalCoordinateSystem,
tapping, tie constraints, etc.).

## Installation

```bash
pip install -e freecad/agent-harness
```

## Basic Usage

```bash
cli-anything-freecad --json <command>           # JSON output for agents
cli-anything-freecad --json -p proj.json <cmd>  # With project file
cli-anything-freecad                            # Interactive REPL
```

## Command Groups (258 commands)

### document (5) — Document management
```bash
cli-anything-freecad --json document new --name "Part" -o proj.json
cli-anything-freecad --json document new --profile print3d -o proj.json
cli-anything-freecad --json -p proj.json document info
cli-anything-freecad --json -p proj.json document save -o copy.json
cli-anything-freecad --json document profiles
```

### part (29) — 3D primitives, boolean, transforms, operations
```bash
# Primitives: box, cylinder, sphere, cone, torus, wedge, helix, spiral, thread, plane, polygon_3d
cli-anything-freecad --json -p p.json part add box -P length=20 -P width=15 -P height=5
cli-anything-freecad --json -p p.json part add cylinder -P radius=3 -P height=10 --position 10,7.5,0

# Operations
cli-anything-freecad --json -p p.json part boolean cut 0 1
cli-anything-freecad --json -p p.json part copy 0
cli-anything-freecad --json -p p.json part mirror 0 --plane XY
cli-anything-freecad --json -p p.json part scale 0 --factor 2.0
cli-anything-freecad --json -p p.json part loft --indices 0,1,2
cli-anything-freecad --json -p p.json part sweep 0 1
cli-anything-freecad --json -p p.json part revolve 0 --axis Z --angle 360
cli-anything-freecad --json -p p.json part extrude 0 --direction 0,0,1 --length 10
cli-anything-freecad --json -p p.json part fillet-3d 0 --radius 2
cli-anything-freecad --json -p p.json part thickness 0 --thickness 1
cli-anything-freecad --json -p p.json part compound --indices 0,1,2
cli-anything-freecad --json -p p.json part section 0 --plane XY
cli-anything-freecad --json -p p.json part info 0
cli-anything-freecad --json -p p.json part line-3d --start 0,0,0 --end 10,5,0
cli-anything-freecad --json -p p.json part wire --points "0,0,0;10,0,0;10,10,0"
```

### sketch (26) — 2D constrained sketching
```bash
cli-anything-freecad --json -p p.json sketch new --plane XY
cli-anything-freecad --json -p p.json sketch add-line 0 --start 0,0 --end 20,0
cli-anything-freecad --json -p p.json sketch add-circle 0 --center 10,10 --radius 5
cli-anything-freecad --json -p p.json sketch add-rect 0 --corner 0,0 --width 20 --height 15
cli-anything-freecad --json -p p.json sketch add-arc 0 --center 0,0 --radius 5
cli-anything-freecad --json -p p.json sketch add-ellipse 0 --center 0,0 --major-radius 10 --minor-radius 5
cli-anything-freecad --json -p p.json sketch add-polygon 0 --center 0,0 --sides 6 --radius 10
cli-anything-freecad --json -p p.json sketch add-bspline 0 --points "0,0;5,10;10,0;15,10"
cli-anything-freecad --json -p p.json sketch add-slot 0 --center1 0,0 --center2 10,0 --radius 2
cli-anything-freecad --json -p p.json sketch constrain 0 distance --elements 0,1 --value 10
cli-anything-freecad --json -p p.json sketch edit-element 0 0 --radius 8
cli-anything-freecad --json -p p.json sketch remove-element 0 2
cli-anything-freecad --json -p p.json sketch validate 0
cli-anything-freecad --json -p p.json sketch solve-status 0
# Constraints: coincident, horizontal, vertical, parallel, perpendicular, equal,
#   fixed, distance, angle, radius, tangent, symmetric, block, diameter,
#   point_on_object, distance_x, distance_y
```

### body (38) — PartDesign features
```bash
cli-anything-freecad --json -p p.json body new
cli-anything-freecad --json -p p.json body pad 0 0 --length 10
cli-anything-freecad --json -p p.json body pocket 0 1 --length 5
cli-anything-freecad --json -p p.json body groove 0 0 --angle 360
cli-anything-freecad --json -p p.json body fillet 0 --radius 2
cli-anything-freecad --json -p p.json body chamfer 0 --size 1.5
cli-anything-freecad --json -p p.json body revolution 0 0 --angle 360
cli-anything-freecad --json -p p.json body additive-loft 0 --sketch-indices 0,1
cli-anything-freecad --json -p p.json body additive-pipe 0 0 1
cli-anything-freecad --json -p p.json body additive-helix 0 0 --pitch 5 --height 20
cli-anything-freecad --json -p p.json body additive-box 0 -P length=10 -P width=10 -P height=10
cli-anything-freecad --json -p p.json body hole 0 0 --diameter 5 --depth 10 --threaded
cli-anything-freecad --json -p p.json body draft-feature 0 --angle 5
cli-anything-freecad --json -p p.json body thickness-feature 0 --thickness 1
cli-anything-freecad --json -p p.json body linear-pattern 0 --occurrences 5 --length 50
cli-anything-freecad --json -p p.json body polar-pattern 0 --occurrences 6 --angle 360
cli-anything-freecad --json -p p.json body mirrored 0 --plane XY
cli-anything-freecad --json -p p.json body datum-plane 0 --reference XY --offset 10
```

### material (8) — PBR materials with engineering properties
```bash
# 21 presets: steel, aluminum, copper, brass, titanium, stainless_steel, cast_iron,
#   carbon_fiber, nylon, abs, pla, petg, plastic_white, plastic_black, wood, glass,
#   rubber, gold, concrete, granite, marble
cli-anything-freecad --json -p p.json material create --preset steel
cli-anything-freecad --json -p p.json material create --preset titanium
cli-anything-freecad --json -p p.json material assign 0 0
cli-anything-freecad --json -p p.json material set 0 density 7800
cli-anything-freecad --json -p p.json material import-material mat.json
cli-anything-freecad --json -p p.json material export-material 0 --output mat.json
```

### assembly (11) — Assembly management
```bash
cli-anything-freecad --json -p p.json assembly new --name "MyAssembly"
cli-anything-freecad --json -p p.json assembly add-part 0 0
cli-anything-freecad --json -p p.json assembly constrain 0 coincident --components 0,1
cli-anything-freecad --json -p p.json assembly constrain 0 distance --components 0,1 --distance 10
cli-anything-freecad --json -p p.json assembly solve 0
cli-anything-freecad --json -p p.json assembly dof 0
cli-anything-freecad --json -p p.json assembly bom 0
cli-anything-freecad --json -p p.json assembly explode 0 --factor 2.0
# Constraints: fixed, coincident, distance, angle, parallel, perpendicular,
#   tangent, revolute, prismatic, cylindrical, ball, planar, gear, belt
```

### mesh (16) — Mesh operations
```bash
cli-anything-freecad --json -p p.json mesh from-shape 0 --deviation 0.1
cli-anything-freecad --json -p p.json mesh import path/to/model.stl
cli-anything-freecad --json -p p.json mesh export 0 output.stl --format stl
cli-anything-freecad --json -p p.json mesh boolean union 0 1
cli-anything-freecad --json -p p.json mesh decimate 0 --target-faces 1000
cli-anything-freecad --json -p p.json mesh smooth 0 --iterations 5
cli-anything-freecad --json -p p.json mesh repair 0
cli-anything-freecad --json -p p.json mesh to-shape 0
```

### techdraw (15) — Technical drawings
```bash
cli-anything-freecad --json -p p.json techdraw new-page
cli-anything-freecad --json -p p.json techdraw add-view 0 0 --direction 0,0,1 --scale 1.0
cli-anything-freecad --json -p p.json techdraw add-projection-group 0 0
cli-anything-freecad --json -p p.json techdraw add-section-view 0 0
cli-anything-freecad --json -p p.json techdraw add-dimension 0 0 length --references 0,1
cli-anything-freecad --json -p p.json techdraw add-annotation 0 "Note text"
cli-anything-freecad --json -p p.json techdraw export-pdf 0 drawing.pdf
cli-anything-freecad --json -p p.json techdraw export-svg 0 drawing.svg
```

### draft (33) — 2D drafting
```bash
cli-anything-freecad --json -p p.json draft wire --points "0,0,0;10,0,0;10,10,0"
cli-anything-freecad --json -p p.json draft rectangle --width 20 --height 15
cli-anything-freecad --json -p p.json draft circle --radius 10
cli-anything-freecad --json -p p.json draft polygon --sides 6 --radius 10
cli-anything-freecad --json -p p.json draft text --content "Hello" --position 0,0,0
cli-anything-freecad --json -p p.json draft move 0 --vector 10,5,0
cli-anything-freecad --json -p p.json draft array-linear 0 --direction 1,0,0 --count 5 --spacing 10
cli-anything-freecad --json -p p.json draft array-polar 0 --center 0,0,0 --count 6
cli-anything-freecad --json -p p.json draft extrude 0 --direction 0,0,1 --length 10
cli-anything-freecad --json -p p.json draft to-sketch 0
```

### measure (12) — Measurement and analysis
```bash
cli-anything-freecad --json -p p.json measure volume 0
cli-anything-freecad --json -p p.json measure area 0
cli-anything-freecad --json -p p.json measure distance 0 1
cli-anything-freecad --json -p p.json measure bounding-box 0
cli-anything-freecad --json -p p.json measure center-of-mass 0
cli-anything-freecad --json -p p.json measure check-geometry 0
```

### surface (6) — Surface operations
```bash
cli-anything-freecad --json -p p.json surface filling --edges 0,1,2
cli-anything-freecad --json -p p.json surface sections --sections 0,1,2
cli-anything-freecad --json -p p.json surface extend 0 --length 10
cli-anything-freecad --json -p p.json surface sew --indices 0,1
```

### fem (12) — Finite Element Analysis
```bash
cli-anything-freecad --json -p p.json fem new-analysis
cli-anything-freecad --json -p p.json fem add-fixed 0 --references face1,face2
cli-anything-freecad --json -p p.json fem add-force 0 --references face3 --magnitude 1000
cli-anything-freecad --json -p p.json fem set-material 0 0
cli-anything-freecad --json -p p.json fem mesh-generate 0 --max-size 5
cli-anything-freecad --json -p p.json fem solve 0
cli-anything-freecad --json -p p.json fem results 0
```

### cam (10) — CNC machining
```bash
cli-anything-freecad --json -p p.json cam new-job 0
cli-anything-freecad --json -p p.json cam set-stock 0 --stock-type box
cli-anything-freecad --json -p p.json cam set-tool 0 --diameter 6 --type endmill
cli-anything-freecad --json -p p.json cam add-profile 0
cli-anything-freecad --json -p p.json cam add-pocket 0 --depth 5
cli-anything-freecad --json -p p.json cam generate-gcode 0
cli-anything-freecad --json -p p.json cam export-gcode 0 output.nc
```

### spreadsheet (7) — Parametric data tables
```bash
cli-anything-freecad --json -p p.json spreadsheet new
cli-anything-freecad --json -p p.json spreadsheet set-cell 0 A1 "50"
cli-anything-freecad --json -p p.json spreadsheet set-cell 0 B1 "=A1*2"
cli-anything-freecad --json -p p.json spreadsheet set-alias 0 A1 plate_width
cli-anything-freecad --json -p p.json spreadsheet export-csv 0 data.csv
```

### import (13) — Import CAD/mesh files
```bash
cli-anything-freecad --json -p p.json import auto model.step
cli-anything-freecad --json -p p.json import step model.step
cli-anything-freecad --json -p p.json import stl model.stl
cli-anything-freecad --json -p p.json import dxf drawing.dxf
cli-anything-freecad --json -p p.json import info model.step
# Formats: step, iges, stl, obj, dxf, svg, brep, 3mf, ply, off, gltf
```

### export (3) — Export to 17 formats
```bash
# Presets: step, iges, stl, stl_fine, obj, brep, fcstd, dxf, svg, gltf, 3mf, ply, off, amf, pdf, png, jpg
cli-anything-freecad --json -p p.json export render output.step --preset step
cli-anything-freecad --json -p p.json export render model.stl --preset stl --overwrite
cli-anything-freecad --json -p p.json export presets
```

### session (4) — Undo/redo
```bash
cli-anything-freecad --json -p p.json session undo
cli-anything-freecad --json -p p.json session redo
cli-anything-freecad --json -p p.json session status
cli-anything-freecad --json -p p.json session history
```

### generate (5) — Model generation from templates, parameters, or text
```bash
# List available templates (box, cylinder, tube, plate_with_holes, bracket_l, gear_spur, enclosure_box, threaded_bolt, washer, standoff, knob)
cli-anything-freecad --json generate templates
cli-anything-freecad --json generate template-info plate_with_holes

# Generate from template with parameter overrides
cli-anything-freecad --json generate from-template plate_with_holes -P length=80 -P holes_x=3 -o plate.json
cli-anything-freecad --json generate from-template gear_spur -P teeth=24 -P module=2.5 --material steel -o gear.json
cli-anything-freecad --json generate from-template enclosure_box -P length=100 -P width=60 -P height=40 -o case.json
cli-anything-freecad --json generate from-template bracket_l --material aluminum -o bracket.json

# Suggest template from text description
cli-anything-freecad --json generate suggest "mounting plate with 6 holes"
cli-anything-freecad --json generate suggest "M8 hex bolt 30mm long"

# Parse dimensions from natural language
cli-anything-freecad --json generate parse-dims "20mm x 15mm x 5mm with 6mm holes"
```

#### Workflow: Prompt → 3D Model → Export
```bash
# 1. Suggest template from description
cli-anything-freecad --json generate suggest "gear with 20 teeth"
# 2. Generate model from template + parsed params
cli-anything-freecad --json generate from-template gear_spur -P teeth=20 --material steel -o gear.json
# 3. Export to STEP/STL
cli-anything-freecad --json -p gear.json export render gear.step --preset step
```

## JSON Output

All commands support `--json`. Responses include structured data. Errors: `{"error": "message"}`.

## Error Handling

- Missing FreeCAD: Clear install instructions
- Invalid types: Lists valid options
- Index out of range: Reports valid range
- File exists: Use `--overwrite`
