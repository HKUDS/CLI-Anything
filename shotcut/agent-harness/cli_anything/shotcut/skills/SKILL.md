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
- shotcut must be installed on your system


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

When invoked without a subcommand, the CLI enters an interactive REPL session:

```bash
cli-anything-shotcut
# Enter commands interactively with tab-completion and history
```


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
| `add-clip` | Add a media clip to a track |
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


### Media

Media operations: probe, list, check files.

| Command | Description |
|---------|-------------|
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
cli-anything-shotcut --project myproject.json export render output.pdf --overwrite
```


## State Management

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

## More Information

- Full documentation: See README.md in the package
- Test coverage: See TEST.md in the package
- Methodology: See HARNESS.md in the cli-anything-plugin

## Version

1.0.0