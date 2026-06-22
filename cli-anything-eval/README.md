# cli-anything-eval

Shared eval/benchmark framework for CLI-Anything harnesses. Provides a generic task
runner, baseline regression detection, JSON+Markdown reports, and a cross-harness
leaderboard.

## Install

```bash
pip install -e cli-anything-eval
```

## Authoring tasks

Create modules under `cli_anything/<software>/eval/tasks/`. Each module exports:

```python
TASK = {
    "id": "export_png",
    "name": "PNG export",
    "description": "Create a project and render to PNG",
    "prompt": "Create an image and export it to PNG.",   # optional (future agent grading)
    "requires": ["gimp"],                                 # optional (binaries via shutil.which)
}

def run(ctx):                 # the scripted reference solution
    out = ctx.task_artifact_path("out.png")
    ...
    return {"metrics": {...}, "artifacts": [str(out)]}

def verify(ctx):              # optional grader; reused by future agent mode
    out = ctx.task_artifact_path("out.png")
    return {"ok": out.exists() and out.stat().st_size > 0, "metrics": {...}}

def precheck(ctx):            # optional; return a skip-reason string, or None to proceed
    ...
```

If `verify` is present, the pass/fail verdict comes from it; otherwise from `run`'s
returned `{"ok": ...}` (the legacy form).

## Running

```bash
# Any harness that ships an eval/tasks package, no harness change required:
cli-anything-eval run --harness cli_anything.gimp.eval.tasks --name GIMP

# Cross-harness leaderboard (auto-discovers installed harnesses):
cli-anything-eval suite

# Optional per-harness subcommand (if the harness registered it):
cli-anything-gimp eval run
```

## Status model

`pass`, `fail`, `error`, `skipped`. `attempted = pass + fail + error`;
`success_rate = passed / attempted`. `skipped` (unmet `requires`/`precheck`) is reported
separately and excluded from `attempted`.
