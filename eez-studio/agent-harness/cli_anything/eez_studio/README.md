# cli-anything-eez-studio

CLI harness for **EEZ Studio** project, LVGL UI, and SCPI workflows.

The CLI edits native `.eez-project` JSON files and calls the real EEZ Studio source backend for build/export operations when configured.

## Prerequisites

- Python 3.10+
- Node.js for EEZ Studio backend commands
- EEZ Studio source tree for real backend export:

```bash
git clone https://github.com/eez-open/studio.git
cd studio
npm install
npm run build
export EEZ_STUDIO_SOURCE=/absolute/path/to/studio
```

Full LVGL simulator builds also require Docker.

## Installation

```bash
cd eez-studio/agent-harness
pip install -e .
```

## Usage

```bash
# Start the REPL
cli-anything-eez-studio

# Create a native EEZ Studio LVGL project
cli-anything-eez-studio --json project new -o app.eez-project --name TestPanel

# Add LVGL widgets and save automatically
cli-anything-eez-studio --project app.eez-project lvgl add-label --text "Ready"
cli-anything-eez-studio --project app.eez-project lvgl add-button --text "Run"

# Add SCPI command metadata
cli-anything-eez-studio --project app.eez-project scpi subsystem-add SOURCE
cli-anything-eez-studio --project app.eez-project scpi command-add SOURCE :VOLTage?

# Inspect through the real EEZ Studio backend
cli-anything-eez-studio --json --project app.eez-project lvgl backend-inspect
```

## Command Reference

| Group | Commands |
| --- | --- |
| `project` | `new`, `open`, `save`, `info`, `validate`, `pages`, `widgets`, `set`, `set-destination`, `add-build-file` |
| `lvgl` | `add-page`, `add-label`, `add-button`, `ensure-destination`, `backend-inspect`, `build-files`, `simulator-build`, `verify-simulator` |
| `scpi` | `subsystem-list`, `subsystem-add`, `command-list`, `command-add`, `parameter-add` |
| `backend` | `status` |
| `session` | `status`, `undo`, `redo`, `save-state`, `list` |

## JSON Output

Every command supports `--json` at the root:

```bash
cli-anything-eez-studio --json --project app.eez-project project info
```

## Testing

```bash
cd eez-studio/agent-harness
python3 -m pytest cli_anything/eez_studio/tests/test_core.py -v
python3 -m pytest cli_anything/eez_studio/tests/test_full_e2e.py -v
```

The default E2E suite does not require a real EEZ Studio backend; it verifies backend status and the structured unavailable-backend error path. To run the live backend inspection test, set `EEZ_STUDIO_RUN_LIVE_BACKEND=1` and `EEZ_STUDIO_SOURCE` to a built EEZ Studio checkout.
