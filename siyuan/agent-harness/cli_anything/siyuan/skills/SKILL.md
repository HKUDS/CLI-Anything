---
name: cli-anything-siyuan
description: SiYuan (思源笔记) CLI — manage notebooks, documents, blocks, and search your knowledge base from the terminal.
---

# cli-anything-siyuan

CLI harness for [SiYuan](https://github.com/siyuan-note/siyuan) (思源笔记),
a local-first knowledge management and note-taking application.

This CLI connects to a running SiYuan kernel via its HTTP API
(`http://127.0.0.1:6806`) and provides structured access to notebooks,
documents, blocks, search, and export.

## Prerequisites

- SiYuan must be running (Settings → About shows the API token)
- Python 3.10+
- Install: `pip install cli-anything-siyuan` or `pip install -e .` from agent-harness/

## Command Groups

### notebook — Notebook management
| Subcommand | Description |
|------------|-------------|
| `list` | List all notebooks |
| `create <name>` | Create a new notebook |
| `rename <id> <name>` | Rename a notebook |
| `remove <id>` | Delete a notebook |
| `open <id>` | Open a notebook |

### doc — Document management
| Subcommand | Description |
|------------|-------------|
| `create <notebook> <path> [--md "content"]` | Create a document |
| `list <notebook> [path]` | List documents |
| `tree <notebook> [--path / --depth]` | Show doc tree |
| `get <id>` | Get document path by ID |
| `rename <id> <title>` | Rename a document |
| `remove <id>` | Delete a document |

### block — Block operations
| Subcommand | Description |
|------------|-------------|
| `insert <data> [--previous / --parent]` | Insert a block |
| `update <id> <data>` | Update a block |
| `delete <id>` | Delete a block |
| `get <id>` | Get block kramdown source |
| `children <id>` | Get child blocks |

### Other commands
| Command | Description |
|---------|-------------|
| `sql <stmt>` | Execute SQL on the block database |
| `search <query>` | Full-text search across blocks |
| `export md <doc-id>` | Export document as Markdown |
| `tag list` | List all tags |
| `version` | Show SiYuan kernel version |
| `status` | Show connection and session status |
| `repl` | Start interactive REPL |

## Agent Guidance

- Always use `--json` for machine-readable output
- Power search: use `sql "SELECT * FROM blocks WHERE content LIKE '%keyword%'"` for SQL-level access
- Document IDs look like `20210817205410-2kvfpfn` (timestamp-based)
- API token can be found in SiYuan Settings → About
- Connection defaults: `http://127.0.0.1:6806`

## Examples

```bash
# List notebooks (JSON)
cli-anything-siyuan --json notebook list

# Create a document with Markdown (--md flag, watch shell escaping)
cli-anything-siyuan doc create nb1 /projects/new --md "## Title\n\nContent"

# Create a document — pipe Markdown via stdin (avoids shell escaping)
# PowerShell here-string (literal, no escaping needed):
@'
## Title
Content with `backticks` and (parentheses) and "quotes"
'@ | cli-anything-siyuan doc create nb1 /projects/new --md -

# Bash heredoc:
# cat <<'EOF' | cli-anything-siyuan doc create nb1 /projects/new --md -
# ## Title
# Content with `backticks` and (parentheses)
# EOF

# SQL search
cli-anything-siyuan sql "SELECT id, content FROM blocks WHERE content LIKE '%meeting%' LIMIT 5"

# Export
cli-anything-siyuan export md doc123

# Enter REPL
cli-anything-siyuan
```

## Error Handling

- Connection errors: check that SiYuan is running and the API token is correct
- API errors: returned as `{"code": N, "msg": "..."}` — check the message field
- Auth errors: verify the token in `~/.siyuan-cli.json` or `SIYUAN_TOKEN` env var
