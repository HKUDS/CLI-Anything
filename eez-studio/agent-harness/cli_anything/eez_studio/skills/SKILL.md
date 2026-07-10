---
name: "cli-anything-eez-studio"
description: "Use EEZ Studio from the command line: inspect and modify native .eez-project files, edit LVGL screens/widgets, manage SCPI commands, and invoke the real EEZ Studio backend for LVGL builds."
---

# cli-anything-eez-studio

Use this skill when you need to automate EEZ Studio projects, LVGL UI scaffolding, SCPI instrument command metadata, or backend LVGL simulator builds.

## Install

```bash
cd eez-studio/agent-harness
pip install -e .
```

Backend commands require the real EEZ Studio source tree:

```bash
git clone https://github.com/eez-open/studio.git
cd studio
npm install
npm run build
export EEZ_STUDIO_SOURCE=/absolute/path/to/studio
```

## Core Usage

Always use `--json` for agent-readable output.

```bash
cli-anything-eez-studio --json project new -o panel.eez-project --name Panel
cli-anything-eez-studio --json --project panel.eez-project lvgl add-label --text "Ready"
cli-anything-eez-studio --json --project panel.eez-project lvgl add-button --text "Run"
cli-anything-eez-studio --json --project panel.eez-project project widgets
```

## SCPI Commands

```bash
cli-anything-eez-studio --json --project panel.eez-project scpi subsystem-add SOURCE
cli-anything-eez-studio --json --project panel.eez-project scpi command-add SOURCE :VOLTage?
cli-anything-eez-studio --json --project panel.eez-project scpi parameter-add SOURCE :VOLTage? channel --type nr1 --optional
```

## Backend Commands

```bash
cli-anything-eez-studio --json backend status
cli-anything-eez-studio --json --project panel.eez-project lvgl ensure-destination
cli-anything-eez-studio --json --project panel.eez-project lvgl backend-inspect
cli-anything-eez-studio --json --project panel.eez-project lvgl simulator-build build/sim
```

`lvgl backend-inspect` and `lvgl simulator-build` call EEZ Studio's built Node modules. They should fail loudly if the backend is missing.

## State

Use `session undo`, `session redo`, and `session status` during REPL or scripted sessions. One-shot commands with `--project` auto-save project mutations unless `--dry-run` is provided.
