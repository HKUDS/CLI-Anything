# SiYuan (思源笔记) — Agent CLI Harness Analysis

## Overview

SiYuan is a local-first, privacy-focused knowledge management and note-taking application.
It uses a Go backend with an Electron/TypeScript frontend. Data is stored as `.sy` files
(Siyuan JSON format) with a SQLite database for indexing and search.

## Backend

- **Language**: Go
- **HTTP Server**: Gin framework, runs on `http://127.0.0.1:6806`
- **Auth**: Token-based (`Authorization: Token xxx`)
- **Entry point**: `kernel/main.go` → starts HTTP server + background jobs

## Data Model

```
Notebook (Box)
  └── Document (tree node, .sy file)
       └── Blocks (paragraphs, headings, lists, code, etc.)
            └── Attributes (key-value, custom-* prefix)
```

- **Notebook**: Top-level container, identified by ID (e.g., `20210817205410-2kvfpfn`)
- **Document**: Tree node in a notebook, stored as `.sy` file
- **Block**: Content unit (paragraph, heading, list item, etc.), each has unique ID
- **SQLite Database**: blocks, refs, attributes, history, asset_content tables
- **IDs**: Timestamp-based IDs like `20210817205410-2kvfpfn` (datetime + random suffix)

## API Surface

Base URL: `http://127.0.0.1:6806`

### Notebook API (`/api/notebook/*`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `lsNotebooks` | POST | List all notebooks |
| `openNotebook` | POST | Open a notebook |
| `closeNotebook` | POST | Close a notebook |
| `createNotebook` | POST | Create new notebook |
| `removeNotebook` | POST | Delete notebook |
| `renameNotebook` | POST | Rename notebook |
| `getNotebookConf` | POST | Get notebook config |
| `setNotebookConf` | POST | Set notebook config |
| `setNotebookIcon` | POST | Set notebook icon |

### Document/Filetree API (`/api/filetree/*`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `createDocWithMd` | POST | Create doc with Markdown content |
| `createDailyNote` | POST | Create daily note |
| `renameDoc` | POST | Rename doc by path |
| `renameDocByID` | POST | Rename doc by ID |
| `removeDoc` | POST | Delete doc by path |
| `removeDocByID` | POST | Delete doc by ID |
| `moveDocs` | POST | Move docs by paths |
| `moveDocsByID` | POST | Move docs by IDs |
| `getHPathByID` | POST | Get human-readable path by ID |
| `getHPathByPath` | POST | Get human-readable path by path |
| `getIDsByHPath` | POST | Get IDs by human-readable path |
| `getPathByID` | POST | Get storage path by ID |
| `listDocsByPath` | POST | List docs at a path |
| `listDocTree` | POST | List full document tree |
| `searchDocs` | POST | Search document names |

### Block API (`/api/block/*`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `insertBlock` | POST | Insert block at position |
| `prependBlock` | POST | Insert as first child |
| `appendBlock` | POST | Insert as last child |
| `updateBlock` | POST | Update block content |
| `deleteBlock` | POST | Delete a block |
| `moveBlock` | POST | Move a block |
| `foldBlock` | POST | Fold/collapse a block |
| `unfoldBlock` | POST | Unfold/expand a block |
| `getBlockKramdown` | POST | Get block kramdown source |
| `getChildBlocks` | POST | Get child blocks |

### Attribute API (`/api/attr/*`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `setBlockAttrs` | POST | Set block attributes |
| `getBlockAttrs` | POST | Get block attributes |

### SQL Query API (`/api/query/sql`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `sql` | POST | Execute SQL query on block database |

### Search API (`/api/search/*`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `fullTextSearchBlock` | POST | Full-text search in blocks |
| `searchTag` | POST | Search tags |
| `findReplace` | POST | Find and replace |

### Export API (`/api/export/*`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `exportMdContent` | POST | Export doc as Markdown |
| `exportResources` | POST | Export files as ZIP |

### Asset API (`/api/asset/*`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `upload` | POST | Upload asset file |

### Tag API (`/api/tag/*`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `getTag` | POST | List tags |
| `renameTag` | POST | Rename tag |
| `removeTag` | POST | Remove tag |

### System API (`/api/system/*`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `version` | GET/POST | Get system version |
| `currentTime` | POST | Get current server time |

## Existing CLI Tools

None. SiYuan ships with only the desktop GUI (Electron) and mobile apps.
The kernel starts automatically with the GUI; there is no standalone CLI mode.

## CLI Harness Strategy

Since SiYuan has no headless CLI backend, the harness will:

