# cli-anything-iterm2

A stateful CLI harness for [iTerm2](https://iterm2.com) — gives AI agents (and humans) full programmatic control over a running iTerm2 instance from the command line.

Part of the [CLI-Anything](https://github.com/HKUDS/CLI-Anything) ecosystem.

---

## What it does

iTerm2 has a powerful Python API, but using it directly requires writing async Python scripts for every operation. `cli-anything-iterm2` wraps the entire API into a clean, composable CLI with structured JSON output — so agents can drive iTerm2 the same way a human would, without screenshots or UI automation.

```bash
# Send a command to the focused terminal
cli-anything-iterm2 session send "git status"

# Read what's on screen
cli-anything-iterm2 --json session screen

# Split the pane and start a server in the new one
cli-anything-iterm2 session split --vertical --use-as-context
cli-anything-iterm2 session send "python3 -m http.server 8000"

# Broadcast a keypress to every pane at once
cli-anything-iterm2 broadcast all-panes
cli-anything-iterm2 session send "clear"
```

---

## Prerequisites

**1. macOS + iTerm2 running**
```bash
brew install --cask iterm2
```

**2. Enable the Python API in iTerm2**
```
iTerm2 → Preferences → General → Magic → Enable Python API ✓
```

**3. Python 3.10+**

---

## Installation

```bash
pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=iterm2/agent-harness
```

From source (for development):
```bash
git clone https://github.com/HKUDS/CLI-Anything.git
cd CLI-Anything/iterm2/agent-harness
pip install -e .
```

Verify:
```bash
cli-anything-iterm2 --help
```

---

## Command Groups

| Group | What it controls |
|-------|-----------------|
| `app` | Workspace snapshot, app status, context management, app-level variables, modal dialogs, file panels |
| `window` | Create, list, close, resize, fullscreen windows |
| `tab` | Create, list, close, activate tabs; navigate split panes by direction |
| `session` | Send text, inject raw bytes, read screen, full scrollback, split panes, prompt detection |
| `profile` | List profiles, get profile details, list and apply color presets |
| `arrangement` | Save and restore complete window layouts |
| `tmux` | Full `tmux -CC` integration: bootstrap, connections, windows, send commands |
| `broadcast` | Sync keystrokes across multiple panes via broadcast domains |
| `menu` | Invoke any iTerm2 menu item programmatically |
| `pref` | Read and write global iTerm2 preferences; tmux integration settings |

---

## Usage

### Syntax

```bash
cli-anything-iterm2 [--json] <group> <command> [OPTIONS] [ARGS]
```

Use `--json` for machine-readable output. Every command supports it.

### App & context

```bash
cli-anything-iterm2 --json app snapshot         # rich workspace orientation: path, process, role, last output per pane
cli-anything-iterm2 app status                  # lightweight window/tab/session inventory
cli-anything-iterm2 app current                 # focus + save context
cli-anything-iterm2 app context                 # show saved context
cli-anything-iterm2 app get-var hostname        # read app-level variable
```

### Windows

```bash
cli-anything-iterm2 window list
cli-anything-iterm2 window create --profile "Default"
cli-anything-iterm2 window create --command "python3"
cli-anything-iterm2 window activate <window-id>
cli-anything-iterm2 window set-title "My Window"
cli-anything-iterm2 window fullscreen on
cli-anything-iterm2 window frame                # get/set x/y/w/h
cli-anything-iterm2 window close <window-id>
```

### Tabs

```bash
cli-anything-iterm2 tab list
cli-anything-iterm2 tab create --window-id <id>
cli-anything-iterm2 tab activate <tab-id>
cli-anything-iterm2 tab close <tab-id>
```

### Sessions (panes)

```bash
cli-anything-iterm2 session list
cli-anything-iterm2 session send "echo hello"           # sends with newline
cli-anything-iterm2 session send "text" --no-newline
cli-anything-iterm2 session screen                      # visible terminal output
cli-anything-iterm2 session screen --lines 20
cli-anything-iterm2 session scrollback --tail 200       # full scrollback history
cli-anything-iterm2 session scrollback --tail 200 --strip  # strip ANSI codes
cli-anything-iterm2 session split                       # horizontal split
cli-anything-iterm2 session split --vertical            # vertical split
cli-anything-iterm2 session split --vertical --use-as-context
cli-anything-iterm2 session set-name "API Worker"
cli-anything-iterm2 session restart
cli-anything-iterm2 session resize --columns 220 --rows 50
cli-anything-iterm2 session selection                   # get selected text
cli-anything-iterm2 session get-var hostname            # session variable
cli-anything-iterm2 session set-var user.project "myapp"
```

### Shell integration (requires iTerm2 Shell Integration installed)

```bash
cli-anything-iterm2 session wait-prompt                 # block until shell prompt appears
cli-anything-iterm2 session wait-command-end            # block until running command finishes
cli-anything-iterm2 session get-prompt                  # read last prompt string
```

### Profiles

```bash
cli-anything-iterm2 profile list
cli-anything-iterm2 profile get "Default"
cli-anything-iterm2 profile color-presets
cli-anything-iterm2 profile apply-preset "Solarized Dark"
```

### Arrangements

```bash
cli-anything-iterm2 arrangement list
cli-anything-iterm2 arrangement save "dev-env"
cli-anything-iterm2 arrangement restore "dev-env"
```

### tmux -CC integration

```bash
cli-anything-iterm2 tmux bootstrap                      # start tmux -CC and wait for connection
cli-anything-iterm2 tmux list                           # list active tmux connections
cli-anything-iterm2 tmux tabs --connection-id <id>     # list tmux windows
cli-anything-iterm2 tmux send "ls -la" --connection-id <id>
cli-anything-iterm2 tmux create-window --connection-id <id>
cli-anything-iterm2 tmux set-visible <window-id>
```

### Broadcast

```bash
cli-anything-iterm2 broadcast list                      # list broadcast domains
cli-anything-iterm2 broadcast all-panes                 # broadcast to all panes in window
cli-anything-iterm2 broadcast add <session-id>          # add pane to broadcast domain
cli-anything-iterm2 broadcast clear                     # stop broadcasting
```

### Menu

```bash
cli-anything-iterm2 menu list-common                    # show common menu actions
cli-anything-iterm2 menu select "Edit>Find>Find..."
cli-anything-iterm2 menu state "View>Show Tabs in Fullscreen"
```

### Preferences

```bash
cli-anything-iterm2 pref get TabViewType
cli-anything-iterm2 pref set TabViewType 1
cli-anything-iterm2 pref list                           # all valid preference keys
cli-anything-iterm2 pref tmux-get                       # tmux integration settings
cli-anything-iterm2 pref theme                          # current UI theme
```

---

## Stateful Context

The CLI saves context (window_id, tab_id, session_id) to `~/.cli-anything-iterm2/session.json`. Once set with `app current`, subsequent commands target the same pane automatically — no `--session-id` needed.

```bash
# Set context once
cli-anything-iterm2 app current

# All subsequent commands use it implicitly
cli-anything-iterm2 session send "git pull"
cli-anything-iterm2 --json session screen
cli-anything-iterm2 session split --vertical --use-as-context
cli-anything-iterm2 session send "npm run dev"
```

---

## Typical Agent Workflow

```bash
# 1. Orient — get every pane's name, path, process, role, and last output in one call
cli-anything-iterm2 --json app snapshot

# 2. Lock onto the focused session
cli-anything-iterm2 app current

# 3. Send a command and read the result
cli-anything-iterm2 session send "git log --oneline -10"
cli-anything-iterm2 --json session scrollback --tail 50 --strip

# 4. Set up a multi-pane workspace — label panes so snapshot identifies them later
cli-anything-iterm2 window create --profile "Default"
cli-anything-iterm2 app current
cli-anything-iterm2 session split --vertical --use-as-context
cli-anything-iterm2 session send "python3 -m http.server 8000"
cli-anything-iterm2 session set-var user.role "http-server"

# 5. Wait for the server to start, then verify
cli-anything-iterm2 session wait-prompt
cli-anything-iterm2 --json session screen
```

---

## Interactive REPL

Run without arguments to enter an interactive REPL that maintains context between commands:

```bash
cli-anything-iterm2
```

---

## Architecture

```
cli-anything-iterm2 (Click CLI)
        │
        │  iterm2 Python package
        │  asyncio + WebSocket (ws://localhost:1912)
        ▼
iTerm2.app  ←  running macOS terminal emulator
```

All iTerm2 API calls are async. The harness uses `iterm2.run_until_complete()` to bridge async operations into Click's synchronous command model, so every command works identically in scripts, pipelines, and agent tool calls.

The object model iTerm2 exposes:
```
App
└── Window  (one or more)
    └── Tab  (one or more per window)
        └── Session  (one or more per tab — split panes)
```

---

## Session Variables

iTerm2 sessions expose built-in variables you can read:

```bash
cli-anything-iterm2 session get-var hostname   # current host
cli-anything-iterm2 session get-var username   # current user
cli-anything-iterm2 session get-var path       # current directory
cli-anything-iterm2 session get-var pid        # shell PID
```

Custom variables use a `user.` prefix:
```bash
cli-anything-iterm2 session set-var user.project "myapp"
cli-anything-iterm2 session get-var user.project
```

---

## Tests

Unit tests run without iTerm2, E2E tests require a live instance.

```bash
git clone https://github.com/HKUDS/CLI-Anything.git
cd CLI-Anything/iterm2/agent-harness
pip install -e .

# Unit tests (no iTerm2 needed)
python3 -m pytest cli_anything/iterm2_ctl/tests/test_core.py -v

# E2E tests (iTerm2 must be running)
python3 -m pytest cli_anything/iterm2_ctl/tests/test_full_e2e.py -v -s

# Full suite
CLI_ANYTHING_FORCE_INSTALLED=1 python3 -m pytest cli_anything/iterm2_ctl/tests/ -v
```

| Suite | Requires |
|-------|---------|
| Unit | Nothing — pure logic |
| E2E | iTerm2 running |
| tmux E2E | iTerm2 + active `tmux -CC` session |
| Subprocess | Installed `cli-anything-iterm2` command |

---

## Project Structure

```
cli_anything/iterm2_ctl/
├── iterm2_ctl_cli.py          # CLI entry point (Click groups + commands)
├── core/
│   ├── session.py             # session send/screen/scrollback/split
│   ├── session_state.py       # persistent context (window/tab/session IDs)
│   ├── window.py              # window create/list/close/resize
│   ├── tab.py                 # tab create/list/close/activate
│   ├── profile.py             # profile list/get/presets
│   ├── arrangement.py         # save/restore window layouts
│   ├── tmux.py                # tmux -CC integration
│   ├── broadcast.py           # broadcast domains
│   ├── menu.py                # menu item invocation
│   ├── pref.py                # preferences read/write
│   ├── prompt.py              # shell integration (wait-prompt etc.)
│   └── dialogs.py             # modal dialogs + file panels
├── utils/
│   ├── iterm2_backend.py      # connection helpers, error messages
│   └── repl_skin.py           # interactive REPL skin
├── skills/
│   ├── SKILL.md               # AI-discoverable skill definition
│   └── references/            # 12 narrow reference files for agents
└── tests/
    ├── test_core.py            # unit tests
    ├── test_full_e2e.py        # E2E tests
    └── TEST.md                 # test plan + results
```

---

## License

MIT
