# cli-anything-orcaslicer

A stateful command-line harness for [OrcaSlicer](https://github.com/OrcaSlicer/OrcaSlicer) that lets
agents (and humans) prepare 3D prints without the GUI: add models, transform them, choose
machine / process / filament presets, tune any setting, **slice with the real OrcaSlicer**, export
G-code / 3MF / STL, and publish truthful preview bundles.

Everything that matters is produced by the real application: slicing, G-code, statistics, 3MF
projects and plate thumbnails all come from the OrcaSlicer binary running headless
(`OrcaSlicer --slice … --load-settings … --load-filaments …`). The harness manages project state,
preset flattening, validation and verification around it — it never re-implements slicing.

## 1. Install the real software (hard dependency)

```bash
brew install --cask orcaslicer                        # macOS
# Linux / Windows: https://github.com/OrcaSlicer/OrcaSlicer/releases
```

Tested with OrcaSlicer 2.5.0. If the binary lives elsewhere: `export ORCASLICER_BIN=/path/to/OrcaSlicer`.
The CLI fails with install instructions if OrcaSlicer is missing — there is no fallback.

## 2. Install the CLI

```bash
cd orcaslicer/agent-harness
pip install -e .
which cli-anything-orcaslicer
cli-anything-orcaslicer backend info      # confirms the OrcaSlicer binary, version, supported flags
```

## 3. Usage

```bash
# One-shot (every mutation is auto-saved to the project file; add --dry-run to suppress)
cli-anything-orcaslicer project new -n bracket -o bracket.orca-cli.json \
    --machine "Generic FDM 256" --process "0.20mm Standard" --filament "Generic PLA"
P="--project bracket.orca-cli.json"
cli-anything-orcaslicer $P model add bracket.stl
cli-anything-orcaslicer $P model inspect                     # real mesh info from OrcaSlicer
cli-anything-orcaslicer $P transform rotate 90 --axis x      # ordered transforms
cli-anything-orcaslicer $P config set sparse_infill_density 30%
cli-anything-orcaslicer $P config set nozzle_temperature 215
cli-anything-orcaslicer --json $P slice run --outdir out --export-3mf out/bracket.3mf
cli-anything-orcaslicer --json $P slice stats                # per-feature time/filament

# Interactive REPL (default with no subcommand)
cli-anything-orcaslicer
```

Every command accepts the global `--json` flag (put it before the group name).

### Command groups

| Group | Commands |
|---|---|
| `project` | `new`, `open`, `save`, `info`, `json` |
| `model` | `add`, `remove`, `list`, `inspect` |
| `transform` | `scale`, `rotate [--axis x\|y\|z]`, `orient`, `arrange`, `ensure-on-bed`, `repetitions`, `ground`, `repair`, `list`, `remove`, `clear` |
| `profile` | `list`, `show`, `use`, `dirs`, `add-dir` |
| `filament` | `add`, `remove`, `list` (multi-material slots) |
| `config` | `keys`, `get`, `set`, `apply`, `unset`, `list` |
| `slice` | `options`, `run`, `stats`, `last`, `gcode-info` |
| `export` | `3mf`, `settings`, `stl`, `gcode` |
| `preview` | `recipes`, `capture`, `latest`, `diff` |
| `backend` | `info` |
| `session` | `status`, `undo`, `redo`, `history` |

### Presets

* Built-in generic presets: machines `Generic FDM 220/256/350`; processes `0.08mm Extra Fine` …
  `0.28mm Extra Draft` and `0.20mm Strength`; filaments `Generic PLA/PETG/ABS/ASA/TPU`.
* Your own or vendor presets: pass a path to a preset `.json`, or a preset **name** found in a preset
  directory. Directories searched: `--profiles-dir` / `profile add-dir`, `ORCASLICER_PROFILES_DIR`,
  and OrcaSlicer's data directory. `inherits` chains are flattened for you (the OrcaSlicer CLI does
  not do this itself). Point it at an OrcaSlicer checkout's `resources/profiles` to use all vendor presets.
