# Zotero CLI Harness

`cli-anything-zotero` is an agent-native CLI for Zotero desktop. It does not
reimplement Zotero. Instead, it composes Zotero's real local surfaces:

- SQLite for offline, read-only inventory
- connector endpoints for GUI state and official write flows
- Local API for citation, bibliography, export, and live search

## What It Is Good For

This harness is designed for practical daily Zotero workflows:

- import a RIS/BibTeX/JSON record into a chosen collection
- attach local or downloaded PDFs during the same import session
- find a paper by keyword or full title
- inspect one collection or one paper in detail
- read child notes and attachments
- add a child note to an existing item
- export BibTeX or CSL JSON for downstream tools
- generate structured context for an LLM
- optionally call OpenAI directly for analysis
- inspect, search, and export from both the local user library and group libraries
- experimentally create collections or re-file existing items when Zotero is closed

## Requirements

- Python 3.10+
- Zotero desktop installed
- a local Zotero profile and data directory

The Windows-first validation target for this harness is:

```text
C:\Program Files\Zotero
```

## Install

```bash
cd zotero/agent-harness
py -m pip install -e .
```

If `cli-anything-zotero` is not recognized afterwards, your Python Scripts
directory is likely not on `PATH`. You can still use:

```bash
py -m cli_anything.zotero --help
```

## Local API

Some commands require Zotero's Local API. Zotero 7 keeps it disabled by default.

Enable it from the CLI:

```bash
cli-anything-zotero --json app enable-local-api
cli-anything-zotero --json app enable-local-api --launch
```

Or manually add this to the active profile's `user.js`:

```js
user_pref("extensions.zotero.httpServer.localAPI.enabled", true);
```

Then restart Zotero.

## Quickstart

```bash
cli-anything-zotero --json app status
cli-anything-zotero --json collection list
cli-anything-zotero --json item list --limit 10
cli-anything-zotero --json item find "embodied intelligence" --limit 5
cli-anything-zotero
```

## Library Context

- stable read, search, export, citation, bibliography, and saved-search execution work for both the local user library and group libraries
- `session use-library 1` and `session use-library L1` are equivalent and persist the normalized `libraryID`
- if a bare key matches multiple libraries, the CLI raises an ambiguity error and asks you to set `session use-library <id>` before retrying
- experimental direct SQLite write commands remain limited to the local user library

## Workflow Guide

### 1. Import Literature Into a Specific Collection

Use Zotero's official connector write path.

```bash
cli-anything-zotero --json import file .\paper.ris --collection COLLAAAA --tag review
cli-anything-zotero --json import json .\items.json --collection COLLAAAA --tag imported
cli-anything-zotero --json import file .\paper.ris --collection COLLAAAA --attachments-manifest .\attachments.json
cli-anything-zotero --json import json .\items-with-pdf.json --collection COLLAAAA --attachment-timeout 90
```

`import json` supports a harness-private inline `attachments` array on each item:

```json
[
  {
    "itemType": "journalArticle",
    "title": "Embodied Intelligence Paper",
    "attachments": [
      { "path": "C:\\papers\\embodied.pdf", "title": "PDF" },
      { "url": "https://example.org/embodied.pdf", "title": "Publisher PDF", "delay_ms": 500 }
    ]
  }
]
```

`import file` supports the same attachment descriptors through a sidecar manifest:

```json
[
  {
    "index": 0,
    "expected_title": "Embodied Intelligence Paper",
    "attachments": [
      { "path": "C:\\papers\\embodied.pdf", "title": "PDF" }
    ]
  }
]
```

Attachment behavior:

- attachments are uploaded only for items created in the current import session
- local files and downloaded URLs must pass PDF magic-byte validation
- duplicate attachment descriptors for the same imported item are skipped idempotently
- if metadata import succeeds but one or more attachments fail, the command returns JSON with `status: "partial_success"` and exits non-zero

When Zotero is running, target resolution is:

1. explicit `--collection`
2. current session collection
3. current GUI-selected collection
4. user library

Backend:

- connector

Zotero must be running:

- yes

### 2. Find a Collection

```bash
cli-anything-zotero --json collection find "robotics"
```

Use this when you remember a folder name but not its key or ID.

Backend:

- SQLite

Zotero must be running:

- no

### 3. Find a Paper by Keyword or Full Title

```bash
cli-anything-zotero --json item find "foundation model"
cli-anything-zotero --json item find "A Very Specific Paper Title" --exact-title
cli-anything-zotero --json item find "vision" --collection COLLAAAA --limit 10
```

Behavior:

- default mode prefers Local API search and falls back to SQLite title search when needed
- when Local API is used, the harness automatically switches between `/api/users/0/...` and `/api/groups/<libraryID>/...`
- `--exact-title` forces exact title matching through SQLite
- results include `itemID` and `key`, so you can pass them directly to `item get`
- if a bare key is duplicated across libraries, set `session use-library <id>` to disambiguate follow-up commands

