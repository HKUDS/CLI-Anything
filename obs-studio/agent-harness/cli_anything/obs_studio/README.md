# OBS Studio CLI - Agent Harness

A stateful command-line interface for OBS Studio scene collection editing,
following the same patterns as the Blender CLI harness. Uses a JSON scene
collection format. No OBS installation required for editing.

## Installation

```bash
pip install click prompt_toolkit
```

## Quick Start

```bash
# Create a new project
cli-anything-obs-studio project new --name "my_stream" -o project.json

# Add sources
cli-anything-obs-studio --project project.json source add video_capture --name "Camera"
cli-anything-obs-studio --project project.json source add display_capture --name "Game"

# Add filters
cli-anything-obs-studio --project project.json filter add chroma_key -S 0 -p similarity=400

# Add scenes
cli-anything-obs-studio --project project.json scene add --name "BRB"

# Configure streaming
cli-anything-obs-studio --project project.json output streaming --service twitch --key "your_key"

# Save
cli-anything-obs-studio --project project.json project save
```

## JSON Output Mode

```bash
cli-anything-obs-studio --json project new -o project.json
cli-anything-obs-studio --json --project project.json source list
```

## Interactive REPL

```bash
cli-anything-obs-studio repl
cli-anything-obs-studio repl --project project.json
```

## Command Groups

### Project Management
```
project new   - Create a new scene collection
project open  - Open an existing project file
project save  - Save the current project
project info  - Show project information
project json  - Print raw project JSON
```

### Scene Management
```
scene add        - Add a new scene
scene remove     - Remove a scene by index
scene duplicate  - Duplicate a scene
scene set-active - Set the active scene
scene list       - List all scenes
```

### Source Management
```
source add       - Add a source (video_capture, display_capture, image, text, browser, etc.)
source remove    - Remove a source by index
source duplicate - Duplicate a source
source set       - Set a source property (name, visible, locked, opacity, rotation)
source transform - Transform a source (position, size, crop, rotation)
source list      - List all sources in a scene
```

### Filter Management
```
filter add            - Add a filter to a source
filter remove         - Remove a filter
filter set            - Set a filter parameter
filter list           - List filters on a source
filter list-available - List all available filter types
```

### Audio Management
```
audio add     - Add a global audio source
audio remove  - Remove an audio source
audio volume  - Set volume (0.0-3.0)
audio mute    - Mute an audio source
audio unmute  - Unmute an audio source
audio monitor - Set audio monitoring type
audio list    - List all audio sources
```

### Transition Management
```
transition add        - Add a transition
transition remove     - Remove a transition
transition set-active - Set the active transition
transition duration   - Set transition duration
transition list       - List all transitions
```

### Output Configuration
```
output streaming - Configure streaming settings
output recording - Configure recording settings
output settings  - Configure encoder/resolution/bitrate
output info      - Show current output configuration
output presets   - List available encoding presets
```

### Session
```
session status  - Show session status
session undo    - Undo the last operation
session redo    - Redo the last undone operation
session history - Show undo history
```

## Running Tests

```bash
# From the agent-harness directory:
python3 -m pytest cli/tests/ -v

# Unit tests only
python3 -m pytest cli/tests/test_core.py -v

# E2E tests only
python3 -m pytest cli/tests/test_full_e2e.py -v
```

## Architecture

```
cli/
├── __init__.py
├── obs_cli.py            # Main CLI entry point (Click + REPL)
├── core/
│   ├── __init__.py
│   ├── project.py        # Project create/open/save/info
│   ├── scenes.py         # Scene management
│   ├── sources.py        # Source management + SOURCE_TYPES registry
│   ├── filters.py        # Filter management + FILTER_TYPES registry
│   ├── audio.py          # Audio source management
│   ├── transitions.py    # Transition management
│   ├── output.py         # Streaming/recording/encoding config
│   └── session.py        # Session state, undo/redo
├── utils/
│   ├── __init__.py
│   └── obs_utils.py      # JSON helpers and utilities
└── tests/
    ├── __init__.py
    ├── test_core.py       # Unit tests (60+ tests)
    └── test_full_e2e.py   # E2E tests (40+ tests)
```

## Source Types

video_capture, display_capture, window_capture, image, media, browser,
text, color, audio_input, audio_output, group, scene

## Filter Types

color_correction, chroma_key, color_key, lut, image_mask, crop_pad, scroll,
sharpen, noise_suppress, gain, compressor, noise_gate, limiter
