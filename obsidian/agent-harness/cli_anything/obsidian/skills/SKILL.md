---
name: >-
  cli-anything-obsidian
description: >-
  Command-line interface for Obsidian — Knowledge management and note-taking via Obsidian Local REST API. Use to list/open vaults, read/write/search notes, manage daily notes, list tags, and run Obsidian commands. Requires Obsidian running with the Local REST API plugin.
---

# cli-anything-obsidian

Knowledge management and note-taking via the Obsidian Local REST API. Designed for AI agents and power users who need to manage notes, search the vault, and execute commands without the GUI.

## Installation

This CLI is installed as part of the cli-anything-obsidian package:

```bash
# Installed on this machine via uv tool (patched v1.2.0 from ~/work/.worktrees/cli-obsidian)
command -v cli-anything-obsidian
# Upstream: cli-hub install obsidian
```

**Prerequisites:**
- Python 3.10+
- Obsidian must be installed and running with the [Local REST API plugin](https://github.com/coddingtonbear/obsidian-local-rest-api) enabled
- API key: Obsidian > Settings > Local REST API (also stored in `<vault>/.obsidian/plugins/obsidian-local-rest-api/data.json` as `apiKey`). Export it as `OBSIDIAN_API_KEY`.
- The REST API serves whichever vault is currently open in Obsidian. Use `vaults open NAME` to switch.
- `vaults list`, `vaults open`, and `daily path` work without the API.


## Usage

### Basic Commands

```bash
# Show help
cli-anything-obsidian --help

# Start interactive REPL mode
cli-anything-obsidian

# List vault files
cli-anything-obsidian vault list

# Run with JSON output (for agent consumption)
cli-anything-obsidian --json vault list
```

### REPL Mode

When invoked without a subcommand, the CLI enters an interactive REPL session:

```bash
cli-anything-obsidian
# Enter commands interactively with tab-completion and history
```


## Command Groups


### Vault

Vault file management commands.

| Command | Description |
|---------|-------------|
| `list` | List files in the vault or a subdirectory |
| `read` | Read the content of a note |
| `create` | Create a new note |
| `update` | Overwrite an existing note |
| `delete` | Delete a note from the vault |
| `append` | Append content to an existing note |


### Search

Vault search commands.

| Command | Description |
|---------|-------------|
| `query` | Search using Obsidian query syntax |
| `simple` | Plain text search across the vault |


### Note

Active note commands.

| Command | Description |
|---------|-------------|
| `active` | Get the currently active note in Obsidian |
| `open` | Open a note in the Obsidian editor (`--new-leaf` for a new tab) |


### Vaults (local, no API key)

| Command | Description |
|---------|-------------|
| `list` | List vaults registered in the Obsidian app (name, path, open) |
| `open NAME [--file NOTE] [--print-only]` | Open/switch vault via `obsidian://open` URI |


### Daily

Daily notes live at `<folder>/YYYY-MM-DD.md`. Folder from `--folder` or env `OBSIDIAN_DAILY_FOLDER` (default vault root). `--date YYYY-MM-DD` defaults to today.

| Command | Description |
|---------|-------------|
| `path` | Print the daily note path |
| `list` | List existing daily notes in the folder |
| `create [-c TEXT]` | Create if missing (never overwrites); returns `created: true/false` |
| `read` | Read the daily note |
| `append -c TEXT` | Append a new line (creates the note first if missing) |


### Tags

| Command | Description |
|---------|-------------|
| `list` | All tags in the vault with counts |


### Command

Obsidian command palette commands.

| Command | Description |
|---------|-------------|
| `list` | List all available Obsidian commands |
| `execute` | Execute a command by its ID |


### Server

Server status and info commands.

| Command | Description |
|---------|-------------|
| `status` | Check if the Obsidian Local REST API is running |


### Session

Session state commands.

| Command | Description |
|---------|-------------|
| `status` | Show current session state |



## Examples


### List and Read Notes

```bash
# List all vault files
cli-anything-obsidian vault list

# List files in a subdirectory
cli-anything-obsidian vault list "Daily Notes"

# Read a note
cli-anything-obsidian vault read "Projects/my-project.md"
```


### Create and Update Notes

```bash
# Create a new note
cli-anything-obsidian vault create "Projects/new-project.md" --content "# New Project"

# Update (overwrite) a note
cli-anything-obsidian vault update "Projects/new-project.md" --content "# Updated Content"

# Append to a note
cli-anything-obsidian vault append "Projects/new-project.md" --content "\n## New Section"
```


### Search

```bash
# Plain text search (GET /search/simple/)
cli-anything-obsidian search simple "meeting notes"

# Dataview DQL query — default --type dql, sent as
# application/vnd.olrapi.dataview.dql+txt
cli-anything-obsidian search query 'TABLE file.link FROM "Projects"'

# JsonLogic query — application/vnd.olrapi.jsonlogic+json
cli-anything-obsidian search query --type jsonlogic \
  '{"==":[{"var":"frontmatter.status"},"active"]}'
```


### Vaults, Daily Notes, Tags

```bash
cli-anything-obsidian --json vaults list
cli-anything-obsidian vaults open "My Vault" --file "Inbox.md"
cli-anything-obsidian --json daily create --folder "Daily"
cli-anything-obsidian daily append --folder "Daily" -c "- [ ] follow up"
cli-anything-obsidian --json tags list
```

Links/backlinks: use `search simple "[[Note Name]]"` or a DQL query (`LIST FROM [[Note Name]]`, needs Dataview).

Note: `vault append` concatenates verbatim; start `--content` with `\n` for a new line (`daily append` adds it for you).


### Commands

```bash
# List available commands
cli-anything-obsidian command list

# Execute a command by ID
cli-anything-obsidian command execute "editor:toggle-bold"
```


### Interactive REPL Session

Start an interactive session for exploratory use.

```bash
cli-anything-obsidian
# Enter commands interactively
# Use 'help' to see available commands
```


### API Key Configuration

```bash
# Via flag
cli-anything-obsidian --api-key YOUR_KEY vault list

# Via environment variable (recommended for agents)
export OBSIDIAN_API_KEY=YOUR_KEY
cli-anything-obsidian vault list
```


## State Management

The CLI maintains lightweight session state:

- **API key**: Configurable via `--api-key` or `OBSIDIAN_API_KEY` environment variable
- **Host URL**: Defaults to `https://localhost:27124`; configurable via `--host`

## Output Formats

All commands support dual output modes:

- **Human-readable** (default): Tables, colors, formatted text
- **Machine-readable** (`--json` flag): Structured JSON for agent consumption

```bash
# Human output
cli-anything-obsidian vault list

# JSON output for agents
cli-anything-obsidian --json vault list
```

## For AI Agents

When using this CLI programmatically:

1. **Always use `--json` flag** for parseable output
2. **Check return codes** - 0 for success, non-zero for errors
3. **Parse stderr** for error messages on failure
4. **Set `OBSIDIAN_API_KEY`** environment variable to avoid passing `--api-key` on every call
5. **Verify Obsidian is running** with `server status` before other commands

## More Information

- Full documentation: See README.md in the package
- Test coverage: See TEST.md in the package
- Methodology: See HARNESS.md in the cli-anything-plugin

## Version

1.2.0
