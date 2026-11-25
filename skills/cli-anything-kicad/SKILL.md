---
name: "cli-anything-kicad"
description: Run headless KiCad electrical rule checks and package Gerber, drill, placement, and BOM outputs with cli-anything-kicad.
---

# KiCad

Install KiCad 9 with `kicad-cli` on PATH or set `KICAD_CLI` to its path.

```bash
cli-anything-kicad --json sch lint controller.kicad_sch
cli-anything-kicad --json pcb export-fab controller.kicad_pcb --schematic controller.kicad_sch --output controller-fab.zip
```

Read the ERC report when the lint command exits with 5. For fabrication,
supply the schematic that matches the board and use a new archive path.
Use `--layers` when a subset of the board's Gerber layers is required.
