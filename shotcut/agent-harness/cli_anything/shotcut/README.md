# Shotcut CLI

A stateful command-line interface for video editing, built on the MLT XML format.
Designed for AI agents and power users who need to create and edit Shotcut projects
without a GUI.

## Prerequisites

- Python 3.10+
- `click` (CLI framework)
- `melt` (MLT CLI) — **required** for rendering and playback
- `ffmpeg` / `ffprobe` — required for media probing and export

Optional (for interactive REPL):
- `prompt_toolkit`

## Install Dependencies

```bash
pip install click prompt_toolkit
```

System tools (required for full functionality):
```bash
# Arch Linux
pacman -S melt ffmpeg

# Ubuntu/Debian
apt install melt ffmpeg

# macOS
brew install mlt ffmpeg
```

## How to Run

All commands are run from the `agent-harness/` directory.

### One-shot commands

```bash
# Show help
python3 -m cli.shotcut_cli --help

# Create a new project
python3 -m cli.shotcut_cli project new --profile hd1080p30 -o my_project.mlt

# Open a project and show info
python3 -m cli.shotcut_cli --project my_project.mlt project info

# JSON output (for agent consumption)
python3 -m cli.shotcut_cli --json --project my_project.mlt project info
```

### Interactive REPL

```bash
# Start with a new project
python3 -m cli.shotcut_cli repl

# Or open an existing project
python3 -m cli.shotcut_cli repl --project my_project.mlt
```

Inside the REPL, type `help` for all available commands.

#### REPL Command Reference

**Project & Session:**

| Command | Description |
|---------|-------------|
| `new [profile]` | Create new project (default: `hd1080p30`) |
| `open <path>` | Open an existing `.mlt` project file |
| `save [path]` | Save the project |
| `info` | Show project info |
| `xml` | Print raw MLT XML |
| `status` | Show session status |
| `undo` | Undo last operation |
| `redo` | Redo last undone operation |

**Media:**

| Command | Description |
|---------|-------------|
| `media import <file> [--caption name]` | Import media file, returns `clip_id` |
| `media` | List all imported media |
| `probe <file>` | Analyze a media file |

**Timeline:**

| Command | Description |
|---------|-------------|
| `add-track <video\|audio> [name]` | Add a track |
| `tracks` | List all tracks |
| `show` | Show timeline overview |
| `add-clip <clip_id> <track> [in] [out] [--at time]` | Add clip to track |
| `clips <track>` | List clips on a track |
| `remove-clip <track> <clip>` | Remove a clip |
| `trim <track> <clip> [--in tc] [--out tc]` | Trim clip in/out points |
| `split <track> <clip> <at>` | Split clip at timecode |

**Filters:**

| Command | Description |
|---------|-------------|
| `list-filters [video\|audio]` | Browse available filters |
| `filter-info <name>` | Show filter details and params |
| `add-filter <name> [--track n] [--clip n] [p=v ...]` | Add filter |
| `filters [--track n] [--clip n]` | List active filters |
| `remove-filter <idx> [--track n] [--clip n]` | Remove filter |
| `set-filter <idx> <param> <value> [--track n] [--clip n]` | Set filter param |
| `volume-envelope [--track n] [--clip n] TIME=LEVEL ...` | Set volume envelope |
| `duck [--track n] [--clip n] START..END ...` | Apply ducking envelope |

**Export:**

| Command | Description |
|---------|-------------|
| `presets` | List export presets |
| `render <output> [--preset name]` | Render project |

#### REPL Example Session

```
> new hd1080p30
> add-track video Main
> media import intro.mp4
  Imported intro.mp4 as clip0
> media import main.mp4
  Imported main.mp4 as clip1
> add-clip clip0 1 00:00:00.000 00:00:05.000
> add-clip clip1 1 00:00:00.000 00:00:10.000 --at 00:00:05.000
> add-filter brightness --track 1 --clip 0 level=1.3
> show
> save
> render output.mp4 --preset h264-high
```

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
timeline add-clip <clip_id> --track <n> [--in tc] [--out tc] [--at tc]  # Add clip
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
filter volume-envelope [--track n] [--clip n] --point TIME=LEVEL ...  # Volume envelope
filter duck [--track n] [--clip n] --window START..END ...   # Ducking envelope
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
media import <file> [--caption name]               # Import media into project bin
media list                                         # List media in project
media probe <file>                                 # Analyze media file
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
python3 -m cli.shotcut_cli --json --project p.mlt timeline clips 1
```

## Preview and Live Preview

Shotcut supports both static preview bundles and live preview sessions.

```bash
# Capture a low-res preview bundle
cli-anything-shotcut --json --project edit.mlt preview capture --recipe quick

# Start poll-mode live preview
cli-anything-shotcut --json --project edit.mlt preview live start --recipe quick --mode poll --source-poll-ms 500

# Query the current live session without rendering
cli-anything-shotcut --json --project edit.mlt preview live status --recipe quick
```

The default `quick` bundle contains:

- `preview.mp4`
- sampled frames
- midpoint `hero.png`
- `summary.json`

Live preview persists `session.json`, immutable bundle dirs, and
`trajectory.json`.

Inspect or open published preview state with:

```bash
cli-hub previews inspect /path/to/bundle-or-session
cli-hub previews html /path/to/bundle-or-session -o page.html
cli-hub previews watch /path/to/session --open
cli-hub previews open /path/to/bundle-or-session
```

## Running Tests

```bash
cd agent-harness
python3 -m pytest cli/tests/test_core.py -v
```

## Example Workflow

```bash
# Create a project with two video tracks
python3 -m cli.shotcut_cli project new --profile hd1080p30 -o edit.mlt
python3 -m cli.shotcut_cli --project edit.mlt timeline add-track --type video --name "Main"
python3 -m cli.shotcut_cli --project edit.mlt timeline add-track --type audio --name "Music"

# Import media files into the project bin
python3 -m cli.shotcut_cli --project edit.mlt media import intro.mp4
python3 -m cli.shotcut_cli --project edit.mlt media import main.mp4

# Add clips to the timeline by clip_id
python3 -m cli.shotcut_cli --project edit.mlt timeline add-clip clip0 --track 1 --in 00:00:00.000 --out 00:00:05.000
python3 -m cli.shotcut_cli --project edit.mlt timeline add-clip clip1 --track 1 --in 00:00:00.000 --out 00:00:30.000 --at 00:00:08.000

# Apply a brightness filter to the first clip
python3 -m cli.shotcut_cli --project edit.mlt filter add brightness --track 1 --clip 0 --param level=1.3

# Duck the music during narration
python3 -m cli.shotcut_cli --project edit.mlt filter duck --track 2 \
  --window 00:00:00.000..00:00:05.000 --duck 0.2

# View the timeline
python3 -m cli.shotcut_cli --project edit.mlt timeline show

# Save and render
python3 -m cli.shotcut_cli --project edit.mlt project save
python3 -m cli.shotcut_cli --project edit.mlt export render output.mp4 --preset h264-high --overwrite
```
