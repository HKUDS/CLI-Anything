---
name: "cli-anything-safari"
description: >-
  Safari browser automation CLI on macOS via safari-mcp. Controls real Safari
  (native, keeps logins) by wrapping the safari-mcp MCP server. Every one of
  the 84 MCP tools is exposed 1:1 with schema-accurate arguments — guaranteed
  parity, no manual drift.
---

# cli-anything-safari

A command-line interface for Safari browser automation on macOS. Wraps the
[`safari-mcp`](https://github.com/achiya-automation/safari-mcp) Node.js MCP
server in a Python Click CLI.

**Feature parity is guaranteed.** Every Click command is generated
automatically from `safari-mcp`'s tool schema (bundled as
`resources/tools.json`). All 84 tools are reachable with the exact
argument names and types the MCP server expects.

## When to use this CLI

Each CLI invocation spawns a fresh subprocess, so there is per-call
overhead. If your agent speaks MCP natively (Claude Code, Cursor, Cline,
etc.), using `safari-mcp` directly over MCP stdio will be faster.

**Use this CLI when:**
- Your agent framework does **not** speak MCP (Codex CLI, GitHub Copilot
  CLI, custom scripts, older agent frameworks).
- You need to **script browser automation from bash** —
  `cli-anything-safari --json tool snapshot | jq '...'`.
- You run in **CI/CD** and want cron-able, subprocess-friendly output.
- You're **debugging interactively** from Terminal.

## Installation

### Prerequisites

1. **macOS** — Safari MCP is macOS-only.
2. **Safari** — already installed on macOS.
3. **Node.js 18+** — `brew install node` or from https://nodejs.org/
4. **Python 3.10+**
5. **Enable Apple Events for Safari**: Safari → Develop → Allow JavaScript from Apple Events

### Install the CLI

```bash
cd safari/agent-harness
pip install -e .
```

The first `tool` call will download the `safari-mcp` npm package (one-time, a few MB).

## Command Structure

The CLI has 5 top-level commands:

| Command   | Purpose                                                           |
|-----------|-------------------------------------------------------------------|
| `tool`    | Call any of safari-mcp's **84 tools** (dynamic, schema-driven)    |
| `tools`   | Inspect the bundled tool registry (`list`, `describe`, `count`)   |
| `raw`     | Escape hatch — call a tool by full name with raw JSON args        |
| `session` | In-memory session state (last URL, current tab)                   |
| `repl`    | Interactive REPL (default when no subcommand given)               |

## Usage Examples

### Discover the tool surface

```bash
# Count of tools (sanity check — must match safari-mcp's registered tools)
cli-anything-safari tools count
# → 84

# List every tool
cli-anything-safari tools list
cli-anything-safari tools list --filter click   # filter by substring

# Full schema for one tool (JSON or human format)
cli-anything-safari tools describe safari_scroll
cli-anything-safari --json tools describe safari_click
```

### Call a tool (schema-driven)

```bash
# Navigate
cli-anything-safari tool navigate --url https://example.com

# Take a snapshot (preferred over screenshot — structured text with ref IDs)
cli-anything-safari --json tool snapshot

# Click by ref (refs come from snapshot; they expire on the next snapshot!)
cli-anything-safari tool click --ref 0_5

# Click by selector or visible text
cli-anything-safari tool click --selector "#submit"
cli-anything-safari tool click --text "Log in"

# Fill a field
cli-anything-safari tool fill --selector "#email" --value "user@example.com"

# Scroll by direction/amount (NOT x/y — note the schema!)
cli-anything-safari tool scroll --direction down --amount 500

# Drag one element onto another
cli-anything-safari tool drag \
    --source-selector ".card" \
    --target-selector ".trash"

# Screenshot — returns base64 JPEG in stdout. Decode with:
cli-anything-safari --json tool screenshot --full-page \
    | python3 -c "import sys,json,base64; \
        d=json.load(sys.stdin); \
        open('/tmp/shot.jpg','wb').write(base64.b64decode(d['data']))"

# Save as PDF (this one writes to disk directly)
cli-anything-safari tool save-pdf --path /tmp/page.pdf

# Evaluate JavaScript (note: parameter is --script, not --code)
cli-anything-safari tool evaluate --script "document.title"
```

### Navigate and read in one round-trip

```bash
cli-anything-safari --json tool navigate-and-read --url https://example.com
```

### Form fill (bulk)

`safari_fill_form` takes an **array** of `{selector, value}` objects.
Pass it as a JSON string:

