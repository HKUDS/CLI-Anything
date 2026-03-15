---
name: >-
  cli-anything-libreoffice
description: >-
  Command-line interface for Libreoffice - A stateful command-line interface for document editing, producing real ODF files (ZIP archives with ...
---

# cli-anything-libreoffice

A stateful command-line interface for document editing, producing real ODF files (ZIP archives with XML). Designed for AI agents and power users who need to create and manipulate Writer, Calc, and Impress documents without a GUI or LibreOffice installation.

## Installation

This CLI is installed as part of the cli-anything-libreoffice package:

```bash
pip install cli-anything-libreoffice
```

**Prerequisites:**
- Python 3.10+
- libreoffice must be installed on your system


## Usage

### Basic Commands

```bash
# Show help
cli-anything-libreoffice --help

# Start interactive REPL mode
cli-anything-libreoffice

# Create a new project
cli-anything-libreoffice project new -o project.json

# Run with JSON output (for agent consumption)
cli-anything-libreoffice --json project info -p project.json
```

### REPL Mode

When invoked without a subcommand, the CLI enters an interactive REPL session:

```bash
cli-anything-libreoffice
# Enter commands interactively with tab-completion and history
```


## Command Groups


### Document

Document management commands.

| Command | Description |
|---------|-------------|



### Writer

Writer (word processor) commands.

| Command | Description |
|---------|-------------|



### Calc

Calc (spreadsheet) commands.

| Command | Description |
|---------|-------------|



### Impress

Impress (presentation) commands.

| Command | Description |
|---------|-------------|



### Style Group

Style management commands.

| Command | Description |
|---------|-------------|



### Export Group

Export/render commands.

| Command | Description |
|---------|-------------|



### Session

Session management commands.

| Command | Description |
|---------|-------------|




## Examples


### Create a New Project

Create a new libreoffice project file.

```bash
cli-anything-libreoffice project new -o myproject.json
# Or with JSON output for programmatic use
cli-anything-libreoffice --json project new -o myproject.json
```


### Interactive REPL Session

Start an interactive session with undo/redo support.

```bash
cli-anything-libreoffice
# Enter commands interactively
# Use 'help' to see available commands
# Use 'undo' and 'redo' for history navigation
```


### Export Project

Export the project to a final output format.

```bash
cli-anything-libreoffice --project myproject.json export render output.pdf --overwrite
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
cli-anything-libreoffice project info -p project.json

# JSON output for agents
cli-anything-libreoffice --json project info -p project.json
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