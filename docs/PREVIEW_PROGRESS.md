# Preview Progress

Last updated: 2026-04-23 UTC

This file tracks the current state of the preview work on the dedicated preview
branch and records the next design direction for live popup preview windows.

## Workspace

- Repo: `/root/CLI-Anything-preview`
- Branch: `feat/preview-protocol`
- Primary protocol doc: `docs/PREVIEW_PROTOCOL.md`

## What Is Implemented

The current branch already has a working first-pass preview stack:

- Shared preview bundle helper:
  `cli-anything-plugin/preview_bundle.py`
- Shared static viewer/inspector:
  `cli-hub/cli_hub/preview.py`
- Preview protocol documented:
  `docs/PREVIEW_PROTOCOL.md`
- Harness-level preview support implemented for:
  - `shotcut`
  - `openscreen`
  - `blender`
  - `freecad`
  - `renderdoc`

The current shape is:

- harnesses emit `preview-bundle/v1` bundles
- `cli-hub` can inspect or render static HTML for a bundle
- preview commands are normalized around:
  - `preview recipes`
  - `preview capture`
  - `preview latest`
- `renderdoc` also has `preview diff`

## New In This Iteration

The preview branch now has working live popup preview loops for:

- `shotcut`
- `freecad`
- `blender`

The current FreeCAD demo selection notes now live in:

- `docs/FREECAD_DEMO_PROPOSALS.md`

The first selected post-landmark showcase is:

- `mars-rover`

The current FreeCAD mechanical-modeling quality push also added:

- `part bounds`
- `part align`
- a new `Curiosity v6` connector pass:
  - mirrored right-side wheel outboard alignment
  - 6 wheel-level axle blocks
  - 4 suspension pivot housings
  - a full real live-preview rerun after those connector parts were added

These commands provide primitive-level world bounding boxes and bbox-anchor
alignment so CLI-built models do not have to rely purely on guessed
`-pos/-rot` placements.

The current FreeCAD video tooling now also has:

- a true `combo` motion ending for Curiosity:
  - one full rotation
  - then forward travel
- a redesigned split-screen left panel:
  - `Agent Command Stream`
  - card-based command display instead of a literal terminal dump
- a render fix in the demo script so custom output paths create parent
  directories before calling `ffmpeg`

What was added:

- `shotcut` live session lifecycle:
  - `preview live start`
  - `preview live push`
  - `preview live status`
  - `preview live stop`
- `shotcut` producer-side auto polling:
  - `preview live start --mode poll --source-poll-ms ...`
  - hidden background `preview live monitor --session-dir ...`
  - project-file fingerprint polling with automatic preview recapture
- `freecad` live session lifecycle:
  - `preview live start`
  - `preview live push`
  - `preview live status`
  - `preview live stop`
- `freecad` producer-side auto polling:
  - `preview live start --mode poll --source-poll-ms ...`
  - hidden background `preview live monitor --session-dir ...`
  - saved project JSON fingerprint polling with automatic preview recapture
  - demo tooling for `freecad`:
  - `docs/scripts/freecad_live_preview_demo.py collect`
  - `docs/scripts/freecad_live_preview_demo.py render`
  - `docs/scripts/freecad_live_preview_demo.py run-all`
  - scenarios:
    - `orbital-relay`
    - `empire-state-building`
    - `taipei-101`
- `blender` live session lifecycle:
  - `preview live start`
  - `preview live push`
  - `preview live status`
  - `preview live stop`
- `blender` producer-side auto polling:
  - `preview live start --mode poll --source-poll-ms ...`
  - hidden background `preview live monitor --session-dir ...`
  - saved scene JSON fingerprint polling with automatic preview recapture
  - demo tooling for `blender`:
  - `docs/scripts/blender_orbital_relay_drone_demo.py`
  - `docs/scripts/blender_preview_story_demo.py`
  - scenarios:
    - `orbital-relay-drone`
    - real staged preview bundles
    - real turntable motion video
    - polished build-story video with turntable ending
- `cli-hub` live viewer surface:
  - `previews inspect` now understands live sessions
  - `previews html` now renders bundle and live-session HTML
  - `previews watch` now serves a live session over localhost with auto-refresh
  - `previews open` now opens bundles or live sessions in a separate window
  - live pages and inspect output now consume `trajectory.json` when present

The live split now looks like this:

- harness owns preview bundle generation and live-session state publication
- harness can now also own source-state polling and automatic bundle refresh
- `cli-hub` owns the popup window, local server, polling page, and browser launch

This is the intended cross-software direction.

## Current Validation Status

### Fully verified on this machine