```bash
cli-anything-safari tool fill-form --fields '[
  {"selector": "#email",    "value": "user@example.com"},
  {"selector": "#password", "value": "hunter2"}
]'
```

Run `cli-anything-safari tools describe safari_fill_form` to see the
exact schema, including any new fields safari-mcp adds upstream.

### Network monitoring

```bash
cli-anything-safari tool start-network-capture
cli-anything-safari tool navigate --url https://example.com
cli-anything-safari --json tool network
cli-anything-safari tool performance-metrics
```

### Storage

```bash
cli-anything-safari tool get-cookies
cli-anything-safari tool set-cookie --name session --value abc123 --domain example.com
cli-anything-safari tool local-storage --key theme
# export-storage returns JSON to stdout — no --path arg. Pipe to a file:
cli-anything-safari --json tool export-storage > /tmp/storage.json
```

### Raw JSON escape hatch

When you need to pass a complex nested object or want to drive the CLI from
a pre-built JSON blob:

```bash
cli-anything-safari raw safari_evaluate \
    --json-args '{"code":"[...document.querySelectorAll(\"a\")].map(a => a.href)"}'
```

### Interactive REPL

```bash
cli-anything-safari
```

The REPL banner prints the absolute path to this SKILL.md so agents can
self-discover capabilities.

## JSON Output

All commands support `--json` as a global flag:

```bash
cli-anything-safari --json tool snapshot
cli-anything-safari --json tool list-tabs
cli-anything-safari --json tools list
```

## State Management

The CLI maintains a small amount of in-memory state for REPL display only:

- **`last_url`** — last URL the CLI navigated to (updated after every
  successful `tool navigate`, `tool navigate-and-read`, or
  `tool new-tab`)
- **`current_tab_index`** — last known active tab index

There is **no persistent session**, no undo/redo, no document model.
Every CLI invocation starts with fresh state. Safari MCP itself is
stateless per-call: each `tool` command spawns a fresh
`npx safari-mcp` subprocess, performs the action, and exits. This is a
deliberate design choice; see `HARNESS.md` and `TEST.md` for the
reasoning behind the deviation from the standard undo/redo pattern.

## Output Formats

All commands support dual output modes:

- **Human-readable** (default): indented key-value text for `dict`
  results, bullet lists for arrays, plain text otherwise
- **Machine-readable** (`--json` flag): structured JSON for agent
  consumption

```bash
# Human output
cli-anything-safari tool snapshot

# JSON output for agents
cli-anything-safari --json tool snapshot
cli-anything-safari --json tools list
cli-anything-safari --json tools describe safari_click
```

## For AI Agents

When using this CLI programmatically:

1. **Always use `--json` flag** for parseable output.
2. **Check return codes** — 0 for success, non-zero for errors (URL
   validation failures, MCP call failures, invalid JSON args).
3. **Parse stderr** for error messages; use stdout for data.
4. **File-handling tools have inconsistent path arg names** — always
   check `tools describe <name>` first:
   - `tool save-pdf --path /tmp/x.pdf`
   - `tool upload-file --selector ... --file-path /tmp/x.txt` (note: `--file-path`, not `--path`)
   - `tool export-storage` — no path arg; pipe JSON output to a file
   - `tool import-storage --path /tmp/x.json`
   - `tool screenshot` / `screenshot-element` — return base64 in
     the JSON response, no path arg (decode it yourself)
5. **Snapshot before click** — refs from `tool snapshot` expire on the
   next snapshot. Always snapshot → find ref → click in close
   succession.
6. **Discover tools via `tools list`** — the bundled registry is the
   source of truth for what's available. Do not hard-code tool names
   that may change upstream.
7. **Use `tools describe <name>`** to learn the exact schema (required
   args, enum choices, JSON-typed args) before constructing a call.
   **Never assume parameter names from the description** — for example,
   `safari_evaluate` takes `--script` (not `--code`) even though the
   description says "JavaScript code to execute".

## Agent-Specific Guidance

### Finding the right tool

Use the introspection commands. The CLI is **guaranteed** to reflect the
MCP server 1:1:

```bash
# Find all click-related tools
cli-anything-safari tools list --filter click

# Get the full schema (including every argument with type, description,
# required/optional, enum choices, defaults)
cli-anything-safari --json tools describe safari_click
```

### Tool selection strategy

1. **`tool snapshot`** over `tool screenshot` — structured text with ref IDs
   is orders of magnitude cheaper and carries the refs needed for clicks.
