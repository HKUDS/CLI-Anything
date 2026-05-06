# cli-anything-calibre

A stateful command-line interface for calibre library management, metadata
editing, export, and format conversion.

This harness wraps real calibre tools (`calibredb`, `ebook-meta`,
`ebook-convert`) and adds:
- a unified Click CLI
- REPL mode by default
- machine-readable JSON output via `--json`
- lightweight session state with undo/redo history

## Requirements

- Python 3.10+
- calibre installed and available on PATH

Typical backend binaries used by this harness:
- `calibredb`
- `ebook-meta`
- `ebook-convert`

## Installation

```bash
# From calibre/agent-harness
pip install -e .
```

## Quick Start

```bash
# Show help
cli-anything-calibre --help

# Enter REPL mode
cli-anything-calibre

# Open a library and inspect
cli-anything-calibre --json --library "D:/Books/Calibre Library" library stats
cli-anything-calibre --json --library "D:/Books/Calibre Library" book list --limit 5

# Add, search, export, and convert
cli-anything-calibre --json --library "D:/Books/Calibre Library" book add "D:/tmp/book.epub" --title "My Book" --authors "Me"
cli-anything-calibre --json --library "D:/Books/Calibre Library" book search "title:My Book" --limit 5
cli-anything-calibre --json --library "D:/Books/Calibre Library" export book 1 --to-dir "D:/tmp/exported" --single-dir
cli-anything-calibre --json convert run "D:/tmp/exported/My Book.epub" "D:/tmp/converted/My Book.mobi" --preset kindle
```

## JSON Output Mode

All commands support `--json` for machine-readable output:

```bash
cli-anything-calibre --json --library "D:/Books/Calibre Library" library info
cli-anything-calibre --json --library "D:/Books/Calibre Library" book get 1
```

## Interactive REPL

```bash
# Starts REPL when no subcommand is provided
cli-anything-calibre
```

Inside REPL you can run grouped commands and use session operations (`undo`,
`redo`, `history`) through the `session` group.

## Command Groups

### Library
```
library open <path>      - Open a calibre library
library info             - Show current library metadata
library list-fields      - List supported library fields
library stats            - Show book/author/format statistics
```

### Book
```
book add <file>          - Add an ebook to library
book list                - List books
book get <book_id>       - Show one book metadata
book search <query>      - Search books by calibre query syntax
book set-field <book_id> - Update selected fields (title/authors/tags...)
book remove <book_id>    - Remove a book
```

### Meta
```
meta show <ebook_path>                   - Show file metadata
meta set <ebook_path> [--title --authors] - Update file metadata
meta set-cover <ebook_path> <cover_path> - Set cover image
meta clear <ebook_path>                  - Clear selected metadata fields
```

### Convert
```
convert formats                          - List common output formats
convert presets                          - List preset argument bundles
convert run <input> <output>             - Convert ebook format
```

### Export
```
export book <book_id...> --to-dir <dir>  - Export book files
export catalog <output_path>             - Build catalog output
export backup                            - Backup OPF metadata
```

### Session
```
session status                           - Show session context
session undo                             - Undo last state change
session redo                             - Redo last undone change
session history                          - Show recorded snapshots
session save                             - Persist session to JSON
```

## Running Tests

```bash
# From calibre/agent-harness

# Unit tests
python -m pytest cli_anything/calibre/tests/test_core.py -v

# E2E tests (requires calibre installed)
python -m pytest cli_anything/calibre/tests/test_full_e2e.py -v -s

# Full suite
python -m pytest cli_anything/calibre/tests/ -v
```

## Architecture

```
cli_anything/calibre/
├── __main__.py
├── calibre_cli.py                 # Click CLI entry point + REPL
├── core/
│   ├── library.py                 # Library open/info/stats/fields
│   ├── books.py                   # Book add/list/get/search/remove/set-field
│   ├── metadata.py                # ebook-meta wrappers
│   ├── convert.py                 # Conversion presets + run
│   ├── export.py                  # Export/catalog/backup
│   └── session.py                 # Stateful context + undo/redo
├── utils/
│   ├── calibre_backend.py         # subprocess wrappers + parsing
│   └── repl_skin.py               # Interactive REPL UX
├── skills/
│   └── SKILL.md                   # Agent-discoverable usage guide
└── tests/
    ├── test_core.py
    ├── test_full_e2e.py
    └── TEST.md                    # Test plan + results + agent test notes
```

## Agent Test Prompt

For reproducible CLI-only agent validation (OpenCode/Cursor/Claude Code), use:

- [`../../AGENT_TEST_PROMPT.md`](../../AGENT_TEST_PROMPT.md)

This prompt file is an example template for reproducible agent testing and can
be adapted to your environment.
