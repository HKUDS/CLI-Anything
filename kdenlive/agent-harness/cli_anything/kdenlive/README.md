# Kdenlive CLI - Agent Harness

A stateful command-line interface for video editing, following the same
patterns as the Blender CLI harness. Uses a JSON project format with
MLT XML generation for Kdenlive/melt.

## Installation

```bash
# From the agent-harness directory:
pip install click

# No Kdenlive or melt installation required for project editing.
# Kdenlive is only needed to open the generated .kdenlive XML files.
```

## Quick Start

```bash
# Create a new project
python3 -m cli.kdenlive_cli project new --name "MyVideo" --profile hd1080p30 -o project.json

# Import clips into the bin
python3 -m cli.kdenlive_cli --project project.json bin import /path/to/video.mp4 --name "Interview" -d 120.5
python3 -m cli.kdenlive_cli --project project.json bin import /path/to/music.mp3 --name "BGM" -d 180.0 --type audio

# Add tracks
python3 -m cli.kdenlive_cli --project project.json timeline add-track --type video
python3 -m cli.kdenlive_cli --project project.json timeline add-track --type audio

# Place clips on timeline
python3 -m cli.kdenlive_cli --project project.json timeline add-clip 0 clip0 --position 0 --out 30.0
python3 -m cli.kdenlive_cli --project project.json timeline add-clip 1 clip1 --position 0 --out 60.0

# Add filters
python3 -m cli.kdenlive_cli --project project.json filter add 0 0 brightness -p level=1.3

# Add transitions
python3 -m cli.kdenlive_cli --project project.json transition add dissolve 0 1 -d 2.0

# Add guides
python3 -m cli.kdenlive_cli --project project.json guide add 30.0 --label "Scene 2"

# Export to Kdenlive XML
python3 -m cli.kdenlive_cli --project project.json export xml -o output.kdenlive

# Save project
python3 -m cli.kdenlive_cli --project project.json project save
```

## JSON Output Mode

```bash
python3 -m cli.kdenlive_cli --json project new -o project.json
python3 -m cli.kdenlive_cli --json --project project.json bin list
```

## Interactive REPL

```bash
python3 -m cli.kdenlive_cli repl
# or with existing project:
python3 -m cli.kdenlive_cli repl --project project.json
```

## Command Groups

### Project Management
```
project new      - Create a new project
project open     - Open an existing project file
project save     - Save the current project
project info     - Show project information
project profiles - List available video profiles
project json     - Print raw project JSON
```

### Media Bin
```
bin import - Import a clip into the media bin
bin remove - Remove a clip from the bin
bin list   - List all clips in the bin
bin get    - Get detailed clip info
```

### Timeline
```
timeline add-track    - Add a video or audio track
timeline remove-track - Remove a track
timeline add-clip     - Place a clip on a track
timeline remove-clip  - Remove a clip from a track
timeline trim         - Trim a clip's in/out points
timeline split        - Split a clip at a time offset
timeline move         - Move a clip to a new position
timeline list         - List all tracks
```

### Filters
```
filter add       - Add a filter/effect to a clip
filter remove    - Remove a filter
filter set       - Set a filter parameter
filter list      - List filters on a clip
filter available - List all available filters
```

### Transitions
```
transition add    - Add a transition between tracks
transition remove - Remove a transition
transition set    - Set a transition parameter
transition list   - List all transitions
```

### Guides
```
guide add    - Add a guide/marker
guide remove - Remove a guide
guide list   - List all guides
```

### Export
```
export xml     - Generate Kdenlive/MLT XML
export presets - List available render presets
```

### Session
```
session status  - Show session status
session undo    - Undo the last operation
session redo    - Redo the last undone operation
session history - Show undo history
```

## Available Filters

brightness, contrast, saturation, blur, fade_in_video, fade_out_video,
fade_in_audio, fade_out_audio, volume, crop, rotate, speed, chroma_key

## Video Profiles

hd1080p30, hd1080p25, hd1080p24, hd1080p60, hd720p30, hd720p25,
hd720p60, 4k30, 4k60, sd_ntsc, sd_pal

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
├── __main__.py              # python3 -m cli.kdenlive_cli
├── kdenlive_cli.py          # Main CLI entry point (Click + REPL)
├── core/
│   ├── __init__.py
│   ├── project.py           # Project create/open/save/info/profiles
│   ├── bin.py               # Media bin management
│   ├── timeline.py          # Tracks and clip placement
│   ├── filters.py           # Filter/effect registry and management
│   ├── transitions.py       # Transition management
│   ├── guides.py            # Guide/marker management
│   ├── export.py            # XML generation and render presets
│   └── session.py           # Session with undo/redo
├── utils/
│   ├── __init__.py
│   └── mlt_xml.py           # MLT XML helpers, timecode conversions
└── tests/
    ├── __init__.py
    ├── test_core.py          # 60+ unit tests
    └── test_full_e2e.py      # 40+ E2E tests
```

## JSON Project Format

```json
{
  "version": "1.0",
  "name": "my_video",
  "profile": {
    "name": "hd1080p30", "width": 1920, "height": 1080,
    "fps_num": 30, "fps_den": 1, "progressive": true,
    "dar_num": 16, "dar_den": 9
  },
  "bin": [
    {"id": "clip0", "name": "Interview", "source": "/path/to/video.mp4",
     "duration": 120.5, "type": "video"}
  ],
  "tracks": [
    {"id": 0, "name": "V1", "type": "video", "mute": false, "hide": false,
     "locked": false, "clips": [
      {"clip_id": "clip0", "in": 0.0, "out": 30.0, "position": 0.0, "filters": []}
    ]}
  ],
  "transitions": [],
  "guides": [],
  "metadata": {}
}
```

## MLT XML Output

The generated XML is valid MLT XML with Kdenlive metadata, suitable for:
- Opening directly in Kdenlive
- Processing with `melt` command-line tool
- Further automated pipeline processing
