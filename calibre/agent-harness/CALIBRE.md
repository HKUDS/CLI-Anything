# CALIBRE.md

## Overview

calibre is a Python/PyQt6 desktop application for ebook library management, format conversion, metadata editing, and content serving. Unlike some GUI-first tools, calibre already exposes a rich set of headless CLI tools, which makes it a strong fit for a cli-anything harness.

## Backend engine

Primary backend components:
- Library database: `src/calibre/db/backend.py`
- Database cache layer: `src/calibre/db/cache.py`
- Legacy library API: `src/calibre/db/legacy.py`
- Search/query layer: `src/calibre/db/search.py`
- Metadata readers/writers: `src/calibre/ebooks/metadata/`
- Conversion pipeline: `src/calibre/ebooks/conversion/`

The GUI is primarily a PyQt6 frontend over these backend capabilities.

## Existing native CLI tools

From `src/calibre/linux.py`, calibre already ships these console tools:
- `calibredb`
- `ebook-convert`
- `ebook-meta`
- `ebook-polish`
- `calibre-server`
- `calibre-debug`
- `calibre-customize`
- `fetch-ebook-metadata`
- `calibre-smtp`
- `calibre-parallel`
- `calibre-complete`
- `web2disk`

For this harness, the most important are:
- `calibredb` for library inspection and mutation
- `ebook-convert` for format conversion
- `ebook-meta` for per-file metadata inspection/update

## Native data model

calibre libraries are directory-based and centered on `metadata.db` (SQLite). Book records map to directories containing one or more format files plus metadata. This means the harness does not need to emulate GUI state; it can operate against the library and file model directly.

## GUI toolkit

The GUI uses PyQt6 through calibre's lazy-loading `qt` shim.

Relevant paths:
- `src/qt/`
- `src/calibre/gui2/`
- `pyproject.toml`

## Command mapping strategy

### Library operations
Map to `calibredb` subcommands:
- list books → `calibredb list --for-machine`
- search books → `calibredb list --search ... --for-machine`
- add book → `calibredb add`
- remove book → `calibredb remove`
- show metadata → `calibredb show_metadata`
- export books → `calibredb export`
- backup metadata → `calibredb backup_metadata`

### Metadata operations
Map to:
- `ebook-meta <file>` for file metadata inspection
- `ebook-meta <file> --title ... --authors ...` for file metadata mutation
- `calibredb set_metadata <id> <opf-file>` when operating on library records via OPF

### Conversion operations
Map to:
- `ebook-convert input.epub output.mobi ...`

## Harness design implications

Because calibre already provides robust CLIs, this harness should:
1. Wrap real calibre binaries via subprocess
2. Add a stateful session layer on top
3. Normalize outputs into friendly text / JSON
4. Provide REPL UX for interactive agent workflows
5. Avoid reimplementing calibre internals in Python when a real CLI exists

## Recommended command groups

- `library` — open/info/list-fields/stats
- `book` — add/remove/list/get/search/set-field
- `meta` — show/set/set-cover/clear
- `convert` — formats/run/presets
- `export` — book/catalog/backup
- `session` — status/undo/redo/history

## Constraints

- Real calibre tools are a hard dependency for E2E workflows
- The harness must fail clearly if calibre binaries are not on PATH
- REPL should be the default entry behavior
- All commands should support `--json`
- Session persistence should use locked JSON writes
