# 3MF CLI — Standard Operating Procedure

## Overview

The **3MF CLI** (`cli-anything-3mf`) is an agent-native command-line interface for
inspecting, modifying, and repairing 3MF mesh files used in 3D printing.

Unlike traditional 3D-printing CLI tools (PrusaSlicer CLI, BambuStudio CLI, admesh)
that treat meshes as opaque triangle soups, this tool provides **feature-aware
geometry editing** — it can detect cylindrical holes, measure their diameters, and
resize them via CLI commands.

## 3MF Format

A 3MF file is a ZIP archive containing:
- `[Content_Types].xml` — MIME type declarations
- `_rels/.rels` — relationship definitions
- `3D/3dmodel.model` — XML mesh data (core spec namespace: `http://schemas.microsoft.com/3dmanufacturing/core/2015/02`)
- `Metadata/` — slicer settings, thumbnails, plate configurations (BambuStudio, PrusaSlicer)

## Architecture

```
threemf_cli.py          Click CLI + REPL entry point
  |
  +-- core/parser.py     3MF ZIP/XML parsing, lossless repack
  +-- core/inspector.py   Cross-section hole detection
  +-- core/modifier.py    Radial vertex scaling for hole resize
  +-- core/repair.py      Degenerate face removal, vertex merge
  |
  +-- utils/threemf_backend.py   trimesh/numpy geometry utilities
  +-- utils/repl_skin.py         Unified REPL styling
```

## Core Algorithm

### Hole Detection (inspector.py)
1. Take N cross-sections perpendicular to the hole axis
2. At each section, identify circular entities via trimesh path analysis
3. Fit circles using least-squares (Kasa method)
4. Group circles across sections by center proximity
5. Calculate confidence from detection consistency

### Hole Resize (modifier.py)
1. Re-detect holes to get current geometry
2. Find wall vertices at known radii from hole axis
3. Scale vertices radially: `new_pos = center + direction * (new_r / old_r)`
4. Fix degenerate faces caused by coincident vertices

### Mesh Repair (repair.py)
1. Merge duplicate vertices (coordinate rounding + dedup)
2. Remove degenerate triangles (collapsed faces)
3. Remove unreferenced vertices
4. Fix face winding via trimesh

## Slicer Compatibility

The tool preserves all non-mesh content during repack:
- BambuStudio: project_settings.config, model_settings.config, plate thumbnails
- PrusaSlicer: slic3r_pe configs, layer height profiles

Output files can be reopened in the original slicer without configuration loss.
