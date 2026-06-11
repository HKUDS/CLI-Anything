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
```

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

## Command Groups

| Command | Description |
|---------|-------------|
| `notebook list` | List all notebooks |
| `notebook create <name>` | Create a notebook |
| `notebook rename <id> <name>` | Rename a notebook |
| `notebook remove <id>` | Delete a notebook |
| `notebook open <id>` | Open a notebook |
| `doc create <notebook-id> <path>` | Create a document |
| `doc list <notebook-id> [path]` | List documents |
| `doc tree <notebook-id>` | Show document tree |
| `doc get <id>` | Get document path by ID |
| `doc rename <id> <title>` | Rename a document |
| `doc remove <id>` | Delete a document |
| `block insert <data>` | Insert a block (use `-` or omit for stdin pipe) |
| `block update <id> <data>` | Update block content (use `-` or omit for stdin pipe) |
| `block delete <id>` | Delete a block |
| `block get <id>` | Get block kramdown source |
| `block children <id>` | Get child blocks |
| `sql <stmt>` | Execute SQL query |
| `search <query>` | Full-text search |
| `export md <doc-id>` | Export as Markdown |
| `tag list` | List all tags |
| `version` | Show SiYuan version |
| `status` | Show connection status |

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
