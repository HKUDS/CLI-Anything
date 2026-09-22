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
| `remove <id> --dangerous` | Delete a notebook (requires `--dangerous`) |
| `open <id>` | Open a notebook |

### doc — Document management
| Subcommand | Description |
|------------|-------------|
| `create <notebook> <path> [--md "content" \| --file path]` | Create a document |
| `list <notebook> [path]` | List documents |
| `tree <notebook> [--path / --depth]` | Show doc tree |
| `get <id>` | Get document path by ID |
| `rename <id> <title>` | Rename a document |
| `remove <id> --dangerous` | Delete a document (requires `--dangerous`) |

### block — Block operations
| Subcommand | Description |
|------------|-------------|
| `insert [<data> \| --file <path>] --parent <id>` | Insert a block (exactly one anchor required: `--parent`/`--previous`/`--next`) |
| `prepend <parent-id> [<data> \| --file <path>]` | Insert as the first child of a container block |
| `append <parent-id> [<data> \| --file <path>]` | Insert as the last child of a container block |
| `update <id> [<data> \| --file <path>]` | Update a block (doc root blocks are not updateable) |
| `move <id> --previous <id>` | Move a block after a sibling (or `--parent <id>` to nest it) |
| `delete <id> --dangerous` | Delete a block (requires `--dangerous`) |
| `get <id>` | Get block kramdown source |
| `children <id>` | Get child blocks |

`insert` lands as the **first** child and takes exactly one anchor — the kernel
applies `nextID > previousID > parentID` and drops the rest, so two anchors are
rejected rather than half-honoured. To land at the end of a container use
`append <parent-id>`; `move` is for relocating a block that already exists.
Note the anchor asymmetry: `insert`
takes `--next` but `move` does not.

### asset — Asset (资源文件) upload
| Subcommand | Description |
|------------|-------------|
| `upload <file> [<file>...] [--dir /assets/]` | Upload local files; prints `assets/…` paths to reference in markdown |

### attr — Block attributes (块属性)
| Subcommand | Description |
|------------|-------------|
| `get <id>` | Show every attribute (includes read-only synthesized `id`/`type`/`updated`) |
| `set <id> KEY=VALUE...` | Set attributes; only the first `=` splits, an empty value removes the key |
| `unset <id> KEY...` | Remove attributes (the kernel drops a key set to an empty value) |

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

## REPL mode

Running the CLI with no command enters a REPL with the same command surface
(`notebook`/`doc`/`block`/`asset`/`attr`/`sql`/`search`/`export`/`tag`/`version`/`status`),
plus `help` and `quit`. Three differences from one-shot mode:

- `--json` must be the **first** token of the line (`--json notebook list`).
- Block/notebook/doc IDs are positional:
  `block insert <parent_id> <data> [--data-type <markdown|dom>] [--file <path>]`,
  `block move <block_id> [--previous <id> | --parent <id>]`. `--previous`/
  `--next` are one-shot `insert` options only — use `block move` to reorder.
  `--data-type dom` stores the payload as DOM HTML instead of Markdown.
- No stdin pipe: content is the argument or `--file`.

`--md`/`--file` values keep a literal `--json` (a flag value is data, not a
switch); an unclosed quote, a dangling option (`--dir` with no value), an empty
option value (`--depth=`, `--file=`), a repeated option and a surplus positional
argument are errors — and so is any `--` prefixed name the command does not
declare: `doc rename d1 --file x` refuses rather than retitling the document to
`--file x`, and a typo (`doc rename d1 --flie x`) is refused instead of becoming
the new title. Attached values parse here too (`doc tree nb1 --depth=2`). The
one-shot entry point is equally strict: `--depth 1 --depth 2` is rejected, not
last-wins.

`sql` and `search` are the exception — they have no option surface, so their
tail is text: `sql SELECT 1 --comment` and `content LIKE '--%'` reach the kernel
as written (a known flag there still errors). `sql` sends the statement
verbatim, quotes included — write it as `sql "SELECT … WHERE x = '1'"`
(or bare) and both spellings send the same statement.

## Agent Guidance

- Always use `--json` for machine-readable output
- Power search: use `sql "SELECT * FROM blocks WHERE content LIKE '%keyword%'"` for SQL-level access
- Document IDs look like `20210817205410-2kvfpfn` (timestamp-based)
- API token can be found in SiYuan Settings → About
- Connection defaults: `http://127.0.0.1:6806`
- Prefer `--file <path>` over stdin piping for CJK/multiline content — reading the file directly avoids shell/PowerShell pipe encoding issues
- Destructive commands (`remove`/`delete`) refuse to run without `--dangerous`
- Arguments are strict: a flag the command does not declare, an option whose
  value is missing, an option given twice, and a surplus positional argument are
  all errors rather than silently ignored content (`doc get <id> extra` fails,
  it does not drop `extra`)
- Uploading an image is two steps: `asset upload pic.png` prints the `assets/…` path, then reference it as `![](assets/…)` in a block; the `assets` index table only registers referenced assets, a few seconds later
- `move` needs a destination anchor; `--parent` only accepts container blocks (document/list/super block), a paragraph-like leaf rejects children — use `--previous` for that
- Never reorder a document by deleting and recreating it: that replaces every child block ID and invalidates references

## Examples

```bash
# List notebooks (JSON)
cli-anything-siyuan --json notebook list

# Create a document with Markdown (--md flag, watch shell escaping)
cli-anything-siyuan doc create nb1 /projects/new --md "## Title\n\nContent"

# Create a document from a Markdown file (avoids shell escaping and CJK pipe issues)
cli-anything-siyuan doc create nb1 /projects/new --file note.md

# SQL search
cli-anything-siyuan sql "SELECT id, content FROM blocks WHERE content LIKE '%meeting%' LIMIT 5"

# Upload an image and reference the printed path
cli-anything-siyuan asset upload pic.png --dir /assets/notes/

# Tag a block, then read it back
cli-anything-siyuan attr set 20210817205410-2kvfpfn custom-status=todo name=待核验
cli-anything-siyuan attr get 20210817205410-2kvfpfn

# Append a block at the end of a document
cat section.md | cli-anything-siyuan block append <doc-id>

# Export
cli-anything-siyuan export md doc123

# Enter REPL
cli-anything-siyuan
```

## Error Handling

- Connection errors: check that SiYuan is running and the API token is correct
- API errors: returned as `{"code": N, "msg": "..."}` — check the message field
- Auth errors: verify the token in `~/.siyuan-cli.json` or `SIYUAN_TOKEN` env var
