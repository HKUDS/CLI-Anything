---
name: "cli-anything-obs-studio"
description: >-
  Command-line interface for Obs Studio - A stateful command-line interface for OBS Studio scene collection editing, following the same patter...
---

# cli-anything-obs_studio

A stateful command-line interface for OBS Studio scene collection editing, following the same patterns as the Blender CLI harness. Uses a JSON scene collection format. No OBS installation required for editing.

## Installation

This CLI is installed as part of the cli-anything-obs_studio package:

```bash
pip install cli-anything-obs_studio
```

**Prerequisites:**
- Python 3.10+
- obs_studio must be installed on your system


## Usage

### Basic Commands

```bash
# Show help
cli-anything-obs_studio --help

# Start interactive REPL mode
cli-anything-obs_studio

# Create a new project
cli-anything-obs_studio project new -o project.json

# Run with JSON output (for agent consumption)
cli-anything-obs_studio --json project info -p project.json
```

### REPL Mode

When invoked without a subcommand, the CLI enters an interactive REPL session:

```bash
cli-anything-obs_studio
# Enter commands interactively with tab-completion and history
```


## Command Groups


### Project

Project management commands.

| Command | Description |
|---------|-------------|
| `new` | Create a new OBS scene collection |
| `open` | Open an existing project |
| `save` | Save the current project |
| `info` | Show project information |
| `json` | Print raw project JSON |


### Scene Group

Scene management commands.

| Command | Description |
|---------|-------------|
| `add` | Add a new scene |
| `remove` | Remove a scene by index |
| `duplicate` | Duplicate a scene |
| `set-active` | Set the active scene |
| `list` | List all scenes |


### Source Group

Source management commands.

| Command | Description |
|---------|-------------|
| `add` | Add a source to a scene |
| `remove` | Remove a source by index |
| `duplicate` | Duplicate a source |
| `set` | Set a source property (name, visible, locked, opacity, rotation) |
| `transform` | Transform a source (position, size, crop, rotation) |
| `list` | List all sources in a scene |


### Filter Group

Filter management commands.

| Command | Description |
|---------|-------------|
| `add` | Add a filter to a source |
| `remove` | Remove a filter from a source |
| `set` | Set a filter parameter |
| `list` | List all filters on a source |
| `list-available` | List all available filter types |


### Audio Group

Audio management commands.

| Command | Description |
|---------|-------------|
| `add` | Add a global audio source |
| `remove` | Remove a global audio source |
| `volume` | Set volume for an audio source (0.0-3.0) |
| `mute` | Mute an audio source |
| `unmute` | Unmute an audio source |
| `monitor` | Set audio monitoring type |
| `list` | List all audio sources |


### Transition Group

Transition management commands.

| Command | Description |
|---------|-------------|
| `add` | Add a transition |
| `remove` | Remove a transition |
| `set-active` | Set the active transition |
| `duration` | Set transition duration in milliseconds |
| `list` | List all transitions |


### Output Group

Output/streaming/recording configuration.

| Command | Description |
|---------|-------------|
| `streaming` | Configure streaming settings |
| `recording` | Configure recording settings |
| `settings` | Configure output settings |
| `info` | Show current output configuration |
| `presets` | List available encoding presets |


### Session

Session management commands.

| Command | Description |
|---------|-------------|
| `status` | Show session status |
| `undo` | Undo the last operation |
| `redo` | Redo the last undone operation |
| `history` | Show undo history |




## Examples


### Create a New Project

Create a new obs_studio project file.

```bash
cli-anything-obs_studio project new -o myproject.json
# Or with JSON output for programmatic use
cli-anything-obs_studio --json project new -o myproject.json
```


### Interactive REPL Session

Start an interactive session with undo/redo support.

```bash
cli-anything-obs_studio
# Enter commands interactively
# Use 'help' to see available commands
# Use 'undo' and 'redo' for history navigation
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
cli-anything-obs_studio project info -p project.json

# JSON output for agents
cli-anything-obs_studio --json project info -p project.json
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