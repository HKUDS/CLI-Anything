# AnyGen CLI

A stateful command-line interface for AnyGen OpenAPI — generate professional
slides, documents, websites, diagrams, and more from natural language prompts.
Designed for AI agents and power users.

## Prerequisites

- Python 3.10+
- `requests` (HTTP client)
- `click` (CLI framework)
- AnyGen API key (`sk-xxx`)

Optional (for interactive REPL):
- `prompt_toolkit`

## Install Dependencies

```bash
pip install requests click prompt_toolkit
```

## Get an API Key

1. Go to [anygen.io/home](https://www.anygen.io/home) → Setting → Integration
2. Create an API key (format: `sk-xxx`)
3. Configure it:

```bash
# Option 1: Config file (recommended)
cli-anything-anygen config set api_key "sk-xxx"

# Option 2: Environment variable
export ANYGEN_API_KEY="sk-xxx"
```

## How to Run

All commands are run from the `agent-harness/` directory or via the installed command.

### One-shot Commands

```bash
# Show help
cli-anything-anygen --help

# Full workflow: create → poll → download
cli-anything-anygen task run --operation slide --prompt "AI trends presentation" --output ./

# Create a task (returns task ID)
cli-anything-anygen task create --operation doc --prompt "Technical design document"

# Check task status
cli-anything-anygen task status task_xxx

# Poll until completion (with auto-download)
cli-anything-anygen task poll task_xxx --output ./

# Download result file
cli-anything-anygen task download task_xxx --output ./

# JSON output for agent consumption
cli-anything-anygen --json task status task_xxx
```

### Interactive REPL

```bash
cli-anything-anygen
```

Inside the REPL, type `help` for all available commands.

## Command Reference

### Task

```bash
task create --operation <type> --prompt <text> [options]
task run --operation <type> --prompt <text> [--output dir] [options]
task status <task-id>
task poll <task-id> [--output dir]
task download <task-id> --output <dir>
task thumbnail <task-id> --output <dir>
task list [--limit N] [--status completed]
task prepare --message <text> [--file-token tk_xxx] [--save conv.json]
```

Operations: `slide`, `doc`, `smart_draw`, `chat`, `storybook`, `data_analysis`, `website`

Create / run options:
- `--language` / `-l` — zh-CN or en-US
- `--slide-count` / `-c` — Number of slides (slide only)
- `--template` / `-t` — Slide template (slide only)
- `--ratio` / `-r` — 16:9 or 4:3 (slide only)
- `--export-format` / `-f` — pptx/image/thumbnail/docx/drawio/excalidraw
- `--file-token` — File token from upload (repeatable)
- `--style` / `-s` — Style preference

### File

```bash
file upload <path>
```

### Config

```bash
config set api_key "sk-xxx"
config set default_language "en-US"
config get [key]
config delete <key>
config path
```

### Session

```bash
session status
session history [--limit N]
session undo
session redo
```

## JSON Mode

Add `--json` before the subcommand for machine-readable output:

```bash
cli-anything-anygen --json task status task_xxx
cli-anything-anygen --json task list --limit 5
```

## Running Tests

```bash
cd agent-harness

# Unit tests (mock HTTP, no API key needed)
python3 -m pytest cli_anything/anygen/tests/test_core.py -v

# E2E tests (requires ANYGEN_API_KEY)
ANYGEN_API_KEY=sk-xxx python3 -m pytest cli_anything/anygen/tests/test_full_e2e.py -v

# All tests
python3 -m pytest cli_anything/anygen/tests/ -v
```

## Example Workflow

```bash
# Configure API key
cli-anything-anygen config set api_key "sk-xxx"

# Upload a reference file
cli-anything-anygen file upload ./quarterly_data.pdf
# Output: ✓ Uploaded: quarterly_data.pdf → token: tk_abc123

# Requirement analysis (multi-turn)
cli-anything-anygen task prepare --message "I need a quarterly review slide deck" --save conv.json
# AnyGen asks clarifying questions...

cli-anything-anygen task prepare --message "Focus on revenue growth, 10 slides" --input conv.json --save conv.json
# Status: ready, suggested operation: slide

# Create and download in one step
cli-anything-anygen task run \
  --operation slide \
  --prompt "Quarterly business review..." \
  --file-token tk_abc123 \
  --slide-count 10 \
  --style "business formal" \
  --output ./output/

# Or step-by-step
cli-anything-anygen task create --operation slide --prompt "..."
# Task ID: task_xxx

cli-anything-anygen task poll task_xxx --output ./output/
# ✓ Downloaded: ./output/presentation.pptx (2,048,576 bytes)

# Verify the file
cli-anything-anygen --json task status task_xxx
```

## Supported Operations

| Operation | Type | Output | Downloadable |
|-----------|------|--------|-------------|
| Slides | `slide` | PPTX | Yes |
| Documents | `doc` | DOCX | Yes |
| Diagrams | `smart_draw` | drawio/excalidraw | Yes |
| General | `chat` | — | No (URL) |
| Storybooks | `storybook` | — | No (URL) |
| Data Analysis | `data_analysis` | — | No (URL) |
| Websites | `website` | — | No (URL) |
