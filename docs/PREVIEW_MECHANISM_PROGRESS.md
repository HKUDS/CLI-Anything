# Preview Mechanism Progress

Last updated: 2026-04-23 UTC

This document records the current state of the cross-harness preview mechanism
work on the dedicated preview branch.

## Workspace

- Repo: `/root/CLI-Anything-preview`
- Branch: `feat/preview-protocol`
- Current checkpoint commit: `81dbe58`

This checkpoint contains the first end-to-end version of the preview stack,
including live preview sessions, bundle protocol, generic viewing tools, and
FreeCAD motion-backed showcase rendering.

## Mechanism Summary

The current mechanism is built as five layers:

1. `Preview Bundle`
   - A stable on-disk contract for preview outputs.
   - Defined in `docs/PREVIEW_PROTOCOL.md`.
   - Implemented by `cli-anything-plugin/preview_bundle.py` and vendored
     harness helpers.

2. `Harness Preview Commands`
   - Normalized command surface:
     - `preview recipes`
     - `preview capture`
     - `preview latest`
     - `preview diff` where relevant
   - Each harness is responsible for generating truthful preview artifacts with
     the real backend, not by screen scraping.

3. `Live Session`
   - A long-lived directory that tracks:
     - mutable `session.json`
     - append-only `trajectory.json`
     - current bundle head
   - Supports both:
     - explicit push
     - poll-first automatic refresh based on source-state fingerprints

4. `Generic Viewer`
   - Implemented in `cli-hub`.
   - Supports:
     - `cli-hub previews inspect`
     - `cli-hub previews html`
     - `cli-hub previews watch`
     - `cli-hub previews open`
   - Lets agents and humans consume the same preview state through different
     surfaces.

5. `Final Motion Showcase`
   - Separate from preview.
   - Used for end-of-work demonstrations where static preview is not enough.
   - Currently implemented for FreeCAD via real frame-by-frame motion renders.

## What Is Implemented

### Protocol / Platform

- `docs/PREVIEW_PROTOCOL.md`
- `cli-anything-plugin/preview_bundle.py`
- `cli-anything-plugin/HARNESS.md` preview requirements
- `cli-hub/cli_hub/preview.py`
- `cli-hub` previews CLI integration

### Harnesses with preview support

- `shotcut`
  - quick preview capture
  - live session
  - poll-mode auto refresh
  - black-preview regression fixed

- `openscreen`
  - quick preview capture
  - bundle emission
  - append-only `trajectory.json` beside stable preview roots

- `blender`
  - preview capture
  - live session
  - poll-mode auto refresh
  - `preview live status --json` returns `trajectory_summary`
  - real Gyro Observatory demo script with stage-by-stage preview checkpoints

- `freecad`
  - quick preview capture
  - live session
  - poll-mode auto refresh
  - `preview live status --json` returns `trajectory_summary`
  - richer preview/export macro reconstruction
  - motion CLI for true frame rendering

- `renderdoc`
  - preview capture
  - preview diff
  - replay-oriented bundle generation
  - append-only `trajectory.json` for capture/diff history

## Canonical Command Split

Use this wording consistently:

- software harnesses publish previews through `cli-anything-<software> preview ...`
- `cli-hub previews ...` only inspects, renders, opens, or watches existing
  bundles and live sessions

There are no `cli-hub preview`, `cli-hub review`, or `cli-hub open-preview`
aliases in the current command surface.

## FreeCAD-Specific Preview Mechanism Progress

FreeCAD is currently the deepest preview integration on this branch.

Implemented:

- preview capture and live preview
- poll-first live refresh
- `part bounds`
- `part align`
- better preview/export macro reconstruction for:
  - additive/subtractive primitives
  - pattern features
  - mirrored parts
- motion CLI surface:
  - `motion new`
  - `motion list`
  - `motion get`
  - `motion delete`
  - `motion keyframe`
  - `motion sample`
  - `motion render-frames`
  - `motion render-video`

This makes FreeCAD the main proof point for the full mechanism:

- real CLI trajectory
- real preview bundles
- real live session updates
- real final motion render
- programmatic split-screen video composition

## Video / Showcase State

Current reference artifacts are recorded in:

- `docs/FREECAD_VIDEO_REFERENCE.md`

Important completed pieces:

- split-screen agent-manipulation visualization video
- redesigned left-side `Agent Command Stream`
- true FreeCAD motion endings
  - drive
  - turntable spin
  - combo: one full rotation, then forward travel

## Known Gaps

The mechanism is working, but it is not feature-complete.

Current limits:

- live preview is near-real-time, not continuous viewport streaming
- some harnesses are only first-pass preview integrations
- FreeCAD motion is currently part-placement driven, not Assembly-joint driven
- RenderDoc preview is limited by machine graphics/runtime constraints when
  generating fresh captures locally
- Blender now has live preview parity at the protocol/session level, but its
  showcase/demo tooling is still shallower than FreeCAD's motion/video stack

## Recommended Next Work

1. Expand Blender demo tooling beyond the first Gyro Observatory proof point.
2. Restack this preview branch onto a clean `origin/main` base before the PR
   stack grows larger.
3. Split this large checkpoint into a reviewable commit stack later:
   - protocol + cli-hub
   - shotcut / openscreen
   - blender
   - freecad
   - renderdoc
   - demo/video tooling

## Related Docs

- `docs/PREVIEW_PROTOCOL.md`
- `docs/PREVIEW_PROGRESS.md`
- `docs/FREECAD_VIDEO_REFERENCE.md`
- `docs/FREECAD_DEMO_PROPOSALS.md`