- `shotcut`
  - preview implementation works
  - black-frame issue was fixed by preferring the ffmpeg preview path
  - preview E2E passes
  - live preview session + live viewer now works end-to-end
  - automatic poll mode now works end-to-end without manual `preview live push`
- `openscreen`
  - preview implementation works
  - preview E2E passes
- `blender`
  - preview implementation works
  - preview E2E passes
  - live preview session lifecycle now works end-to-end
  - automatic poll mode now works end-to-end without manual `preview live push`
  - a real stage-by-stage `gyro-observatory` build now exists with:
    - 4 preview bundle checkpoints
    - a persisted live session
    - a final 1600x1600 Blender still render
- `freecad`
  - preview implementation works on the current Ubuntu machine after local
    environment setup
  - preview E2E passes
  - live preview session + live poll mode now work end-to-end
  - a real programmatic demo video now exists, built from real CLI outputs and
    real live preview bundles
  - preview macro now reconstructs real body/additive/subtractive primitive
    features plus linear/polar/mirror pattern features with placement
  - multiple real Taipei 101 studies now exist; the old shipped scenario has
    been replaced because the earlier stacked-box version was not acceptable
  - preview/export macro generation now also reconstructs `part mirror` for
    primitive-backed mirrored parts, which was required for truthful symmetric
    mechanical builds like the rover
  - a first real `mars-rover` live-preview trajectory now exists and completes
    successfully end-to-end
  - the live demo collector now treats preview events as a stable sequence even
    when FreeCAD live sessions change bundle ids without strictly monotonic
    `bundle_count` behavior
  - a real `curiosity` live-preview trajectory now exists and completes
    successfully end-to-end
  - the harness now has primitive-level `part bounds` and `part align`
    commands, with unit and CLI subprocess coverage
  - a fuller `Curiosity v6` run now exists and completes successfully with
    explicit suspension connector parts; the final right/front views are much
    more symmetric and structurally coherent than the earlier `v5` build
  - a polished Curiosity split-screen video now exists with:
    - real command-card trajectory view
    - real live preview bundles
    - a true frame-by-frame combo motion ending

### Partially verified on this machine

- `renderdoc`
  - replaying existing `.rdc` captures works
  - `renderdoccmd thumb` works on suitable sample captures
  - local capture generation on this machine is still blocked by the current
    graphics backend environment

## Current Machine Notes

### FreeCAD

To make `freecad` preview work on this Ubuntu machine, the environment had to
be completed locally:

- FreeCAD AppImage extracted under `/opt/freecad/app`
- local launcher/wrapper installed at `/usr/local/bin/freecad`
- wrapper forces GUI-capable execution through `xvfb-run` for script-driven
  preview capture

This is machine-local setup, not repo content.

Result:

- `freecad` preview E2E now passes on this machine
- generated 4-view preview images are valid and non-empty

### RenderDoc

To make `renderdoc` preview usable on this Ubuntu machine, the environment had
to be completed locally:

- RenderDoc installed under `/opt/renderdoc`
- `renderdoccmd` and `qrenderdoc` exposed in `/usr/local/bin`
- Vulkan and shader tooling installed:
  - `vulkan-tools`
  - `glslang-tools`

Important limitation discovered on this machine:

- in the current terminal Ubuntu environment using software rendering
  (`llvmpipe` / `lavapipe`), RenderDoc can inject into demo apps and expose the
  in-app API, but local `StartFrameCapture`/`EndFrameCapture` still returns no
  saved captures
- this is not a CLI wiring issue; it is a backend/runtime limitation of the
  current graphics environment

What still works:

- replaying existing `.rdc` captures
- exporting thumbnails from existing `.rdc` files when the capture includes a
  usable embedded thumbnail

## Local Artifacts

Useful local verification outputs currently available:

- consolidated final artifacts:
  - `/root/preview-artifacts/20260420/final/freecad-preview.png`
  - `/root/preview-artifacts/20260420/final/renderdoc-preview.png`
- Blender Gyro Observatory artifacts:
  - `/root/preview-artifacts/20260422/blender-gyro-observatory/gyro_observatory.blend-cli.json`
  - `/root/preview-artifacts/20260422/blender-gyro-observatory/live-root/blender/live/gyro-observatory-blend-cli-0043d42f-quick/session.json`
  - `/root/preview-artifacts/20260422/blender-gyro-observatory/live-root/blender/quick/20260422T123252Z_a0409b02_quick/artifacts/hero.png`
  - `/root/preview-artifacts/20260422/blender-gyro-observatory/live.html`
  - `/root/preview-artifacts/20260422/blender-gyro-observatory/renders/gyro_observatory_final.png`
