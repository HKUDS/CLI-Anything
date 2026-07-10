# Obsidian CLI

A command-line interface for knowledge management and note-taking via the Obsidian Local REST API.
Designed for AI agents and power users who need to manage notes, search the vault, and execute commands without a GUI.

## Prerequisites

- Python 3.10+
- [Obsidian](https://obsidian.md) installed and running with the [Local REST API plugin](https://github.com/coddingtonbear/obsidian-local-rest-api) enabled
- `click` (CLI framework)
- `requests` (HTTP client)

Optional (for interactive REPL):
- `prompt_toolkit`

## Install Dependencies

```bash
pip install click requests prompt_toolkit
```

## How to Run

All commands are run from the `agent-harness/` directory, or via the installed entry point.

### One-shot commands

```bash
# Show help
cli-anything-obsidian --help

# List vault files
cli-anything-obsidian vault list

# Read a note
cli-anything-obsidian vault read "Notes/my-note.md"

# Search the vault
cli-anything-obsidian search simple "meeting notes"

# JSON output (for agent consumption)
cli-anything-obsidian --json server status
```

### Interactive REPL

```bash
cli-anything-obsidian
# Enter commands interactively with tab-completion and history
```

Inside the REPL, type `help` for all available commands.

## Command Reference

### Vault

```bash
vault list [path]                           # List files in the vault (or subdirectory)
vault read <path>                           # Read note content
vault create <path> --content "..."        # Create a new note
vault update <path> --content "..."        # Overwrite a note
vault delete <path>                         # Delete a note
vault append <path> --content "..."        # Append content to a note
```

### Search

```bash
# Dataview DQL (default) — body is sent verbatim with
# Content-Type: application/vnd.olrapi.dataview.dql+txt
search query 'TABLE file.link FROM "Projects"'

# JsonLogic — Content-Type: application/vnd.olrapi.jsonlogic+json
search query --type jsonlogic '{"==":[{"var":"frontmatter.status"},"active"]}'

# Plain text search across the vault (GET /search/simple/)
search simple <query>
```

### Note

```bash
note active                                 # Get the currently active note
note open <path>                            # Open a note in Obsidian
```

### Command

```bash
command list                                # List all available Obsidian commands
command execute <id>                        # Execute a command by ID
```

### Server

```bash
server status                               # Check if Obsidian Local REST API is running
```

### Session

```bash
session status                              # Show session state
```

## JSON Mode

Add `--json` before the subcommand for machine-readable output:

```bash
cli-anything-obsidian --json vault list
cli-anything-obsidian --json search simple "project ideas"
```

## API Key

Provide your Obsidian Local REST API key via flag or environment variable:

```bash
# Via flag
cli-anything-obsidian --api-key YOUR_KEY vault list

# Via environment variable
export OBSIDIAN_API_KEY=YOUR_KEY
cli-anything-obsidian vault list
```

## Example Workflow

```bash
# Check server
cli-anything-obsidian server status

# List all notes
cli-anything-obsidian vault list

# Read a specific note
cli-anything-obsidian vault read "Daily Notes/2024-01-15.md"

# Create a new note
cli-anything-obsidian vault create "Projects/new-project.md" --content "# New Project\n\nProject notes here."

# Search for notes
cli-anything-obsidian search simple "quarterly review"

# Append to a note
cli-anything-obsidian vault append "Projects/new-project.md" --content "\n## Update\nProgress notes."

# Open a note in Obsidian
cli-anything-obsidian note open "Projects/new-project.md"

# Execute a command
cli-anything-obsidian command list
cli-anything-obsidian command execute "editor:toggle-bold"

# Clean up
cli-anything-obsidian vault delete "Projects/new-project.md"
```

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

## Running Tests

```bash
cd agent-harness
python -m pytest cli_anything/obsidian/tests/test_core.py -v        # Unit tests (no Obsidian needed)
python -m pytest cli_anything/obsidian/tests/test_full_e2e.py -v    # E2E tests (requires Obsidian)
python -m pytest cli_anything/obsidian/tests/ -v                     # All tests
```

## Version

1.0.0
