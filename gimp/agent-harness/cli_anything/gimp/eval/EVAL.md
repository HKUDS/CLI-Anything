# GIMP CLI — Eval Tasks

Run with the shared framework:

```bash
cli-anything-eval run --harness cli_anything.gimp.eval.tasks --name GIMP
# or, if installed: cli-anything-gimp eval run
```

## Tasks

| ID | Name | Backend | Notes |
| --- | --- | --- | --- |
| export_png | PNG export | Pillow (skipped if missing) | create -> solid layer -> render PNG; verify file_size > 0 |
