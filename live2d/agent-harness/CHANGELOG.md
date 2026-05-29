# Changelog

## 0.3.0 (2026-05-29)

### New features

**Edit commands** (all auto-backup before modifying):
- `edit-motion` — Edit motion fade-in/out times or file path
- `add-motion` — Add a motion to a group (creates group if needed)
- `rm-motion` — Remove a motion from a group
- `add-expr` — Add an expression to the model
- `rm-expr` — Remove an expression from the model
- `edit-texture` — Replace a texture file path
- `edit-model` — Edit model-level references (moc3, physics, pose, userdata)
- `param-edit` — Edit parameter values inside .exp3.json files
- `rename-group` — Rename a motion group
- `find-replace` — Batch rename file references across the entire model

**Asset management:**
- `orphan` — Find files in the model directory not referenced by any model
- `restore-file` — Restore a specific file from backup
- `backup-clean` — Clean old backups, keep only the N most recent
- `manifest` — Generate a manifest of all files with SHA256 checksums and sizes
- `stats` — Project overview (model count, motions, expressions, textures, disk usage)

**Generation:**
- `gen-motion` — Generate a skeleton .motion3.json file
- `gen-expr` — Generate a skeleton .exp3.json file
- `init` — Generate a full model template/skeleton

**Analysis:**
- `lint` — Best practice checks (naming, textures, motions, structure)
- `diff` — Detailed diff between two models at field/motion/expression/texture level
- `param-list` — List all unique parameters used across motions and expressions
- `runtime-check` — Check compatibility with specific runtimes (Cubism Viewer, Web SDK, Yoyo)
- `atlas` — Texture atlas analysis with merge/split suggestions

**Workflow:**
- `undo` — Restore model from auto-backup (with `--list` and `--backup` options)
- `batch` — Batch-edit multiple models in a directory (supports `--dry-run`)
- `snapshot` — Generate HTML preview page with dark theme and texture previews
- `watch` — Watch directory for file changes and auto-validate
- `flatten` — Flatten directory structure for deployment (all files in one dir)
- `migrate` — Migrate model format to newer versions

### Changes

- `save_model()` function added to `parser.py` for writing modified models back to disk
- All edit commands create automatic backups before modifying files
- Version bumped to 0.3.0

### New modules

- `core/backup.py` — Auto-backup, snapshot, list, restore
- `core/linter.py` — Best practice lint checks
- `core/differ.py` — Detailed model diffing
- `core/snapshot.py` — HTML preview generation

### Tests

- 40 new tests covering all new features

### Documentation

- Updated LIVE2D.md with all 42 commands
- Updated SKILL.md with full command reference and examples

## 0.2.0

Initial release with read-only commands: inspect, validate, motions, motion-info, expressions, expr-info, textures, physics, moc3, deps, compare, pack, yoyo-check, init, scan, export, params.
