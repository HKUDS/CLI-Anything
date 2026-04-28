# Calibre: Project-Specific Analysis & SOP

## Architecture Summary

calibre is an ebook management suite covering library operations, metadata editing,
export, and format conversion. Unlike many GUI-first tools, calibre already
ships mature native CLI binaries, so the harness strategy is to compose these
commands into an agent-friendly, stateful interface.

```
┌──────────────────────────────────────────┐
│              Calibre GUI                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│  │ Library  │ │ Metadata │ │ Convert  │ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ │
│       │             │            │       │
│  ┌────┴─────────────┴────────────┴─────┐ │
│  │   Calibre backend (db + metadata)   │ │
│  │  SQLite library + conversion stack  │ │
│  └─────────────────┬───────────────────┘ │
│                    │                     │
│   ┌────────────────┴──────────────────┐  │
│   │ Native CLI binaries               │  │
│   │ calibredb | ebook-meta |          │  │
│   │ ebook-convert                     │  │
│   └───────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

Primary backend components:
- Library database: `src/calibre/db/backend.py`
- Database cache layer: `src/calibre/db/cache.py`
- Legacy library API: `src/calibre/db/legacy.py`
- Search/query layer: `src/calibre/db/search.py`
- Metadata readers/writers: `src/calibre/ebooks/metadata/`
- Conversion pipeline: `src/calibre/ebooks/conversion/`

The GUI is primarily a PyQt6 frontend over these backend capabilities.

## CLI Strategy: Native CLI Composition + Session Layer

The harness wraps real calibre binaries and adds:
1. stable command groups for agents (`library`, `book`, `meta`, `convert`, `export`, `session`)
2. consistent machine-readable output via `--json`
3. REPL-first interactive flow with undo/redo session history
4. explicit validation and clearer error reporting for automation

### Core Domains

| Domain | Module | Native Tool(s) | Key Operations |
|--------|--------|----------------|----------------|
| Library | `core/library.py` | `calibredb` | open/info/list-fields/stats |
| Books | `core/books.py` | `calibredb` | add/list/get/search/remove/set-field |
| Metadata | `core/metadata.py` | `ebook-meta`, `calibredb` | show/set/clear/set-cover |
| Convert | `core/convert.py` | `ebook-convert` | formats/presets/run |
| Export | `core/export.py` | `calibredb` | export book/catalog/backup |
| Session | `core/session.py` | harness layer | status/undo/redo/history/save |

### Native Tool Registry

From `src/calibre/linux.py`, calibre ships these console tools:
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

Harness-critical tools:
- `calibredb` for library inspection and mutation
- `ebook-meta` for per-file metadata inspection/update
- `ebook-convert` for format conversion

### Conversion Presets

Current harness-facing presets:
- `kindle`
- `tablet`
- `generic-epub`

These are mapped to curated `ebook-convert` argument bundles for stable agent use.

### Translation Gap: Low Risk

There is minimal translation gap because the harness delegates core behavior to
calibre's own binaries rather than reimplementing internals. The main harness
responsibility is orchestration, validation, and normalized output.

## Data Model and Mapping

calibre libraries are directory-based and centered on `metadata.db` (SQLite).
Book records map to folders containing one or more format files plus metadata.
This allows direct CLI operations without emulating GUI state.

### Library/book mapping (`calibredb`)
- list books -> `calibredb list --for-machine`
- search books -> `calibredb list --search ... --for-machine`
- add book -> `calibredb add`
- remove book -> `calibredb remove`
- show metadata -> `calibredb show_metadata`
- export books -> `calibredb export`
- backup metadata -> `calibredb backup_metadata`

### File metadata mapping (`ebook-meta`)
- inspect file metadata -> `ebook-meta <file>`
- mutate file metadata -> `ebook-meta <file> --title ... --authors ...`
- library-record metadata update -> `calibredb set_metadata <id> <opf-file>`

### Conversion mapping (`ebook-convert`)
- convert formats -> `ebook-convert input.epub output.mobi ...`

## GUI Toolkit

The GUI uses PyQt6 through calibre's lazy-loading `qt` shim.

Relevant paths:
- `src/qt/`
- `src/calibre/gui2/`
- `pyproject.toml`

## Constraints

- Real calibre tools are hard dependencies for E2E workflows
- The harness must fail clearly if required binaries are not on PATH
- REPL should remain the default entry behavior
- All commands should support `--json`
- Session persistence should use locked JSON writes
