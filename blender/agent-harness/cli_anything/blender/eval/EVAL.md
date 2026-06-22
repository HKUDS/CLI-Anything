# Blender CLI — Eval Tasks

```bash
cli-anything-eval run --harness cli_anything.blender.eval.tasks --name Blender
```

## Tasks

| ID | Name | Backend | Notes |
| --- | --- | --- | --- |
| render_script | Render script generation | none | verifies a valid bpy script is generated |
| render_execute | Single-frame render | blender (skipped if missing) | runs blender headless; verifies a PNG is produced |