- FreeCAD live poll demo artifacts:
  - `/root/preview-artifacts/20260421/freecad-live-demo/live-root/freecad/live/project-379d4e4a-quick/session.json`
  - `/root/preview-artifacts/20260421/freecad-live-demo/live-root/freecad/quick/20260421T051634Z_88a6b6d6_quick/artifacts/hero.png`
  - `/root/preview-artifacts/20260421/freecad-live-demo/live.html`
- FreeCAD programmatic video demo artifacts:
  - `/root/preview-artifacts/20260421/freecad-live-video/demo.mp4`
  - `/root/preview-artifacts/20260421/freecad-live-video/trajectory.json`
  - `/root/preview-artifacts/20260421/freecad-live-video/live.html`
  - `/root/preview-artifacts/20260421/freecad-live-video/stills/frame_10s.png`
  - `/root/preview-artifacts/20260421/freecad-live-video/stills/frame_35s.png`
  - `/root/preview-artifacts/20260421/freecad-live-video/stills/frame_60s.png`
- FreeCAD skyscraper demo artifacts:
  - `/root/preview-artifacts/20260421/freecad-taipei-101-video/demo.mp4`
  - `/root/preview-artifacts/20260421/freecad-taipei-101-video/trajectory.json`
  - `/root/preview-artifacts/20260421/freecad-taipei-101-video/live.html`
  - `/root/preview-artifacts/20260421/freecad-taipei-101-video/stills/frame_15s.png`
  - `/root/preview-artifacts/20260421/freecad-taipei-101-video/stills/frame_55s.png`
  - `/root/preview-artifacts/20260421/freecad-taipei-101-video/stills/frame_95s.png`
  - `/root/preview-artifacts/20260421/freecad-taipei-101-video/snapshots/15_spire-tip/front.png`
  - `/root/preview-artifacts/20260421/freecad-taipei-101-video/snapshots/15_spire-tip/hero.png`
- FreeCAD rover prototype artifacts:
  - `/root/preview-artifacts/20260421/freecad-mars-rover-proto3/trajectory.json`
  - `/root/preview-artifacts/20260421/freecad-mars-rover-proto3/live.html`
  - `/root/preview-artifacts/20260421/freecad-mars-rover-proto3/snapshots/21_sample-head/hero.png`
  - `/root/preview-artifacts/20260421/freecad-mars-rover-proto3/snapshots/21_sample-head/front.png`
  - `/root/preview-artifacts/20260421/freecad-mars-rover-proto3/snapshots/21_sample-head/top.png`
  - this rover run produced `22` real CLI commands and `21` real preview
    updates on the current machine
- FreeCAD Curiosity artifacts:
  - `/root/preview-artifacts/20260421/freecad-curiosity-proto4/trajectory.json`
  - `/root/preview-artifacts/20260421/freecad-curiosity-proto4/live.html`
  - `/root/preview-artifacts/20260421/freecad-curiosity-proto4/snapshots/35_deck-sensor-pack/hero.png`
  - `/root/preview-artifacts/20260421/freecad-curiosity-proto4/snapshots/35_deck-sensor-pack/front.png`
  - `/root/preview-artifacts/20260421/freecad-curiosity-proto4/snapshots/35_deck-sensor-pack/top.png`
  - `/root/preview-artifacts/20260421/freecad-curiosity-proto4/snapshots/35_deck-sensor-pack/right.png`
  - this Curiosity run produced `36` real CLI commands and `35` real preview
    updates on the current machine
  - average preview refresh latency on this run was `8.503s`
- FreeCAD Curiosity arm/attachment refinement artifacts:
  - `/root/preview-artifacts/20260421/freecad-curiosity-v3-armfix-preview/freecad/quick/20260421T162607Z_12c18d75_quick/artifacts/hero.png`
  - `/root/preview-artifacts/20260421/freecad-curiosity-v3-armfix-preview/freecad/quick/20260421T162607Z_12c18d75_quick/artifacts/front.png`
  - `/root/preview-artifacts/20260421/freecad-curiosity-v3-armfix-preview/freecad/quick/20260421T162607Z_12c18d75_quick/artifacts/top.png`
  - these were generated from the real Curiosity project after applying
    `part align` fixes to the upper/fore arm and turret chain
