---
name: "cli-anything-3mf"
description: "3MF mesh geometry editor — detect and resize cylindrical holes, repair meshes, compare 3D printing files. Works with BambuStudio and PrusaSlicer 3MF files."
---

# cli-anything-3mf

3MF mesh geometry editor for 3D printing files.

## Installation

```bash
pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=3MF/agent-harness
```

## Commands

```bash
# Show mesh info (vertices, faces, bounding box, watertight status, volume)
cli-anything-3mf info <file.3mf>

# Detect cylindrical holes (center, diameter, confidence)
cli-anything-3mf inspect <file.3mf>

# Resize holes to target diameter
cli-anything-3mf resize <file.3mf> --hole 0 --hole 1 --diameter 4.2 -o output.3mf

# Fix mesh issues (degenerate faces, duplicate vertices, normals)
cli-anything-3mf repair <file.3mf> -o repaired.3mf

# Compare two 3MF files
cli-anything-3mf compare <file1.3mf> <file2.3mf>
```

## JSON Output

All commands support `--json` for machine-readable output:

```bash
cli-anything-3mf --json inspect model.3mf
```

## Key Features

- Detects cylindrical holes via multi-plane cross-section analysis
- Resizes holes by radial vertex scaling (preserves mesh topology)
- Preserves slicer metadata (BambuStudio, PrusaSlicer) during file repack
- Repairs degenerate faces and duplicate vertices after modification
- Works with any 3MF file conforming to the 3MF Core Specification
