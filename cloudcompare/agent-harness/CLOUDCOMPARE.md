# CloudCompare CLI Harness — SOP

## Overview

CloudCompare is a 3D point cloud (and triangular mesh) processing software.
It was originally designed for comparison between two 3D point clouds (e.g. laser scanner data).
It supports a full **command-line mode** via the `-SILENT` flag, which this harness wraps.

## Backend

**CloudCompare itself** is the backend. The Python harness constructs valid `-SILENT` command
strings and invokes them as subprocesses. It does NOT reimplement any 3D processing.

```
CloudCompare -SILENT -O input.las -SS SPATIAL 0.05 -C_EXPORT_FMT LAS -NO_TIMESTAMP -SAVE_CLOUDS FILE output.las
```

### Detecting CloudCompare

The `find_cloudcompare()` function tries (in order):
1. Native binary (`CloudCompare` or `cloudcompare` in PATH)
2. Flatpak (`flatpak run org.cloudcompare.CloudCompare`)
3. Snap (`/snap/bin/cloudcompare`)

### Installation (required)

```bash
# Flatpak (recommended for Linux)
flatpak install flathub org.cloudcompare.CloudCompare

# Debian/Ubuntu
sudo apt install cloudcompare

# macOS
brew install --cask cloudcompare

# Windows
# https://cloudcompare.org/release/index.html
```

## Native CLI Mode

CloudCompare's `-SILENT` mode processes commands sequentially:

```
CloudCompare -SILENT [commands...]
```

Key commands used by this harness:

| CC Command | Purpose |
|-----------|---------|
| `-O <file>` | Open/load a file |
| `-SILENT` | Suppress GUI, run headlessly |
| `-SS METHOD PARAM` | Subsample (RANDOM/SPATIAL/OCTREE) |
| `-ROUGH <radius>` | Compute roughness SF |
| `-DENSITY <radius>` | Compute density SF |
| `-CURV TYPE <radius>` | Compute curvature SF |
| `-SOR <k> <std>` | Statistical Outlier Removal |
| `-NOISE ...` | Noise filter |
| `-CROP x:y:z:X:Y:Z` | Crop to bounding box |
| `-MERGE_CLOUDS` | Merge all loaded clouds |
| `-C2C_DIST` | Cloud-to-cloud distance |
| `-C2M_DIST` | Cloud-to-mesh distance |
| `-ICP` | Iterative Closest Point registration |
| `-OCTREE_NORMALS <level>` | Compute normals |
| `-C_EXPORT_FMT <fmt>` | Set cloud output format |
| `-M_EXPORT_FMT <fmt>` | Set mesh output format |
| `-NO_TIMESTAMP` | No timestamp suffix on output files |
| `-SAVE_CLOUDS FILE <path>` | Save to specific file |
| `-SAVE_MESHES FILE <path>` | Save mesh to specific file |

## Data Model

The harness uses JSON project files:

```json
{
  "version": "1.0",
  "name": "my_survey",
  "clouds": [
    {"path": "/abs/path/cloud.las", "label": "cloud", ...}
  ],
  "meshes": [...],
  "settings": {
    "cloud_export_format": "LAS",
    "cloud_export_ext": "las"
  },
  "history": [
    {"operation": "subsample", "inputs": [...], "outputs": [...], "params": {...}}
  ]
}
```

## Supported File Formats

### Point Clouds
| Extension | Format | Notes |
|-----------|--------|-------|
| .bin | BIN | CloudCompare native binary (default) |
| .las / .laz | LAS | LiDAR format (most common) |
| .ply | PLY | Polygon format |
| .pcd | PCD | Point Cloud Data (ROS/PCL) |
| .xyz / .txt / .asc / .csv | ASC | Plain text ASCII |
| .e57 | E57 | LiDAR exchange format |

### Meshes
| Extension | Format |
|-----------|--------|
| .obj | OBJ (Wavefront) |
| .stl | STL |
| .ply | PLY |
| .bin | CloudCompare binary |

## Key Workflows

### Scan Comparison
```bash
cli-anything-cloudcompare project new -o survey.json
cli-anything-cloudcompare -p survey.json cloud add scan_before.las
cli-anything-cloudcompare -p survey.json cloud add scan_after.las
cli-anything-cloudcompare -p survey.json distance c2c --compare 1 --reference 0 -o diff.las
```

### Point Cloud Cleanup Pipeline
```bash
cli-anything-cloudcompare -p project.json cloud filter-sor 0 -o clean.las
cli-anything-cloudcompare -p project.json cloud subsample 0 -o thin.las --method SPATIAL --param 0.02
```

### ICP Registration
```bash
cli-anything-cloudcompare -p project.json transform icp --aligned 1 --reference 0 -o aligned.las
```

## Agent Usage Notes

1. Always use `--json` flag for machine-parseable output
2. Use absolute paths for all file arguments
3. The `--add-to-project` flag adds outputs back to the project for chaining
4. Check `exists: true` in output JSON to verify CloudCompare produced the file
5. `returncode: 0` means CloudCompare exited successfully
