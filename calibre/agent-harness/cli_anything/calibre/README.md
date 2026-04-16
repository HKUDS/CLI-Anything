# cli-anything-calibre

Stateful CLI harness for calibre.

This package wraps the real calibre command-line tools (`calibredb`, `ebook-convert`, and `ebook-meta`) and adds:
- a unified Click-based CLI
- REPL mode by default
- machine-readable JSON output via `--json`
- lightweight session state with undo/redo history

## Requirements

- Python 3.10+
- calibre installed and on PATH

Typical binaries used by this harness:
- `calibredb`
- `ebook-convert`
- `ebook-meta`

## Install

```bash
pip install -e .
```

## Usage

```bash
cli-anything-calibre --help
cli-anything-calibre
cli-anything-calibre --json library info --library /path/to/library
cli-anything-calibre book list --search "title:Example"
```

## Command groups

- `library` — library inspection and context
- `book` — add/remove/list/get/search/set-field
- `meta` — inspect and edit standalone ebook file metadata
- `convert` — file conversion using `ebook-convert`
- `export` — export books, build catalog, backup metadata
- `session` — session state / undo / redo / history

## REPL

Running `cli-anything-calibre` with no subcommand enters REPL mode.

## JSON mode

Use `--json` for machine-readable output.
