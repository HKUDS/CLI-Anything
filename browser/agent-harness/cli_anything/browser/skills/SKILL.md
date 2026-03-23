---
name: "cli-anything-browser"
description: "Browser automation CLI using DOMShell MCP server. Maps Chrome's Accessibility Tree to a virtual filesystem for agent-native navigation."
---

# cli-anything-browser

A command-line interface for browser automation using [DOMShell](https://github.com/apireno/DOMShell)'s MCP server. Navigate web pages using filesystem commands: `ls`, `cd`, `cat`, `grep`, `click`.

## Installation

### Prerequisites

1. **Node.js and npx** (for DOMShell MCP server):
   ```bash
   # Install Node.js from https://nodejs.org/
   npx --version
   ```

2. **Chrome/Chromium** with [DOMShell extension](https://chromewebstore.google.com/detail/domshell-browser-filesy/okcliheamhmijccjknkkplploacoidnp):
   - Install extension in Chrome
   - Ensure Chrome is running before using CLI

3. **Python 3.10+**

### Install CLI

```bash
cd browser/agent-harness
pip install -e .
```

## Command Groups

### `page` — Page Navigation

- `page open <url>` — Navigate to URL
- `page reload` — Reload current page
- `page back` — Navigate back in history
- `page forward` — Navigate forward in history
- `page info` — Show current page info

### `fs` — Filesystem Commands (Accessibility Tree)

- `fs ls [path]` — List elements at path
- `fs cd <path>` — Change directory
- `fs cat [path]` — Read element content
- `fs grep <pattern> [path]` — Search for text pattern
- `fs pwd` — Print working directory

### `act` — Action Commands

- `act click <path>` — Click an element
- `act type <path> <text>` — Type text into input

### `session` — Session Management

- `session status` — Show session state
- `session daemon-start` — Start persistent daemon mode
- `session daemon-stop` — Stop daemon mode

## Usage Examples

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
cli-anything-browser fs grep "Login"
cli-anything-browser act click /main/button[0]
```

### Form Fill

```bash
cli-anything-browser act type /main/input[0] "user@example.com"
cli-anything-browser act click /main/button[0]
```

### JSON Output

```bash
cli-anything-browser --json fs ls /
```

### Daemon Mode (Faster Interactive Use)

```bash
# Start persistent connection
cli-anything-browser session daemon-start

# Run commands (uses persistent connection)
cli-anything-browser fs ls /
cli-anything-browser fs cd /main

# Stop daemon when done
cli-anything-browser session daemon-stop
```

### Interactive REPL

```bash
cli-anything-browser
```

## Path Syntax

DOMShell uses a filesystem-like path for the Accessibility Tree:

```
/                           — Root (document)
/main                       — Main landmark
/main/div[0]                — First div in main
/main/div[0]/button[2]      — Third button in first div
```

- Array indices are **0-based**: `button[0]` is the first button
- Use `..` to go up one level
- Use `/` for root

## Agent-Specific Guidance

### JSON Output for Parsing

All commands support `--json` flag for machine-readable output:

```bash
cli-anything-browser --json fs ls /
```

Returns:
```json
{
  "path": "/",
  "entries": [
    {"name": "main", "role": "landmark", "path": "/main"}
  ]
}
```

### Error Handling

The CLI provides clear error messages for common issues:

- **npx not found**: Install Node.js from https://nodejs.org/
- **DOMShell not found**: Run `npx @apireno/domshell --version`
- **MCP call failed**: Install DOMShell Chrome extension

Check `is_available()` return value before running commands.

### Daemon Mode for Efficiency

For agent workflows with multiple commands, use daemon mode:

1. Start daemon: `cli-anything-browser session daemon-start`
2. Run commands: Each command reuses the MCP connection
3. Stop daemon: `cli-anything-browser session daemon-stop`

This avoids the 1-3 second cold start overhead for each command.

## Links

- [DOMShell GitHub](https://github.com/apireno/DOMShell)
- [CLI-Anything](https://github.com/HKUDS/CLI-Anything)
- [Issue #90](https://github.com/HKUDS/CLI-Anything/issues/90)
