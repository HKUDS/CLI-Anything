# cli-anything-browser — Browser Automation CLI

A command-line interface for browser automation using [DOMShell](https://github.com/apireno/DOMShell)'s MCP server. Maps Chrome's Accessibility Tree to a virtual filesystem for agent-native browser automation.

## Features

- **Filesystem-first navigation**: Use `ls`, `cd`, `cat` to explore web pages
- **Search**: `grep` for text patterns in the accessibility tree
- **Actions**: `click`, `type` to interact with elements
- **JSON output**: `--json` flag for machine-readable output
- **Interactive REPL**: Stateful session with command history
- **Daemon mode**: Optional persistent connection for faster interactive use

## Installation

### Prerequisites

1. **Node.js and npx** (required for DOMShell MCP server):
   ```bash
   # Install Node.js from https://nodejs.org/
   node --version
   npx --version
   ```

2. **Chrome/Chromium** with DOMShell extension:
   - Install DOMShell from [Chrome Web Store](https://chromewebstore.google.com/detail/domshell-%E2%80%94-browser-filesy/okcliheamhmijccjknkkplploacoidnp)
   - Ensure Chrome is running before using the CLI

3. **Python 3.10+**:
   ```bash
   python --version
   ```

### Install CLI

```bash
cd browser/agent-harness
pip install -e .
```

Verify installation:
```bash
cli-anything-browser --help
```

## Usage

### One-Shot Commands

```bash
# Open a page
cli-anything-browser page open https://example.com

# List elements at root
cli-anything-browser fs ls /

# Navigate into a section
cli-anything-browser fs cd /main

# List elements in current directory
cli-anything-browser fs ls

# Read element content
cli-anything-browser fs cat /main/button[0]

# Search for text
cli-anything-browser fs grep "Login"

# Click an element
cli-anything-browser act click /main/button[0]

# Type into an input
cli-anything-browser act type /main/input[0] "Hello, World!"

# Get page info
cli-anything-browser page info

# Navigate back/forward
cli-anything-browser page back
cli-anything-browser page forward
```

**Note:** One-shot commands each start with a fresh session (no URL or working directory). For stateful workflows (like `cd` followed by `ls` without a path), use the REPL instead.

### JSON Output

```bash
# Get machine-readable output
cli-anything-browser --json fs ls /

# Returns:
{
  "path": "/",
  "entries": [
    {
      "name": "main",
      "role": "landmark",
      "path": "/main"
    }
  ]
}
```

### Daemon Mode (Persistent Connection)

For faster interactive use, start daemon mode within a REPL session:

```bash
# Start REPL with daemon mode
cli-anything-browser --daemon

# Or start daemon within REPL
session daemon-start

# Run commands (uses persistent connection)
fs ls /
fs cd /main

# Stop daemon when done
session daemon-stop
```

**Note:** Daemon mode only works within a single running process (REPL or `--daemon` flag). State does not persist across separate CLI invocations.

### Interactive REPL

Run without arguments to enter interactive mode:

```bash
cli-anything-browser
```

REPL commands:
- `page open <url>` — Open a URL
- `fs ls [path]` — List elements
- `fs cd <path>` — Change directory
- `fs cat [path]` — Read element
- `fs grep <pattern>` — Search for text
- `fs pwd` — Print working directory
- `act click <path>` — Click element
- `act type <path> <text>` — Type text
- `session status` — Show session state
- `help` — Show commands
- `quit` — Exit REPL

## Command Groups

### `page` — Page Navigation
- `open <url>` — Navigate to URL
- `reload` — Reload current page
- `back` — Navigate back in history
- `forward` — Navigate forward in history
- `info` — Show current page info

### `fs` — Filesystem Commands
- `ls [path]` — List elements at path
- `cd <path>` — Change directory
- `cat [path]` — Read element content
- `grep <pattern> [path]` — Search for text
- `pwd` — Print working directory

### `act` — Action Commands
- `click <path>` — Click an element
- `type <path> <text>` — Type text into input

### `session` — Session Management
- `status` — Show session status
- `daemon-start` — Start persistent daemon mode
- `daemon-stop` — Stop daemon mode

## Path Syntax

DOMShell uses a filesystem-like path syntax for the Accessibility Tree:

```
/                           — Root (page)
/main                       — Main landmark
/main/div[0]                — First div in main
/main/div[0]/button[2]      — Third button in first div
```

Array indices are 0-based. Use relative paths with `..` to go up.

## Examples

### Basic Navigation
```bash
# Open a page
cli-anything-browser page open https://example.com

# Explore structure
cli-anything-browser fs ls /
cli-anything-browser fs cd /main
cli-anything-browser fs ls

# Go back to root
cli-anything-browser fs cd /
```

### Search and Click
```bash
# Open page and search for login button
cli-anything-browser page open https://example.com/login
cli-anything-browser fs grep "Login"

# Click the login button (adjust path as needed)
cli-anything-browser act click /main/button[0]
```

### Form Fill
```bash
# Type into form fields
cli-anything-browser act type /main/input[0] "user@example.com"
cli-anything-browser act type /main/input[1] "password123"

# Click submit
cli-anything-browser act click /main/button[0]
```

## Testing

Run tests:

```bash
# Unit tests (no Chrome required)
pytest cli_anything/browser/tests/test_core.py -v

# E2E tests (requires Chrome + DOMShell)
pytest cli_anything/browser/tests/test_full_e2e.py -v
```

## Troubleshooting

### "npx not found"
Install Node.js from https://nodejs.org/

### "DOMShell not found"
Run: `npx @apireno/domshell --version` (first run downloads the package)

### "DOMShell MCP call failed"
- Ensure Chrome is running
- Install DOMShell extension from Chrome Web Store
- Check that DOMShell is enabled in Chrome
- Verify `DOMSHELL_TOKEN` matches the token used by the running DOMShell server

### Commands hang on first use
First `npx` call downloads DOMShell package (10-50 MB). Subsequent calls are faster. Use `--daemon` mode for persistent connection.

If the server is unreachable or auth token is wrong, MCP calls now fail with timeout instead of hanging forever.
Set timeout (seconds) via:

```bash
export CLI_ANYTHING_BROWSER_MCP_TIMEOUT=20
```

## Architecture

This CLI follows the [CLI-Anything harness methodology](https://github.com/HKUDS/CLI-Anything/tree/main/cli-anything-plugin/HARNESS.md):

- **Backend**: DOMShell MCP server via stdio transport
- **State**: Page state (URL, working directory, navigation history)
- **Pattern**: Filesystem-first commands map to Accessibility Tree

## Links

- [DOMShell GitHub](https://github.com/apireno/DOMShell)
- [CLI-Anything](https://github.com/HKUDS/CLI-Anything)
- [Issue #90](https://github.com/HKUDS/CLI-Anything/issues/90)

## License

MIT License — See [CLI-Anything](https://github.com/HKUDS/CLI-Anything) for details.
