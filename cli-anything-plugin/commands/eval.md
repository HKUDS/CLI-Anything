# cli-anything:eval Command

Run a harness's eval/benchmark tasks and report agent task completion rate.

## CRITICAL: Read HARNESS.md First

**Before running eval, read `./HARNESS.md`** — see its "Eval / Benchmark" section for the task
contract and the deterministic-vs-skipped rules.

## Usage

```bash
/cli-anything:eval <software-path-or-repo>
```

## Arguments

- `<software-path-or-repo>` — **Required.** A local path or GitHub URL. The software name is
  derived from the directory; the harness is located at `<software-name>/agent-harness/`.

## What This Command Does

1. **Locates the harness** and its `cli_anything/<software>/eval/tasks/` package.
2. **Runs the shared runner**: `cli-anything-eval run --harness cli_anything.<software>.eval.tasks --name <Software>`.
3. **Captures the report** (`eval_report.json` + `eval_report.md`).
4. **Updates `cli_anything/<software>/eval/EVAL.md`** with the latest results table.
5. **Reports** pass/attempted/skipped and success rate.

## Authoring tasks (if none exist)

Create modules under `cli_anything/<software>/eval/tasks/` following the contract in HARNESS.md:
`TASK` dict + `run(ctx)` + optional `verify(ctx)` + optional `precheck(ctx)`/`requires`.
Backend-free tasks must pass deterministically; backend-dependent tasks must declare
`requires`/`precheck` so they report `skipped` (not `fail`) when the binary is absent.

## Success Criteria

- The runner completes and writes `eval_report.json` + `eval_report.md`.
- No task reports `error` (unexpected exception). `skipped` is acceptable when a backend is absent.
- `EVAL.md` reflects the latest run.

## Failure Handling

If a task reports `error`, show the captured message and fix the task or the harness code.
Use `--baseline <file>` + `--fail-on-regression` to gate against a stored baseline.
