---
name: >-
  cli-anything-kicad
description: >-
  Command-line interface for KiCad - Schematic export, PCB DRC, Gerber generation,
  BOM creation, netlist export, and 3D model export via kicad-cli...
---

# cli-anything-kicad

A stateful command-line interface for electronics design, built on KiCad. Designed for AI agents and power users who need to export schematics, run DRC, generate Gerbers, and analyze PCBs.

## Installation

```bash
pip install cli-anything-kicad
```

**Prerequisites:**
- Python 3.10+
- KiCad 7+ must be installed (`apt install kicad`)

## Command Groups

### Schematic (sch)

| Command | Description |
|---------|-------------|
| `export` | Export schematic to PDF/SVG/PNG |
| `bom` | Generate Bill of Materials (CSV/XML) |
| `netlist` | Export netlist (KiCad/Allegro/PADS/SPICE) |
| `symbols list` | List symbols in schematic |

### PCB (pcb)

| Command | Description |
|---------|-------------|
| `export` | Export PCB to SVG/Gerber/PDF |
| `drc` | Run Design Rule Check |
| `drill` | Generate drill files |
| `gerber` | Generate Gerber files (all layers) |
| `3d` | Export 3D model (STEP/VRML) |
| `stats` | PCB statistics (tracks, vias, components) |

### Library (lib)

| Command | Description |
|---------|-------------|
| `list` | List symbols/footprints in a library |
| `export` | Export library symbols to SVG |

### Session

| Command | Description |
|---------|-------------|
| `status` | Show session status |
| `undo` | Undo last operation |
| `redo` | Redo last undone operation |
| `history` | Show undo history |

## Examples

```bash
# Export schematic to PDF
cli-anything-kicad sch export circuit.kicad_sch --output circuit.pdf

# Generate BOM
cli-anything-kicad sch bom circuit.kicad_sch --output bom.csv

# Run DRC on PCB
cli-anything-kicad pcb drc board.kicad_pcb

# Generate Gerber files
cli-anything-kicad pcb gerber board.kicad_pcb --output gerbers/

# Export 3D model
cli-anything-kicad pcb 3d board.kicad_pcb --output board.step

# Get PCB statistics
cli-anything-kicad pcb stats board.kicad_pcb

# List library symbols
cli-anything-kicad lib list /path/to/library
```

## Version

1.0.0
