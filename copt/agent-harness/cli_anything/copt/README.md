# CLI-Anything COPT

Structured commands for the installed Cardinal Optimizer COPT solver. All optimization, model conversion, and IIS computation is performed by `copt_cmd`.

## Requirements

- Python 3.10 or newer
- A licensed COPT installation with `copt_cmd` (tested with COPT 8.0.2)
- Set `COPT_CMD` to the executable path, or `COPT_HOME` to the installation directory. The macOS fallback is `/Applications/copt802-scuc/bin/copt_cmd`.

## Install

From this `agent-harness` directory, run `pip install -e .` in a Python environment. Once the harness is merged upstream, it can also be installed with `pip install 'git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=copt/agent-harness'`. The command is `cli-anything-copt`. COPT and its license are not included in the Python package.

## Commands

```bash
cli-anything-copt --json doctor
cli-anything-copt --json model inspect /path/to/model.mps
cli-anything-copt --json solve /path/to/model.mps --time-limit 60 --threads 8 --rel-gap 0.001
cli-anything-copt --json solve /path/to/model.lp --solution /path/to/result.json
cli-anything-copt --json model convert /path/to/model.mps --output /path/to/model.lp
cli-anything-copt --json diagnose iis /path/to/infeasible.lp --output /path/to/conflict.iis
cli-anything-copt
```

The final command enters the interactive REPL. Each model command takes an existing `.lp`, `.mps`, `.lp.gz`, or `.mps.gz` file. Output files must not already exist. `--json` emits one JSON object for scripts and agents; failures exit nonzero and print the COPT error on stderr. The `solve` command returns the solver status, objective, and COPT attributes. Use `--lp-relaxation` to run `optimizelp` on a MIP.

The wrapper is stateless: each command reads the model again. It does not modify the input model. For advanced solver commands, use `copt_cmd` directly.

For a time-limited MIP solve, `status: "timeout"` can still include an `objective` if COPT found a feasible solution. The `attributes.BestGap` field shows the remaining relative gap; a timeout does not mean the solution is proven optimal.

## COPT 8.0.2 names

This installation documents `RelGap` for MIP gap, `BestObj` for the MIP objective, and `PoolSols` for the solution pool count. The names `mipgap`, `MipObjval`, and `SolCount` in some older notes are rejected by this local `copt_cmd`.
