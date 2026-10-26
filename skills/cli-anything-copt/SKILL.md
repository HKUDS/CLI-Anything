---
name: cli-anything-copt
description: Use the installed COPT solver through cli-anything-copt to inspect, solve, convert LP/MPS models and export IIS or JSON solutions.
---

# CLI-Anything COPT

Use `cli-anything-copt` for structured, scriptable COPT operations. The command invokes the real `copt_cmd` solver and requires a valid COPT license. If COPT is in a different installation, set `COPT_CMD` to its executable or `COPT_HOME` to its installation root.

The input is an existing `.lp`, `.mps`, `.lp.gz`, or `.mps.gz` model. Each invocation reads the model anew and leaves it unchanged. Output paths must not exist yet. Use `--json` before the subcommand for machine-readable stdout; errors exit nonzero and go to stderr.

## Commands

```bash
cli-anything-copt --json doctor
cli-anything-copt --json model inspect /path/to/model.mps
cli-anything-copt --json solve /path/to/model.mps --time-limit 60 --threads 8 --rel-gap 0.001
cli-anything-copt --json solve /path/to/model.lp --solution /path/to/result.json
cli-anything-copt --json model convert /path/to/model.mps --output /path/to/model.lp
cli-anything-copt --json diagnose iis /path/to/infeasible.lp --output /path/to/conflict.iis
```

`solve --lp-relaxation` uses COPT `optimizelp`. The `solve` result includes `status`, `status_code`, `objective`, and raw COPT attributes. For MIP, it reports `BestObj`; for LP, `LpObjval`. Inspect `attributes.BestBnd` and `attributes.BestGap` for MIP progress. `model inspect` reports `Rows`, `Cols`, `Elems`, `IsMIP`, `Bins`, and `Ints`.

A time-limited MIP may return `status: "timeout"` with a feasible `objective`; inspect `BestGap` to see how far COPT is from a proof of optimality.

Run `cli-anything-copt` without arguments for a REPL that accepts the same subcommands. The REPL has command history; there is no saved project state or undo/redo.

The installed solver also supports advanced COPT operations directly via `copt_cmd`. For command details, run `cli-anything-copt --help` or read the packaged `README.md`.
