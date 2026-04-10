# cli-anything-3mf

**3MF Mesh Geometry Editor** — Detect and resize cylindrical holes, repair meshes, compare 3D printing files.

Part of the [CLI-Anything](https://github.com/HKUDS/CLI-Anything) ecosystem.

## Installation

```bash
pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=3MF/agent-harness
```

Or for development:

```bash
cd 3MF/agent-harness
pip install -e ".[dev]"
```

## Quick Start

```bash
# Show mesh info
cli-anything-3mf info model.3mf

# Detect cylindrical holes
cli-anything-3mf inspect model.3mf

# Resize holes 0,1,2,3 to 4.2mm diameter
cli-anything-3mf resize model.3mf --hole 0 --hole 1 --hole 2 --hole 3 --diameter 4.2 -o output.3mf

# Repair mesh issues
cli-anything-3mf repair model.3mf -o repaired.3mf

# Compare two files
cli-anything-3mf compare original.3mf modified.3mf

# Interactive REPL
cli-anything-3mf
```

## Commands

| Command | Description |
|---------|-------------|
| `info <file>` | Show mesh statistics (vertices, faces, bounds, watertight, volume) |
| `inspect <file>` | Detect and list all cylindrical holes with diameter and position |
| `resize <file>` | Resize specified holes to a target diameter |
| `repair <file>` | Fix degenerate faces, duplicate vertices, and normals |
| `compare <f1> <f2>` | Side-by-side comparison of two 3MF files |

All commands support `--json` for machine-readable output.

## How It Works

### Hole Detection
The tool takes cross-sections at multiple planes perpendicular to the hole axis,
identifies circular features via least-squares circle fitting, and groups them
across planes to detect consistent cylindrical holes.

### Hole Resizing
Wall vertices are identified by their radial distance from the hole axis.
Vertices are then scaled radially to achieve the target diameter while preserving
mesh topology and angular position.

### Slicer Compatibility
All non-mesh content (slicer settings, thumbnails, plate configurations) is
preserved during file repack. Output files can be reopened in BambuStudio or
PrusaSlicer without configuration loss.

## Architecture

```
cli_anything/threemf/
├── threemf_cli.py          # Click CLI + REPL
├── core/
│   ├── parser.py           # 3MF ZIP/XML parsing
│   ├── inspector.py        # Cross-section hole detection
│   ├── modifier.py         # Hole resizing
│   └── repair.py           # Mesh repair
├── utils/
│   ├── threemf_backend.py  # Geometry utilities (trimesh/numpy)
│   └── repl_skin.py        # Unified REPL styling
├── skills/
│   └── SKILL.md            # Agent-discoverable skill
└── tests/
    ├── test_core.py        # Unit tests (74+)
    └── test_full_e2e.py    # E2E tests (30+)
```

## Dependencies

- Python 3.10+
- numpy, scipy, trimesh
- click, prompt-toolkit

## License

MIT — See [CLI-Anything LICENSE](https://github.com/HKUDS/CLI-Anything/blob/main/LICENSE)
