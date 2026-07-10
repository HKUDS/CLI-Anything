# EEZ Studio CLI-Anything Harness

## Target

EEZ Studio is an Electron/Node application for embedded UI projects, LVGL code generation, SCPI instrument models, and flow-based automation. The authoritative upstream source is `https://github.com/eez-open/studio`.

## Native Surfaces

- Project files are JSON documents with the `.eez-project` extension.
- LVGL projects store display metadata under `settings.general`, build configuration under `settings.build`, screens under `userPages`, widgets inside page `components`, and SCPI command models under `scpi`.
- EEZ Studio source exports build functions in `packages/project-editor/build/build.ts` and LVGL simulator support in `packages/project-editor/lvgl/docker-build/docker-build-lib.ts`.
- The harness uses native EEZ marker templates such as `//${eez-studio LVGL_SCREENS_DEF}` in `settings.build.files`.

## Harness Architecture

```text
eez-studio/agent-harness/
├── setup.py
└── cli_anything/eez_studio/
    ├── eez_studio_cli.py
    ├── core/
    │   ├── project.py
    │   ├── scpi.py
    │   ├── session.py
    │   └── export.py
    ├── utils/
    │   ├── eez_studio_backend.py
    │   └── repl_skin.py
    └── tests/
        ├── test_core.py
        ├── test_full_e2e.py
        └── TEST.md
```

## Backend Rules

Unit commands manipulate `.eez-project` JSON directly and require no EEZ Studio install. Backend commands require the real EEZ Studio source tree:

```bash
git clone https://github.com/eez-open/studio.git
cd studio
npm install
npm run build
export EEZ_STUDIO_SOURCE=/absolute/path/to/studio
```

`lvgl backend-inspect` invokes the built upstream `docker-build-lib.js` to parse project metadata. `lvgl simulator-build` uses the same upstream library plus Docker to build and verify the LVGL simulator artifacts (`index.html`, `index.js`, `index.wasm`).

If a future EEZ Studio release exposes a documented headless code-generation command, set `EEZ_STUDIO_BUILD_COMMAND` and run `lvgl build-files`. The harness does not synthesize EEZ exports in Python.

## Command Groups

- `project`: create, open, save, validate, inspect, set build settings, list pages/widgets.
- `lvgl`: add pages, labels, buttons, prepare build directories, invoke real backend inspect/build.
- `scpi`: add/list subsystems, commands, and command parameters.
- `backend`: report EEZ Studio source/build availability.
- `session`: status, undo, redo, and saved session metadata.

## Testing

Unit tests cover native project JSON operations and subprocess JSON output without the backend. The default E2E suite verifies backend status and the unavailable-backend error path; live EEZ Studio backend inspection is opt-in with `EEZ_STUDIO_RUN_LIVE_BACKEND=1` and a built `EEZ_STUDIO_SOURCE`.
