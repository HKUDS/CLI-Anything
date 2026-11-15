# OrcaSlicer — Agent Harness SOP

CLI-Anything harness for [OrcaSlicer](https://github.com/OrcaSlicer/OrcaSlicer)
(open-source C++17 FFF slicer, wxWidgets GUI, fork of Bambu Studio / PrusaSlicer).

## 1. Codebase analysis

### Backend engine
The GUI (`src/slic3r/GUI`) is a thin layer over **libslic3r** (`src/libslic3r`).
The *same binary* exposes a complete headless mode (`src/OrcaSlicer.cpp`,
option tables in `libslic3r/PrintConfig.cpp`: `CLIActionsConfigDef`,
`CLITransformConfigDef`, `CLIMiscConfigDef`). Running
`OrcaSlicer --slice 0 --load-settings "machine.json;process.json" --load-filaments f.json model.stl`
performs the identical pipeline as pressing *Slice plate* → *Export G-code*.
**That binary is the backend; the harness never re-implements slicing.**

| Platform | Binary |
|---|---|
| macOS | `/Applications/OrcaSlicer.app/Contents/MacOS/OrcaSlicer` (`brew install --cask orcaslicer`) |
| Linux | `orca-slicer` (AppImage / distro package / flatpak wrapper) |
| Windows | `C:\Program Files\OrcaSlicer\orca-slicer.exe` |

Override with `ORCASLICER_BIN`.

### GUI action → CLI mapping
| GUI action | Backend flag(s) |
|---|---|
| Import model (STL/OBJ/3MF/STEP/AMF) | positional input files |
| Slice plate / all plates | `--slice N` (0 = all) |
| Export G-code | `--outputdir DIR` (`plate_N.gcode`) |
| Save project | `--export-3mf FILE` (also embeds G-code + thumbnails when sliced) |
| Statistics panel (time, filament, per-feature) | `--export-statistics` → `plate_N.statistics.json` |
| Scale / Rotate X/Y/Z | `--scale`, `--rotate`, `--rotate-x`, `--rotate-y` |
| Auto-orient / Arrange | `--orient 1`, `--arrange 1` (+`--allow-rotations`) |
| Lay on face | `--ground-largest-face`, `--ground-face-normal`, `--ground-face-point` |
| Fix model | `--repair` |
| Clone / skip objects | `--clone-objects`, `--skip-objects` |
| Object→filament assignment | `--load-filament-ids` |
| Object info dialog | `--info`, `--inspect-mesh` (JSON), `--inspect-paint` (JSON) |
| Dump effective config | `--export-settings FILE|-` |
| Process/printer/filament presets | `--load-settings "m.json;p.json"`, `--load-filaments "f1.json;f2.json"` |

### Data model
* **Native project**: `.3mf` (ZIP: `3D/*.model`, `Metadata/project_settings.config`,
  `Metadata/plate_N.gcode`, `plate_N.png`, `slice_info.config`, …).
* **Presets**: JSON, three kinds — `machine`, `process`, `filament`. Vendor presets
  form `inherits` chains (`0.20mm Standard @X` → `fdm_process_x_common` → `fdm_process_common`).
  The CLI does **not** resolve `inherits` itself, so presets passed to
  `--load-settings` must be flattened. The harness does that.
* **Config keys**: ~740 preset keys. Values are strings; per-extruder values are arrays.
  `OrcaSlicer --export-settings -` prints every valid key with its default.

### Existing CLI behaviours that shape the design (verified against 2.5.0)
* Exit code is `CLI_*` (negative, `libslic3r/Utils.hpp`) modulo 256 (e.g. `253` = -3 file not found,
  `205` = -51 validate error, `251` = -5 config error). Harness decodes these.
* `result.json` is written on **Linux only** → harness derives results from files + exit code.
* `--export-3mf NAME` is joined onto `--outputdir`; without `--outputdir`, an absolute path works.
* Unknown config keys are **silently ignored** → harness validates keys against the real binary's dump.
* A filament preset without `filament_diameter` **segfaults** the binary → harness always supplies it.
* Bare defaults fail validation (`G92 E0` missing from `layer_gcode`, zero extruder clearances) → built-in
  generic presets set them.
* **Scale/tilt clipping**: transforms pivot about the object centre and anything below the bed is silently
  clipped (`--rotate-x 90` of a 30 mm box prints 5 mm, exit 0). `--ensure-on-bed` fixes it → the harness
  appends it automatically whenever `scale` / `rotate_x` / `rotate_y` is present.
* **`--repetitions` only works for 3MF input** with `--slice N>0` (STL → `CLI_INVALID_PARAMS`, `--slice 0` →
  `CLI_INVALID_PARAMS`). `--clone-objects N,N,…` works for meshes and arranges copies without overlap → the
  harness maps its `repetitions` transform to `--clone-objects`, falling back to native `--repetitions`
  (+ plate 1) for 3MF-only projects.
* Preset JSON needs `"from"` ∈ {`system`,`User`,`user`}; anything else → `CLI_CONFIG_FILE_ERROR` ("from
  unsupported"). The harness normalises it.
* With more than one filament every filament preset must define **all** per-filament vectors
  ("filament_is_support's count 1 not equal to filament_colour's size 2" → `CLI_CONFIG_FILE_ERROR`). The harness completes
  each slot with the binary's own defaults (`config.complete_filament`) — multi-material then slices with real `T1` changes.
* Vendor trees reuse parent names (`fdm_machine_common` in every vendor) → resolving by name alone inherits from the
  wrong vendor (A1 mini got a Klipper `PRINT_START` start G-code). The harness prefers the parent nearest the child.
* Bambu presets set `extruder_clearance_max_radius` (newer name) but the 2.5.0 CLI validates `extruder_clearance_radius`
  (parent value 0 → `CLI_INVALID_VALUES_IN_3MF`). OrcaSlicer's `handle_legacy` renames it; the harness mirrors that.
* Bundle ids for `preview capture --force` could collide within one second → the harness disambiguates.
* No undo/redo exists in the CLI → the harness provides it for project edits.

## 2. CLI architecture

* **Interaction model**: both — one-shot subcommands and REPL (default with no args).
* **State**: file-backed project JSON (`*.orca-cli.json`) holding models, ordered transforms,
  preset selection, per-kind overrides, slice options and last slice results. Session keeps
  undo/redo (50 deep). One-shot mutations auto-save; `--dry-run` suppresses the save.
  Saves use `_locked_save_json` (exclusive flock).
* **Output**: human text by default, `--json` on every command.

```
cli-anything-orcaslicer [--json] [--project P] [--dry-run] <group> <cmd>
  project   new | open | save | info | json
  model     add | remove | list | inspect
  transform scale | rotate | orient | arrange | ensure-on-bed | repetitions | ground | repair | list | remove | clear
  profile   list | show | use | dirs | add-dir
  config    keys | get | set | apply | unset | list
  filament  add | remove | list
  slice     options | run | stats | last | gcode-info
  export    3mf | settings | stl | gcode
  preview   recipes | capture | latest | diff
  backend   info
  session   status | undo | redo | history
  repl
```

### Pipeline (`slice run`)
1. resolve presets (built-in → flattened `inherits` chain → apply project overrides),
2. write `machine.json` / `process.json` / `filament_N.json` into `<outdir>/settings/`,
3. invoke the real binary with absolute paths and `cwd=<outdir>`,
4. verify exit code, G-code existence and magic (`; HEADER_BLOCK_START`, `; generated by OrcaSlicer`),
5. parse `plate_N.statistics.json` and the G-code footer into a result dict.

### Preview (truthful)
`preview capture` slices with the real binary and `--export-3mf`; the **thumbnails OrcaSlicer itself
rendered** (`Metadata/plate_N.png`, `top_N.png`) plus `statistics.json` are packaged in a
`preview-bundle/v1`. No Python rendering, no GUI scraping. Live sessions are not provided
(a slice is not an incremental state stream).

## 3. Licensing note
Built-in presets are original minimal value sets layered over the defaults of the real binary; no
OrcaSlicer (AGPL-3.0) profile data is redistributed. The key→category table (`data/config_categories.json`)
contains only option names derived from `Preset.cpp`.
