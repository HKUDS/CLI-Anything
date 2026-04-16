---
name: "cli-anything-calibre"
description: "Command-line interface for Calibre - Stateful CLI harness for calibre...."
---

# cli-anything-calibre

Stateful CLI harness for calibre.

## Installation

This CLI is installed as part of the cli-anything-calibre package:

```bash
pip install cli-anything-calibre
```

**Prerequisites:**
- Python 3.10+
- Calibre must be installed on your system

## Usage

### Basic Commands

```bash
# Show help
cli-anything-calibre --help

# Start interactive REPL mode
cli-anything-calibre

# Create a new project
cli-anything-calibre project new -o project.json

# Run with JSON output (for agent consumption)
cli-anything-calibre --json project info -p project.json
```

## Command Groups

### Library

Library management commands.

### Book

Book management commands.

### Meta

Standalone ebook metadata commands.

### Convert

Format conversion commands.

### Export

Export and backup commands.

### Session

Session management commands.

## Examples

### Create a New Project

Create a new calibre project file.

```bash
cli-anything-calibre project new -o myproject.json
# Or with JSON output for programmatic use
cli-anything-calibre --json project new -o myproject.json
```

### Interactive REPL Session

Start an interactive session with undo/redo support.

```bash
cli-anything-calibre
# Enter commands interactively
# Use 'help' to see available commands
# Use 'undo' and 'redo' for history navigation
```

### Export Project

Export the project to a final output format.

```bash
cli-anything-calibre --project myproject.json export render output.pdf --overwrite
```

## For AI Agents

When using this CLI programmatically:

1. **Always use `--json` flag** for parseable output
2. **Check return codes** - 0 for success, non-zero for errors
3. **Parse stderr** for error messages on failure
4. **Use absolute paths** for all file operations
5. **Verify outputs exist** after export operations

## Version

1.0.0