- FreeCAD Curiosity full suspension/alignment refinement:
  - `/root/preview-artifacts/20260421/freecad-curiosity-v5/trajectory.json`
  - `/root/preview-artifacts/20260421/freecad-curiosity-v5/live.html`
  - `/root/preview-artifacts/20260421/freecad-curiosity-v5/snapshots/58_align-sensor-pack/hero.png`
  - `/root/preview-artifacts/20260421/freecad-curiosity-v5/snapshots/58_align-sensor-pack/front.png`
  - `/root/preview-artifacts/20260421/freecad-curiosity-v5/snapshots/58_align-sensor-pack/right.png`
  - this run produced `62` real CLI commands and `58` real preview updates
  - average preview refresh latency on this run was `14.454s`
  - suspension updates now include explicit wheel-plane alignment for
    rocker/bogie/link parts before the upper assembly stack is added
- FreeCAD Curiosity connector rebuild:
  - `/root/preview-artifacts/20260421/freecad-curiosity-v6/trajectory.json`
  - `/root/preview-artifacts/20260421/freecad-curiosity-v6/live.html`
  - suspension connector checkpoint:
    - `/root/preview-artifacts/20260421/freecad-curiosity-v6/snapshots/50_align-right-bogie-pivot-housing/right.png`
    - `/root/preview-artifacts/20260421/freecad-curiosity-v6/snapshots/50_align-right-bogie-pivot-housing/front.png`
    - `/root/preview-artifacts/20260421/freecad-curiosity-v6/snapshots/50_align-right-bogie-pivot-housing/hero.png`
  - final v6 snapshot:
    - `/root/preview-artifacts/20260421/freecad-curiosity-v6/snapshots/82_align-sensor-pack/hero.png`
    - `/root/preview-artifacts/20260421/freecad-curiosity-v6/snapshots/82_align-sensor-pack/front.png`
    - `/root/preview-artifacts/20260421/freecad-curiosity-v6/snapshots/82_align-sensor-pack/right.png`
  - this run produced `85` real CLI commands and `82` real preview updates
  - average preview refresh latency on this run was `10.059s`
  - compared with `v5`, the biggest gains are symmetric right-side track width
    and visibly attached wheel/suspension connectors in the key front/right
    views
  - a programmatic video now also exists for this same `v6` trajectory:
    - `/root/preview-artifacts/20260421/freecad-curiosity-v6/demo.mp4`
    - `/root/preview-artifacts/20260421/freecad-curiosity-v6/showcase/sequence.json`
    - `/root/preview-artifacts/20260421/freecad-curiosity-v6/stills/showcase-start.png`
    - `/root/preview-artifacts/20260421/freecad-curiosity-v6/stills/showcase-mid.png`
    - `/root/preview-artifacts/20260421/freecad-curiosity-v6/stills/showcase-final.png`
  - the ending showcase is built from extra real FreeCAD hero captures derived
    from the final `Curiosity v6` project on a staged ground run
- Shotcut live preview demo artifacts:
  - `/root/preview-artifacts/20260420/shotcut-live-demo/live-viewer-shot.png`
  - `/root/preview-artifacts/20260420/shotcut-live-demo/live-root/shotcut/live/project-9e62c8c7-quick/live.html`
  - `/root/preview-artifacts/20260420/shotcut-live-demo/live-root/shotcut/live/project-9e62c8c7-quick/session.json`
- Temporary poll-mode demo artifacts:
  - `/tmp/shotcut-poll-demo/live-initial.png`
  - `/tmp/shotcut-poll-demo/live-updated.png`
  - `/tmp/shotcut-poll-demo/live-red-updated.png`
  - `/tmp/shotcut-poll-demo/live-root/shotcut/live/project-35fa4f1f-quick/session.json`
- FreeCAD bundle snapshots:
  - `/root/preview-artifacts/20260420/freecad/`
- RenderDoc sample replay artifacts:
  - `/root/preview-artifacts/20260420/renderdoc/sample/`

Interpretation:

- `freecad-preview.png` is a real 4-view preview contact sheet generated from
  the FreeCAD preview path on this machine
- the `20260421/freecad-live-demo/` directory proves the new FreeCAD poll-mode
  behavior: after a saved-project mutation, the live session advances from
  bundle 1 to 2 without any manual `preview live push` command
- the `20260421/freecad-live-video/` directory contains a real end-to-end demo
  of an agent-like CLI build on the left and the actual FreeCAD live preview
  outputs on the right; the video is programmatic, but the underlying commands,
  outputs, timings, and preview images are all real
- the `20260421/freecad-empire-state-video/` directory does the same for a
  tiny Empire State Building reproduction built entirely with
  `cli-anything-freecad` primitives and real poll-mode preview refresh
  - after self-review, this Empire State Building attempt is not considered
    shippable because the silhouette still reads as a generic stepped tower
