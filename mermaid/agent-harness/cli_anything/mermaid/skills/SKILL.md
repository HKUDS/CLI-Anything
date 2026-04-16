---
name: >-
  cli-anything-mermaid
description: >-
  Command-line interface for Mermaid Live Editor - Create, edit, and render Mermaid diagrams via stateful project files and mermaid.ink renderer URLs. Designed for AI agents and power users who need to generate flowcharts, sequence diagrams, and other visualizations without a GUI.
---

# cli-anything-mermaid

Create, edit, and render Mermaid diagrams via stateful project files and the mermaid.ink renderer. Designed for AI agents and power users who need to generate flowcharts, sequence diagrams, and other visualizations without a GUI.

## Installation

This CLI is installed as part of the cli-anything-mermaid package:

```bash
pip install cli-anything-mermaid
```

**Prerequisites:**
- Python 3.10+
- No external software required (rendering uses mermaid.ink cloud service)

## Usage

### Basic Commands

```bash
# Show help
cli-anything-mermaid --help

# Start interactive REPL mode
cli-anything-mermaid

# Create a new project
cli-anything-mermaid project new -o diagram.json

# Run with JSON output (for agent consumption)
cli-anything-mermaid --json project info
```

### REPL Mode

When invoked without a subcommand, the CLI enters an interactive REPL session:

```bash
cli-anything-mermaid
# Enter commands interactively with tab-completion and history
```

## Command Groups

### Project

Project lifecycle commands.

| Command | Description |
|---------|-------------|
| `new` | Create a new Mermaid project with optional sample preset and theme |
| `open` | Open an existing Mermaid project file |
| `save` | Save the current project to a file |
| `info` | Show current project information |
| `samples` | List available sample diagram presets |

### Diagram

Diagram source manipulation commands.

| Command | Description |
|---------|-------------|
| `set` | Replace the Mermaid source text (inline or from file) |
| `show` | Print the current Mermaid source code |

### Export

Render and share commands.

| Command | Description |
|---------|-------------|
| `render` | Render the diagram to SVG or PNG via mermaid.ink |
| `share` | Generate a Mermaid Live Editor URL for sharing |

### Session

Session state commands.

| Command | Description |
|---------|-------------|
| `status` | Show current session state |
| `undo` | Undo the last diagram source change |
| `redo` | Redo the last undone change |

## Examples

### Create and Render a Flowchart

```bash
# Create a project with flowchart sample
cli-anything-mermaid project new --sample flowchart -o flow.json

# Replace diagram source
cli-anything-mermaid --project flow.json diagram set --text "graph TD; A-->B; B-->C;"

# Render to SVG
cli-anything-mermaid --project flow.json export render output.svg --format svg
```

### Create a Sequence Diagram

```bash
# Create project with sequence sample
cli-anything-mermaid project new --sample sequence -o seq.json

# Set diagram from file
cli-anything-mermaid --project seq.json diagram set --file my_diagram.mmd

# Render to PNG
cli-anything-mermaid --project seq.json export render output.png --format png
```

### Share a Diagram

```bash
# Generate an editable Mermaid Live URL
cli-anything-mermaid --project flow.json export share --mode edit

# Generate a view-only URL
cli-anything-mermaid --project flow.json export share --mode view
```

### Interactive REPL Session

```bash
cli-anything-mermaid
# new flowchart
# set graph TD; A-->B; B-->C;
# render output.svg
# share
# quit
```

## State Management

The CLI maintains session state with:

- **Undo/Redo**: Revert or replay diagram source changes
- **Project persistence**: Save/load project state as JSON
- **Session tracking**: Track modifications and changes

## Output Formats

All commands support dual output modes:

- **Human-readable** (default): Tables, colors, formatted text
- **Machine-readable** (`--json` flag): Structured JSON for agent consumption

```bash
# Human output
cli-anything-mermaid project info

# JSON output for agents
cli-anything-mermaid --json project info
```

## For AI Agents

When using this CLI programmatically:

1. **Always use `--json` flag** for parseable output
2. **Check return codes** - 0 for success, non-zero for errors
3. **Parse stderr** for error messages on failure
4. **Use absolute paths** for all file operations
5. **Verify outputs exist** after render operations

## More Information

- Full documentation: See README.md in the package
- Test coverage: See TEST.md in the package
- Methodology: See HARNESS.md in the cli-anything-plugin

## Version

1.0.0