Backend:

- Local API first
- SQLite fallback

Zotero must be running:

- recommended for keyword search
- not required for exact-title search

### 4. Read a Collection or One Item

```bash
cli-anything-zotero --json collection items COLLAAAA
cli-anything-zotero --json item get REG12345
cli-anything-zotero --json item attachments REG12345
cli-anything-zotero --json item file REG12345
```

Typical use:

- read the papers under a collection
- inspect a single paper's fields, creators, and tags
- resolve the local PDF path for downstream processing

Backend:

- SQLite

Zotero must be running:

- no

### 5. Read Notes for a Paper

```bash
cli-anything-zotero --json item notes REG12345
cli-anything-zotero --json note get NOTEKEY
```

Responsibilities:

- `item notes` lists only child notes for the paper
- `note get` reads the full content of one note by item ID or key

Backend:

- SQLite

Zotero must be running:

- no

### 6. Add a Child Note to a Paper

```bash
cli-anything-zotero --json note add REG12345 --text "Key takeaway: ..."
cli-anything-zotero --json note add REG12345 --file .\summary.md --format markdown
```

Behavior:

- always creates a child note attached to the specified paper
- `text` and `markdown` are converted to safe HTML before save
- `html` is passed through as-is

Important connector note:

- Zotero must be running
- the Zotero UI must currently be on the same library as the parent item

Backend:

- connector `/connector/saveItems`

### 7. Export BibTeX, CSL JSON, and Citations

```bash
cli-anything-zotero --json item export REG12345 --format bibtex
cli-anything-zotero --json item export REG12345 --format csljson
cli-anything-zotero --json item citation REG12345 --style apa --locale en-US
cli-anything-zotero --json item bibliography REG12345 --style apa --locale en-US
```

These commands automatically use the correct Local API scope for user and group libraries.

Supported export formats:

- `ris`
- `bibtex`
- `biblatex`
- `csljson`
- `csv`
- `mods`
- `refer`

Backend:

- Local API

Zotero must be running:

- yes

### 8. Produce LLM-Ready Context

```bash
cli-anything-zotero --json item context REG12345 --include-notes --include-links --include-bibtex
```

This command is the stable, model-independent path for AI workflows. It returns:

- item metadata and fields
- attachments and local file paths
- optional notes
- optional BibTeX and CSL JSON
- optional DOI and URL links
- a `prompt_context` text block you can send to any LLM

Backend:

- SQLite
- optional Local API when BibTeX or CSL JSON export is requested

### 9. Ask OpenAI to Analyze a Paper

```bash
set OPENAI_API_KEY=...
cli-anything-zotero --json item analyze REG12345 --question "What is this paper's likely contribution?" --model gpt-5.4-mini --include-notes
```

Behavior:

- builds the same structured context as `item context`
- adds links automatically
- sends the question and context to the OpenAI Responses API

Requirements:

- `OPENAI_API_KEY`
- explicit `--model`

Recommended usage:

- use `item context` when you want portable data
- use `item analyze` when you want an in-CLI answer

### 10. Experimental Collection Refactoring

These commands write directly to `zotero.sqlite` and are intentionally marked
experimental.

```bash
cli-anything-zotero --json collection create "New Topic" --parent COLLAAAA --experimental
cli-anything-zotero --json item add-to-collection REG12345 COLLBBBB --experimental
cli-anything-zotero --json item move-to-collection REG67890 COLLAAAA --from COLLBBBB --experimental
cli-anything-zotero --json item move-to-collection REG67890 COLLAAAA --all-other-collections --experimental
```

Safety rules:

- Zotero must be closed
- `--experimental` is mandatory
- the harness automatically backs up `zotero.sqlite` before the write
- commands run in a single transaction and roll back on failure
- only the local user library is supported for these experimental commands

Semantics:

- `add-to-collection` only appends a collection membership
- `move-to-collection` adds the target collection and removes memberships from the specified sources

Backend:

- experimental direct SQLite writes

## Command Groups

### `app`

| Command | Purpose | Requires Zotero Running | Backend |
|---|---|---:|---|
| `status` | Show executable, profile, data dir, SQLite path, connector state, and Local API state | No | discovery + probes |
| `version` | Show package version and Zotero version | No | discovery |
| `launch` | Start Zotero and wait for liveness | No | executable + connector |
| `enable-local-api` | Enable the Local API in `user.js`, optionally launch and verify | No | profile prefs |
| `ping` | Check `/connector/ping` | Yes | connector |

### `collection`