- the `20260421/freecad-taipei-101-video/` directory is a second real
  skyscraper experiment built with the same CLI + real live preview pipeline
  - after later review, it is also not shippable as a Taipei 101 demo; the
    silhouette is still too generic and the command script only builds a crude
    stacked-box approximation
  - do not treat it as a finished landmark reproduction
- after the FreeCAD body/additive/pattern preview alignment work, a new set of
  real Taipei studies was generated directly against the improved harness:
  - `/root/preview-artifacts/20260421/taipei-body-proto1/`
  - `/root/preview-artifacts/20260421/taipei-body-proto7/`
  - `/root/preview-artifacts/20260421/taipei-parts-proto2/`
  - the current best silhouette is the stepped-shoulder parts study in
    `/root/preview-artifacts/20260421/taipei-parts-proto2/`
  - `docs/scripts/freecad_live_preview_demo.py` now uses that newer Taipei 101
    step generator instead of the earlier incorrect stacked-box scenario
- the updated `taipei-101` scenario was then re-collected end-to-end into:
  - `/root/preview-artifacts/20260421/freecad-taipei-101-rework/trajectory.json`
  - `/root/preview-artifacts/20260421/freecad-taipei-101-rework/final-preview.html`
  - `/root/preview-artifacts/20260421/freecad-taipei-101-rework/snapshots/30_spire-tip/`
  - this rework run produced `31` real CLI commands and `30` real preview
    updates on the current machine
- while starting the rover direction, one more real preview gap was exposed:
  `part mirror` objects were valid project state but were not reconstructed by
  the FreeCAD preview macro layer
  - this caused preview drift or stalled capture once symmetric right-side
    wheel copies entered the project
  - the macro generator now resolves mirrored primitive parts into renderable
    mirrored primitives for preview/export
- the first rover prototype is not yet the final showcase model, but it now
  reads clearly as a six-wheel exploration rover in real `hero/front/top`
  preview and is a stronger subject for continued iteration than the failed
  landmark demos
- `renderdoc-preview.png` is a real thumbnail exported on this machine from an
  existing `.rdc` sample capture
- `live-viewer-shot.png` is a real screenshot of the new Shotcut live preview
  window UI, rendered from the live-session viewer over localhost on this
  machine
- the `/tmp/shotcut-poll-demo/` artifacts prove the new poll-mode behavior:
  after project-file mutations, the live session advances from bundle 1 to 2 to
  3 without any manual `preview live push` command

## Gaps Still Open

### Cross-process live session stability

This iteration exposed and fixed an important issue:

- the first implementation derived the live session name partly from the
  in-process `session_id`
- that broke one-shot CLI usage because each command got a different session dir

The current behavior is now:

- if a project has a saved `project_path`, live session identity is derived from
  the stable project path + recipe
- only unsaved in-memory projects fall back to `session_id`

That is the correct agent-facing behavior for one-shot command flows.

### RenderDoc capture generation

The current repo implementation of `renderdoc` preview still assumes that a
real replayable capture already exists.

That is normal for RenderDoc as a product, but on this machine there is a
further limitation:

- generating a fresh `.rdc` locally from test apps is not currently reliable in
  the present software-rendered terminal environment

This means:

- `renderdoc` preview is usable for existing captures
- `renderdoc` preview is not yet fully self-hosted on this specific machine

### FreeCAD boolean preview gap

While building the video demo, one real limitation showed up:

- after `part boolean fuse`, the current FreeCAD preview path can still produce
  a bundle, but it may degrade to `partial` with no image artifacts

This is why the current demo trajectory avoids boolean operations and uses only
part additions that keep the live preview image stream valid.

### Empire State Building attempt

I explicitly reviewed the first Empire State Building video and artifacts after
they were generated.

Result:

- the model was too generic and did not read as the Empire State Building
- the right fix was not to keep claiming it was correct

Current disposition:

- keep the Empire State attempt only as an experiment
- do not treat it as the shipped skyscraper demo
- do not treat the old Taipei 101 stacked-box run as shipped either
- the current Taipei 101 work has moved to the newer study artifacts and the
  updated `freecad_live_preview_demo.py` scenario

### FreeCAD body preview alignment

The main FreeCAD gap behind the bad landmark demos was real:

- the CLI could describe richer body/additive/pattern edits than the preview
  macro could faithfully reconstruct

This is now improved in the current branch:

- additive and subtractive body primitives now accept feature placement
- the preview/export macro now reconstructs:
  - additive/subtractive `box/cylinder/sphere/cone/torus/wedge`
  - `linear_pattern`
  - `polar_pattern`
  - `mirrored`
  - `multi_transform` as a sequential expansion of supported pattern features
