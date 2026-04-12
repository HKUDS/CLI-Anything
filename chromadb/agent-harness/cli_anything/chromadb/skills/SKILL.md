---
name: >-
  cli-anything-chromadb
description: >-
  Command-line interface for ChromaDB - A stateless CLI for managing vector database collections, documents, and semantic search. Designed for AI agents and automation via the ChromaDB HTTP API v2.
---

# cli-anything-chromadb

A stateless command-line interface for ChromaDB vector database, built on the HTTP API v2. Designed for AI agents and power users who need to manage collections, documents, and run semantic queries without a browser UI.

## Installation

This CLI is installed as part of the cli-anything-chromadb package:

```bash
pip install cli-anything-chromadb
```

**Prerequisites:**
- Python 3.10+
- ChromaDB server running at localhost:8000 (or specify via --host)

## Usage

### Basic Commands

```bash
# Show help
cli-anything-chromadb --help

# Start interactive REPL mode
cli-anything-chromadb

# Check server health
cli-anything-chromadb --json server heartbeat

# List all collections
cli-anything-chromadb --json collection list

# Semantic search
cli-anything-chromadb --json query search --collection hub_knowledge --text "How to deploy"
```

### REPL Mode

When invoked without a subcommand, the CLI enters an interactive REPL session:

```bash
cli-anything-chromadb
# Enter commands interactively with tab-completion and history
```

## Command Groups

### server
Server health and version commands.

| Command | Description |
|---------|-------------|
| `heartbeat` | Check ChromaDB server health |
| `version` | Get ChromaDB server version |

### collection
Manage ChromaDB collections.

| Command | Description |
|---------|-------------|
| `list` | List all collections |
| `create --name NAME` | Create a new collection |
| `delete --name NAME` | Delete a collection |
| `info NAME` | Get collection info |

### document
Manage documents in collections.

| Command | Description |
|---------|-------------|
| `add --collection C --id ID --document TEXT` | Add document(s) |
| `get --collection C` | Get documents |
| `delete --collection C --id ID` | Delete document(s) |
| `count --collection C` | Count documents |

### query
Semantic search against collections.

| Command | Description |
|---------|-------------|
| `search --collection C --text T` | Semantic search |

## Output Formats

All commands support dual output modes:

- **Human-readable** (default): Tables, colors, formatted text
- **Machine-readable** (`--json` flag): Structured JSON for agent consumption

```bash
# Human output
cli-anything-chromadb server heartbeat

# JSON output for agents
cli-anything-chromadb --json server heartbeat
```

## For AI Agents

When using this CLI programmatically:

1. **Always use `--json` flag** for parseable output
2. **Check return codes** - 0 for success, non-zero for errors
3. **Parse stderr** for error messages on failure
4. **Use `--host`** to connect to non-default ChromaDB instances

## Version

1.0.0
