# Calibre CLI Harness — SOP

## Overview

Calibre is the world's most popular e-book management application. This CLI harness wraps the real Calibre tools (`calibredb`, `ebook-convert`, `ebook-meta`) to give AI agents and scripts a clean, structured interface for library management, metadata editing, and format conversion.

## Backend Architecture

### Real Software Used

All heavy lifting is done by the **actual Calibre binaries**:

| Task | Tool | Command Pattern |
|------|------|----------------|
| Library operations | `calibredb` | `calibredb <cmd> --library-path <lib>` |
| Format conversion | `ebook-convert` | `ebook-convert input.epub output.mobi` |
| File metadata | `ebook-meta` | `ebook-meta book.epub --field value` |

The CLI harness is a **stateful wrapper** — it tracks the library path in a session file and passes it to every `calibredb` invocation. It never reimplements library logic.

### Data Model

```
~/Calibre Library/
├── metadata.db              # SQLite database (all metadata)
├── Author Name (ID)/
│   ├── Book Title (ID)/
│   │   ├── cover.jpg        # Cover image
│   │   ├── metadata.opf     # OPF metadata file
│   │   ├── Title - Author.epub
│   │   └── Title - Author.mobi
```

### Session State

The CLI maintains a JSON session file at `~/.cli-anything-calibre/session.json`:
```json
{
  "library_path": "/path/to/Calibre Library",
  "last_command": "list",
  "filters": {}
}
```

## Command Groups

### `library` - Library management
- `connect <path>` — Set active library path
- `info` — Show library stats (book count, formats, size)
- `check` — Verify library integrity

### `books` — Book operations (wrap `calibredb`)
- `list` — List books with filtering and sorting
- `search <query>` — Search using Calibre query language
- `add <files>` — Add book files to library
- `remove <ids>` — Remove books (move to trash)
- `show <id>` — Show full metadata for a book
- `export <ids>` — Export books to directory

### `meta` — Metadata editing (wrap `calibredb set_metadata`)
- `set <id> <field> <value>` — Set a metadata field
- `get <id> [field]` — Get metadata (all or specific field)
- `embed <ids>` — Embed metadata into book files

### `formats` — Format management (wrap `calibredb` + `ebook-convert`)
- `list <id>` — List available formats for a book
- `add <id> <file>` — Add a format to a book
- `remove <id> <fmt>` — Remove a format from a book
- `convert <id> <input_fmt> <output_fmt>` — Convert book format

### `custom` — Custom columns (wrap `calibredb`)
- `list` — List all custom columns
- `add <label> <name> <type>` — Create custom column
- `remove <label>` — Delete custom column
- `set <id> <label> <value>` — Set custom field value

### `catalog` — Catalog generation
- `generate <output>` — Generate a catalog of the library

## Calibre Query Language

Used with `books search` and `books list --search`:

```
author:asimov                    # Author contains "asimov"
title:"Foundation"               # Title phrase
tags:fiction                     # Tag match
rating:>3                        # Rating greater than 3
series:"Foundation"              # Series match
pubdate:[2020-01-01,2021-12-31]  # Date range
identifiers:isbn:1234567890      # Specific identifier
has:cover                        # Has cover image
not:tags:fiction                 # Negation
author:asimov and tags:scifi     # Boolean AND
```

## Key Metadata Fields

| Field | Type | Description |
|-------|------|-------------|
| `title` | text | Book title |
| `authors` | text | Author names (&-separated) |
| `tags` | text | Comma-separated tags |
| `series` | text | Series name |
| `series_index` | float | Position in series |
| `rating` | float | Rating 1-5 |
| `publisher` | text | Publisher name |
| `pubdate` | datetime | Publication date |
| `comments` | text | Description/comments |
| `cover` | path | Path to cover image |
| `languages` | text | Language codes |
| `identifiers` | text | ISBN, ASIN, etc. (`type:value`) |

## Supported Formats

**Input:** EPUB, MOBI, AZW, AZW3, PDF, HTML, DOCX, ODT, FB2, TXT, RTF, LIT, and more

**Output (conversion):** EPUB, MOBI, AZW3, PDF, HTML, DOCX, TXT, and more

## Installation Requirements

```bash
# Calibre must be installed (hard dependency)
sudo apt-get install calibre          # Debian/Ubuntu
brew install --cask calibre           # macOS
# Or download from: https://calibre-ebook.com/download

# Verify tools are in PATH:
which calibredb
which ebook-convert
which ebook-meta
```

## Testing Philosophy

- Unit tests: synthetic CLI argument parsing, query building, JSON output
- E2E tests with `calibredb`: real library operations, real output verification
- E2E tests with `ebook-convert`: real format conversion, output file validation
- Subprocess tests via `_resolve_cli("cli-anything-calibre")`

## Example Workflows

### Import a library of epubs and tag them:
```bash
cli-anything-calibre library connect ~/my-books
cli-anything-calibre books add *.epub
cli-anything-calibre books search "not:tags:read" --json
```

### Convert EPUB to MOBI for Kindle:
```bash
cli-anything-calibre formats convert 42 EPUB MOBI
```

### Batch metadata update:
```bash
cli-anything-calibre meta set 42 series "Foundation"
cli-anything-calibre meta set 42 series_index 1
cli-anything-calibre meta set 42 tags "scifi,classic"
```