- full verification now passes on this machine:
  - `cli_anything/freecad/tests/test_core.py` -> `76 passed`
  - `cli_anything/freecad/tests/test_full_e2e.py -k 'macro_generation or preview_capture_bundle or preview_capture_subprocess or preview_live_poll_auto_refresh'` -> `6 passed`

### Shared runtime cleanup

The preview bundle helper currently exists in:

- canonical form in `cli-anything-plugin/preview_bundle.py`
- copied form in each harness under `utils/preview_bundle.py`

That is acceptable for a first pass, but the long-term direction should be:

- one shared runtime helper
- no more copy-based drift

## Design Question: Can Preview Support A Separate Real-Time Popup Window?

Short answer:

- yes, but it should be implemented as a host/viewer feature, not as five
  different app-specific mini GUIs
- the generic solution should target near-real-time live preview sessions, not a
  universal raw GUI-streaming protocol

## Recommended Position

The root design should be:

- keep bundle generation in the harness
- add a new live session abstraction above bundles
- let `cli-hub` own the popup window and live refresh behavior

In other words:

- harnesses publish preview updates
- `cli-hub` opens and updates the separate window

This is the cleanest split for both agents and humans.

## Why The Window Should Live In `cli-hub`

Reasons:

- popup behavior is cross-harness UI logic, not app-specific rendering logic
- the viewer already understands the preview bundle contract
- Linux/Ubuntu popup behavior belongs to the host layer
- this avoids rebuilding the same preview monitor in every harness

If every harness implements its own popup window:

- command surfaces drift
- dependencies drift
- live refresh logic gets duplicated
- Linux windowing quirks get re-solved five times

## What "Real-Time" Should Mean Here

There are two possible meanings:

1. True continuous streaming at interactive frame rates
2. Fast, repeated preview refresh in a dedicated live window

The generic cross-software solution should target the second one.

That means:

- auto-refreshing stills
- low-res review clip replacement
- event-driven redraw after each mutating command
- optional periodic refresh for long-running tasks

This is realistic across video, CAD, 3D, and GPU-debug workflows.

A universal 30-60 FPS live remote viewport for all supported software is not a
good root abstraction for CLI-Anything.

## Proposed New Abstraction: Live Preview Session

The current protocol is bundle-centric.

To support popup live preview, add a second object:

- `Live Preview Session`

Recommended shape:

```text
<root>/
  sessions/
    <session_id>/
      session.json
      current/
        manifest.json
        summary.json
        artifacts/
      history/
        <bundle_id_1>/
        <bundle_id_2>/
```

Where:

- `history/` stores immutable preview bundles
- `current/` points to the newest visible state for the live viewer
- `session.json` stores session metadata and refresh sequence numbers

This adds one key capability:

- the live window can watch one stable path while harnesses keep publishing new
  preview states

## Canonical Command Surface

### `cli-hub`

The current canonical viewer commands are:

- `cli-hub previews inspect <bundle-or-session>`
  - inspect an existing bundle or live session in text or JSON
- `cli-hub previews html <bundle-or-session>`
  - render HTML for a bundle or live session
- `cli-hub previews watch <session-dir>`
  - run a live preview viewer against a session
- `cli-hub previews open <bundle-or-session>`
  - open a bundle or live session in a browser window

Useful flags:

- `--open`
- `--browser default|chromium|firefox`
- `--app-mode`
- `--poll-ms 500`
- `--host 127.0.0.1`
- `--port 0`

### Harnesses

Keep harness surfaces minimal and standardized:

- `preview live start --recipe quick [--open]`
- `preview live push`
- `preview live stop`
- `preview live status`

Behavior:

- `start` creates a live session and optionally opens the viewer window
- `push` publishes a new preview state into the session
- `stop` closes the session cleanly
- `status` reports session path, current bundle metadata, and compact
  `trajectory_summary` for agent use

The first implementation can make `push` explicit.

Later, mutating commands can optionally trigger `push` automatically when a
session is active.

## Popup Window Strategy On Linux/Ubuntu

This must support a normal Ubuntu terminal inside a desktop session.

Recommended open order:

1. `chromium --app=http://127.0.0.1:PORT/...`
2. `google-chrome --app=...`
3. `microsoft-edge --app=...`
4. `firefox --new-window ...`
5. `xdg-open ...`

Rules:

- if `DISPLAY` or `WAYLAND_DISPLAY` is set, `--open` may launch a popup window
- if the machine is headless, do not fail the preview command just because a
  popup cannot open
- print the local URL and keep serving

Why browser app mode is the recommended root solution:

- no extra heavy GUI dependency in the repo
- easy image/video/JSON layout
- easy auto-refresh
- simple Linux popup support from terminal
- agents and humans can share the same viewer

