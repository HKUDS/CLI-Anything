# Zotero: Project-Specific Analysis and Operator Guide

## Current Capability Snapshot

### Stable and Supported

- import literature into a specific collection through official connector flows
- attach local or downloaded PDFs during the same import session
- inspect libraries, collections, items, attachments, tags, styles, and saved searches
- find items by keyword or exact title
- read child notes under an item
- add a child note to an existing item through official connector save flows
- export RIS, BibTeX, BibLaTeX, CSL JSON, CSV, MODS, and Refer
- render citations and bibliography entries through Zotero's own CSL engine
- route stable read/search/export flows across both user and group libraries
- build LLM-ready structured context for one item
- optionally call OpenAI directly for analysis

### Experimental Local Enhancements

- create a collection by writing directly to `zotero.sqlite`
- add an existing top-level item to another collection
- move an existing top-level item between collections

These experimental commands are intentionally not presented as official Zotero
API capabilities. They exist as local power-user tooling with explicit safety
guards.

### Still Out of Scope

- snapshot capture
- arbitrary existing-item attachment upload outside the current import session
- word-processor transaction integration
- privileged JavaScript execution inside Zotero
- standalone note creation
- group-library write support for experimental SQLite operations

## Architecture Summary

This harness treats Zotero as a layered desktop system:

1. SQLite for local inventory and offline reads
2. connector endpoints for GUI-aware state and official write flows
3. Local API endpoints for live search, CSL rendering, and translator-backed export
4. experimental CLI-only SQLite writes for a few local library-management tasks

The default rule is conservative:

- use official Zotero surfaces whenever they exist
- do not reimplement translators or citeproc
- isolate non-official writes behind explicit `--experimental`

## Source Anchors

The implementation is derived from the installed Zotero source under:

```text
C:\Program Files\Zotero
```

Primary anchors:

- `app/omni.ja`
  - `chrome/content/zotero/xpcom/server/server_localAPI.js`
  - `chrome/content/zotero/xpcom/server/server_connector.js`
  - `chrome/content/zotero/xpcom/server/server_connectorIntegration.js`
  - `chrome/content/zotero/xpcom/server/saveSession.js`
  - `chrome/content/zotero/modules/commandLineOptions.mjs`
- `defaults/preferences/zotero.js`

Important constants from Zotero 7.0.32:

- default HTTP port: `23119`
- Local API pref default: `extensions.zotero.httpServer.localAPI.enabled = false`
- connector liveness endpoint: `/connector/ping`
- selected collection endpoint: `/connector/getSelectedCollection`
- official connector write endpoints used here:
  - `/connector/import`
  - `/connector/saveItems`
  - `/connector/saveAttachment`
  - `/connector/updateSession`

## Backend Responsibilities

### SQLite

Used for:

- libraries
- collection listing, lookup, and tree building
- top-level item inventory
- child notes, attachments, and annotations
- tag lookup
- saved-search metadata
- style inventory
- experimental local collection writes

Behavior notes:

- regular inspection uses `mode=ro&immutable=1`
- no write path is shared with normal stable commands
- experimental writes open a separate transaction-only writable connection

### Connector

Used for:

- liveness
- selected collection detection
- file import
- JSON item import
- import-time attachment upload through the same connector save session
- child note creation
- session retargeting and post-save tagging

Behavior notes:

- Zotero must be running
- write behavior depends on the live desktop app state
- import-time PDF attachment upload is limited to items created in the same connector session
- `note add` inherits connector constraints and therefore expects the GUI to be on the same library as the parent item

### Local API

Used for:

- keyword item search
- citation rendering
- bibliography rendering
- export
- saved-search execution

Behavior notes:

- Zotero must be running
- Local API must be enabled in `user.js` or `prefs.js`
- stable read/search/export commands automatically switch between user and group Local API routes
- there is no fake local fallback for citeproc or translator export

### OpenAI

Used for:

- optional `item analyze`

Behavior notes:

- requires `OPENAI_API_KEY`
- requires explicit `--model`
- recommended stable interface remains `item context`

## How To Enable Local API

### Recommended CLI Path

```bash
cli-anything-zotero --json app enable-local-api
cli-anything-zotero --json app enable-local-api --launch
```

What this does:

- resolves the active Zotero profile
- writes `extensions.zotero.httpServer.localAPI.enabled=true` into `user.js`
- reports whether the pref was already enabled
- optionally launches Zotero and verifies connector and Local API readiness

### Manual Path

Add this line to the active profile's `user.js`:

```js
user_pref("extensions.zotero.httpServer.localAPI.enabled", true);
```