2. **`tool click --ref`** over `tool click --selector` — refs are stable
   within a single snapshot, selectors may be brittle.
3. **`tool navigate-and-read`** over `navigate` + `read-page` — saves one
   round-trip.
4. **`tool click-and-read`** over `click` + `read-page` — saves one round-trip.
5. **`tool native-click`** only when regular click fails with 405/403 (WAF
   blocks, G2, Cloudflare) — it physically moves the cursor.

### Refs Expire

Refs from `tool snapshot` expire when you take a new snapshot:
- First snapshot: refs `0_1`, `0_2`, `0_3`...
- Second snapshot: refs `1_1`, `1_2`, `1_3`...

Always snapshot → click in close succession. If in doubt, snapshot again.

### Tab Ownership Safety

Safari MCP tracks tab ownership per session. Tools that modify a tab
(navigate, click, fill) are **blocked** on tabs the session did not open.
To operate on a specific page, always start with `tool new-tab --url ...`.

### Error Handling

Common errors:
- `npx not found` → install Node.js 18+
- `safari-mcp package not found on npm registry` → check network
- `Not macOS` → harness is macOS-only
- `AppleScript denied` → enable "Allow JavaScript from Apple Events" in Safari → Develop
- `Blocked URL scheme: file` → URL validation rejected the input (by design)

### URL Validation

The CLI validates URLs before passing them to `safari_navigate`,
`safari_navigate_and_read`, and `safari_new_tab`. Blocked schemes:
`file`, `javascript`, `data`, `vbscript`, `about`, `chrome`, `safari`,
`webkit`, `x-apple`, and other browser-internal schemes. The `raw`
command **also** enforces this for navigation tools.

### Multi-Session Warning

Safari MCP enforces a single active session by killing stale Node.js
processes older than 10 seconds. If you run two CLI instances at once,
one will kill the other's backend. **There is currently no daemon
mode** — for latency-sensitive workflows, drive the CLI from a
long-lived Python script that imports
``cli_anything.safari.utils.safari_backend.call()`` directly to avoid
re-spawning the subprocess on every invocation.

## Links

- [Safari MCP GitHub](https://github.com/achiya-automation/safari-mcp)
- [Safari MCP on npm](https://www.npmjs.com/package/safari-mcp)
- [CLI-Anything](https://github.com/HKUDS/CLI-Anything)
- [MCP Backend Pattern Guide](https://github.com/HKUDS/CLI-Anything/blob/main/cli-anything-plugin/guides/mcp-backend.md)

## Security Considerations

### URL Validation

All navigation tools (`tool navigate`, `tool navigate-and-read`, `tool
new-tab`, and `raw safari_navigate*`) pass the `url` argument through
`utils/security.py` which blocks dangerous schemes and optionally blocks
private networks (set `CLI_ANYTHING_SAFARI_BLOCK_PRIVATE=1`).

### Tab Isolation

Safari MCP enforces per-session tab ownership upstream — tools cannot
operate on tabs the session did not open.

### Profile Isolation

Set `SAFARI_PROFILE` env var to use a separate Safari profile for
automation:

```bash
export SAFARI_PROFILE="Automation"
cli-anything-safari tool navigate --url https://example.com
```

This keeps cookies/logins/history separate from the user's main browsing.

### JavaScript Execution

`tool evaluate` and `tool run-script` run arbitrary JavaScript in the page
context. Treat untrusted input with the same care as any dynamic code
execution path.

### Clipboard

`tool clipboard-read` and `tool clipboard-write` touch the system
clipboard. Be careful when running inside a user's active session —
overwriting the clipboard mid-task is disruptive.

## Regenerating the tool registry

If you upgrade `safari-mcp`, regenerate the bundled schema:

```bash
python scripts/extract_tools.py \
    "$(npm root -g)/safari-mcp/index.js" \
    cli_anything/safari/resources/tools.json
```

The parity test (`test_parity.py`) pins the expected tool count; update
it when the upstream tool list changes.

## More Information

- **Full documentation:** `cli_anything/safari/README.md` in the package
- **Test coverage:** `cli_anything/safari/tests/TEST.md` in the package
- **Architecture analysis:** `safari/agent-harness/SAFARI.md`
- **Methodology:** `cli-anything-plugin/HARNESS.md`
- **MCP backend pattern:** `cli-anything-plugin/guides/mcp-backend.md`

## Version

1.0.0 — targets safari-mcp 2.7.8 (84 tools). Bundled tool registry is
regenerated via `scripts/extract_tools.py` when safari-mcp upgrades.
