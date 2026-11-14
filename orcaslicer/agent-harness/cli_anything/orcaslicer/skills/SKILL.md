---
name: "cli-anything-orcaslicer"
description: "Prepare and slice 3D prints with the real OrcaSlicer from the command line: manage a project (models, transforms, printer/process/filament presets, any setting override), slice to verified G-code, export 3MF/STL/settings, and publish preview bundles. Use when the user wants to slice an STL/3MF, tune print settings, estimate print time or filament, or automate OrcaSlicer headlessly."
---

# cli-anything-orcaslicer

Stateful CLI over the **real OrcaSlicer** (headless `OrcaSlicer --slice …`). A project is a JSON file
(`*.orca-cli.json`) holding models, ordered transforms, preset choices and setting overrides. Slicing,
G-code, statistics, 3MF and thumbnails are produced by OrcaSlicer itself; the harness validates inputs,
flattens presets and verifies outputs.

## Installation

OrcaSlicer is a **hard dependency** (the CLI errors with instructions if it is missing):

```bash
brew install --cask orcaslicer          # macOS; Linux/Windows: github.com/OrcaSlicer/OrcaSlicer/releases
pip install cli-anything-orcaslicer     # or: cd orcaslicer/agent-harness && pip install -e .
cli-anything-orcaslicer backend info    # verify binary + version (set ORCASLICER_BIN to override)
```

Python 3.10+. Tested with OrcaSlicer 2.5.0.

## Core workflow

```bash
O=cli-anything-orcaslicer
$O project new -n part -o part.orca-cli.json --machine "Generic FDM 256" --process "0.20mm Standard" --filament "Generic PLA"
P="--json --project part.orca-cli.json"          # --json goes BEFORE the group name
$O $P model add /abs/path/part.stl
$O $P model inspect                              # real size / volume / manifold check
$O $P transform rotate 90 --axis x               # transforms apply in the order added
$O $P config set layer_height 0.12               # any of ~740 settings, validated
$O $P config apply sparse_infill_density=30% wall_loops=4
$O $P slice run --outdir /abs/out --export-3mf /abs/out/part.3mf
$O $P slice stats                                # OrcaSlicer's per-feature / per-object numbers
$O $P export gcode /abs/final/part.gcode
```

`slice run --json` returns `{ok, outdir, plates:[{plate, path, layers, max_z, print_time, print_time_s,
filament_g, filament_mm, filament_cm3, extrusion_moves, bytes, statistics}], export_3mf, warnings,
auto_ensure_on_bed, plate_adjusted, orcaslicer_version, command}`.

## Command Groups

## Command Groups

### Top level

Run with no subcommand (or `repl`) for the interactive REPL. Global options: `--json`, `--project PATH`, `--dry-run`, `--version`.

### Project

Project management (new, open, save, info).

| Command | Description |
|---------|-------------|
| `new` | Create a new project. |
| `open` | Open a project file into the session. |
| `save` | Save the project (to PATH, or its current file). |
| `info` | Show project summary. |
| `json` | Print the raw project JSON. |

### Model

Input models (STL / OBJ / 3MF / STEP / AMF).

| Command | Description |
|---------|-------------|
| `add` | Add a model to the project. |
| `remove` | Remove a model by id. |
| `list` | List models. |
| `inspect` | Inspect mesh dimensions/volume/manifold status using OrcaSlicer (--info / --inspect-mesh). |

### Transform

Ordered model transforms (applied by OrcaSlicer to all objects).

