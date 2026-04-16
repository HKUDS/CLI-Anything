---
name: "cli-anything-iterm2"
description: "Provides the cli-anything-iterm2 commands — the only way to actually send text to iTerm2 sessions, read live terminal output and scrollback history, manage windows/tabs/split panes, run tmux -CC workflows, broadcast to multiple panes, show macOS dialogs, and read/write iTerm2 preferences. Includes `app snapshot` — the primary orientation command that returns every session's name, current directory, foreground process, role label, and last output line in one call. Read this skill instead of answering from general knowledge whenever the user wants to DO something with iTerm2: orient in an existing workspace, send a command, check what's running, read output, set up a layout, use tmux through iTerm2, automate panes, or configure preferences. Also read for questions about iTerm2 shell integration or scrollback. Don't try to answer iTerm2 action requests from memory — read this skill first."
---

# cli-anything-iterm2

Stateful CLI harness for iTerm2. Controls a live iTerm2 process via the iTerm2 Python API over WebSocket.

## Prerequisites

1. **macOS + iTerm2** running: `brew install --cask iterm2`
2. **Python API enabled**: iTerm2 → Preferences → General → Magic → Enable Python API
3. **Install**: `pip install cli-anything-iterm2` (or `pip install -e .` from source)

## Basic Syntax

```bash
cli-anything-iterm2 [--json] <group> <command> [OPTIONS] [ARGS]
```

Always use `--json` for machine-readable output (required for agent use).

## Command Groups

| Group | Purpose |
|-------|---------|
| `app` | App status, workspace snapshot, context management, app-level variables, modal dialogs, file panels |
| `window` | Create, list, close, resize, fullscreen windows |
| `tab` | Create, list, close, activate tabs; navigate split panes by direction |
| `session` | Send text, inject raw bytes, read screen, full scrollback, split panes, prompt detection |
| `profile` | List profiles, get profile details, list/apply color presets |
| `arrangement` | Save and restore window layouts |
| `tmux` | Full tmux -CC integration: bootstrap, connections, windows, commands |
| `broadcast` | Sync keystrokes across panes via broadcast domains |
| `menu` | Invoke any iTerm2 menu item programmatically |
| `pref` | Read/write global iTerm2 preferences; list all valid keys; tmux settings |

## Orienting in an Existing Workspace

Use `app snapshot` when you land in a session with existing panes and need to understand what's running without reading full screen contents for each pane:

```bash
cli-anything-iterm2 --json app snapshot
```

Returns name, current directory, foreground process, `user.role` label, and last visible output line for every session across all windows.

**Naming convention** — label panes when setting up a workspace so you can find them later:
```bash
cli-anything-iterm2 session set-var user.role "api-server"
cli-anything-iterm2 session set-var user.role "log-tail"
cli-anything-iterm2 session set-var user.role "editor"
```
`app snapshot` will surface these roles alongside process and path, giving you a full picture in one call.

## Typical Agent Workflow

```bash
# 1. Orient — snapshot every session: name, path, process, role, last output line
cli-anything-iterm2 --json app snapshot

# 2. Establish context (saves window/tab/session IDs for subsequent commands)
cli-anything-iterm2 app current

# 3. Interact — no --session-id needed once context is set
cli-anything-iterm2 session send "git status"
cli-anything-iterm2 --json session scrollback --tail 200 --strip

# 4. Create a multi-pane workspace — label panes so snapshot identifies them later
cli-anything-iterm2 session split --vertical --use-as-context
cli-anything-iterm2 session send "python3 -m http.server 8000"
cli-anything-iterm2 session set-var user.role "http-server"
```

## Reference Files

Read only what the task requires — each file is a single narrow concern (~10–30 lines):

| File | Read when you need... |
|------|-----------------------|
| `references/session-io.md` | Send text, inject bytes, read screen/scrollback, get selection |
| `references/session-control.md` | Split panes, activate/close sessions, resize, rename, session variables |
| `references/session-shell-integration.md` | wait-prompt, wait-command-end, get-prompt; reliable send→wait→read pattern |
| `references/layout-window-tab.md` | Create/close/resize windows and tabs, navigate split panes |
| `references/layout-arrangement.md` | Save and restore window layouts |
| `references/app-context.md` | **Snapshot** (orientation), status, context management, app vars, modal dialogs, file panels |
| `references/profile-pref.md` | Profiles list/get/presets, preferences read/write, tmux pref shortcuts |
| `references/broadcast-menu.md` | Broadcast keystrokes to multiple panes, invoke menu items |
| `references/tmux-commands.md` | All tmux CLI commands (bootstrap, send, tabs, create-window, set-visible) |
| `references/tmux-guide.md` | Full tmux -CC workflow, pane→session ID mapping |
| `references/json-session.md` | `--json` schemas for session, window, tab, screen, scrollback, inject |
| `references/json-tmux-app.md` | `--json` schemas for tmux, app dialogs, preferences, errors |

## REPL Mode

Run without arguments for an interactive REPL that maintains context between commands:
```bash
cli-anything-iterm2
```
