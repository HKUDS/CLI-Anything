---
name: "cli-anything-audacity"
description: >-
  Command-line interface for Audacity - A stateful command-line interface for audio editing, following the same patterns as the GIMP and Ble...
---

# cli-anything-audacity

A stateful command-line interface for audio editing, following the same patterns as the GIMP and Blender CLIs in this repo.

## Installation

This CLI is installed as part of the cli-anything-audacity package:

```bash
pip install cli-anything-audacity
```

**Prerequisites:**
- Python 3.10+
- audacity must be installed on your system


## Usage

### Basic Commands

```bash
# Show help
cli-anything-audacity --help

# Start interactive REPL mode
cli-anything-audacity

# Create a new project
cli-anything-audacity project new -o project.json

# Run with JSON output (for agent consumption)
cli-anything-audacity --json project info -p project.json
```

### REPL Mode

When invoked without a subcommand, the CLI enters an interactive REPL session:

```bash
cli-anything-audacity
# Enter commands interactively with tab-completion and history
```


## Command Groups


### Project

Project management commands.

| Command | Description |
|---------|-------------|
| `new` | Create a new project |
| `open` | Open an existing project |
| `save` | Save the current project |
| `info` | Show project information |
| `settings` | View or update project settings |
| `json` | Print raw project JSON |


### Track

Track management commands.

| Command | Description |
|---------|-------------|
| `add` | Add a new track |
| `remove` | Remove a track by index |
| `list` | List all tracks |
| `set` | Set a track property (name, mute, solo, volume, pan) |


### Clip

Clip management commands.

| Command | Description |
|---------|-------------|
| `import` | Probe/import an audio file (show metadata) |
| `add` | Add an audio clip to a track |
| `remove` | Remove a clip from a track |
| `trim` | Trim a clip's start and/or end |
| `split` | Split a clip at a given time position |
| `move` | Move a clip to a new start time |
| `list` | List clips on a track |


### Effect Group

Effect management commands.

| Command | Description |
|---------|-------------|
| `list-available` | List all available effects |
| `info` | Show details about an effect |
| `add` | Add an effect to a track |
| `remove` | Remove an effect by index |
| `set` | Set an effect parameter |
| `list` | List effects on a track |


### Selection

Selection management commands.

| Command | Description |
|---------|-------------|
| `set` | Set selection range |
| `all` | Select all (entire project duration) |
| `none` | Clear selection |
| `info` | Show current selection |


### Label

Label/marker management commands.

| Command | Description |
|---------|-------------|
| `add` | Add a label at a time position |
| `remove` | Remove a label by index |
| `list` | List all labels |


### Media

Media file operations.

| Command | Description |
|---------|-------------|
| `probe` | Analyze an audio file |
| `check` | Check that all referenced audio files exist |


### Export Group

Export/render commands.

| Command | Description |
|---------|-------------|
| `presets` | List export presets |
| `preset-info` | Show preset details |
| `render` | Render the project to an audio file |


### Session Group

Session management commands.

| Command | Description |
|---------|-------------|
| `status` | Show session status |
| `undo` | Undo the last operation |
| `redo` | Redo the last undone operation |
| `history` | Show undo history |




## Examples


### Create a New Project

Create a new audacity project file.

```bash
cli-anything-audacity project new -o myproject.json
# Or with JSON output for programmatic use
cli-anything-audacity --json project new -o myproject.json
```


### Interactive REPL Session

Start an interactive session with undo/redo support.

```bash
cli-anything-audacity
# Enter commands interactively
# Use 'help' to see available commands
# Use 'undo' and 'redo' for history navigation
```


### Export Project

Export the project to a final output format.

```bash
cli-anything-audacity --project myproject.json export render output.pdf --overwrite
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
cli-anything-audacity project info -p project.json

# JSON output for agents
cli-anything-audacity --json project info -p project.json
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