| Command | Purpose | Requires Zotero Running | Backend |
|---|---|---:|---|
| `list` | List collections in the current library | No | SQLite |
| `find <query>` | Find collections by name | No | SQLite |
| `tree` | Show nested collection structure | No | SQLite |
| `get <ref>` | Read one collection by ID or key | No | SQLite |
| `items <ref>` | Read the items under one collection | No | SQLite |
| `use-selected` | Persist the currently selected GUI collection | Yes | connector |
| `create <name> --experimental` | Create a collection locally with backup protection | No, Zotero must be closed | experimental SQLite |

### `item`

| Command | Purpose | Requires Zotero Running | Backend |
|---|---|---:|---|
| `list` | List top-level regular items | No | SQLite |
| `find <query>` | Find papers by keyword or full title | Recommended | Local API + SQLite |
| `get <ref>` | Read a single item by ID or key | No | SQLite |
| `children <ref>` | Read notes, attachments, and annotations under an item | No | SQLite |
| `notes <ref>` | Read only child notes under an item | No | SQLite |
| `attachments <ref>` | Read attachment metadata and resolved paths | No | SQLite |
| `file <ref>` | Resolve one attachment file path | No | SQLite |
| `export <ref> --format <fmt>` | Export one item through Zotero translators | Yes | Local API |
| `citation <ref>` | Render one citation | Yes | Local API |
| `bibliography <ref>` | Render one bibliography entry | Yes | Local API |
| `context <ref>` | Build structured, LLM-ready context | Optional | SQLite + optional Local API |
| `analyze <ref>` | Send item context to OpenAI for analysis | Yes for exports only; API key required | OpenAI + local context |
| `add-to-collection <item> <collection> --experimental` | Append a collection membership | No, Zotero must be closed | experimental SQLite |
| `move-to-collection <item> <collection> --experimental` | Move an item between collections | No, Zotero must be closed | experimental SQLite |

### `note`

| Command | Purpose | Requires Zotero Running | Backend |
|---|---|---:|---|
| `get <ref>` | Read one note by ID or key | No | SQLite |
| `add <item-ref>` | Create a child note under an item | Yes | connector |

### `search`

| Command | Purpose | Requires Zotero Running | Backend |
|---|---|---:|---|
| `list` | List saved searches | No | SQLite |
| `get <ref>` | Read one saved search definition | No | SQLite |
| `items <ref>` | Execute one saved search | Yes | Local API |

### `tag`

| Command | Purpose | Requires Zotero Running | Backend |
|---|---|---:|---|
| `list` | List tags and item counts | No | SQLite |
| `items <tag>` | Read items carrying a tag | No | SQLite |

### `style`

| Command | Purpose | Requires Zotero Running | Backend |
|---|---|---:|---|
| `list` | Read installed CSL styles | No | SQLite data dir |

### `import`

| Command | Purpose | Requires Zotero Running | Backend |
|---|---|---:|---|
| `file <path>` | Import RIS/BibTeX/BibLaTeX/Refer and other translator-supported text files | Yes | connector |
| `json <path>` | Save official Zotero connector item JSON | Yes | connector |

### `session`

`session` keeps current library, collection, item, and command history for the
REPL and one-shot commands.

## REPL

Run without a subcommand to enter the stateful REPL:

```bash
cli-anything-zotero
```

Useful builtins:

- `help`
- `exit`
- `current-library`
- `current-collection`
- `current-item`
- `use-library <id-or-Lid>`
- `use-collection <id-or-key>`
- `use-item <id-or-key>`
- `use-selected`
- `status`
- `history`
- `state-path`

## Testing

```bash
py -m pip install -e .
py -m pytest cli_anything/zotero/tests/test_core.py -v
py -m pytest cli_anything/zotero/tests/test_cli_entrypoint.py -v
py -m pytest cli_anything/zotero/tests/test_agent_harness.py -v
py -m pytest cli_anything/zotero/tests/test_full_e2e.py -v -s
py -m pytest cli_anything/zotero/tests/ -v --tb=no

set CLI_ANYTHING_FORCE_INSTALLED=1
py -m pytest cli_anything/zotero/tests/test_cli_entrypoint.py -v
py -m pytest cli_anything/zotero/tests/test_full_e2e.py -v -s
```

Opt-in live write tests:

```bash
set CLI_ANYTHING_ZOTERO_ENABLE_WRITE_E2E=1
set CLI_ANYTHING_ZOTERO_IMPORT_TARGET=<collection-key-or-id>
py -m pytest cli_anything/zotero/tests/test_full_e2e.py -v -s
```

## Limitations

- `item analyze` depends on `OPENAI_API_KEY` and an explicit model name
- `search items`, `item export`, `item citation`, and `item bibliography` require Local API
- `note add` depends on connector behavior and therefore expects the Zotero UI to be on the same library as the parent item
- experimental collection write commands are intentionally not presented as stable Zotero APIs
- no `saveSnapshot`
- import-time PDF attachments are supported, but arbitrary existing-item attachment upload is still out of scope
- no word-processor integration transaction client
- no privileged JavaScript execution inside Zotero