* `config set KEY VALUE` overrides any of ~740 settings. Keys are validated against the installed
  binary (OrcaSlicer itself silently ignores typos) and typos get "did you mean" suggestions.

### Bambu Lab printers (e.g. A1 mini)

The real Bambu presets work. They are read from OrcaSlicer's data dir, **Bambu Studio's** plain-JSON
profiles (same format; searched automatically: `/Applications/BambuStudio.app/…/profiles` and
`~/Library/Application Support/BambuStudio/system`), or any directory in `ORCASLICER_PROFILES_DIR`.

```bash
cli-anything-orcaslicer project new -o a1.orca-cli.json -n mypart \
    --machine "Bambu Lab A1 mini 0.4 nozzle" --process "0.20mm Standard @BBL A1M" \
    --filament "Bambu PLA Basic @BBL A1M" --model part.stl
cli-anything-orcaslicer --project a1.orca-cli.json slice run --outdir out
cli-anything-orcaslicer profile list --kind process --source system | grep "A1M"   # all A1 mini presets
```

The result is genuine A1 mini G-code (180×180 bed, Bambu `M970` calibration start sequence). The harness only
slices and exports — it does not talk to the printer.

### Things the harness handles for you (found while testing against OrcaSlicer 2.5.0)

* **Scale / tilt clipping** — OrcaSlicer pivots around the object centre and silently clips whatever
  ends up below the bed (`rotate-x 90` of a 30 mm box prints 5 mm). The harness appends
  `--ensure-on-bed` automatically (opt out: `slice options --no-auto-ensure-on-bed`).
* **Copies** — `transform repetitions N` uses `--clone-objects` (OrcaSlicer's own `--repetitions`
  rejects STL input).
* **Multi-material** — each filament slot is completed with OrcaSlicer's per-filament defaults (otherwise it refuses with a config error).
* **Vendor presets** — same-named parents (`fdm_machine_common` exists in every vendor) are resolved inside the
  child's own vendor directory, and the renamed `extruder_clearance_max_radius` key is migrated as OrcaSlicer does.
* **Crash guard** — a filament preset without `filament_diameter` segfaults the binary; always supplied.
* **Exit codes** are decoded (`253` → `CLI_FILE_NOTFOUND`) and surfaced with hints; `result.json` is
  Linux-only so results are derived from the files.

## 4. Previews

Producer (this CLI) and consumer (`cli-hub`) are separate:

```bash
# publish — real OrcaSlicer slices and renders; bundles follow preview-bundle/v1
cli-anything-orcaslicer --json --project bracket.orca-cli.json preview capture --recipe quick
cli-anything-orcaslicer --json --project bracket.orca-cli.json preview diff       # vs. last capture
cli-anything-orcaslicer --json --project bracket.orca-cli.json preview latest     # never renders

# inspect — read-only viewer, not a render path
cli-hub previews inspect <bundle_dir>
cli-hub previews html <bundle_dir>
```

Recipes: `quick` (isometric + top plate renders, metrics) and `full` (+ OrcaSlicer statistics JSON and
the sliced 3MF). Modes: static capture and diff (no live mode — a slice isn't an incremental stream).
Truthfulness: the PNGs are the thumbnails OrcaSlicer itself renders into the 3MF — they show the
**model on the plate** after your transforms, *not* toolpaths; toolpath facts (layers, time, filament,
per-feature stats) come from OrcaSlicer's G-code and statistics output. Bundles are cached by a
fingerprint of models + transforms + presets + overrides.

## 5. Tests

```bash
pip install -e ".[dev]"
CLI_ANYTHING_FORCE_INSTALLED=1 python3 -m pytest cli_anything/orcaslicer/tests/ -v -s
```

* `tests/test_core.py` — unit tests, synthetic data, no OrcaSlicer needed.
* `tests/test_full_e2e.py` — runs the **real OrcaSlicer**, verifies G-code/3MF/PNG/STL output, and
  drives the installed `cli-anything-orcaslicer` command through subprocess. Fails (never skips)
  when OrcaSlicer is missing. Results are recorded in `tests/TEST.md`.
