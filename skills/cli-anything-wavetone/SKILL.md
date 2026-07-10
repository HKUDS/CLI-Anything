---
name: "cli-anything-wavetone"
description: "Control WaveTone 2.61 workflows through a JSON manifest and launch the real Windows WaveTone executable."
---

# cli-anything-wavetone

Use this skill when an agent needs to prepare, inspect, and launch WaveTone 2.61
audio transcription workflows.

## Requirements

- Windows host.
- WaveTone 2.61 extracted locally.
- Set `WAVETONE_EXE` to `wavetone.exe` or `WAVETONE_HOME` to the extracted
  WaveTone directory when the default portable path is not used.

## Core Commands

All commands support the top-level `--json` flag.

```bash
cli-anything-wavetone --json wavetone doctor
cli-anything-wavetone --json project new input.wav -o project.wt.json
cli-anything-wavetone --project project.wt.json --json audio probe
cli-anything-wavetone --project project.wt.json --json project set-tempo --bpm 120 --meter 4/4
cli-anything-wavetone --project project.wt.json --json project add-label chorus --time 64.0
cli-anything-wavetone --project project.wt.json --json wavetone launch
```

## Command Groups

- `project`: create manifests, set tempo, add labels, update intended analysis
  settings, and attach a WFD saved from WaveTone.
- `audio`: probe audio metadata before opening it in WaveTone.
- `wavetone`: run `doctor`, list supported formats, or launch the real GUI.
- `session`: record lightweight event logs for multi-step agent workflows.
- `defaults`: show default analysis settings.

## Agent Guidance

The JSON project manifest is not a WaveTone WFD file. It is an agent-facing plan
for the source audio, intended analysis settings, labels, and tempo metadata.
Use WaveTone itself to perform analysis and save WFD/MIDI/text/WAVE outputs.

When running in automated checks, use:

```bash
cli-anything-wavetone --json wavetone launch input.wav --wait 1 --terminate
```

This confirms that the real backend can be started without leaving a persistent
GUI process behind.
