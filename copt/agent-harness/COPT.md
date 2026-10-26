# COPT 8.0.2 command-line harness

Development backend: COPT 8.0.2 at `/Applications/copt802-scuc` (installed binaries, headers, libraries, docs and examples; no application source code). Users can supply another installation through `COPT_CMD`, `COPT_HOME`, or `PATH`. COPT and its license are external dependencies and are not redistributed with this harness.

Backend: `copt_cmd`. This native solver reads `.lp`, `.mps`, and their `.gz` variants. It exposes `read`, `optimize`, `get`, `iis`, `writeiis`, `writesol`, `writejsonsol`, `writelp`, and `writemps` through `-c` scripts. The harness calls this backend directly and never computes optimization results itself.

The harness has no saved project state: a model file is the input for each operation. One-shot commands and the REPL use the same command handlers. JSON output reports COPT attributes and artifact paths. User model paths are staged under a safe temporary name before interpolation into a COPT script; requested artifacts are copied out after COPT writes them.

Command groups: `doctor`, `model inspect`, `solve`, `diagnose iis`, and `model convert`. The native COPT CLI remains available for advanced commands not surfaced here.
