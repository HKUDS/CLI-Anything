# Browser Harness: DOMShell MCP Integration

## Purpose

This harness provides browser automation using [DOMShell](https://github.com/apireno/DOMShell)'s MCP server. DOMShell maps Chrome's Accessibility Tree to a virtual filesystem, enabling filesystem-first browser automation with familiar shell commands (`ls`, `cd`, `cat`, `grep`, `click`).

## Architecture Overview

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   CLI Commands   │────▶│  browser_cli.py │────▶│   MCP Backend   │
│  (Click groups)  │     │  (CLI entry)    │     │ (domshell_      │
└─────────────────┘     └─────────────────┘     │  backend.py)    │
                                                 └────────┬────────┘
                                                          │
                    ┌─────────────────────────────────────┼────────────┐
                    │                                     │            │
                    ▼                                     ▼            ▼
            ┌───────────────┐                 ┌────────────┐    ┌──────────┐
            │ Spawn npx     │                 │  DOMShell  │    │  Chrome  │
            │ subprocess    │◀──stdio─────────▶│  MCP Server│◀───│ + Ext    │
            └───────────────┘                 └────────────┘    └──────────┘

State Management:
┌─────────────────────────────────────────────────────────────────┐
│  _session: Session                                              │
│    - current_url: str                                           │
│    - working_dir: str  (path in accessibility tree)            │
│    - history: list[str]  (for back/forward)                    │
│    - daemon_mode: bool  (persistent connection)                │
└─────────────────────────────────────────────────────────────────┘
```

## DOMShell MCP Server

DOMShell is an npm package that exposes Chrome's Accessibility Tree via MCP:

### Installation

```bash
# Verify DOMShell is available
npx @apireno/domshell --version

# Install Chrome extension
# https://chromewebstore.google.com/detail/domshell
```

### MCP Tools

DOMShell exposes these MCP tools:

| Tool | Description | CLI Command |
|------|-------------|-------------|
| `domshell_ls` | List directory contents | `fs ls` |
| `domshell_cd` | Change directory | `fs cd` |
| `domshell_cat` | Read element content | `fs cat` |
| `domshell_grep` | Search for pattern | `fs grep` |
| `domshell_click` | Click element | `act click` |
| `domshell_type` | Type text | `act type` |
| `domshell_open` | Navigate to URL | `page open` |
| `domshell_reload` | Reload page | `page reload` |
| `domshell_back` | Navigate back | `page back` |
| `domshell_forward` | Navigate forward | `page forward` |

## Key Design Decisions

### 1. MCP Backend Pattern (First in CLI-Anything)

This is the first CLI-Anything harness to use an MCP server as a backend.

**Backend wrapper** (`domshell_backend.py`):
- Uses `mcp` Python SDK with `stdio` transport
- Spawns `npx @apireno/domshell` subprocess per command
- Async MCP interface wrapped in sync functions via `asyncio.run()`

**Session management**:
- MCP server is stateless (spawned per command)
- CLI maintains state (URL, working directory, history)
- Daemon mode (`--daemon`) provides persistent connection

### 2. Daemon Mode

By default, each CLI command spawns a new MCP server process. This is simple but adds latency (~1-3s cold start).

**Daemon mode** (`--daemon` flag):
- Spawns MCP server once, reuses connection
- Much faster for interactive use
- Requires explicit `daemon-start`/`daemon-stop`

### 3. State Model

**Page state** (not project state):
- `current_url`: Currently loaded page
- `working_dir`: Current path in accessibility tree
- `history`: Back navigation stack
- `forward_stack`: Forward navigation stack

**No persistence**: State is in-memory only. Accessibility tree structure changes when pages update, so saving paths would be fragile.

### 4. Filesystem-First Commands

DOMShell's key insight: **filesystem primitives outperform DOM queries** for agents.

Compare:
```
# DOM query approach (selector-based)
await page.querySelector("#main button[type='submit']")

# Filesystem approach
ls /main
grep "submit"
click /main/button[0]
```

The filesystem approach is more discoverable and composable.

## Chrome DevTools Protocol

DOMShell uses Chrome's DevTools Protocol to access the Accessibility Tree:

### Accessibility Tree vs DOM

The Accessibility Tree is a simplified view of the DOM that:
- Filters out structural elements (divs, spans without semantic meaning)
- Includes computed accessible names and roles
- Flattens complex structures
- Provides stable IDs for screen readers

**Why use Accessibility Tree:**
- Stable: Page updates don't change structure as much as DOM
- Semantic: Roles and names are what screen readers use
- Agent-friendly: Flatter, simpler to navigate

**Tradeoffs:**
- Less granular than full DOM (can't access arbitrary divs)
- Chrome-dependent (requires extension)

## Path Syntax

DOMShell uses a filesystem-like path syntax:

```
/                           — Root (document)
/main                       — Main landmark (role="main")
/main/div[0]                — First div in main
/main/div[0]/button[2]      — Third button in first div
```

### Array Indexing

- **0-based**: `button[0]` is the first button
- **Relative paths**: `..` goes up one level
- **Root**: `/` is always the document root

### Special Paths

- `.` — Current directory
- `..` — Parent directory
- `/` — Root (document)

## Command Groups

### Page Commands (`page`)

| Command | Description | State Impact |
|---------|-------------|--------------|
| `open <url>` | Navigate to URL | Sets `current_url`, resets `working_dir` |
| `reload` | Reload current page | None |
| `back` | Navigate back | Pops `history`, pushes to `forward_stack` |
| `forward` | Navigate forward | Pops `forward_stack`, pushes to `history` |
| `info` | Show page info | None |

### Filesystem Commands (`fs`)

| Command | Description | State Impact |
|---------|-------------|--------------|
| `ls [path]` | List elements | None |
| `cd <path>` | Change directory | Sets `working_dir` |
| `cat [path]` | Read element | None |
| `grep <pat> [path]` | Search | None |
| `pwd` | Print working dir | None |

### Action Commands (`act`)

| Command | Description | State Impact |
|---------|-------------|--------------|
| `click <path>` | Click element | May trigger navigation |
| `type <path> <text>` | Type text | None |

### Session Commands (`session`)

| Command | Description | State Impact |
|---------|-------------|--------------|
| `status` | Show session state | None |
| `daemon-start` | Start daemon mode | Sets `daemon_mode=True` |
| `daemon-stop` | Stop daemon mode | Sets `daemon_mode=False` |

## Error Handling

### Dependency Checks

The CLI checks dependencies at startup:

```python
available, message = is_available()
if not available:
    print(f"Error: {message}")
    # Install instructions...
```

**Error messages:**
- "npx not found" → Install Node.js
- "DOMShell not found" → Run `npx @apireno/domshell --version`
- "DOMShell MCP call failed" → Install Chrome extension

### MCP Tool Failures

MCP tool failures raise `RuntimeError` with context:

```python
try:
    result = await session.call_tool(tool_name, arguments)
except Exception as e:
    raise RuntimeError(
        f"DOMShell MCP call failed: {e}\n"
        f"Ensure Chrome is running with DOMShell extension."
    )
```

## Testing Strategy

### Unit Tests (`test_core.py`)

- Mock MCP backend responses
- Test path resolution logic (`..`, relative paths)
- Test state management (history, working_dir)
- No Chrome required

### E2E Tests (`test_full_e2e.py`)

- Requires Chrome + DOMShell extension
- Test real web pages (example.com, etc.)
- Verify accessibility tree structure
- Test daemon lifecycle

### Test Scenarios

1. **Basic navigation**: Open → ls → cd → ls
2. **Search and act**: Open → grep → click
3. **Form interaction**: Open → type → click submit
4. **Daemon mode**: Start → ls → cd → stop
5. **Error paths**: Missing dependencies, invalid paths

## Performance Considerations

### Per-Command Overhead

Each command spawns `npx @apireno/domshell`:
- **Cold start**: 1-3 seconds (first run, package download)
- **Warm start**: ~100-500ms (subsequent runs)

**Mitigation**: Use daemon mode for interactive sessions.

### Accessibility Tree Size

Complex pages may have thousands of accessible elements:
- `ls /` on a large page could return 1000+ entries
- Use specific paths to limit results
- `grep` is more efficient than `ls` for finding elements

## Future Enhancements

**Not in scope for V1:**
- Screenshot capture
- Wait-for-element commands
- Form fill helper (bulk)
- Headless Chrome mode
- Multi-browser support (Firefox, Safari)
- Concurrent MCP operations (batch commands)

## References

- [DOMShell GitHub](https://github.com/apireno/DOMShell)
- [DOMShell Benchmark](https://github.com/apireno/DOMShell/tree/main/experiments/claude_domshell_vs_cic)
- [Chrome Accessibility Tree](https://developer.chrome.com/docs/accessibility/tree)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [CLI-Anything HARNESS.md](https://github.com/HKUDS/CLI-Anything/tree/main/cli-anything-plugin/HARNESS.md)

## Applying This Pattern

The MCP backend pattern can be applied to any software that exposes an MCP server:

| Software | MCP Server | Transport | Use Case |
|----------|------------|-----------|----------|
| DOMShell | `@apireno/domshell` | stdio | Browser automation |
| (future) | Various | stdio/SSE | Any MCP-compatible service |

**Pattern:**
1. Identify MCP server and tools
2. Create backend wrapper with `mcp` SDK
3. Map tools to CLI commands
4. Maintain state on CLI side (MCP is stateless per command)
5. Optional: Add daemon mode for persistent connection
