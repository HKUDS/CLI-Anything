---
name: "cli-anything-cloudcompare"
description: "Command-line interface for CloudCompare — Agent-friendly harness for CloudCompare, the open-source 3D point cloud and mesh processing software. Supports 41 commands across 9 groups: project management, session control, point cloud operations (subsample, filter, segment, analyze), mesh operations, distance computation (C2C, C2M), transformations (ICP, matrix), export (LAS/LAZ/PLY/PCD/OBJ/STL/E57), and interactive REPL."
---

# cli-anything-cloudcompare

Agent-friendly command-line harness for [CloudCompare](https://cloudcompare.org) — the open-source 3D point cloud and mesh processing software.

**41 commands** across 9 groups.

## Installation

```bash
pip install cli-anything-cloudcompare
```

**Prerequisites:**
- Python 3.10+
- CloudCompare installed on your system
  - Linux (Flatpak): `flatpak install flathub org.cloudcompare.CloudCompare`
  - macOS/Windows: download from https://cloudcompare.org

**Tested with:** CloudCompare 2.13.2 (Flatpak, Linux)

## Global Options

These options must be placed **before** the subcommand:

```bash
cli-anything-cloudcompare [--project FILE] [--json] COMMAND [ARGS]...
```

| Option | Description |
|---|---|
| `-p, --project TEXT` | Path to project JSON file |
| `--json` | Output results as JSON (for agent consumption) |

## Command Groups

### 1. project — Project Management (3 commands)

#### project new
Create a new empty project file.

```bash
# Create a project with default name
cli-anything-cloudcompare project new -o myproject.json

# Create a project with a custom name
cli-anything-cloudcompare project new -o myproject.json -n "Bridge Survey 2024"

# JSON output for agents
cli-anything-cloudcompare --json project new -o myproject.json
```

Options: `-o/--output TEXT` (required), `-n/--name TEXT`

#### project info
Show project info and loaded entities.

```bash
cli-anything-cloudcompare --project myproject.json project info

# JSON output
cli-anything-cloudcompare --project myproject.json --json project info
```

#### project status
Show quick project status (cloud count, mesh count, last operation).

```bash
cli-anything-cloudcompare --project myproject.json project status
```

---

### 2. session — Session Management (4 commands)

#### session save
Save the current project state to disk.

```bash
cli-anything-cloudcompare --project myproject.json session save
```

#### session history
Show recent operation history.

```bash
# Show last 10 operations (default)
cli-anything-cloudcompare --project myproject.json session history

# Show last 5 operations
cli-anything-cloudcompare --project myproject.json session history -n 5
```

Options: `-n/--last INTEGER`

#### session set-format
Update the default export format for future operations.

```bash
# Set default cloud export to LAS
cli-anything-cloudcompare --project myproject.json session set-format --cloud-fmt LAS --cloud-ext las

# Set default mesh export to OBJ
cli-anything-cloudcompare --project myproject.json session set-format --mesh-fmt OBJ --mesh-ext obj

# Set both cloud and mesh defaults
cli-anything-cloudcompare --project myproject.json session set-format \
  --cloud-fmt PLY --cloud-ext ply \
  --mesh-fmt STL --mesh-ext stl
```

Options: `--cloud-fmt TEXT`, `--cloud-ext TEXT`, `--mesh-fmt TEXT`, `--mesh-ext TEXT`

#### session undo
Remove the last operation from history (soft undo — does not delete output files).

```bash
cli-anything-cloudcompare --project myproject.json session undo
```

---

### 3. cloud — Point Cloud Operations (21 commands)

All cloud commands take `CLOUD_INDEX` (0-based integer from `cloud list`) and most accept `--add-to-project` to register the output back into the project.

#### cloud add
Add a point cloud file to the project.

```bash
# Add a LAS file
cli-anything-cloudcompare --project myproject.json cloud add /data/scan.las

# Add with a label
cli-anything-cloudcompare --project myproject.json cloud add /data/scan.las -l "roof scan"
```

Options: `-l/--label TEXT`

#### cloud list
List all clouds currently in the project.

```bash
cli-anything-cloudcompare --project myproject.json cloud list

# JSON output for parsing indices
cli-anything-cloudcompare --project myproject.json --json cloud list
```

#### cloud convert
Convert a cloud from one format to another (format determined by file extension).

```bash
# LAS → PLY
cli-anything-cloudcompare cloud convert /data/scan.las /data/scan.ply

# PCD → LAS
cli-anything-cloudcompare cloud convert /data/cloud.pcd /data/cloud.las
```

#### cloud subsample
Reduce the number of points using RANDOM, SPATIAL, or OCTREE method.

```bash
# Random: keep 100 000 points
cli-anything-cloudcompare --project myproject.json cloud subsample 0 \
  -o /data/sub_random.las -m random -n 100000

# Spatial: minimum distance 0.05 m between points
cli-anything-cloudcompare --project myproject.json cloud subsample 0 \
  -o /data/sub_spatial.las -m spatial -n 0.05

# Octree: level 8
cli-anything-cloudcompare --project myproject.json cloud subsample 0 \
  -o /data/sub_octree.las -m octree -n 8 --add-to-project
```

Options: `-o/--output TEXT` (required), `-m/--method [random|spatial|octree]`, `-n/--param FLOAT`, `--add-to-project`

#### cloud crop
Crop a cloud to an axis-aligned bounding box.

```bash
# Keep points inside the box
cli-anything-cloudcompare --project myproject.json cloud crop 0 \
  -o /data/cropped.las \
  --xmin 0.0 --ymin 0.0 --zmin 0.0 \
  --xmax 10.0 --ymax 10.0 --zmax 5.0

# Keep points OUTSIDE the box
cli-anything-cloudcompare --project myproject.json cloud crop 0 \
  -o /data/exterior.las \
  --xmin 0.0 --ymin 0.0 --zmin 0.0 \
  --xmax 10.0 --ymax 10.0 --zmax 5.0 --outside
```

Options: `-o/--output TEXT` (required), `--xmin/ymin/zmin/xmax/ymax/zmax FLOAT` (all required), `--outside`, `--add-to-project`

#### cloud normals
Compute surface normals via the octree method.

```bash
# Compute normals at octree level 6
cli-anything-cloudcompare --project myproject.json cloud normals 0 \
  -o /data/with_normals.ply --level 6

# Compute normals oriented toward +Z
cli-anything-cloudcompare --project myproject.json cloud normals 0 \
  -o /data/with_normals.ply --level 6 --orientation plus_z --add-to-project
```

Options: `-o/--output TEXT` (required), `--level INTEGER` (1–10), `--orientation [plus_x|plus_y|plus_z|minus_x|minus_y|minus_z]`, `--add-to-project`

#### cloud invert-normals
Flip all normal vectors in the cloud.

```bash
cli-anything-cloudcompare --project myproject.json cloud invert-normals 0 \
  -o /data/flipped_normals.ply --add-to-project
```

Options: `-o/--output TEXT` (required), `--add-to-project`

#### cloud filter-sor
Statistical Outlier Removal — removes isolated noise points.

```bash
# Default parameters (k=6 neighbours, 1.0 std ratio)
cli-anything-cloudcompare --project myproject.json cloud filter-sor 0 \
  -o /data/denoised.las

# Custom parameters
cli-anything-cloudcompare --project myproject.json cloud filter-sor 0 \
  -o /data/denoised.las --nb-points 12 --std-ratio 2.0 --add-to-project
```

Options: `-o/--output TEXT` (required), `--nb-points INTEGER`, `--std-ratio FLOAT`, `--add-to-project`

#### cloud noise-filter
Remove noisy points using the PCL noise filter (KNN or radius mode).

```bash
# KNN mode (default)
cli-anything-cloudcompare --project myproject.json cloud noise-filter 0 \
  -o /data/clean.las --knn 8 --noisiness 1.0

# Radius mode
cli-anything-cloudcompare --project myproject.json cloud noise-filter 0 \
  -o /data/clean.las --radius 0.1 --use-radius --add-to-project
```

Options: `-o/--output TEXT` (required), `--knn INTEGER`, `--noisiness FLOAT`, `--radius FLOAT`, `--use-radius`, `--absolute`, `--add-to-project`

#### cloud filter-csf
Ground filtering using the Cloth Simulation Filter (CSF) algorithm. Separates ground from off-ground points (buildings, vegetation).

```bash
# Extract ground only — mixed terrain
cli-anything-cloudcompare --project myproject.json cloud filter-csf 0 \
  --ground /data/ground.las --scene relief

# Split ground + off-ground — urban scene
cli-anything-cloudcompare --project myproject.json cloud filter-csf 0 \
  --ground /data/ground.las \
  --offground /data/buildings.las \
  --scene flat --cloth-resolution 0.5 --class-threshold 0.3

# Steep forested slope with slope post-processing
cli-anything-cloudcompare --project myproject.json cloud filter-csf 0 \
  --ground /data/terrain.las --scene slope --proc-slope --add-to-project
```

Options: `-g/--ground TEXT` (required), `-u/--offground TEXT`, `--scene [slope|relief|flat]`, `--cloth-resolution FLOAT`, `--class-threshold FLOAT`, `--max-iteration INTEGER`, `--proc-slope`, `--add-to-project`

#### cloud filter-sf
Filter a cloud by scalar field value range (keep points where SF ∈ [min, max]).

```bash
# Keep points with SF value between 10 and 50
cli-anything-cloudcompare --project myproject.json cloud filter-sf 0 \
  -o /data/filtered.las --min 10.0 --max 50.0

# Filter using a specific SF index
cli-anything-cloudcompare --project myproject.json cloud filter-sf 0 \
  -o /data/filtered.las --min 0.0 --max 1.5 --sf-index 2 --add-to-project
```

Options: `-o/--output TEXT` (required), `--min FLOAT` (required), `--max FLOAT` (required), `--sf-index INTEGER`, `--add-to-project`

#### cloud sf-from-coord
Convert a coordinate axis (X/Y/Z) to a scalar field. Commonly used to create a height (Z) scalar field.

```bash
# Create Z scalar field (height)
cli-anything-cloudcompare --project myproject.json cloud sf-from-coord 0 \
  -o /data/with_z_sf.las --dim z --add-to-project

# Create X scalar field with a specific active index
cli-anything-cloudcompare --project myproject.json cloud sf-from-coord 0 \
  -o /data/with_x_sf.las --dim x --sf-index 0
```

Options: `-o/--output TEXT` (required), `--dim [x|y|z]` (default: z), `--sf-index INTEGER`, `--add-to-project`

#### cloud sf-filter-z
Convenience command: convert Z → scalar field and filter by height range in one step.

```bash
# Extract points between z=1.0 m and z=2.5 m
cli-anything-cloudcompare --project myproject.json cloud sf-filter-z 0 \
  -o /data/slice.las --min 1.0 --max 2.5 --add-to-project

# Only apply upper bound
cli-anything-cloudcompare --project myproject.json cloud sf-filter-z 0 \
  -o /data/below_5m.las --max 5.0
```

Options: `-o/--output TEXT` (required), `--min FLOAT`, `--max FLOAT`, `--add-to-project`

#### cloud sf-to-rgb
Convert the active scalar field to RGB colours.

```bash
cli-anything-cloudcompare --project myproject.json cloud sf-to-rgb 0 \
  -o /data/coloured.ply --add-to-project
```

Options: `-o/--output TEXT` (required), `--add-to-project`

#### cloud rgb-to-sf
Convert RGB colours to a scalar field (luminance value).

```bash
cli-anything-cloudcompare --project myproject.json cloud rgb-to-sf 0 \
  -o /data/luminance.las --add-to-project
```

Options: `-o/--output TEXT` (required), `--add-to-project`

#### cloud curvature
Compute curvature scalar field (MEAN or GAUSS).

```bash
# Mean curvature with radius 0.5 m
cli-anything-cloudcompare --project myproject.json cloud curvature 0 \
  -o /data/curvature.las --type mean --radius 0.5

# Gaussian curvature
cli-anything-cloudcompare --project myproject.json cloud curvature 0 \
  -o /data/curvature.las --type gauss --radius 0.5 --add-to-project
```

Options: `-o/--output TEXT` (required), `--type [mean|gauss]`, `-r/--radius FLOAT`, `--add-to-project`

#### cloud roughness
Compute roughness scalar field (deviation from local best-fit plane).

```bash
cli-anything-cloudcompare --project myproject.json cloud roughness 0 \
  -o /data/roughness.las --radius 0.2 --add-to-project
```

Options: `-o/--output TEXT` (required), `-r/--radius FLOAT`, `--add-to-project`

#### cloud density
Compute point density scalar field.

```bash
# KNN density
cli-anything-cloudcompare --project myproject.json cloud density 0 \
  -o /data/density.las --type knn --radius 0.5

# Surface density
cli-anything-cloudcompare --project myproject.json cloud density 0 \
  -o /data/density.las --type surface --radius 1.0 --add-to-project
```

Options: `-o/--output TEXT` (required), `-r/--radius FLOAT`, `--type [knn|surface|volume]`, `--add-to-project`

#### cloud segment-cc
Segment cloud into connected components (clusters). Each component is saved as a separate file.

```bash
# Segment with octree level 8, minimum 100 points per component
cli-anything-cloudcompare --project myproject.json cloud segment-cc 0 \
  -o /data/components/ --octree-level 8 --min-points 100

# Save components as PLY files
cli-anything-cloudcompare --project myproject.json cloud segment-cc 0 \
  -o /data/components/ --octree-level 6 --min-points 50 --fmt ply
```

Options: `-o/--output-dir TEXT` (required), `--octree-level INTEGER`, `--min-points INTEGER`, `--fmt TEXT`

#### cloud merge
Merge all clouds in the project into a single cloud.

```bash
cli-anything-cloudcompare --project myproject.json cloud merge \
  -o /data/merged.las --add-to-project
```

Options: `-o/--output TEXT` (required), `--add-to-project`

#### cloud mesh-delaunay
Build a 2.5-D Delaunay triangulation mesh from a cloud.

```bash
# Basic Delaunay mesh
cli-anything-cloudcompare --project myproject.json cloud mesh-delaunay 0 \
  -o /data/surface.obj

# Best-fit plane with max edge length limit
cli-anything-cloudcompare --project myproject.json cloud mesh-delaunay 0 \
  -o /data/surface.ply --best-fit --max-edge-length 2.0 --add-to-project
```

Options: `-o/--output TEXT` (required), `--best-fit`, `--max-edge-length FLOAT`, `--add-to-project`

---

### 4. mesh — Mesh Operations (3 commands)

#### mesh add
Add a mesh file to the project.

```bash
cli-anything-cloudcompare --project myproject.json mesh add /data/model.obj

# Add with label
cli-anything-cloudcompare --project myproject.json mesh add /data/model.ply -l "building model"
```

Options: `-l/--label TEXT`

#### mesh list
List all meshes in the project.

```bash
cli-anything-cloudcompare --project myproject.json mesh list

# JSON output
cli-anything-cloudcompare --project myproject.json --json mesh list
```

#### mesh sample
Sample a point cloud from a mesh surface.

```bash
# Sample 50 000 points from mesh at index 0
cli-anything-cloudcompare --project myproject.json mesh sample 0 \
  -o /data/sampled.las -n 50000

# Add sampled cloud back to project
cli-anything-cloudcompare --project myproject.json mesh sample 0 \
  -o /data/sampled.las -n 100000 --add-to-project
```

Options: `-o/--output TEXT` (required), `-n/--count INTEGER`, `--add-to-project`

---

### 5. distance — Distance Computation (2 commands)

#### distance c2c
Compute cloud-to-cloud distances. Adds a distance scalar field to the compared cloud.

```bash
# Compare cloud 1 to reference cloud 0
cli-anything-cloudcompare --project myproject.json distance c2c \
  --compare 1 --reference 0 -o /data/distances.las

# Split into X/Y/Z components at octree level 8
cli-anything-cloudcompare --project myproject.json distance c2c \
  --compare 1 --reference 0 -o /data/distances.las \
  --split-xyz --octree-level 8 --add-to-project
```

Options: `--compare TEXT` (required), `--reference TEXT` (required), `-o/--output TEXT` (required), `--split-xyz`, `--octree-level INTEGER`, `--add-to-project`

#### distance c2m
Compute cloud-to-mesh distances. Adds a distance scalar field to the cloud.

```bash
# Basic cloud-to-mesh distance
cli-anything-cloudcompare --project myproject.json distance c2m \
  --cloud 0 --mesh 0 -o /data/c2m_dist.las

# With flipped normals and unsigned distances
cli-anything-cloudcompare --project myproject.json distance c2m \
  --cloud 0 --mesh 0 -o /data/c2m_dist.las \
  --flip-normals --unsigned --add-to-project
```

Options: `--cloud INTEGER` (required), `--mesh INTEGER` (required), `-o/--output TEXT` (required), `--flip-normals`, `--unsigned`, `--add-to-project`

---

### 6. transform — Transformations and Registration (2 commands)

#### transform apply
Apply a 4×4 rigid-body transformation matrix to a cloud.

```bash
# Apply a transformation matrix from file
cli-anything-cloudcompare --project myproject.json transform apply 0 \
  -o /data/transformed.las -m /data/matrix.txt

# Apply the inverse transformation
cli-anything-cloudcompare --project myproject.json transform apply 0 \
  -o /data/transformed.las -m /data/matrix.txt --inverse --add-to-project
```

The matrix file must contain 4 rows of 4 space-separated values:
```
1 0 0 0
0 1 0 0
0 0 1 0
0 0 0 1
```

Options: `-o/--output TEXT` (required), `-m/--matrix TEXT` (required), `--inverse`, `--add-to-project`

#### transform icp
Run ICP (Iterative Closest Point) registration to align one cloud to another.

```bash
# Basic ICP alignment
cli-anything-cloudcompare --project myproject.json transform icp \
  --aligned 1 --reference 0 -o /data/aligned.las

# ICP with overlap and iteration control
cli-anything-cloudcompare --project myproject.json transform icp \
  --aligned 1 --reference 0 -o /data/aligned.las \
  --max-iter 50 --overlap 80 --min-error-diff 1e-6 --add-to-project
```

Options: `--aligned INTEGER` (required), `--reference INTEGER` (required), `-o/--output TEXT` (required), `--max-iter INTEGER`, `--min-error-diff FLOAT`, `--overlap FLOAT`, `--add-to-project`

---

### 7. export — Export Clouds and Meshes (4 commands)

#### export formats
List all available export format presets.

```bash
cli-anything-cloudcompare export formats

# JSON output
cli-anything-cloudcompare --json export formats
```

#### export cloud
Export a cloud to a target format.

```bash
# Export cloud at index 0 as LAS
cli-anything-cloudcompare --project myproject.json export cloud 0 /data/output.las

# Export as PLY using preset
cli-anything-cloudcompare --project myproject.json export cloud 0 /data/output.ply -f ply

# Overwrite if file exists
cli-anything-cloudcompare --project myproject.json export cloud 0 /data/output.las -f las --overwrite
```

Supported presets: `las`, `laz`, `ply`, `pcd`, `xyz`, `asc`, `csv`, `bin`, `e57`

Options: `-f/--preset TEXT`, `--overwrite`

#### export mesh
Export a mesh to a target format.

```bash
# Export mesh at index 0 as OBJ
cli-anything-cloudcompare --project myproject.json export mesh 0 /data/model.obj

# Export as STL
cli-anything-cloudcompare --project myproject.json export mesh 0 /data/model.stl -f stl --overwrite
```

Supported presets: `obj`, `stl`, `ply`, `bin`

Options: `-f/--preset TEXT`, `--overwrite`

#### export batch
Batch export all project clouds to a directory.

```bash
# Export all clouds as LAS
cli-anything-cloudcompare --project myproject.json export batch \
  -d /data/exports/ -f las

# Overwrite existing files
cli-anything-cloudcompare --project myproject.json export batch \
  -d /data/exports/ -f ply --overwrite
```

Options: `-d/--output-dir TEXT` (required), `-f/--preset TEXT`, `--overwrite`

---

### 8. info — Installation Info (1 command)

Show CloudCompare installation path and version.

```bash
cli-anything-cloudcompare info

# JSON output
cli-anything-cloudcompare --json info
```

---

### 9. repl — Interactive REPL (1 command)

Start the interactive REPL session with history and undo support.

```bash
# Start REPL without a project
cli-anything-cloudcompare repl

# Start REPL with an existing project
cli-anything-cloudcompare repl -p myproject.json

# Equivalent: run without subcommand
cli-anything-cloudcompare --project myproject.json
```

Options: `-p/--project TEXT`

Inside the REPL, type `help` to list available commands or `session undo` to revert the last operation.

---

## Supported File Formats

| Format | Extension | Read | Write | Notes |
|---|---|---|---|---|
| LAS | `.las` | ✓ | ✓ | LiDAR standard, supports intensity/RGB |
| LAZ | `.laz` | ✓ | ✓ | Compressed LAS |
| PLY | `.ply` | ✓ | ✓ | ASCII or binary |
| PCD | `.pcd` | ✓ | ✓ | PCL format |
| XYZ | `.xyz` | ✓ | ✓ | Plain text XYZ |
| ASC | `.asc` | ✓ | ✓ | ASCII with header |
| CSV | `.csv` | ✓ | ✓ | Comma-separated |
| E57 | `.e57` | ✓ | ✓ | ASTM scanner exchange |
| BIN | `.bin` | ✓ | ✓ | CloudCompare native binary |
| OBJ | `.obj` | ✓ | ✓ | Mesh (Wavefront) |
| STL | `.stl` | ✓ | ✓ | Mesh (3D printing) |

---

## Typical Workflows

### Workflow 1: LiDAR Pre-processing Pipeline

```bash
P=myproject.json

# 1. Create project and load scan
cli-anything-cloudcompare project new -o $P
cli-anything-cloudcompare --project $P cloud add /data/scan.las
cli-anything-cloudcompare --project $P cloud list  # note index → 0

# 2. Denoise
cli-anything-cloudcompare --project $P cloud filter-sor 0 \
  -o /data/denoised.las --nb-points 6 --std-ratio 1.0 --add-to-project

# 3. Subsample to 5 cm grid
cli-anything-cloudcompare --project $P cloud subsample 1 \
  -o /data/subsampled.las -m spatial -n 0.05 --add-to-project

# 4. Extract ground plane (CSF)
cli-anything-cloudcompare --project $P cloud filter-csf 2 \
  --ground /data/ground.las --offground /data/objects.las \
  --scene relief --add-to-project

# 5. Export result
cli-anything-cloudcompare --project $P export cloud 3 /data/ground_final.las -f las --overwrite
```

### Workflow 2: Change Detection Between Two Scans

```bash
P=compare.json
cli-anything-cloudcompare project new -o $P
cli-anything-cloudcompare --project $P cloud add /data/scan_2023.las   # index 0
cli-anything-cloudcompare --project $P cloud add /data/scan_2024.las   # index 1

# ICP alignment (align 2024 to 2023)
cli-anything-cloudcompare --project $P transform icp \
  --aligned 1 --reference 0 -o /data/aligned_2024.las \
  --overlap 90 --add-to-project   # index 2

# Cloud-to-cloud distance
cli-anything-cloudcompare --project $P distance c2c \
  --compare 2 --reference 0 -o /data/change_map.las --add-to-project

# Export as LAS with distance scalar field
cli-anything-cloudcompare --project $P export cloud 3 /data/change_map_final.las --overwrite
```

### Workflow 3: Height Slice Extraction

```bash
P=slice.json
cli-anything-cloudcompare project new -o $P
cli-anything-cloudcompare --project $P cloud add /data/building.las

# Extract points at 2–3 m height (floor level)
cli-anything-cloudcompare --project $P cloud sf-filter-z 0 \
  -o /data/floor_slice.las --min 2.0 --max 3.0 --add-to-project

# Export
cli-anything-cloudcompare --project $P export cloud 1 /data/floor_slice_out.las --overwrite
```

### Workflow 4: Surface Reconstruction

```bash
P=mesh.json
cli-anything-cloudcompare project new -o $P
cli-anything-cloudcompare --project $P cloud add /data/terrain.las

# Compute normals
cli-anything-cloudcompare --project $P cloud normals 0 \
  -o /data/with_normals.ply --level 6 --orientation plus_z --add-to-project

# Delaunay mesh
cli-anything-cloudcompare --project $P cloud mesh-delaunay 1 \
  -o /data/terrain_mesh.obj --max-edge-length 1.0 --add-to-project

# Export mesh
cli-anything-cloudcompare --project $P export mesh 0 /data/terrain_mesh_final.obj --overwrite
```

---

## Error Handling

| Exit Code | Meaning |
|---|---|
| `0` | Success |
| `1` | General error (see stderr for details) |
| `2` | Invalid arguments |

Common errors:

```bash
# CloudCompare not found
# → Install CloudCompare; check `cli-anything-cloudcompare info`

# Index out of range
# → Run `cloud list` or `mesh list` to confirm valid indices

# File already exists (no --overwrite)
# → Add --overwrite flag to export commands

# fcntl not available (Windows)
# → File locking is skipped automatically; project save still works
```

---

## For AI Agents

1. **Always use `--json` flag** for parseable output
2. **Check return codes** — 0 for success, non-zero for errors
3. **Parse stderr** for error messages on failure
4. **Use absolute paths** for all file arguments
5. **Verify output files exist** after export operations
6. **Chain with `--add-to-project`** to build multi-step pipelines without re-loading files
7. **Use `cloud list --json`** to discover valid cloud indices before each operation
8. **Use `export formats --json`** to discover available format presets

## Version

| Component | Version |
|---|---|
| cli-anything-cloudcompare | 1.0.0 |
| CloudCompare (tested) | 2.13.2 |
| Python (minimum) | 3.10 |