## Recommended Live Transport

The simplest reliable approach is:

- local HTTP server
- polling-based viewer refresh first

Recommended first pass:

- viewer polls `session.json` every 500-1000 ms
- if sequence number changes, reload manifest and updated assets

Later upgrade path:

- optional SSE or websocket push

Do not start with websocket complexity unless polling becomes a real bottleneck.

## How Each Software Fits

### Shotcut / Openscreen

Good candidates for live window preview.

Live behavior:

- regenerate low-res review clip
- regenerate sampled frames/contact sheet
- viewer auto-reloads clip and hero frames

This is near-real-time, not frame-by-frame editing playback.

### Blender

Good candidate for live preview.

Live behavior:

- re-run fast Workbench or Eevee preview
- publish hero still, alternate still, or turntable clip
- viewer auto-refreshes images and metadata

### FreeCAD

Good candidate for live preview.

Live behavior:

- regenerate isometric/front/top/right images
- viewer updates the 4-view layout

This is especially strong for agent verification after geometric mutations.

### RenderDoc

RenderDoc is different.

Live behavior should mean:

- watch for newly selected capture/event state
- refresh thumbnail/output-target/pipeline summaries

It is not a continuous render monitor in the same sense as Blender or Shotcut.

## Non-Goals For The First Live Window Version

- no universal remote framebuffer streaming
- no requirement for 60 FPS interactive playback
- no per-harness custom desktop app
- no mandatory Qt dependency for the whole repo

## Phased Implementation Plan

### Phase 1: Popup For Existing Bundles

Goal:

- open an existing preview bundle in a separate window from terminal

Deliverables:

- `cli-hub previews open`
- browser app-mode launch on Linux/Ubuntu
- headless fallback to URL output

This is the fastest high-value step.

### Phase 2: Live Session Protocol

Goal:

- let a viewer watch one stable session while bundles keep updating

Deliverables:

- `session.json`
- `trajectory.json`
- `current/`
- `cli-hub previews watch`
- polling-based live reload

### Phase 3: Harness Integration

Goal:

- let the main preview-capable harnesses publish live updates

Recommended first set:

- `shotcut`
- `openscreen`
- `blender`
- `freecad`

RenderDoc should come after the live session machinery is stable.

### Phase 4: Auto-Publish Hooks

Goal:

- when a live session is active, mutating commands publish a fresh preview
  automatically

This should be opt-in, because automatic preview generation can be expensive.

## Recommended Immediate Next Step

The next concrete move should be:

- keep `cli-hub previews open`
- keep `cli-hub previews watch`
- use browser-window popup as the default Linux/Ubuntu strategy

Reason:

- this produces a real popup preview window quickly
- it works for both agents and humans
- it does not force any harness-specific GUI redesign
- it composes cleanly with the existing bundle protocol

## Bottom Line

Yes, the preview system can support a separate live popup window.

The correct root design is:

- not "every harness owns a live monitor"
- but "every harness publishes preview state, and `cli-hub` owns the live
  popup viewer"

That is the most generic, minimal, and extensible solution for CLI-Anything.

## 2026-04-22: FreeCAD Motion CLI

Status:

- implemented a real `motion` command group for `cli-anything-freecad`
- kept motion separate from preview/live preview
- motion output is now `keyframes -> real FreeCAD GUI frame renders -> ffmpeg video`

New CLI surface:

- `motion new`
- `motion list`
- `motion get`
- `motion delete`
- `motion keyframe`
- `motion sample`
- `motion render-frames`
- `motion render-video`

Current scope:

- target kind supported today: `part`
- interpolation: linear position + Euler rotation interpolation between keyframes
- camera presets: `hero`, `front`, `top`, `right`
- fit modes: `initial`, `per-frame`
- video formats: `mp4`, `webm`, `gif`

Implementation notes:

- new core module: [freecad/core/motion.py](/root/CLI-Anything-preview/freecad/agent-harness/cli_anything/freecad/core/motion.py)
- FreeCAD sequence rendering is done in one GUI macro process, not one FreeCAD process per frame
- frame directories now write a `sequence.json` manifest for later editing / reuse
- this is a truthful frame-by-frame render path; it does not synthesize in-between motion frames

Validation:

- `test_core.py -k 'TestMotion or test_get_info'` -> `6 passed`
- `test_full_e2e.py -k 'motion_render_frames_subprocess or motion_render_video_subprocess'` -> `2 passed`
- targeted unit run including motion/bounds/align -> `9 passed`

Real smoke artifact:

