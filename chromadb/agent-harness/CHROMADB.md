# Agent Harness: ChromaDB Vector Database CLI

## Purpose

This harness provides a standard operating procedure (SOP) and toolkit for coding
agents (Claude Code, Codex, etc.) to interact with ChromaDB vector databases via
a unified CLI interface. The goal: let AI agents query, manage, and populate vector
knowledge bases without needing a browser UI or Python SDK boilerplate.

## Backend Description

**ChromaDB HTTP API v2** running at `http://localhost:8000` (configurable via `--host`).

- Tenant: `default_tenant`
- Database: `default_database`
- Protocol: REST/JSON over HTTP
- Client: Python `requests` library wrapping all API endpoints

ChromaDB is a stateless vector database -- no session or connection state is maintained
between CLI invocations. Each command makes independent HTTP calls.

## Architecture

```
agent-harness/
├── setup.py                          # Package setup with click, prompt-toolkit, requests
├── CHROMADB.md                       # This file -- SOP and architecture
└── cli_anything/
    └── chromadb/
        ├── __init__.py
        ├── __main__.py               # python -m entry point
        ├── README.md                 # Usage docs
        ├── chromadb_cli.py           # Click CLI + REPL dispatcher
        ├── core/
        │   ├── __init__.py
        │   ├── collections.py        # list, create, delete, info
        │   ├── documents.py          # add, get, delete, count
        │   ├── query.py              # semantic search
        │   └── server.py             # heartbeat, version
        ├── utils/
        │   ├── __init__.py
        │   ├── chromadb_backend.py   # HTTP client for ChromaDB v2 API
        │   └── repl_skin.py          # Unified REPL skin
        ├── skills/
        │   └── SKILL.md
        └── tests/
            ├── __init__.py
            ├── TEST.md               # Test plan and results
            ├── test_core.py          # Unit tests (mocked HTTP)
            └── test_full_e2e.py      # E2E tests (real ChromaDB)
```

## Command Groups

### server
Server health and metadata commands.

| Command | Description |
|---------|-------------|
| `server heartbeat` | Check ChromaDB server health (returns nanosecond timestamp) |
| `server version` | Get ChromaDB server version string |

### collection
Collection CRUD operations.

| Command | Description |
|---------|-------------|
| `collection list` | List all collections with IDs and metadata |
| `collection create --name NAME` | Create a new collection |
| `collection delete --name NAME` | Delete a collection by name |
| `collection info NAME` | Get detailed info about a collection |

### document
Document management within collections.

| Command | Description |
|---------|-------------|
| `document add --collection C --id ID --document TEXT` | Add document(s) to a collection |
| `document get --collection C` | Get documents (with optional --id, --limit, --offset) |
| `document delete --collection C --id ID` | Delete document(s) by ID |
| `document count --collection C` | Count documents in a collection |

### query
Semantic search against collections.

| Command | Description |
|---------|-------------|
| `query search --collection C --text T` | Semantic search with optional --n-results |

## State Model

**Stateless.** Every CLI invocation creates a fresh HTTP session and queries the
ChromaDB API directly. There is no local state file, no session persistence, and
no undo/redo. The ChromaDB server itself is the single source of truth.

This means:
- Commands are idempotent where the underlying API supports it
- No risk of stale local state
- Every command can be run independently in any order
- REPL mode maintains only the backend URL and output format preference in memory

## API Endpoints Used

All under ChromaDB v2 API (`/api/v2/`):

| Endpoint | Method | Command |
|----------|--------|---------|
| `/api/v2/heartbeat` | GET | `server heartbeat` |
| `/api/v2/version` | GET | `server version` |
| `/api/v2/tenants/{t}/databases/{d}/collections` | GET | `collection list` |
| `/api/v2/tenants/{t}/databases/{d}/collections` | POST | `collection create` |
| `/api/v2/tenants/{t}/databases/{d}/collections/{name}` | GET | `collection info` |
| `/api/v2/tenants/{t}/databases/{d}/collections/{name}` | DELETE | `collection delete` |
| `/api/v2/tenants/{t}/databases/{d}/collections/{id}/add` | POST | `document add` |
| `/api/v2/tenants/{t}/databases/{d}/collections/{id}/get` | POST | `document get` |
| `/api/v2/tenants/{t}/databases/{d}/collections/{id}/delete` | POST | `document delete` |
| `/api/v2/tenants/{t}/databases/{d}/collections/{id}/count` | POST | `document count` |
| `/api/v2/tenants/{t}/databases/{d}/collections/{id}/query` | POST | `query search` |

## Output Formats

All commands support dual output modes controlled by the `--json` flag:

- **Human-readable** (default): Colored tables, status lines, and formatted text via ReplSkin
- **Machine-readable** (`--json`): Structured JSON on stdout for agent consumption

## Current Collections (Hub)

- **hub_knowledge** -- Main knowledge base with 230+ indexed documents
- **team** -- Team information collection

## Testing Strategy

Two test suites with complementary purposes:

1. **Unit tests** (`test_core.py`): Mocked HTTP calls via `unittest.mock`. Tests CLI
   argument parsing, output formatting, URL construction, and error handling. Fast,
   deterministic, no external dependencies.
2. **E2E tests** (`test_full_e2e.py`): Real subprocess calls to the installed CLI binary
   against a live ChromaDB at localhost:8000. Tests actual JSON output parsing, exit codes,
   and end-to-end command execution.

## Key Principles

- **Stateless by design** -- No local state to get out of sync with the server
- **JSON output for agents** -- Every command supports `--json` for machine parsing
- **Fail loudly** -- Connection errors and bad responses produce clear error messages
- **Leverage the HTTP API directly** -- No ChromaDB Python SDK dependency, just `requests`
