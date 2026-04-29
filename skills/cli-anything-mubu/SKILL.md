---
name: "cli-anything-mubu"
description: >-
  Command-line interface for Mubu - Canonical packaged entrypoint for the Mubu live bridge....
---

# cli-anything-mubu

Canonical packaged entrypoint for the Mubu live bridge.

## Installation

This CLI is packaged from the canonical `agent-harness` source tree:

```bash
pip install -e .
```

**Prerequisites:**
- Python 3.10+
- An active Mubu desktop session on this machine
- Local Mubu profile data available to the CLI
- Set `MUBU_DAILY_FOLDER` if you want no-argument daily helpers

## Entry Points

```bash
cli-anything-mubu
python -m cli_anything.mubu
```

When invoked without a subcommand, the CLI enters an interactive REPL session.

## Command Groups


### Discover

Discovery commands for folders, documents, recency, and daily-document resolution.

| Command | Description |
|---------|-------------|

| `docs` | List latest known document snapshots from local backups. |

| `folders` | List folder metadata from local RxDB storage. |

| `folder-docs` | List document metadata for one folder. |

| `path-docs` | List documents for one folder path or folder id. |

| `recent` | List recently active documents using backups, metadata, and sync logs. |

| `daily` | Find Daily-style folders and list the documents inside them. |

| `daily-current` | Resolve the current daily document from one Daily-style folder. |



### Inspect

Inspection commands for tree views, search, links, sync events, and live node targeting.

| Command | Description |
|---------|-------------|

| `show` | Show the latest backup tree for one document. |

| `search` | Search latest backups for matching node text or note content. |

| `changes` | Parse recent client-sync change events from local logs. |

| `links` | Extract outbound Mubu document links from one document backup. |

| `open-path` | Open one document by full path, suffix path, title, or doc id. |

| `doc-nodes` | List live document nodes with node ids and update-target paths. |

| `daily-nodes` | List live nodes from the current daily document in one step. |



### Mutate

Mutation commands for dry-run-first atomic live edits against the Mubu API.

| Command | Description |
|---------|-------------|

| `create-child` | Build or execute one child-node creation against the live Mubu API. |

| `delete-node` | Build or execute one node deletion against the live Mubu API. |

| `update-text` | Build or execute one text update against the live Mubu API. |



### Session

Session and state commands for current document/node context and local command history.

| Command | Description |
|---------|-------------|

| `status` | Show the current session state. |

| `state-path` | Show the session state file path. |

| `use-doc` | Persist the current document reference. |

| `use-node` | Persist the current node reference. |

| `use-daily` | Resolve and persist the current daily document reference. |

| `clear-doc` | Clear the current document reference. |

| `clear-node` | Clear the current node reference. |

| `history` | Show recent command history stored in session state. |



## Recommended Agent Workflow

```text
discover daily-current '<daily-folder-ref>' --json
        ->
inspect daily-nodes '<daily-folder-ref>' --query '<anchor>' --json
        ->
session use-doc '<doc_path>'
        ->
mutate update-text / create-child / delete-node --json
        ->
--execute only after payload inspection
```

## Safety Rules

1. Prefer grouped commands for agent use; flat legacy commands remain for compatibility.
2. Use `--json` whenever an agent will parse the output.
3. Prefer `discover` or `inspect` commands before any `mutate` command.
4. Live mutations are dry-run by default and only execute with `--execute`.
5. Prefer `--node-id` and `--parent-node-id` over text matching.
6. `delete-node` removes the full targeted subtree.
7. Even same-text updates can still advance document version history.
8. Pass a daily-folder reference explicitly or set `MUBU_DAILY_FOLDER` before using no-arg daily helpers.

## Examples


### Interactive REPL Session

Start an interactive session with persistent document and node context.

```bash
cli-anything-mubu
# Enter commands interactively
# Use 'help' to see builtins
# Use session commands to persist current-doc/current-node
```


### Discover Current Daily Note

Resolve the current daily note from an explicit folder reference.

```bash
cli-anything-mubu --json discover daily-current '<daily-folder-ref>'
```


### Dry-Run Atomic Update

Inspect the exact outgoing payload before a live mutation.

```bash
cli-anything-mubu mutate update-text '<doc-ref>' --node-id <node-id> --text 'new text' --json
```


## Session State

The CLI maintains lightweight session state in JSON:

- `current_doc`
- `current_node`
- local command history

Use the `session` command group to inspect or update this state.

## For AI Agents

1. Start with `discover` or `inspect`, not `mutate`.
2. Use `session status --json` to recover persisted context.
3. Use grouped commands in generated prompts and automation.
4. Verify postconditions after any live mutation.
5. Read the package `TEST.md` and `README.md` when stricter operational detail is needed.

## Version

0.1.1