- project: [/root/preview-artifacts/20260422/freecad-motion-smoke/project.json](/root/preview-artifacts/20260422/freecad-motion-smoke/project.json)
- frames: [/root/preview-artifacts/20260422/freecad-motion-smoke/frames](/root/preview-artifacts/20260422/freecad-motion-smoke/frames)
- video: [rollout.mp4](/root/preview-artifacts/20260422/freecad-motion-smoke/rollout.mp4)

Current limitation:

- motion currently animates part placements only
- it does not yet drive FreeCAD Assembly joints / Simulation objects directly
- it is enough for our current CLI-built rover/Curiosity-style showcase flow, but not yet a native joint-solver animation pipeline

## 2026-04-22: Curiosity V6 True Motion Showcase

Status:

- connected the new FreeCAD `motion` CLI to the real `Curiosity v6` final project
- added a reusable `motion-showcase` mode to [freecad_live_preview_demo.py](/root/CLI-Anything-preview/docs/scripts/freecad_live_preview_demo.py)
- rendered a fully real frame-by-frame Curiosity showcase video

New script path:

- `python3 docs/scripts/freecad_live_preview_demo.py motion-showcase --timeline ... --output-dir ...`

What it does:

- loads the real final `Curiosity v6` project from the existing trajectory
- adds the showcase stage geometry as real parts
- writes `13` key poses into a real project `motions` collection
- calls `cli-anything-freecad motion render-video`
- preserves the real frame sequence and stills

Artifact set:

- motion project: [curiosity_true_motion.json](/root/preview-artifacts/20260422/freecad-curiosity-v6-true-motion/curiosity_true_motion.json)
- video: [curiosity_true_motion.mp4](/root/preview-artifacts/20260422/freecad-curiosity-v6-true-motion/curiosity_true_motion.mp4)
- manifest: [motion_manifest.json](/root/preview-artifacts/20260422/freecad-curiosity-v6-true-motion/motion_manifest.json)
- frames: [/root/preview-artifacts/20260422/freecad-curiosity-v6-true-motion/frames](/root/preview-artifacts/20260422/freecad-curiosity-v6-true-motion/frames)
- stills:
  [start.png](/root/preview-artifacts/20260422/freecad-curiosity-v6-true-motion/stills/start.png)
  [mid.png](/root/preview-artifacts/20260422/freecad-curiosity-v6-true-motion/stills/mid.png)
  [final.png](/root/preview-artifacts/20260422/freecad-curiosity-v6-true-motion/stills/final.png)

Verification:

- script `py_compile` passed
- `motion-showcase` run completed successfully
- output stats:
  - duration: `6.0s`
  - fps: `12`
  - frame count: `73`
  - file size: `315,872 bytes`

Quality note:

- this is now a truthful motion render path
- the motion itself is still placement-driven rather than joint-solver-driven
- visually, the rover translation and staged ground read correctly, but native wheel/rocker-bogie mechanism simulation is still future work

## 2026-04-22: Curiosity Turntable Motion

Status:

- extended `motion-showcase` to support `--motion-style spin`
- rendered a second real frame-by-frame Curiosity motion clip for rotation / turntable presentation

Artifact set:

- motion project: [curiosity_turntable_motion.json](/root/preview-artifacts/20260422/freecad-curiosity-v6-turntable-motion/curiosity_turntable_motion.json)
- video: [curiosity_turntable_motion.mp4](/root/preview-artifacts/20260422/freecad-curiosity-v6-turntable-motion/curiosity_turntable_motion.mp4)
- manifest: [motion_manifest.json](/root/preview-artifacts/20260422/freecad-curiosity-v6-turntable-motion/motion_manifest.json)
- frames: [/root/preview-artifacts/20260422/freecad-curiosity-v6-turntable-motion/frames](/root/preview-artifacts/20260422/freecad-curiosity-v6-turntable-motion/frames)
- stills:
  [start.png](/root/preview-artifacts/20260422/freecad-curiosity-v6-turntable-motion/stills/start.png)
  [mid.png](/root/preview-artifacts/20260422/freecad-curiosity-v6-turntable-motion/stills/mid.png)
  [final.png](/root/preview-artifacts/20260422/freecad-curiosity-v6-turntable-motion/stills/final.png)

Verification:

- script `py_compile` passed after the spin-mode changes
- `motion-showcase --motion-style spin` completed successfully
- output stats:
  - duration: `7.0s`
  - fps: `12`
  - frame count: `85`
  - file size: `719,298 bytes`
- manual visual check of `start/mid/final` confirms a genuine turntable-style rotation view change

Quality note:

- this is a true rendered turntable, not a sparse-pose blend
- it still uses placement-driven motion rather than FreeCAD Assembly/Robot mechanism simulation
