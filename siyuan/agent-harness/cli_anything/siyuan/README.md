# cli-anything-siyuan

A CLI harness for [SiYuan](https://github.com/siyuan-note/siyuan) (思源笔记) —
interact with your knowledge base from the terminal.

## Prerequisites

- **SiYuan** must be running (version 3.x). Download from [b3log.org/siyuan](https://b3log.org/siyuan).
- **Python 3.10+**

## Installation

```bash
cd agent-harness
pip install -e .
```

For REPL support (recommended):

```bash
pip install -e ".[repl]"
```

## Configuration

Create `~/.siyuan-cli.json`:

```json
{
  "host": "127.0.0.1",
  "port": 6806,
  "token": "your-api-token-here"
}
```

Or use environment variables:

```bash
export SIYUAN_HOST=127.0.0.1
export SIYUAN_PORT=6806
export SIYUAN_TOKEN=your-token
```

**Finding your API token:** Open SiYuan → Settings → About → API Token.

## Usage

### One-shot commands

```bash
# List notebooks
cli-anything-siyuan notebook list

# List notebooks (JSON output)
cli-anything-siyuan --json notebook list

# Get version
cli-anything-siyuan version

# Execute SQL query
cli-anything-siyuan sql "SELECT * FROM blocks LIMIT 5"

# Search blocks
cli-anything-siyuan search "keyword"

# Export document as Markdown
cli-anything-siyuan export md <doc-id>

# Show status
cli-anything-siyuan status

# Insert a block (multi-line content via stdin)
cat note.md | cli-anything-siyuan block insert --parent <block-id>

# Update a block content via stdin
echo "new content" | cli-anything-siyuan block update <block-id>

# Prefer --file over stdin for CJK / multiline content — it bypasses the pipe
cli-anything-siyuan block update <block-id> --file note.md

# Upload images and reference the printed asset path in markdown
cli-anything-siyuan asset upload pic.png cover.jpg --dir /assets/notes/

# Tag a block
cli-anything-siyuan attr set <block-id> custom-status=todo name=待核验
```

`--md` and `--file` are mutually exclusive with each other and with the
positional content argument; an empty stdin pipe is rejected rather than
writing empty content. If a CJK-code-page pipe still mangles text and you
cannot use `--file`, pin the encoding explicitly with
`SIYUAN_STDIN_ENCODING=gb18030` (an unknown or non-decodable value is an error,
never a silent lossy decode).

Malformed argument lines are refused rather than guessed at: a flag the command
does not declare, an option left without a value, an option given twice and a
surplus positional argument all exit 2 with the real usage.

### REPL mode

```bash
# Just run without arguments to enter REPL
cli-anything-siyuan
```

Inside the REPL:

```
◆  cli-anything · Siyuan                   v1.0.0
   ◇ Install: npx skills add HKUDS/CLI-Anything --skill cli-anything-siyuan -g -y
   ◇ Global skill: ~/.agents/skills/cli-anything-siyuan/SKILL.md

   Type help for commands, quit to exit

siyuan ❯ notebook list
siyuan ❯ doc tree <notebook-id>
siyuan ❯ search "meeting notes"
siyuan ❯ help
siyuan ❯ quit
```

Two things differ from one-shot mode:

- `--json` must be the **first** token of the line (`--json notebook list`).
- IDs are positional and content never comes from stdin — a `--` prefixed token
  is an option, so anything the command does not declare, a mistyped name
  included, is an error rather than content:
  `block insert <parent_id> <data> [--data-type <markdown|dom>] [--file <path>]`,
  `block update <block_id> <data> [--data-type <markdown|dom>] [--file <path>]`,
  `doc tree <notebook> [--path <path>] [--depth N]`. The one-shot
  `insert --parent/--previous/--next` flags are not REPL options — use
  `block append` to land at the end, or `block move` to reorder.
- `--data-type dom` stores the payload as DOM HTML instead of Markdown, in the
  REPL exactly as one-shot.
- `sql` and `search` take their tail as text — `sql SELECT 1 --comment` and
  `content LIKE '--%'` are passed through, and `sql` keeps the statement's
  quotes verbatim (the documented `sql "SELECT …"` wrapper is unwrapped).

## Command Groups

One-shot syntax (`cli-anything-siyuan <command>`); in the REPL the same
commands exist with the differences noted above.

| Command | Description |
|---------|-------------|
| `notebook list` | List all notebooks |
| `notebook create <name>` | Create a notebook |
| `notebook rename <id> <name>` | Rename a notebook |
| `notebook remove <id> --dangerous` | Delete a notebook (requires `--dangerous`) |
| `notebook open <id>` | Open a notebook |
| `doc create <notebook-id> <path> [--md "content" \| --file path]` | Create a document |
| `doc list <notebook-id> [path]` | List documents |
| `doc tree <notebook-id> [--path / --depth N]` | Show document tree |
| `doc get <id>` | Get document path by ID |
| `doc rename <id> <title>` | Rename a document |
| `doc remove <id> --dangerous` | Delete a document (requires `--dangerous`) |
| `block insert [<data> \| --file <path>] --parent <id>` | Insert a block (one anchor: `--parent`/`--previous`/`--next`; reads stdin when `<data>` is omitted; `--data-type dom` for DOM HTML) |
| `block prepend <parent-id> [<data> \| --file <path>]` | Insert as the first child |
| `block append <parent-id> [<data> \| --file <path>]` | Insert as the last child |
| `block update <id> [<data> \| --file <path>]` | Update block content (reads stdin when `<data>` is omitted; `--data-type dom` for DOM HTML) |
| `block move <id> --previous <id>` | Move a block after a sibling (or `--parent <id>` to nest it) |
| `block delete <id> --dangerous` | Delete a block (requires `--dangerous`) |
| `block get <id>` | Get block kramdown source |
| `block children <id>` | Get child blocks |
| `asset upload <file> [<file>...] [--dir /assets/]` | Upload local files as workspace assets |
| `attr get <id>` | Show every attribute of a block |
| `attr set <id> KEY=VALUE...` | Set block attributes (an empty value removes the key) |
| `attr unset <id> KEY...` | Remove block attributes |
| `sql <stmt>` | Execute SQL query |
| `search <query>` | Full-text search |
| `export md <doc-id>` | Export as Markdown |
| `tag list` | List all tags |
| `version` | Show SiYuan version |
| `status` | Show connection status |

All commands accept the global `--json` flag **before** the command
(`cli-anything-siyuan --json notebook list`) for machine-readable output.

## Running Tests

```bash
# Unit tests (no external dependencies)
cd agent-harness
pip install -e ".[test]"
python -m pytest cli_anything/siyuan/tests/test_core.py -v

# E2E tests (requires running SiYuan)
python -m pytest cli_anything/siyuan/tests/test_full_e2e.py -v -s
```

## License

AGPL-3.0 (same as SiYuan)
