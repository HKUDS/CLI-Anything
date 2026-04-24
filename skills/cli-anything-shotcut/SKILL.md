---
name: >-
  cli-anything-shotcut
description: >-
  Command-line interface for Shotcut - A stateful command-line interface for video editing, built on the MLT XML format. Designed for AI ag...
---

# cli-anything-shotcut

A stateful command-line interface for video editing, built on the MLT XML format. Designed for AI agents and power users who need to create and edit Shotcut projects without a GUI.

## Installation

This CLI is installed as part of the cli-anything-shotcut package:

```bash
pip install cli-anything-shotcut
```

**Prerequisites:**
- Python 3.10+
- `melt` (MLT CLI) — required for rendering and playback
- `ffmpeg` / `ffprobe` — required for media probing
- `shotcut` must be installed on your system


## Usage

### Basic Commands

```bash
# Show help
cli-anything-shotcut --help

# Start interactive REPL mode
cli-anything-shotcut

# Create a new project
cli-anything-shotcut project new -o project.json

# Run with JSON output (for agent consumption)
cli-anything-shotcut --json project info -p project.json
```

### REPL Mode

When invoked without a subcommand, the CLI enters an interactive REPL session with undo/redo support:

```bash
cli-anything-shotcut
# or with a project:
cli-anything-shotcut --project my_project.mlt
```

#### REPL Commands

**Workflow:** Always `media import` first to get a `clip_id`, then use `add-clip` to place it on the timeline.

**Project & Session:**
- `new [profile]` — Create new project (default: `hd1080p30`)
- `open <path>` — Open `.mlt` file
- `save [path]` — Save project
- `info` — Show project info
- `xml` — Print raw MLT XML
- `status` — Show session status
- `undo` / `redo` — Navigate operation history

**Media (two-step model):**
- `media import <file> [--caption name]` — Import file into project bin, returns `clip_id` (e.g., `clip0`)
- `media` — List all imported media
- `probe <file>` — Analyze a media file

**Timeline:**
- `add-track <video|audio> [name]` — Add a track
- `tracks` — List all tracks
- `show` — Visual timeline overview
- `add-clip <clip_id> <track> [in] [out] [--at time]` — Place imported clip on track
- `clips <track>` — List clips on a track
- `remove-clip <track> <clip>` — Remove a clip
- `trim <track> <clip> [--in tc] [--out tc]` — Trim clip
- `split <track> <clip> <at>` — Split clip at timecode

**Filters:**
- `list-filters [video|audio]` — Browse available filters
- `filter-info <name>` — Show filter details
- `add-filter <name> [--track n] [--clip n] [key=val ...]` — Add filter to clip, track, or global
- `filters [--track n] [--clip n]` — List active filters
- `remove-filter <idx> [--track n] [--clip n]` — Remove filter by index
- `set-filter <idx> <param> <value> [--track n] [--clip n]` — Set filter parameter
- `volume-envelope [--track n] [--clip n] TIME=LEVEL ...` — Keyframed volume (e.g., `00:00:00.000=1.0 00:00:03.000=0.35`)
- `duck [--track n] [--clip n] START..END ...` — Ducking envelope (e.g., `00:00:06.000..00:00:09.000`)

**Export:**
- `presets` — List export presets
- `render <output> [--preset name]` — Render to video file


## Command Groups


### Project

Project management: new, open, save, info.

| Command | Description |
|---------|-------------|
| `new` | Create a new blank project |
| `open` | Open an existing .mlt project file |
| `save` | Save the current project |
| `info` | Show detailed project information |
| `profiles` | List available video profiles |
| `xml` | Print the raw MLT XML of the current project |


### Timeline

Timeline operations: tracks, clips, trimming.

| Command | Description |
|---------|-------------|
| `show` | Show the timeline overview |
| `tracks` | List all tracks |
| `add-track` | Add a new track to the timeline |
| `remove-track` | Remove a track by index |
| `add-clip` | Add an imported clip to a track by clip_id; supports `--at` for absolute placement |
| `remove-clip` | Remove a clip from a track |
| `move-clip` | Move a clip between tracks or positions |
| `trim` | Trim a clip's in/out points |
| `split` | Split a clip into two at the given timecode |
| `clips` | List all clips on a track |
| `add-blank` | Add a blank gap to a track |
| `set-name` | Set a track's display name |
| `mute` | Mute or unmute a track |
| `hide` | Hide or unhide a video track |


### Filter Group

Filter operations: add, remove, configure effects.

| Command | Description |
|---------|-------------|
| `list-available` | List all available filters |
| `info` | Show detailed info about a filter and its parameters |
| `add` | Add a filter to a clip, track, or globally |
| `remove` | Remove a filter by index |
| `set` | Set a parameter on a filter |
| `list` | List active filters on a target |
| `volume-envelope` | Create or replace a keyframed volume envelope on a track or clip |
| `duck` | Build a practical ducking envelope over one or more time windows |


### Media

Media operations: probe, list, check files.

| Command | Description |
|---------|-------------|
| `import` | Import a media file into the project bin |
| `probe` | Analyze a media file's properties |
| `list` | List all media clips in the current project |
| `check` | Check all media files for existence |
| `thumbnail` | Generate a thumbnail from a video file |


### Export

Export/render operations.

| Command | Description |
|---------|-------------|
| `presets` | List available export presets |
| `preset-info` | Show details of an export preset |
| `render` | Render the project to a video file |


### Transition Group

Transition operations: dissolve, wipe, and other transitions.

