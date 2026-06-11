---
name: cli-anything-live2d
description: "Inspect, validate, edit, lint, diff, batch-manage, and deploy Live2D Cubism models (.model3.json) from the command line."
metadata: { "cli-anything": { "category": "graphics", "requires": null } }
---

# cli-anything-live2d

Full-featured CLI for Live2D Cubism models. 42 commands covering inspection,
editing, linting, diffing, batch operations, asset management, generation,
and deployment — all without the Live2D Editor.

## Commands (42 total)

### Read (18)

| Command | Purpose |
|---------|---------|
| `inspect <model>` | Model overview (version, counts, features) |
| `validate <model>` | Check all referenced files exist |
| `motions <model>` | List motions with fade times |
| `motion-info <file>` | Detailed motion analysis |
| `expressions <model>` | List expression presets |
| `expr-info <file>` | Detailed expression analysis |
| `textures <model>` | List textures with dimensions and sizes |
| `physics <file>` | Physics simulation config |
| `moc3 <file>` | Moc3 binary info |
| `params <model>` | Parameter groups |
| `param-list <model>` | All params across motions/expressions |
| `deps <model>` | Dependency graph |
| `compare <a> <b>` | Quick comparison |
| `diff <a> <b>` | Detailed diff |
| `scan <dir>` | Find all models in directory |
| `export <model>` | Export as JSON/CSV |
| `stats <dir>` | Project overview |
| `manifest <model>` | File inventory with SHA256 checksums |

### Edit (10, all auto-backup)

| Command | Purpose |
|---------|---------|
| `edit-motion` | Edit motion fade times or file path |
| `add-motion` | Add motion to group |
| `rm-motion` | Remove motion |
| `add-expr` | Add expression |
| `rm-expr` | Remove expression |
| `edit-texture` | Replace texture path |
| `edit-model` | Edit moc3/physics/pose/userdata |
| `param-edit` | Edit parameter value in .exp3.json |
| `rename-group` | Rename a motion group |
| `find-replace` | Batch rename file references |

### Generation (3)

| Command | Purpose |
|---------|---------|
| `init` | Generate full model template |
| `gen-motion` | Generate skeleton .motion3.json |
| `gen-expr` | Generate skeleton .exp3.json |

### Analysis (4)

| Command | Purpose |
|---------|---------|
| `lint` | Best practice checks |
| `runtime-check` | Cubism Viewer / Web SDK / Yoyo compatibility |
| `atlas` | Texture atlas analysis |
| `orphan` | Find unreferenced files |

### Workflow (7)

| Command | Purpose |
|---------|---------|
| `undo` | Restore from auto-backup |
| `backup-clean` | Rotate old backups |
| `restore-file` | Restore specific file from backup |
| `batch` | Batch-edit multiple models |
| `snapshot` | Generate HTML preview |
| `watch` | Auto-validate on file changes |
| `flatten` | Flatten directory for deployment |

### Other (3)

| Command | Purpose |
|---------|---------|
| `migrate` | Model format version upgrade |
| `pack` | Package model + deps into zip |
| `yoyo-check` | Yoyo desktop-pet readiness |

All read commands support `--json`. Edit commands auto-backup.

## Examples

```bash
cli-anything-live2d inspect model.model3.json
cli-anything-live2d lint model.model3.json --level info
cli-anything-live2d edit-motion model.model3.json -g Idle -i 0 --fade-in 0.3
cli-anything-live2d find-replace model.model3.json -f "old_tex" -f "new_tex"
cli-anything-live2d orphan model.model3.json
cli-anything-live2d runtime-check model.model3.json --target web-sdk
cli-anything-live2d flatten model.model3.json --out-dir ./deploy/
cli-anything-live2d batch ./models/ --set-fade-in 0.3 --dry-run
cli-anything-live2d snapshot model.model3.json --embed
cli-anything-live2d stats ./project/
```
