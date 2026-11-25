# KiCad harness

The Click commands and shell call the same backend. The harness runs
`kicad-cli` in the input file's directory so KiCad can resolve project
resources. The schematic and board remain the source of truth.

The ERC workflow reads KiCad's temporary JSON report. The fabrication
workflow exports Gerbers, drills, placement and BOM into a temporary directory
and writes one ZIP after validating those outputs.

See the [KiCad 9 CLI reference](https://docs.kicad.org/9.0/en/cli/cli.html).