| Command | Description |
|---------|-------------|
| `list-available` | List all available transition types |
| `info` | Show detailed info about a transition type |
| `add` | Add a transition between two tracks |
| `remove` | Remove a transition by index |
| `set` | Set a parameter on a transition |
| `list` | List all transitions on the timeline |


### Composite Group

Compositing: blend modes, PIP, opacity.

| Command | Description |
|---------|-------------|
| `blend-modes` | List all available blend modes |
| `set-blend` | Set the blend mode for a track |
| `get-blend` | Get the current blend mode for a track |
| `set-opacity` | Set the opacity of a track (0.0-1.0) |
| `pip` | Set picture-in-picture position for a clip |


### Session

Session management: status, undo, redo.

| Command | Description |
|---------|-------------|
| `status` | Show current session status |
| `undo` | Undo the last operation |
| `redo` | Redo the last undone operation |
| `save` | Save session state to disk |
| `list` | List all saved sessions |

### Preview

Preview bundles and live preview sessions for iterative editing review.

| Command | Description |
|---------|-------------|
| `preview recipes` | List preview recipes |
| `preview capture` | Render a low-res preview bundle |
| `preview latest` | Return the latest existing bundle |
| `preview live start` | Start a live preview session and publish the first bundle |
| `preview live push` | Publish a new bundle into the live session |
| `preview live status` | Query current live-session state without rendering |
| `preview live stop` | Stop the live session without deleting artifacts |

Typical `quick` bundle contents:

- `preview.mp4`
- several sampled frames
- midpoint `hero.png`
- `summary.json` with project facts

Poll mode is supported:

```bash
cli-anything-shotcut --json --project edit.mlt preview live start --recipe quick --mode poll --source-poll-ms 500
```

`preview live status --json` includes session refs and a compact
`trajectory_summary` so agents can cheaply understand the latest few publishes.

Viewer commands:

```bash
cli-hub previews inspect /path/to/bundle-or-session
cli-hub previews html /path/to/bundle-or-session -o page.html
cli-hub previews watch /path/to/session --open
cli-hub previews open /path/to/bundle-or-session
```




## Examples


### Create a New Project

Create a new shotcut project file.

```bash
cli-anything-shotcut project new -o myproject.json
# Or with JSON output for programmatic use
cli-anything-shotcut --json project new -o myproject.json
```


### Interactive REPL Session

Start an interactive session with undo/redo support.

```bash
cli-anything-shotcut
# Enter commands interactively
# Use 'help' to see available commands
# Use 'undo' and 'redo' for history navigation
```


### Export Project

Export the project to a final output format.

```bash
cli-anything-shotcut --project myproject.json export render output.mp4 --overwrite
```


### Deterministic Timeline Reconstruction

For rebuilds, prefer absolute placement over append-only clip insertion:

```bash
cli-anything-shotcut --project myproject.mlt media import intro.mp4
cli-anything-shotcut --project myproject.mlt timeline add-clip clip0 \
  --track 1 --in 00:00:00.000 --out 00:00:04.000 --at 00:00:00.000

cli-anything-shotcut --project myproject.mlt media import broll.mp4
cli-anything-shotcut --project myproject.mlt timeline add-clip clip1 \
  --track 1 --in 00:00:10.000 --out 00:00:16.000 --at 00:00:08.000
```

- `--at` inserts blanks automatically when the target time lands in empty space.
- The CLI rejects overlap with an existing clip.
- Prefer explicit `--in` and `--out` values so later absolute placement remains unambiguous.

### Audio Automation

```bash
cli-anything-shotcut --project myproject.mlt filter volume-envelope \
  --track 2 \
  --point 00:00:00.000=1.0 \
  --point 00:00:03.000=0.35 \
  --point 00:00:05.000=1.0

cli-anything-shotcut --project myproject.mlt filter duck \
  --track 2 \
  --window 00:00:06.000..00:00:09.000 \
  --window 00:00:15.000..00:00:18.000 \
  --normal 1.0 --duck 0.25
```

The CLI maintains session state with:

- **Undo/Redo**: Up to 50 levels of history
- **Project persistence**: Save/load project state as JSON
- **Session tracking**: Track modifications and changes

## Output Formats

All commands support dual output modes:

- **Human-readable** (default): Tables, colors, formatted text
- **Machine-readable** (`--json` flag): Structured JSON for agent consumption

```bash
# Human output
cli-anything-shotcut project info -p project.json

# JSON output for agents
cli-anything-shotcut --json project info -p project.json
```

## For AI Agents

When using this CLI programmatically:

1. **Always use `--json` flag** for parseable output
2. **Check return codes** - 0 for success, non-zero for errors
3. **Parse stderr** for error messages on failure
4. **Use absolute paths** for all file operations
5. **Verify outputs exist** after export operations
6. **Prefer `timeline add-clip --at`** when recreating a known edit
7. **Review final renders** after keyframed volume or ducking changes
8. **Use `preview capture` or `preview live ...` to validate pacing, cuts, and filter effects visually**
9. **Read returned artifact paths** such as `hero.png` and `preview.mp4`; JSON payloads reference files on disk
10. **Use `preview live status --json` before reading the full `trajectory.json`**
11. **Use `cli-hub previews ...` only to inspect/open existing bundles or live sessions**

## More Information

- Full documentation: See README.md in the package
- Test coverage: See TEST.md in the package
- Methodology: See HARNESS.md in the cli-anything-plugin

## Version

1.0.0
