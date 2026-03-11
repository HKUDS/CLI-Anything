# Audacity CLI

A stateful command-line interface for audio editing, following the same patterns
as the GIMP and Blender CLIs in this repo.

## Architecture

- **JSON project format** tracks state (tracks, clips, effects, labels, selection)
- **Python stdlib** (`wave`, `struct`, `math`) handles WAV I/O and audio processing
- **Click** provides the CLI framework with subcommand groups and REPL
- Effects are recorded in the project JSON and applied during export/render

## Install

```bash
pip install click numpy   # numpy only needed for tests
```

No other dependencies required. Core functionality uses only Python stdlib.

## Run

```bash
# From the agent-harness/ directory:
cd /root/cli-anything/audacity/agent-harness

# One-shot commands
cli-anything-audacity project new --name "My Podcast"
cli-anything-audacity track add --name "Voice"
cli-anything-audacity clip add 0 /path/to/recording.wav
cli-anything-audacity effect add normalize --track 0
cli-anything-audacity export render output.wav

# JSON output mode (for agent consumption)
cli-anything-audacity --json project info

# Interactive REPL
cli-anything-audacity repl
```

## Run Tests

```bash
cd /root/cli-anything/audacity/agent-harness

# All tests
python3 -m pytest cli/tests/ -v

# Unit tests only (no real audio files)
python3 -m pytest cli/tests/test_core.py -v

# E2E tests (generates real WAV files)
python3 -m pytest cli/tests/test_full_e2e.py -v
```

## Command Groups

| Group | Commands |
|-------|----------|
| `project` | `new`, `open`, `save`, `info`, `settings`, `json` |
| `track` | `add`, `remove`, `list`, `set` |
| `clip` | `import`, `add`, `remove`, `trim`, `split`, `move`, `list` |
| `effect` | `list-available`, `info`, `add`, `remove`, `set`, `list` |
| `selection` | `set`, `all`, `none`, `info` |
| `label` | `add`, `remove`, `list` |
| `media` | `probe`, `check` |
| `export` | `presets`, `preset-info`, `render` |
| `session` | `status`, `undo`, `redo`, `history` |

## Example Workflow

```bash
# Create a podcast project
cli-anything-audacity project new --name "Episode 1" -o project.json

# Add tracks
cli-anything-audacity --project project.json track add --name "Host"
cli-anything-audacity --project project.json track add --name "Guest"
cli-anything-audacity --project project.json track add --name "Music"

# Import audio clips
cli-anything-audacity --project project.json clip add 0 host_recording.wav
cli-anything-audacity --project project.json clip add 1 guest_recording.wav --start 0.5
cli-anything-audacity --project project.json clip add 2 music.wav --volume 0.3

# Apply effects
cli-anything-audacity --project project.json effect add normalize --track 0 -p target_db=-3.0
cli-anything-audacity --project project.json effect add compress --track 0 -p threshold=-20 -p ratio=4.0
cli-anything-audacity --project project.json effect add fade_in --track 2 -p duration=2.0

# Add labels
cli-anything-audacity --project project.json label add 0.0 --text "Intro"
cli-anything-audacity --project project.json label add 30.0 -e 60.0 --text "Main discussion"

# Export
cli-anything-audacity --project project.json export render episode1.wav --preset wav
```