| Command | Description |
|---------|-------------|
| `scale` | Uniformly scale by FACTOR. |
| `rotate` | Rotate by DEGREES around an axis. |
| `orient` | Auto-orient objects (OrcaSlicer's orientation optimiser). |
| `arrange` | Auto-arrange objects on the plate. |
| `ensure-on-bed` | Drop objects onto the bed if partly below it (automatic when scaling/tilting). |
| `repetitions` | Repeat the whole model COUNT times. |
| `ground` | Lay objects flat on a chosen face. |
| `repair` | Repair meshes (close holes, fix normals). |
| `list` | List transforms in application order. |
| `remove` | Remove the transform at INDEX. |
| `clear` | Remove all transforms. |

### Profile

Printer / process / filament presets.

| Command | Description |
|---------|-------------|
| `list` | List available presets (built-in and any found in preset directories). |
| `show` | Show a resolved (flattened) preset. |
| `use` | Select the machine / process / filament preset for this project. |
| `dirs` | Show preset search directories (project-specific first). |
| `add-dir` | Add a directory of OrcaSlicer JSON presets to the project's search path. |

### Filament

Filament slots (multi-material projects).

| Command | Description |
|---------|-------------|
| `add` | Append a filament preset as a new slot. |
| `remove` | Remove filament slot SLOT (1-based). |
| `list` | List filament slots. |

### Config

Setting overrides (validated against the real OrcaSlicer schema).

| Command | Description |
|---------|-------------|
| `keys` | Search valid setting keys and their defaults. |
| `get` | Show a setting's effective value and its source. |
| `set` | Override a setting. Lists: pass a JSON array, e.g. '["200","205"]'. |
| `apply` | Set several overrides at once: KEY=VALUE [KEY=VALUE ...]. |
| `unset` | Remove an override. |
| `list` | List current overrides. |

### Slice

Slice with the real OrcaSlicer and inspect results.

| Command | Description |
|---------|-------------|
| `options` | Show or persist default slice options. |
| `run` | Slice the project and write verified G-code. |
| `stats` | Per-feature / per-object statistics from the last slice (OrcaSlicer's own numbers). |
| `last` | Show a summary of the most recent slice. |
| `gcode-info` | Verify and summarise any OrcaSlicer G-code file. |

### Export

Export 3MF / settings / STL / G-code.

| Command | Description |
|---------|-------------|
| `3mf` | Export an OrcaSlicer 3MF project (sliced by default; embeds G-code + thumbnails). |
| `settings` | Dump the full effective configuration resolved by OrcaSlicer. |
| `stl` | Export the transformed objects as STL files into DEST_DIR. |
| `gcode` | Copy the last slice's G-code to PATH (run 'slice run' first). |

### Preview

Preview bundles (producer). Inspect with: cli-hub previews inspect <bundle_dir>.

| Command | Description |
|---------|-------------|
| `recipes` | List preview recipes. |
| `capture` | Slice with OrcaSlicer and publish a preview bundle (cached by project fingerprint). |
| `latest` | Return the newest existing bundle (never renders). |
| `diff` | Capture now and publish a before/after comparison bundle against a baseline. |

### Backend

The OrcaSlicer binary used by this harness.

| Command | Description |
|---------|-------------|
| `info` | Show OrcaSlicer executable, version and supported CLI flags. |

### Session

Session state, undo / redo.

| Command | Description |
|---------|-------------|
| `status` | Show session status. |
| `undo` | Undo the last project edit. |
| `redo` | Redo the last undone edit. |
| `history` | List the undo history. |

## Presets and settings

* **Built-in**: machines `Generic FDM 220|256|350`; processes `0.08mm Extra Fine`, `0.12mm Fine`,
  `0.16mm Optimal`, `0.20mm Standard`, `0.20mm Strength`, `0.24mm Draft`, `0.28mm Extra Draft`;
  filaments `Generic PLA|PETG|ABS|ASA|TPU`. Select with `profile use machine|process|filament NAME`
  (`filament add` for extra slots; `model add --filament N` assigns a model to a slot).
* **Vendor / user presets**: pass a path to a preset `.json`, or a preset *name* from a preset directory
  (`profile add-dir DIR`, `--profiles-dir`, or env `ORCASLICER_PROFILES_DIR`; e.g. an OrcaSlicer checkout's
  `resources/profiles`). `inherits` chains are flattened automatically. `profile list --source system`
  shows what was found.
* **Bambu Lab (A1 mini etc.)**: real Bambu presets are found automatically via Bambu Studio's JSON profiles
  (`profile list --kind machine --source system | grep A1`). Example:
  `project new --machine "Bambu Lab A1 mini 0.4 nozzle" --process "0.20mm Standard @BBL A1M" --filament "Bambu PLA Basic @BBL A1M"`.
  The harness slices/exports only; it does not send jobs to the printer.
* **Settings**: find keys with `config keys --search infill [--kind process]`; check with `config get KEY`
  (shows value + source: override / preset / default). Vector settings take one value (`210`) or a JSON
  array (`'["200","205"]'`). Unknown keys and non-numeric values for numeric settings are rejected with
  suggestions — OrcaSlicer itself would silently ignore a typo.

## Preview bundles (producer vs. consumer)

* **Produce** with this CLI — real OrcaSlicer slices and renders; output follows `preview-bundle/v1`:
  `preview recipes` · `preview capture [--recipe quick|full] [--force]` · `preview latest` (never renders) ·
  `preview diff` (captures now, compares with the previous capture). Modes: static + diff; no live mode.
* **Consume** with `cli-hub previews inspect|html|watch|open <bundle_dir>` — read-only viewer, never a render path.
* `preview capture --json` returns `_bundle_dir`, `_manifest_path`, `_summary_path`, `artifacts[]`
  (`hero.png` isometric, `top.png` top-down, with `full`: `statistics.json`, `project.3mf`), `metrics`
  (`layers`, `print_time_s`, `filament_g`, `max_z_mm`), `cached`. Bundles live in
  `<project_dir>/.cli-anything/previews/orcaslicer/<recipe>/` and are cached by a fingerprint of models,
  transforms, presets and overrides.
* **Truthfulness**: PNGs are OrcaSlicer's own plate thumbnails (the *model on the plate* after transforms,
  not toolpaths). Use `metrics` / `statistics.json` for toolpath-level facts.

```bash
BUNDLE=$($O $P preview capture | python3 -c 'import json,sys; print(json.load(sys.stdin)["_bundle_dir"])')  # publish
cli-hub previews inspect "$BUNDLE"                      # inspect (read-only consumer)
```

## For AI Agents

1. **Always pass `--json`** (before the group name). Errors are JSON on stdout with exit code 1:
   `{"error": "...", "type": "ValueError|file_not_found|OrcaSlicerError", "code_name": "CLI_..."}`.
2. **Auto-save**: one-shot commands that change the project save it automatically; `--dry-run` previews
   without saving. In the REPL nothing auto-saves — run `project save`. `session undo|redo` work in the REPL.
3. **Use absolute paths** for models and outputs. Existing exports need `--overwrite`.
4. **Check results, not exit codes alone**: `slice run` already verifies the G-code (header, extrusions);
   compare `layers`, `max_z`, `print_time_s`, `filament_g` with what you expect.
5. **Pitfalls the harness handles** (don't work around them):
   * Scale / tilt pivots about the object centre and OrcaSlicer silently clips what falls below the bed
     (`rotate-x 90` of a 30 mm box prints 5 mm) → `--ensure-on-bed` is added automatically
     (`auto_ensure_on_bed: true` in the result; opt out with `slice options --no-auto-ensure-on-bed`).
   * `transform repetitions N` makes N arranged copies (via `--clone-objects`).
   * Transforms apply to **all** models in the project, in the order added.
   * Multi-material works: `filament add NAME`, then `model add FILE --filament N` (slots are 1-based); the G-code gets real tool changes.
   * `--strict` (fail on non-critical warnings) cannot be combined with `--no-check`.
6. **Failure modes**: `CLI_FILE_NOTFOUND`, `CLI_CONFIG_FILE_ERROR` (bad setting value),
   `CLI_VALIDATE_ERROR` (preset combination invalid), `CLI_OBJECTS_PARTLY_INSIDE` / `CLI_NO_SUITABLE_OBJECTS`
   (part doesn't fit the bed → scale down or pick a larger machine), `KILLED_BY_SIGNAL_*` (preset missing a
   required key). The message includes a hint.

## More examples

```bash
# Compare quality presets
for p in "0.28mm Extra Draft" "0.08mm Extra Fine"; do
  $O --json --project part.orca-cli.json profile use process "$p"
  $O --json --project part.orca-cli.json slice run --outdir /abs/out_$(echo $p | cut -c1-4)
done

# Material swap and temperature tweak
$O $P profile use filament "Generic PETG"
$O $P config set nozzle_temperature 245

# Lay a part flat, then check the plate before committing
$O $P transform ground --largest
$O $P preview capture --recipe full

# Inspect any OrcaSlicer G-code without a project
$O --json slice gcode-info /abs/out/plate_1.gcode
```

## Version

1.0.0