Then restart Zotero.

### Verification

Use either:

```bash
cli-anything-zotero --json app status
cli-anything-zotero --json app ping
```

`app status` should show:

- `local_api_enabled_configured: true`
- `local_api_available: true` once Zotero is running

## Workflow Map

### Import Into a Specific Collection

Use:

- `import file <path> --collection <ref>`
- `import json <path> --collection <ref>`
- `import file <path> --attachments-manifest <manifest.json>`
- `import json <path>` with inline per-item `attachments`

Backend:

- connector

Officiality:

- official Zotero write flow
- attachment phase uses official `/connector/saveAttachment` in the same session

### Find One Paper

Use:

- `item find <query>`
- `item find <full-title> --exact-title`
- `item get <item-id-or-key>`

Backend:

- Local API for live keyword search
- SQLite for exact title or offline fallback

### Read One Collection

Use:

- `collection find <query>`
- `collection get <ref>`
- `collection items <ref>`

Backend:

- SQLite

### Read Notes for a Paper

Use:

- `item notes <item-ref>`
- `note get <note-ref>`

Backend:

- SQLite

### Add a Note to a Paper

Use:

- `note add <item-ref> --text ...`
- `note add <item-ref> --file ... --format markdown`

Backend:

- connector `/connector/saveItems`

### Export or Analyze a Paper

Use:

- `item export`
- `item citation`
- `item bibliography`
- `item context`
- `item analyze`

Backends:

- Local API for export/citation/bibliography
- SQLite plus optional Local API enrichment for `item context`
- OpenAI for `item analyze`

### Re-file Existing Items

Use:

- `collection create ... --experimental`
- `item add-to-collection ... --experimental`
- `item move-to-collection ... --experimental`

Backend:

- experimental direct SQLite writes

## Command Reference

| Command | Purpose | Requires Zotero Running | Backend | Notes |
|---|---|---:|---|---|
| `app status` | Show runtime paths and backend availability | No | discovery | Includes profile, data dir, SQLite path, connector, Local API |
| `app version` | Show harness and Zotero version | No | discovery | Uses install metadata |
| `app launch` | Launch Zotero and wait for liveness | No | executable + connector | Waits for Local API too when configured |
| `app enable-local-api` | Enable Local API in `user.js` | No | prefs write | Safe, idempotent helper |
| `app ping` | Check connector liveness | Yes | connector | Only connector, not Local API |
| `collection list` | List collections | No | SQLite | Uses current library context |
| `collection find <query>` | Find collections by name | No | SQLite | Good for recovering keys/IDs |
| `collection tree` | Show nested collection structure | No | SQLite | Parent-child hierarchy |
| `collection get <ref>` | Read one collection | No | SQLite | Accepts ID or key |
| `collection items <ref>` | Read items in one collection | No | SQLite | Top-level items only |
| `collection use-selected` | Save GUI-selected collection into session | Yes | connector | Uses `/connector/getSelectedCollection` |
| `collection create <name> --experimental` | Create a collection locally | No, Zotero must be closed | experimental SQLite | Automatic backup + transaction |
| `item list` | List top-level items | No | SQLite | Children are excluded |
| `item find <query>` | Find papers by keyword | Recommended | Local API + SQLite | Falls back to SQLite title search |
| `item find <title> --exact-title` | Exact title lookup | No | SQLite | Stable offline path |
| `item get <ref>` | Read one item | No | SQLite | Returns fields, creators, tags |
| `item children <ref>` | Read all child records | No | SQLite | Includes notes, attachments, annotations |
| `item notes <ref>` | Read child notes only | No | SQLite | Purpose-built note listing |
| `item attachments <ref>` | Read attachment children | No | SQLite | Resolves `storage:` paths |
| `item file <ref>` | Resolve one attachment file | No | SQLite | Returns first child attachment for regular items |
| `item export <ref> --format <fmt>` | Translator-backed export | Yes | Local API | Zotero handles the export |
| `item citation <ref>` | CSL citation render | Yes | Local API | Supports style, locale, linkwrap |
| `item bibliography <ref>` | CSL bibliography render | Yes | Local API | Supports style, locale, linkwrap |
| `item context <ref>` | Build structured LLM-ready context | Optional | SQLite + optional Local API | Recommended stable AI interface |
| `item analyze <ref>` | Send context to OpenAI | API key required | OpenAI + local context | Model must be explicit |
| `item add-to-collection ... --experimental` | Append collection membership | No, Zotero must be closed | experimental SQLite | Does not remove existing memberships |
| `item move-to-collection ... --experimental` | Move item between collections | No, Zotero must be closed | experimental SQLite | Requires explicit sources or `--all-other-collections` |
| `note get <ref>` | Read one note | No | SQLite | Accepts note item ID or key |
| `note add <item-ref>` | Add a child note | Yes | connector | Parent item must be top-level |
| `search list` | List saved searches | No | SQLite | Metadata only |
| `search get <ref>` | Read one saved search definition | No | SQLite | Includes stored conditions |
| `search items <ref>` | Execute a saved search | Yes | Local API | Live command |
| `tag list` | List tags | No | SQLite | Includes item counts |
| `tag items <tag>` | Read items under one tag | No | SQLite | Tag string or tag ID |
| `style list` | Read installed CSL styles | No | local data dir | Parses local `.csl` files |
| `import file <path>` | Import through Zotero translators | Yes | connector | Supports optional `--attachments-manifest` sidecar |
| `import json <path>` | Save official connector JSON items | Yes | connector | Supports inline per-item `attachments` descriptors |
| `session *` | Persist current context | No | local state | REPL/session helper commands |

