---
name: >-
  cli-anything-openscreen
description: >-
  Command-line interface for Openscreen — a screen recording editor.
  A stateful CLI for editing screen recordings with zoom, speed ramps,
  trim, crop, annotations, and polished exports. Built on the Openscreen
  JSON project format with ffmpeg as the rendering backend. Designed for
  AI agents and power users who need programmatic video editing.
---

# cli-anything-openscreen

A stateful command-line interface for editing screen recordings. Transform raw
captures into polished demo videos with zoom effects, speed adjustments,
trimming, annotations, and beautiful backgrounds.

## Installation

```bash
pip install cli-anything-openscreen
```

**Prerequisites:**
- Python 3.10+
- ffmpeg must be installed on your system

## Usage

### Basic Commands

```bash
cli-anything-openscreen --help
cli-anything-openscreen                     # REPL mode
cli-anything-openscreen project new -v recording.mp4 -o project.openscreen
cli-anything-openscreen --json project info
```

### REPL Mode

Run `cli-anything-openscreen` without arguments to enter interactive mode.
Type `help` for available commands, `quit` to exit.

## Command Groups

### project

Create, open, save, and configure projects.

| Command | Description |
|---------|-------------|
| `project new [-v VIDEO] [-o PATH]` | Create new project with optional video |
| `project open <path>` | Open existing .openscreen project |
| `project save [-o PATH]` | Save project to file |
| `project info` | Show project metadata and region counts |
| `project set-video <path>` | Set source video file |
| `project set <key> <value>` | Set editor setting (padding, wallpaper, etc.) |

### zoom

Manage zoom regions — smooth zoom effects on specific timeline areas.

| Command | Description |
|---------|-------------|
| `zoom list` | List all zoom regions |
| `zoom add --start MS --end MS [--depth 1-6] [--focus-x 0-1] [--focus-y 0-1]` | Add zoom |
| `zoom remove <id>` | Remove zoom region |

Zoom depths: 1=1.25x, 2=1.5x, 3=1.8x, 4=2.2x, 5=3.5x, 6=5.0x

### speed

Manage speed regions — speed up idle time, slow down important moments.

| Command | Description |
|---------|-------------|
| `speed list` | List all speed regions |
| `speed add --start MS --end MS [--speed 0.25-2.0]` | Add speed change |
| `speed remove <id>` | Remove speed region |

Valid speeds: 0.25, 0.5, 0.75, 1.25, 1.5, 1.75, 2.0

### trim

Manage trim regions — cut out sections of the recording.

| Command | Description |
|---------|-------------|
| `trim list` | List all trim regions |
| `trim add --start MS --end MS` | Cut out a section |
| `trim remove <id>` | Remove trim region |

### crop

Set the visible area of the recording.

| Command | Description |
|---------|-------------|
| `crop get` | Show current crop region |
| `crop set --x 0-1 --y 0-1 --width 0-1 --height 0-1` | Set crop (normalized) |

### annotation

Add text overlays to the recording.

| Command | Description |
|---------|-------------|
| `annotation list` | List all annotations |
| `annotation add-text --start MS --end MS --text "..." [--x 0-1] [--y 0-1]` | Add text |
| `annotation remove <id>` | Remove annotation |

### media

Inspect and validate media files.

| Command | Description |
|---------|-------------|
| `media probe <path>` | Show video metadata (resolution, duration, codec) |
| `media check <path>` | Validate a video file |
| `media thumbnail <input> <output> [-t TIME]` | Extract a frame |

### export

Render the final polished video.

| Command | Description |
|---------|-------------|
| `export presets` | List available export presets |
| `export render <output_path>` | Render project to video file |

### preview

Capture truthful review bundles from the current Openscreen project.

| Command | Description |
|---------|-------------|
| `preview recipes` | List available preview recipes |
| `preview capture --recipe quick` | Render a low-res preview bundle |
| `preview latest [--recipe quick]` | Return the latest existing bundle |

Current preview support is static rather than live. A `quick` bundle typically
contains:

- a low-res preview clip
- sampled frames
- a `hero` frame for quick inspection
- `summary.json` with trim/zoom/speed facts

Bundle capture also writes or updates a stable recipe-level `trajectory.json`
beside the preview root so agents can reconstruct preview history over time.

Viewer commands:

```bash
cli-hub previews inspect /path/to/bundle
cli-hub previews html /path/to/bundle -o page.html
cli-hub previews open /path/to/bundle
```

### session

Manage session state with undo/redo.

| Command | Description |
|---------|-------------|
| `session status` | Show session info |
| `session undo` | Undo last operation |
| `session redo` | Redo last undone operation |
| `session save` | Save session state to disk |
| `session list` | List all saved sessions |

## State Management

- **Undo/Redo**: Up to 50 levels of undo history
- **Project persistence**: JSON `.openscreen` files
- **Session tracking**: auto-tracks modifications

## Output Formats

- Human-readable (default): Formatted key-value pairs
- Machine-readable (`--json`): Structured JSON output

## Editor Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `aspectRatio` | string | "16:9" | 16:9, 9:16, 1:1, 4:3, 4:5 |
| `wallpaper` | string | "gradient_dark" | Background preset |
| `padding` | int | 50 | 0-100, padding around video |
| `borderRadius` | int | 12 | Corner radius in pixels |
| `shadowIntensity` | float | 0 | 0-1, drop shadow strength |
| `motionBlurAmount` | float | 0 | 0-1, motion blur during zoom |
| `exportQuality` | string | "good" | medium, good, source |
| `exportFormat` | string | "mp4" | mp4, gif |

## For AI Agents

1. Always use `--json` for parseable output
2. Check return codes — 0 = success, non-zero = error
3. Parse stderr for error messages in non-JSON mode
4. Use absolute file paths
5. After `export render`, verify the output exists and probe it
6. Times are in **milliseconds** for all region commands
7. Coordinates (focus, crop, position) are **normalized 0-1**
8. Use `preview capture --json` to validate zoom, trim, annotation, and timing visually
9. Read returned bundle artifact paths from the JSON payload; images and clips live on disk
10. Use `cli-hub previews ...` only to inspect/open existing bundles

## Version

1.0.0
