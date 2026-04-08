---
name: >-
  cli-anything-zotero
description: >-
  CLI harness for Zotero.
---

# cli-anything-zotero

`cli-anything-zotero` is an agent-native CLI for Zotero desktop. It does not reimplement Zotero. Instead, it composes Zotero's real local surfaces:

## Installation

```bash
pip install -e .
```

## Entry Points

```bash
cli-anything-zotero
python -m cli_anything.zotero
```

## Important Constraints

- `search items`, `item export`, `item citation`, and `item bibliography` require Zotero's Local API to be enabled.
- `note add` depends on the live Zotero GUI context and expects the same library to be selected in the app.
- Import-time PDF attachment support is limited to items created in the same connector session; arbitrary existing-item attachment upload is still out of scope.
- Experimental SQLite write commands are local-only, user-library-only, and should be treated as non-stable power-user operations.
- If a bare key is duplicated across libraries, set `session use-library <id>` before follow-up commands.

## Command Groups

### App

Application and runtime inspection commands.

| Command | Description |
|---------|-------------|
| `status` | Execute `status`. |
| `version` | Execute `version`. |
| `launch` | Execute `launch`. |
| `enable-local-api` | Execute `enable-local-api`. |
| `ping` | Execute `ping`. |

### Collection

Collection inspection and selection commands.

| Command | Description |
|---------|-------------|
| `list` | Execute `list`. |
| `find` | Execute `find`. |
| `tree` | Execute `tree`. |
| `get` | Execute `get`. |
| `items` | Execute `items`. |
| `use-selected` | Execute `use-selected`. |
| `create` | Execute `create`. |

### Item

Item inspection and rendering commands.

| Command | Description |
|---------|-------------|
| `list` | Execute `list`. |
| `find` | Execute `find`. |
| `get` | Execute `get`. |
| `children` | Execute `children`. |
| `notes` | Execute `notes`. |
| `attachments` | Execute `attachments`. |
| `file` | Execute `file`. |
| `export` | Execute `export`. |
| `citation` | Execute `citation`. |
| `bibliography` | Execute `bibliography`. |
| `context` | Execute `context`. |
| `analyze` | Execute `analyze`. |
| `add-to-collection` | Execute `add-to-collection`. |
| `move-to-collection` | Execute `move-to-collection`. |

### Search

Saved-search inspection commands.

| Command | Description |
|---------|-------------|
| `list` | Execute `list`. |
| `get` | Execute `get`. |
| `items` | Execute `items`. |

### Tag

Tag inspection commands.

| Command | Description |
|---------|-------------|
| `list` | Execute `list`. |
| `items` | Execute `items`. |

### Style

Installed CSL style inspection commands.

| Command | Description |
|---------|-------------|
| `list` | Execute `list`. |

### Import

Official Zotero import and write commands.

| Command | Description |
|---------|-------------|
| `file` | Execute `file`. |
| `json` | Execute `json`. |

### Note

Read and add child notes.

| Command | Description |
|---------|-------------|
| `get` | Execute `get`. |
| `add` | Execute `add`. |

### Session

Session and REPL context commands.

| Command | Description |
|---------|-------------|
| `status` | Execute `status`. |
| `use-library` | Execute `use-library`. |
| `use-collection` | Execute `use-collection`. |
| `use-item` | Execute `use-item`. |
| `use-selected` | Execute `use-selected`. |
| `clear-library` | Execute `clear-library`. |
| `clear-collection` | Execute `clear-collection`. |
| `clear-item` | Execute `clear-item`. |
| `history` | Execute `history`. |

## Examples

### Runtime Status

Inspect Zotero paths and backend availability.

```bash
cli-anything-zotero app status --json
```

### Read Selected Collection

Persist the collection selected in the Zotero GUI.

```bash
cli-anything-zotero collection use-selected --json
```

### Render Citation

Render a citation using Zotero's Local API.

```bash
cli-anything-zotero item citation <item-key> --style apa --locale en-US --json
```

### Add Child Note

Create a child note under an existing Zotero item.

```bash
cli-anything-zotero note add <item-key> --text "Key takeaway" --json
```

### Build LLM Context

Assemble structured context for downstream model analysis.

```bash
cli-anything-zotero item context <item-key> --include-notes --include-links --json
```

## Version

0.1.0
