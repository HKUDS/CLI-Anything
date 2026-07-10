# Live2D Cubism CLI Harness

## Architecture

This CLI harness provides command-line access to Live2D Cubism model files
(.model3.json, .moc3, .motion3.json, .exp3.json, etc.) without requiring
the Live2D Cubism Editor or runtime.

### What it does

- **Inspect** — Parse .model3.json and display model structure
- **Validate** — Check all referenced files exist
- **Edit** — Modify motions, expressions, textures, and model references
- **Lint** — Best practice checks (naming, texture sizes, structure)
- **Batch** — Edit multiple models at once
- **Diff** — Detailed comparison at field/motion/expression level
- **Preview** — Generate HTML preview of a model
- **Watch** — Auto-validate on file changes
- **Atlas** — Texture atlas analysis (merge/split suggestions)
- **Migrate** — Model format version upgrades
- **Undo** — Auto-backup before edits, with rollback support
- **Scan** — Batch-discover models in a directory tree
- **Export** — Output model summary as JSON or CSV
- **Orphan** — Find unreferenced files
- **Manifest** — File inventory with checksums
- **Runtime** — Compatibility checks for Cubism Viewer, Web SDK, Yoyo
- **Flatten** — Flatten directory for deployment

### File format reference

| File type | Extension | Purpose |
|-----------|-----------|---------|
| Model data | `.moc3` | Binary model mesh + rig |
| Textures | `.png` | Character artwork layers |
| Physics | `.physics3.json` | Hair/clothing simulation |
| Pose | `.pose3.json` | Part switching |
| Motion | `.motion3.json` | Animation keyframes |
| Expression | `.exp3.json` | Expression presets |
| UserData | `.userdata3.json` | Custom metadata |
| DisplayInfo | `.cdi3.json` | Parameter display names |

### Dependencies

- Python 3.10+
- Click 8.1+

## Commands (42 total)

### Read

```bash
inspect <model>              # Model overview
validate <model> [--strict]  # Check files exist
motions <model> [-g group]   # List motions
motion-info <file>           # Motion analysis
expressions <model>          # List expressions
expr-info <file>             # Expression analysis
textures <model>             # List textures with sizes
physics <file>               # Physics config
moc3 <file>                  # Moc3 binary info
params <model>               # Parameter groups
param-list <model>           # All params across motions/expressions
deps <model>                 # Dependency graph
compare <a> <b>              # Quick comparison
diff <a> <b>                 # Detailed diff
scan <dir> [-v]              # Find all models
export <model> [--format]    # Export as JSON/CSV
stats <dir>                  # Project overview
manifest <model>             # File inventory with checksums
```

### Edit (auto-backup)

```bash
edit-motion <model> -g <group> -i <idx> [--fade-in/--fade-out/--file]
add-motion <model> -g <group> --file <motion>
rm-motion <model> -g <group> -i <idx>
add-expr <model> -n <name> -f <file>
rm-expr <model> -n <name>
edit-texture <model> -i <idx> --path <path>
edit-model <model> [--moc3/--physics/--pose/--userdata]
param-edit <expr> -p <param-id> -v <value>
rename-group <model> --old <name> --new <name>
find-replace <model> -f <find> -r <replace> [--dry-run]
```

### Generation

```bash
init <name> [--dir]           # Full model template
gen-motion <name> [--duration/--fps/--loop/--out]
gen-expr <name> [--fade-in/--fade-out/--out]
```

### Analysis

```bash
lint <model> [--level]        # Best practice checks
runtime-check <model> [--target cubism-viewer|web-sdk|yoyo|all]
atlas <model> [--merge/--split/--max-size]
orphan <model>                # Find unreferenced files
```

### Workflow

```bash
undo <model> [--list/--backup]
backup-clean <model> [--keep/--dry-run]
restore-file <model> --file <path>
batch <dir> [--set-fade-in/--set-fade-out/--add-motion-*/--add-expr-*/--set-moc3/--dry-run]
snapshot <model> [--embed/--out]
watch <dir> [--interval]
flatten <model> --out-dir <dir> [--dry-run]
migrate <model> [--target-version/--dry-run]
pack <model> -o <output.zip>
yoyo-check <model>
```

### Global

```bash
--json    # JSON output (any command)
--version # Show version
```