## Item Search Behavior

### `item find`

Primary behavior:

- when Local API is available, query the library-aware Zotero route:
  - `/api/users/0/...` for the local user library
  - `/api/groups/<libraryID>/...` for group libraries
- resolve Local API result keys back through SQLite so results always include local `itemID` and `key`

Fallback behavior:

- if Local API is unavailable or returns nothing useful, SQLite title search is used
- `--exact-title` always uses SQLite exact matching

Reference behavior:

- numeric IDs remain globally valid
- bare keys are accepted when they match exactly one library
- if a bare key matches multiple libraries, the CLI raises an ambiguity error and asks the caller to set `session use-library <id>`

### Why `item get` and `item find` Are Separate

- `item get` is precise lookup by `itemID` or `key`
- `item find` is discovery by keyword or title

This keeps lookup stable and makes scripting more predictable.

## Notes Model

### `item notes`

- entrypoint for listing note children under one paper
- returns notes only, not attachments or annotations

### `note get`

- reads one note record directly
- good for follow-up scripting when you already have a note key from `item notes`

### `note add`

- only child notes are supported in this harness version
- standalone notes are intentionally left out
- `text` and `markdown` are converted to safe HTML before submit
- `html` is accepted as-is

## LLM and Analysis Model

### Recommended Stable Interface: `item context`

`item context` is the portable interface. It aggregates:

- item fields
- creators and tags
- attachments
- optional notes
- optional exports such as BibTeX and CSL JSON
- optional DOI and URL links
- a prompt-ready `prompt_context`

This is the recommended command if the caller already has its own LLM stack.

### Optional Direct Interface: `item analyze`

`item analyze` layers model calling on top of `item context`.

Design choices:

- requires `OPENAI_API_KEY`
- requires explicit `--model`
- does not hide missing-context uncertainty
- remains optional, not the only AI path

## Experimental SQLite Write Model

### Why It Exists

Zotero's official HTTP surfaces cover import and note save well, but do not expose
general-purpose collection creation and arbitrary re-filing of existing items.

This harness adds a narrow experimental SQLite write path.

### Guardrails

- `--experimental` is mandatory
- Zotero must be closed
- the database is backed up before each write
- each operation runs in a single transaction
- rollback occurs on failure
- only the local user library is supported

### Semantics

`item add-to-collection`:

- append-only
- keeps all current collection memberships

`item move-to-collection`:

- first ensures target membership exists
- then removes memberships from `--from` collections or from all others when `--all-other-collections` is used
- does not delete implicitly without explicit source selection

## SQLite Tables Used

| CLI Area | Zotero Tables |
|---|---|
| Libraries | `libraries` |
| Collections | `collections`, `collectionItems` |
| Items | `items`, `itemTypes` |
| Fields and titles | `itemData`, `itemDataValues`, `fields` |
| Creators | `creators`, `itemCreators` |
| Tags | `tags`, `itemTags` |
| Notes | `itemNotes` |
| Attachments | `itemAttachments` |
| Annotations | `itemAnnotations` |
| Searches | `savedSearches`, `savedSearchConditions` |

## Limitations

- `item analyze` depends on external OpenAI credentials and network access
- `search items`, `item export`, `item citation`, and `item bibliography` require Local API
- `note add` depends on connector behavior and active GUI library context
- experimental SQLite write commands are local power features, not stable Zotero APIs
- no `saveSnapshot`
- import-time PDF attachment upload is supported, but arbitrary existing-item attachment upload is still out of scope
- no word-processor integration transaction client
- no privileged JavaScript execution inside Zotero
