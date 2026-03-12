# Kdenlive CLI - Standard Operating Procedure

## Overview

The Kdenlive CLI harness provides a stateful command-line interface for non-linear video editing. It manipulates project state in JSON format and generates valid Kdenlive/MLT XML for rendering.

## Setup

```bash
cd ~/CLI-Anything/kdenlive/agent-harness
pip install click
```

No Kdenlive or melt installation is required for project editing and XML generation.

## Core Workflow

### 1. Create a Project

```bash
python3 -m cli.kdenlive_cli project new --name "MyProject" --profile hd1080p30 -o project.json
```

Available profiles: hd1080p30, hd1080p25, hd1080p24, hd1080p60, hd720p30, hd720p25, hd720p60, 4k30, 4k60, sd_ntsc, sd_pal

### 2. Import Media

```bash
python3 -m cli.kdenlive_cli --project project.json bin import /path/to/video.mp4 --name "Main" -d 120.0
python3 -m cli.kdenlive_cli --project project.json bin import /path/to/audio.wav --name "Music" -d 180.0 --type audio
```

Clip types: video, audio, image, color, title

### 3. Build Timeline

```bash
# Add tracks
python3 -m cli.kdenlive_cli --project project.json timeline add-track --type video
python3 -m cli.kdenlive_cli --project project.json timeline add-track --type audio

# Place clips
python3 -m cli.kdenlive_cli --project project.json timeline add-clip 0 clip0 --position 0 --out 30.0

# Trim, split, move
python3 -m cli.kdenlive_cli --project project.json timeline trim 0 0 --in 5.0 --out 25.0
python3 -m cli.kdenlive_cli --project project.json timeline split 0 0 10.0
python3 -m cli.kdenlive_cli --project project.json timeline move 0 0 5.0
```

### 4. Apply Effects

```bash
# Available: brightness, contrast, saturation, blur, fade_in_video, fade_out_video,
# fade_in_audio, fade_out_audio, volume, crop, rotate, speed, chroma_key
python3 -m cli.kdenlive_cli --project project.json filter add 0 0 brightness -p level=1.3
python3 -m cli.kdenlive_cli --project project.json filter add 0 0 blur -p hblur=5 -p vblur=5
```

### 5. Add Transitions

```bash
# Available: dissolve, wipe, slide, composite, affine
python3 -m cli.kdenlive_cli --project project.json transition add dissolve 0 1 -p 5.0 -d 2.0
```

### 6. Add Guides

```bash
python3 -m cli.kdenlive_cli --project project.json guide add 30.0 --label "Scene 2"
```

### 7. Export

```bash
# Generate MLT XML for Kdenlive
python3 -m cli.kdenlive_cli --project project.json export xml -o output.kdenlive

# Open in Kdenlive (if installed)
kdenlive output.kdenlive
```

## Session Management

The CLI supports undo/redo for all mutations:

```bash
python3 -m cli.kdenlive_cli --project project.json session undo
python3 -m cli.kdenlive_cli --project project.json session redo
python3 -m cli.kdenlive_cli --project project.json session history
python3 -m cli.kdenlive_cli --project project.json session status
```

## JSON Output

All commands support `--json` flag for machine-readable output:

```bash
python3 -m cli.kdenlive_cli --json --project project.json bin list
python3 -m cli.kdenlive_cli --json --project project.json timeline list
```

## Interactive REPL

```bash
python3 -m cli.kdenlive_cli repl --project project.json
```

## Testing

```bash
cd ~/CLI-Anything/kdenlive/agent-harness

# Run all tests
python3 -m pytest cli/tests/ -v

# Unit tests (60+ tests)
python3 -m pytest cli/tests/test_core.py -v

# E2E tests (40+ tests)
python3 -m pytest cli/tests/test_full_e2e.py -v
```

## Architecture

- **JSON project format**: All state is stored as JSON, easily inspectable and diffable
- **MLT XML export**: Generates valid MLT XML with Kdenlive metadata
- **No binary dependencies**: Only Python stdlib + click required
- **Undo/redo**: Full session history with deep-copy snapshots
- **Timecode support**: Accepts both seconds (float) and HH:MM:SS.mmm format

## Key Files

```
cli/kdenlive_cli.py       - Main CLI entry point
cli/core/project.py       - Project management
cli/core/bin.py           - Media bin
cli/core/timeline.py      - Timeline tracks and clips
cli/core/filters.py       - Filter/effect registry
cli/core/transitions.py   - Transition management
cli/core/guides.py        - Guide/marker management
cli/core/export.py        - XML generation
cli/core/session.py       - Session undo/redo
cli/utils/mlt_xml.py      - MLT XML helpers
```
