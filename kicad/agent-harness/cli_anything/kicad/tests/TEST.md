# KiCad test plan

The offline suite verifies that an existing archive is preserved, a new
archive contains the supplied artifacts, and a missing backend gives a JSON
diagnostic.

The opt-in suite uses the installed CLI with KiCad 9. It verifies an ERC
violation and a clean report, reads the fabrication files in the ZIP and
confirms that the placement and BOM skip do-not-populate parts. Invalid
schematics and missing Gerber layers prevent publication of the archive.
