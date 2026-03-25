# JSON Schemas — Session, Window, Tab

```json
// app snapshot
{"session_count": 3, "sessions": [
  {"session_id": "...", "name": "api-server", "window_id": "...", "tab_id": "...",
   "path": "/Users/alex/project", "pid": 12345, "process": "node",
   "role": "api-server", "last_line": "Server listening on :3000"},
  {"session_id": "...", "name": "shell", "window_id": "...", "tab_id": "...",
   "path": "/Users/alex", "pid": 67890, "process": "zsh",
   "role": null, "last_line": "$ "}
]}

// app status
{"window_count": 2, "windows": [{"window_id": "...", "tabs": [...]}]}

// session list
{"sessions": [{"session_id": "...", "name": "...", "tab_id": "...", "window_id": "...", "is_current": false}]}

// session screen
{"session_id": "...", "total_lines": 40, "returned_lines": 40, "lines": ["$ echo hello", "hello"]}

// session scrollback
{"session_id": "...", "total_available": 4922, "scrollback_lines": 4862, "screen_lines": 60,
 "overflow": 0, "returned_lines": 100, "lines": ["...", "..."]}

// session wait-command-end
{"session_id": "...", "exit_status": 0, "timed_out": false}

// session inject
{"session_id": "...", "injected_bytes": 4}

// tab select-pane
{"tab_id": "...", "direction": "right", "new_session_id": "...", "moved": true}
{"tab_id": "...", "direction": "left",  "new_session_id": null,  "moved": false}

// window create
{"window_id": "...", "tab_id": "...", "session_id": "..."}

// profile get
{"name": "Default", "guid": "...", "badge_text": null}
```

## Errors
```bash
Error: Cannot connect to iTerm2. Make sure iTerm2 is running...
Error: Session 'abc123' not found.
```
With `--json`: `{"error": "Session 'abc123' not found."}`
