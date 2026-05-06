---
name: "cli-anything-calibre"
description: "面向 Agent 的 calibre 命令行：管理书库、编辑元数据、导出与格式转换（基于 calibredb / ebook-meta / ebook-convert）。"
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
```

### JSON mode (for agents)

Use `--json` to get machine-readable output for all commands.

```bash
cli-anything-calibre --json --library "D:/Books/Calibre Library" library info
cli-anything-calibre --json --library "D:/Books/Calibre Library" book list --search "title:Python" --limit 5
```

## Command Groups

### Library

Library management commands.

Common subcommands:
- `library open <path>`
- `library info`
- `library list-fields`
- `library stats`

### Book

Book management commands.

Common subcommands:
- `book add <file> [--title ...] [--authors ...] [--tags ...] [--series ...] [--duplicate]`
- `book list [--search ...] [--limit ...] [--sort-by ...] [--ascending]`
- `book get <book_id>`
- `book search <query> [--limit ...]`
- `book set-field <book_id> [--title ...] [--authors ...] [--tags ...]`
- `book remove <book_id> [--permanent]`

### Meta

Standalone ebook metadata commands.

Common subcommands:
- `meta show <ebook_path>`
- `meta set <ebook_path> [--title ...] [--authors ...] [--tags ...] [--comments ...] [--language ...] [--publisher ...] [--cover ...]`
- `meta set-cover <ebook_path> <cover_path>`
- `meta clear <ebook_path> [--comments] [--tags]`

### Convert

Format conversion commands.

Common subcommands:
- `convert formats`
- `convert presets`
- `convert run <input_path> <output_path> [--preset kindle|tablet|generic-epub] [--extra-arg ...]`

### Export

Export and backup commands.

Common subcommands:
- `export book <book_id...> --to-dir <dir> [--single-dir] [--formats ...]`
- `export catalog <output_path> [--search ...]`
- `export backup [--all]`

### Session

Session management commands.

Common subcommands:
- `session status`
- `session undo`
- `session redo`
- `session history`
- `session save`

## Examples

### Open a library and inspect

```bash
cli-anything-calibre library open "D:/Books/Calibre Library"
cli-anything-calibre --json library stats
cli-anything-calibre --json book list --limit 5
```

### Interactive REPL Session

Start an interactive session with undo/redo support.

```bash
cli-anything-calibre
# Enter commands interactively
# Use 'help' to see available commands
# Use 'undo' and 'redo' for history navigation
```

### Ingest → search → export → convert (workflow)

```bash
# Add a book file into the library
cli-anything-calibre --json --library "D:/Books/Calibre Library" book add "D:/tmp/book.epub" --title "My Book" --authors "Me"

# Search and pick a book id
cli-anything-calibre --json --library "D:/Books/Calibre Library" book search "title:My Book" --limit 5

# Export the book files
cli-anything-calibre --json --library "D:/Books/Calibre Library" export book 1 --to-dir "D:/tmp/exported" --single-dir

# Convert EPUB to MOBI
cli-anything-calibre --json convert run "D:/tmp/exported/My Book.epub" "D:/tmp/converted/My Book.mobi" --preset kindle
```

## For AI Agents

When using this CLI programmatically:

1. **Always use `--json` flag** for parseable output
2. **Check return codes** - 0 for success, non-zero for errors
3. **Parse stderr** for error messages on failure
4. **Use absolute paths** for all file operations (recommended on Windows)
5. **Verify outputs exist** after export operations

## Version

1.0.0