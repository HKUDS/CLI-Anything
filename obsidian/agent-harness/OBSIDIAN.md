# Obsidian: Project-Specific Analysis & SOP

## Architecture Summary

Obsidian is a knowledge management and note-taking app that stores notes as local Markdown files.
The Local REST API plugin exposes vault operations via an HTTPS server on `localhost:27124`.

```
┌───────────────────────────────────────────────────┐
│              Obsidian Desktop App                  │
│  ┌───────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │   Vault    │ │  Search  │ │    Commands      │  │
│  │  Manager   │ │  Engine  │ │    Registry      │  │
│  └─────┬──────┘ └────┬─────┘ └───────┬──────────┘  │
│        │             │               │              │
│  ┌─────┴─────────────┴───────────────┴───────────┐ │
│  │     Local REST API Plugin (port 27124)        │ │
│  │  /vault/     /search/     /commands/          │ │
│  │  /active/    /periodic-notes/                 │ │
│  └───────────────────┬───────────────────────────┘ │
└──────────────────────┼─────────────────────────────┘
                       │ HTTPS + Bearer Token
         ┌─────────────┴──────────────┐
         │   cli-anything-obsidian    │
         │   Click CLI + REPL         │
         └────────────────────────────┘
```

## CLI Strategy: REST API Wrapper

Our CLI wraps the Obsidian Local REST API plugin with:

1. **requests** — HTTP client for all API calls (HTTPS, self-signed cert)
2. **Bearer token** — Authentication via API key
3. **Click CLI** — Structured command groups matching the API surface
4. **REPL** — Interactive mode for exploratory use

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Server status/auth check |
| `/vault/` | GET | List vault files |
| `/vault/{path}` | GET | Read note content |
| `/vault/{path}` | PUT | Create/update note |
| `/vault/{path}` | DELETE | Delete note |
| `/vault/{path}` | PATCH | Append/prepend to note |
| `/search/` | POST | Structured search — Dataview DQL (`application/vnd.olrapi.dataview.dql+txt`) or JsonLogic (`application/vnd.olrapi.jsonlogic+json`) |
| `/search/simple/` | POST | Plain text search |
| `/active/` | GET | Get active note |
| `/active/` | PUT | Overwrite the currently open note |
| `/open/{path}` | POST | Open a note in the Obsidian UI |
| `/commands/` | GET | List commands |
| `/commands/{id}/` | POST | Execute command |

### Authentication

The Local REST API plugin generates an API key in its settings.
Pass via `--api-key` flag or `OBSIDIAN_API_KEY` environment variable.
All requests use HTTPS with a self-signed certificate (`verify=False`).

## CLI → API Mapping

| CLI Command | API Call |
|-------------|----------|
| `vault list [path]` | `GET /vault/[path]/` |
| `vault read <path>` | `GET /vault/{path}` |
| `vault create <path>` | `PUT /vault/{path}` |
| `vault update <path>` | `PUT /vault/{path}` |
| `vault delete <path>` | `DELETE /vault/{path}` |
| `vault append <path>` | `PATCH /vault/{path}` |
| `search query <q> [--type dql\|jsonlogic]` | `POST /search/` (raw body, vendor Content-Type) |
| `search simple <q>` | `POST /search/simple/` |
| `note active` | `GET /active/` |
| `note open <path>` | `POST /open/{path}` |
| `command list` | `GET /commands/` |
| `command execute <id>` | `POST /commands/{id}/` |
| `server status` | `GET /` |
| `session status` | (local state) |
