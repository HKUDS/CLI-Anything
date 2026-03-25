# iTerm2 CLI Harness — SOP

## Software Overview

iTerm2 is a macOS terminal emulator with an extensive Python API that allows programmatic control of windows, tabs, sessions, profiles, arrangements, and more. The API communicates with the running iTerm2 process over a WebSocket connection at `ws://localhost:1912`.

## Architecture

```
┌─────────────────────────────────┐
│   cli-anything-iterm2 (Click)   │  ← This CLI harness
└──────────────┬──────────────────┘
               │ iterm2 Python API (async/websocket)
┌──────────────▼──────────────────┐
│   iTerm2.app (running macOS)    │  ← The real software
└─────────────────────────────────┘
```

## Backend

- **Real software**: iTerm2.app (must be running)
- **Python API**: `iterm2` package (`pip install iterm2`)
- **Connection**: WebSocket at `ws://localhost:1912`
- **Auth**: `ITERM2_COOKIE` and `ITERM2_KEY` env vars (auto-set by iTerm2 when running scripts)

All iTerm2 API calls are async. The harness uses `iterm2.run_until_complete()` to bridge async operations into Click's synchronous command model.

## Object Model

```
App
└── Window (one or more)
    └── Tab (one or more per window)
        └── Session (one or more per tab — split panes)
```

- **Session**: The actual terminal emulator instance. Can send text, read screen, split into panes.
- **Tab**: A tab within a window. Contains one or more sessions (split panes).
- **Window**: A terminal window. Contains one or more tabs.
- **Profile**: A named configuration (colors, font, shell, etc.)
- **Arrangement**: A saved snapshot of all window/tab/session layout.

## Command Groups

| Group | Purpose |
|-------|---------|
| `app` | Workspace snapshot, app status, context management, app-level variables, modal dialogs, file panels |
| `window` | Create, list, close, resize, fullscreen, reposition windows |
| `tab` | Create, list, close, activate tabs; navigate split panes by direction |
| `session` | Send text, inject bytes, read screen/scrollback, split panes, shell integration, session variables |
| `profile` | List profiles, get profile details, list/apply color presets |
| `arrangement` | Save and restore complete window/tab/pane layouts |
| `tmux` | Full `tmux -CC` integration: bootstrap, connections, windows, send commands |
| `broadcast` | Sync keystrokes across multiple panes simultaneously |
| `menu` | Invoke any iTerm2 menu item programmatically |
| `pref` | Read/write global iTerm2 preferences; tmux integration settings |

### Workspace Orientation

Use `app snapshot` as the first command when landing in any existing workspace:

```bash
cli-anything-iterm2 --json app snapshot
```

Returns for every session: name, current directory (`path`), foreground process, `user.role` label, and last visible output line — a full picture without reading each pane's screen contents individually.

Label panes on setup so snapshot can identify them on re-entry:
```bash
cli-anything-iterm2 session set-var user.role "api-server"
```

## Key API Patterns

### Connecting and getting the app

```python
import iterm2
import asyncio

async def main(connection):
    app = await iterm2.async_get_app(connection)
    windows = app.windows  # List[Window]

iterm2.run_until_complete(main)
```

### Sending text to a session

```python
async def main(connection):
    app = await iterm2.async_get_app(connection)
    session = app.current_terminal_window.current_tab.current_session
    await session.async_send_text("echo hello\n")
```

### Reading screen contents

```python
async def main(connection):
    app = await iterm2.async_get_app(connection)
    session = app.current_terminal_window.current_tab.current_session
    contents = await session.async_get_screen_contents()
    for i in range(contents.number_of_lines):
        line = contents.line(i)
        print(line.string)
```

## Installation Prerequisites

1. **macOS**: iTerm2 only runs on macOS
2. **iTerm2 app**: Must be installed and running
3. **Python API access**: Enable at iTerm2 → Preferences → API

## Session State

The CLI stores current context (window_id, tab_id, session_id) in a JSON session file at `~/.cli-anything-iterm2/session.json`. This allows stateful multi-command workflows without re-discovering the target on every call.

## Error Handling

- If iTerm2 is not running: clear error with instructions
- If object (window/tab/session) not found: list available IDs
- Connection failures: retry once, then fail with diagnostics
