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

### Block insert/update with multi-line content

`block insert` and `block update` accept data via stdin pipe when the argument is `-` or omitted:

```bash
# Pipe multi-line content
cat note.md | cli-anything-siyuan block insert --parent <block-id>

# Explicit stdin marker
echo "hello" | cli-anything-siyuan block update <block-id> -

# Requires one of: --parent <id>, --previous <id>, --next <id>
```

### Tag list

`tag list` sends `ignoreMaxListHint: true` to ensure all tags are returned regardless of `Conf.FileTree.MaxListCount`. Tag-heavy workspaces return the complete list.
