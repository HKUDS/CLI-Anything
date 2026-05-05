# cli-anything-calibre

A CLI harness for [Calibre](https://calibre-ebook.com/), the powerful e-book management application. Part of the [cli-anything](https://github.com/HKUDS/CLI-Anything) toolkit.

## What It Does

`cli-anything-calibre` gives AI agents and scripts a clean, structured command-line interface to Calibre's library operations, metadata editing, and format conversion — without reimplementing any of Calibre's logic. It wraps the real tools:

- **`calibredb`** — library management, metadata, import/export
- **`ebook-convert`** — format conversion (EPUB → MOBI, PDF, TXT, etc.)
- **`ebook-meta`** — standalone file metadata editing

## Requirements

### 1. Install Calibre (hard dependency)

```bash
# Debian/Ubuntu
sudo apt-get install calibre

# Fedora/RHEL
sudo dnf install calibre

# macOS
brew install --cask calibre

# Windows / other
# Download from: https://calibre-ebook.com/download
```

Verify:
```bash
which calibredb        # must be in PATH
which ebook-convert    # must be in PATH
```

### 2. Install cli-anything-calibre

```bash
cd agent-harness
pip install -e .
```

Verify:
```bash
which cli-anything-calibre
cli-anything-calibre --version
```

## Quick Start

```bash
# Connect to your Calibre library
cli-anything-calibre library connect ~/Calibre\ Library

# List all books
cli-anything-calibre books list

# List as JSON (for agent consumption)
cli-anything-calibre --json books list

# Search books
cli-anything-calibre books search "author:asimov"

# Show metadata for book ID 42
cli-anything-calibre books show 42

# Set metadata
cli-anything-calibre meta set 42 series "Foundation"
cli-anything-calibre meta set 42 series_index 1

# Convert EPUB to MOBI
cli-anything-calibre formats convert 42 EPUB MOBI

# Export books to directory
cli-anything-calibre books export 42 --to-dir ~/kindle-transfer

# Enter interactive REPL (default when no subcommand given)
cli-anything-calibre
```

## Command Reference

### Library Management

```bash
cli-anything-calibre library connect <path>   # Set active library
cli-anything-calibre library info             # Library statistics
cli-anything-calibre library check            # Verify integrity
```

### Book Operations

```bash
cli-anything-calibre books list [--search QUERY] [--sort FIELD] [--limit N]
cli-anything-calibre books search "title:Foundation"
cli-anything-calibre books add book.epub [book2.epub ...]
cli-anything-calibre books remove 42,43,44
cli-anything-calibre books show 42
cli-anything-calibre books export 42 --to-dir /path/to/dir
```

### Metadata Editing

```bash
cli-anything-calibre meta get 42          # All metadata
cli-anything-calibre meta get 42 title    # Single field
cli-anything-calibre meta set 42 title "New Title"
cli-anything-calibre meta set 42 authors "Author One & Author Two"
cli-anything-calibre meta set 42 tags "scifi,classic,favorite"
cli-anything-calibre meta set 42 rating 5
cli-anything-calibre meta embed 42        # Embed into book file
```

### Format Management

```bash
cli-anything-calibre formats list 42
cli-anything-calibre formats add 42 /path/to/book.mobi
cli-anything-calibre formats remove 42 MOBI
cli-anything-calibre formats convert 42 EPUB MOBI
cli-anything-calibre formats convert 42 EPUB PDF --output /tmp/book.pdf
```

### Custom Columns

```bash
cli-anything-calibre custom list
cli-anything-calibre custom add "#genre" "Genre" text
cli-anything-calibre custom add "#read_date" "Date Read" datetime
cli-anything-calibre custom set 42 "#genre" "Science Fiction"
cli-anything-calibre custom remove "#genre"
```

### Catalog Generation

```bash
cli-anything-calibre catalog /output/catalog.epub --title "My Library"
cli-anything-calibre catalog /output/catalog.csv --format csv
```

## JSON Output Mode

All commands support `--json` for machine-readable output:

```bash
cli-anything-calibre --json books list
cli-anything-calibre --json books search "author:asimov"
cli-anything-calibre --json meta get 42
cli-anything-calibre --json library info
```

## Calibre Query Language

Used with `books list --search` and `books search`:

```
author:asimov                    # Author contains "asimov"
title:"Foundation"               # Title phrase
tags:fiction                     # Tag match
rating:>3                        # Rating greater than 3
series:"Foundation"              # Series exact match
pubdate:[2020-01-01,2021-12-31]  # Date range
identifiers:isbn:9780553293357   # ISBN lookup
has:cover                        # Books with covers
not:tags:read                    # Unread books
author:asimov and tags:scifi     # Boolean AND
```

## Session State

The active library path is persisted in `~/.cli-anything-calibre/session.json`.
Override with the `CALIBRE_LIBRARY` environment variable.

## Running Tests

```bash
cd agent-harness

# Unit tests (no Calibre required)
pytest cli_anything/calibre/tests/test_core.py -v

# Full E2E tests (Calibre required)
pytest cli_anything/calibre/tests/test_full_e2e.py -v -s

# All tests with installed binary
CLI_ANYTHING_FORCE_INSTALLED=1 pytest cli_anything/calibre/tests/ -v -s
```