1. **Connect to an already-running SiYuan instance** via its HTTP API
2. **Provide commands for all major API groups** (notebooks, documents, blocks, search, export)
3. **Store connection state** (host, port, token) for multi-session use
4. **Support SQL queries** for advanced data access
5. **Support import/export** of Markdown content

The SiYuan instance must be running with the API server enabled (default: port 6806).
The API token can be found in Settings → About.

## CLI Usage Notes

### Argument conventions

Both entry points reject a malformed command line instead of guessing:

```bash
cli-anything-siyuan doc tree nb1 --depth 1 --depth 2   # option given twice
cli-anything-siyuan doc get <doc-id> extra             # surplus positional
cli-anything-siyuan doc rename <doc-id> --file x.md    # flag not declared here
cli-anything-siyuan doc rename <doc-id> --flie x.md    # no such option (typo)
cli-anything-siyuan block move <id> --previous --parent p1  # option left without a value
```

Each of those exits 2 with the offending token and the real usage. A flag that
the command does not declare is never taken as content, so `doc rename` cannot
silently retitle a document to the literal text `--file x`; a name no command
declares is refused the same way. An option's *value*
is still data — `--md "--json"` writes the text `--json` — and an explicit empty
argument stays meaningful (`block update <id> ""` clears the block), while an
empty *option* value (`--depth=`, `--file=`) is a usage error rather than a
silent default: `--file=` names no file, so it must not quietly become the
stdin pipe.

Values may be attached with `=`, as on the command line:
`doc tree nb1 --depth=2` and `block update b1 --file=note.md`.

### Block insert/prepend/append/update with multi-line content

`block insert`, `block prepend`, `block append` and `block update` read data from
a stdin pipe when the data argument is omitted (there is no `-` marker — a
literal `-` is just data). If the bytes are neither UTF-8 nor GB18030 the pipe
is refused rather than stored as mojibake; pin the code page with
`SIYUAN_STDIN_ENCODING` or pass `--file`.

`--data-type dom` sends the payload as DOM HTML instead of Markdown. It works in
both entry points and defaults to `markdown`; it is not a content slot, so a
missing value is an error rather than the next flag (`--data-type --json`).

```bash
# Pipe multi-line content
cat note.md | cli-anything-siyuan block insert --parent <block-id>
echo "hello" | cli-anything-siyuan block update <block-id>

# Requires one of: --parent <id>, --previous <id>, --next <id>
```

`prepend`/`append` take an explicit parent and place the block first/last among
its children — `insert` always inserts as the **first** child, so use `append`
when the new block should land at the end:

```bash
cli-anything-siyuan block append <parent-id> --file section.md
```

### Block move (reordering)

`block move <block_id>` takes exactly one destination anchor:

```bash
# Same level — land right after a sibling
cli-anything-siyuan block move <block_id> --previous <sibling_id>

# Nest — land as the first child of another block
cli-anything-siyuan block move <block_id> --parent <parent_id>

# Place after a specific sibling (the API has no "next sibling" flag either,
# so name the block it should follow)
cli-anything-siyuan block move <block_id> --previous <sibling_id>
```

Why this matters: `block insert` lands as the **first** child and `block move`
relocates a block that already exists. To put *new* content at the end of a
container, use `block append <parent-id>` — do not reach for
`move --previous <last-id>`, which is only for naming a specific sibling. Never
reorder a document by deleting and recreating it: that replaces every child
block ID and invalidates any references to them.

Note the asymmetry in the kernel API: `insertBlock` accepts `previousID`,
`parentID` and `nextID`, while `moveBlock` accepts only `previousID` and
`parentID`. There is no `--next` for move.

`--parent` only works when the destination is a **container** block. Nesting
under a paragraph fails with `type "p" is a leaf block and cannot have
children; use previousID to place the block as its sibling instead` — reach for
`--previous` in that case.

### Asset upload (images and files)

```bash
# Upload one or more local files; the kernel renames them to avoid collisions
cli-anything-siyuan asset upload pic.png cover.jpg

# Target a subdirectory of the workspace assets folder
cli-anything-siyuan asset upload pic.png --dir /assets/notes/
```

Output is `assets/…/name-<timestamp>-<hash>.png  <-  <local file>`; the first
column is exactly what goes into markdown (`![](assets/…)`).

Two kernel details worth knowing:

- The endpoint is `multipart/form-data` (`assetsDirPath` plus repeated
  `file[]`), so the request must not carry the session's default JSON
  `Content-Type` — the client passes `Content-Type: None` to drop it for this
  one call, otherwise requests cannot add the multipart boundary.
