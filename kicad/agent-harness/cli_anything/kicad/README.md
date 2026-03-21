# cli-anything-kicad

A stateful command-line interface for electronics design, built on KiCad. Designed for AI agents and power users who need to export schematics, run DRC, generate Gerbers, and analyze PCBs without a GUI.

## Features

- **Schematic Export** — Export to PDF/SVG/PNG with page size control
- **BOM Generation** — Generate Bill of Materials in CSV/XML format
- **Netlist Export** — Export netlists in KiCad/Allegro/PADS/SPICE formats
- **Symbol Listing** — List all symbols in a schematic
- **PCB Export** — Export to SVG/Gerber with layer selection
- **DRC** — Run Design Rule Checks
- **Drill Files** — Generate drill file sets
- **Gerber Generation** — Generate complete Gerber file sets
- **3D Export** — Export STEP/VRML 3D models
- **PCB Stats** — Get track/via/component statistics
- **Library Management** — List and export symbols/footprints
- **JSON output** — Machine-readable output with `--json` flag
- **REPL** — Interactive session with undo/redo history

## Installation

```bash
cd agent-harness
pip install -e .
```

## Quick Start

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
```
