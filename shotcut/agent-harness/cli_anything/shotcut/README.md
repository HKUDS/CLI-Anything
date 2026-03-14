# Shotcut CLI

A stateful command-line interface for video editing, built on the MLT XML format.
Designed for AI agents and power users who need to create and edit Shotcut projects
without a GUI.

## Prerequisites

- Python 3.10+
- `lxml` (XML manipulation)
- `click` (CLI framework)

Optional (for interactive REPL):
- `prompt_toolkit`

Optional (for rendering/media probing):
- `ffmpeg` / `ffprobe`
- `melt` (MLT CLI)

## Install Dependencies

```bash
pip install lxml click prompt_toolkit
```

## How to Run

All commands are run from the `agent-harness/` directory.

### One-shot commands

```bash
# Show help
cli-anything-shotcut --help

# Create a new project
cli-anything-shotcut project new --profile hd1080p30 -o my_project.mlt

# Open a project and show info
cli-anything-shotcut --project my_project.mlt project info

# JSON output (for agent consumption)
cli-anything-shotcut --json --project my_project.mlt project info
```

### Interactive REPL

```bash
cli-anything-shotcut repl
cli-anything-shotcut repl --project my_project.mlt
```

Inside the REPL, type `help` for all available commands.

## Command Reference

### Project

```bash
project new --profile <profile> [-o path]   # Create new project
project open <path>                          # Open .mlt file
project save [path]                          # Save project
project info                                 # Show project details
project profiles                             # List available profiles
project xml                                  # Print raw MLT XML
```

Available profiles: `hd1080p30`, `hd1080p60`, `hd1080p24`, `hd720p30`, `4k30`, `4k60`, `sd480p`

### Timeline

```bash
timeline show                                       # Visual timeline overview
timeline tracks                                     # List all tracks
timeline add-track --type <video|audio> [--name N]  # Add track
timeline remove-track <index>                       # Remove track
timeline add-clip <file> --track <n> [--in tc] [--out tc]  # Add clip
timeline remove-clip <track> <clip> [--no-ripple]   # Remove clip
timeline move-clip <track> <clip> --to-track <n>    # Move clip
timeline trim <track> <clip> [--in tc] [--out tc]   # Trim clip
timeline split <track> <clip> --at <tc>             # Split clip
timeline clips <track>                              # List clips on track
timeline add-blank <track> --length <tc>            # Add gap
timeline set-name <track> <name>                    # Rename track
timeline mute <track> [--unmute]                    # Mute/unmute
timeline hide <track> [--unhide]                    # Hide/unhide
```

### Filters

```bash
filter list-available [--category video|audio]               # Browse filters
filter info <name>                                           # Filter details + params
filter add <name> [--track n] [--clip n] [--param k=v ...]  # Apply filter
filter remove <index> [--track n] [--clip n]                 # Remove filter
filter set <index> <param> <value> [--track n] [--clip n]   # Set param
filter list [--track n] [--clip n]                           # List active filters
```

### Transitions

```bash
transition list-available [--category video|audio]            # Browse transitions
transition info <name>                                        # Transition details + params
transition add <name> --track-a <n> --track-b <n> [--in tc] [--out tc] [--param k=v ...]  # Add transition
transition remove <index>                                     # Remove transition
transition set <index> <param> <value>                        # Set param
transition list                                               # List active transitions
```

Available transitions: `dissolve`, `wipe-left`, `wipe-right`, `wipe-down`, `wipe-up`,
`bar-horizontal`, `bar-vertical`, `diagonal`, `clock`, `iris-circle`, `crossfade`

### Compositing

```bash
composite blend-modes                                 # List available blend modes
composite set-blend <track> <mode>                    # Set track blend mode
composite get-blend <track>                           # Get track blend mode
composite set-opacity <track> <value>                 # Set track opacity (0.0-1.0)
composite pip <track> <clip> [--x X] [--y Y] [--width W] [--height H] [--opacity O]  # Picture-in-picture
```

Available blend modes: `normal`, `add`, `multiply`, `screen`, `overlay`, `darken`,
`lighten`, `colordodge`, `colorburn`, `hardlight`, `softlight`, `difference`,
`exclusion`, `hslhue`, `hslsaturation`, `hslcolor`, `hslluminosity`, `saturate`

### Media

```bash
media probe <file>                                 # Analyze media file
media list                                         # List media in project
media check                                        # Check all files exist
media thumbnail <file> -o <output> [--time tc]     # Extract thumbnail
```

### Export

```bash
export presets                                     # List export presets
export preset-info <name>                          # Preset details
export render <output> [--preset name] [--overwrite]  # Render project
```

Available presets: `default`, `h264-high`, `h264-fast`, `h265`, `webm-vp9`,
`prores`, `gif`, `audio-mp3`, `audio-wav`, `png-sequence`

### Session

```bash
session status      # Current session state
session undo        # Undo last operation
session redo        # Redo
session save        # Persist session to disk
session list        # List saved sessions
```

## Timecode Formats

The CLI accepts these timecode formats anywhere a time value is expected:

| Format | Example | Meaning |
|--------|---------|---------|
| `HH:MM:SS.mmm` | `00:01:30.500` | 1 minute, 30.5 seconds |
| `HH:MM:SS:FF` | `00:01:30:15` | 1 min 30 sec, frame 15 |
| `HH:MM:SS` | `00:01:30` | 1 minute 30 seconds |
| `SS.mmm` | `90.5` | 90.5 seconds |
| Frame number | `2715` | Frame 2715 |

## JSON Mode

Add `--json` before the subcommand for machine-readable output:

```bash
cli-anything-shotcut --json --project p.mlt timeline clips 1
```

## Running Tests

```bash
cd agent-harness
python3 -m pytest cli_anything/shotcut/tests/test_core.py -v
```

## Example Workflow

```bash
# Create a project with two video tracks
cli-anything-shotcut project new --profile hd1080p30 -o edit.mlt
cli-anything-shotcut --project edit.mlt timeline add-track --type video --name "Main"
cli-anything-shotcut --project edit.mlt timeline add-track --type audio --name "Music"

# Add clips (assuming media files exist)
cli-anything-shotcut --project edit.mlt timeline add-clip intro.mp4 --track 1 --in 00:00:00.000 --out 00:00:05.000
cli-anything-shotcut --project edit.mlt timeline add-clip main.mp4 --track 1 --in 00:00:00.000 --out 00:00:30.000

# Apply a brightness filter to the first clip
cli-anything-shotcut --project edit.mlt filter add brightness --track 1 --clip 0 --param level=1.3

# View the timeline
cli-anything-shotcut --project edit.mlt timeline show

# Save and render
cli-anything-shotcut --project edit.mlt project save
cli-anything-shotcut --project edit.mlt export render output.mp4 --preset h264-high --overwrite
```