- `errFiles` comes back as `null` (not `[]`) when everything succeeded, so
  treat it as falsy instead of iterating it.

Uploading only writes the file. The `assets` table indexes **referenced**
assets, so a fresh upload appears in `SELECT … FROM assets` only after a block
references it — and that sync takes a few seconds.

### Block attributes (`attr`)

```bash
cli-anything-siyuan attr get <block-id>
cli-anything-siyuan attr set <block-id> custom-status=todo name=待核验
cli-anything-siyuan attr unset <block-id> custom-status
```

- `set` takes `KEY=VALUE` pairs; only the first `=` splits, so values may
  contain `=`.
- `unset` is `set` with an empty value — the kernel drops a key whose value is
  empty (verified against the document's `.sy` file, not just the API reply).
- Built-in keys: `name` (命名), `alias` (别名), `memo` (备注), `bookmark`
  (书签). Custom keys must be prefixed `custom-` to be indexed.
- `get` also returns the kernel's synthesized fields (`id`, `type`, `updated`,
  and `title` for a named doc) next to the real attributes; those are read-only
  and are not part of the block's `ial`.
- The `attributes` table (queryable via `sql`) lags a few seconds behind the
  write, so a stale row right after `unset` is index latency, not a failed
  delete.

### Tag list

`tag list` sends `ignoreMaxListHint: true` to ensure all tags are returned regardless of `Conf.FileTree.MaxListCount`. Tag-heavy workspaces return the complete list.

The kernel **HTML-escapes** tag names on the way out (`util.EscapeHTML` in
`kernel/model/tag.go`, both `getTag` and `searchTag`) because its own consumers
render HTML. The client decodes the `name` field back, so a tag prints as
`->return-type` and not `-&gt;return-type`. The sibling `label` field is left as
delivered — in the search endpoint it carries markup for the UI, so it is not an
identity field; `name` is.

### REPL vs one-shot differences

Both entry points reach the same commands, with three deliberate differences:

- `--json` must be the **first** token of the REPL line (`--json notebook list`),
  matching the one-shot `sy --json …` position. A `--json` anywhere else is an
  error, not content.
- Block/notebook/doc **IDs are positional** in the REPL:
  `block insert <parent_id> <data> [--data-type <markdown|dom>] [--file <path>]`,
  `block update <block_id> <data> [--data-type <markdown|dom>] [--file <path>]`,
  `block move <block_id> [--previous <id> | --parent <id>]`,
  `doc tree <notebook> [--path <path>] [--depth N]`. The one-shot `insert`
  `--parent/--previous/--next` flags are not REPL options; a stray anchor flag is
  rejected (it used to be swallowed into the block content) — use `block move`
  to reorder after inserting.
- The REPL has no stdin pipe: content is the argument or `--file`.

Option values that are missing, repeated, empty, or are themselves flags
(`--previous --parent p1`) are errors, and an explicit empty value is still
meaningful (`block update b1 ""` clears the block).

A `--` prefixed token is an option wherever it appears, and one no command
declares is an error, not text: `doc rename d1 --file x` refuses instead of
retitling the document to `--file x`, `doc list --depth 2` refuses instead of
querying the path `--depth`, and a typo (`doc rename d1 --flie x`, which used to
retitle the document to `--flie x`) is reported as an unknown option. Attached
values work here too (`doc tree nb1 --depth=2`), and one-shot and REPL parse
both spellings identically.

The two **free-text commands are the exception**: `sql <stmt>` and
`search <query>` have no option surface, so a flag-shaped token there is text —
a SQL comment (`sql SELECT 1 --comment`) or a LIKE pattern
(`content LIKE '--%'`) has no other spelling, since there is no `--` terminator
to escape it. A *known* flag is still refused in those commands (a misplaced
`--depth` is a mistake), but a name nothing declares is passed through.

**`sql` keeps the statement verbatim**, quotes included: the tokens are only
used to validate flags, and the text sent on is the line as typed. Writing
`WHERE '1' = '01'` without the wrapper used to reach the kernel as
`WHERE 1 = 01` — a different query with a different answer. The documented
spelling wraps the statement in quotes (`sql "SELECT … LIKE '%k%'"`); that one
outer pair is unwrapped, so both spellings send the same statement.

A bare `--` is not a terminator: in `sql`/`search` it stays part of the text
(`sql -- SELECT 1`), and in a fixed-arity command it is refused
(`doc get -- d1` used to fetch the id `--` and drop `d1`). Variadic block
content keeps it (`block update b1 a -- b`).

The `help` listing is the single source for every signature, so the hint in an
error is the same text `help` prints.

