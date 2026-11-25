# KiCad CLI

Run electrical rule checks and export PCB fabrication files using KiCad's
native command-line backend. Install KiCad 9 and make `kicad-cli` available on
your PATH. The harness also checks the standard KiCad application path on
macOS. Use `--binary` or `KICAD_CLI` for other installations, including a
Windows install whose `bin` directory is outside PATH.

```bash
pip install -e .
cli-anything-kicad --json sch lint controller.kicad_sch
cli-anything-kicad --json pcb export-fab controller.kicad_pcb \
  --schematic controller.kicad_sch --output controller-fab.zip
```

`sch lint` prints KiCad's ERC JSON report and exits with 5 when the report
contains violations. A clean report exits with 0.

`pcb export-fab` creates a new ZIP with per-layer Gerbers, Excellon drill
files, a millimetre placement CSV and a BOM CSV. Supply the schematic that
matches the board. The placement and BOM exports exclude parts marked
do-not-populate. Use `--layers F.Cu,B.Cu,F.Mask,B.Mask,Edge.Cuts` to limit the
Gerbers to specific layers. Without it, KiCad selects the layers. The CLI
writes the archive after all four exports succeed and every requested layer
has a Gerber. An existing output file is preserved. On Linux and macOS, use a
destination directory on a filesystem that supports hard links for atomic
publication.

Run `cli-anything-kicad` without a subcommand for the interactive shell.
Set the native executable at startup when using the shell.

## Tests

```bash
python -m pytest cli_anything/kicad/tests/test_core.py
KICAD_E2E=1 python -m pytest cli_anything/kicad/tests/test_full_e2e.py
```

The second command requires KiCad 9 and an installed `cli-anything-kicad`
command. It uses the included schematic and board fixtures.
