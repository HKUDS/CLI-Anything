# JSON Schemas — tmux, App, Preferences

```json
// tmux list
{"connections": [{"connection_id": "user@host", "owning_session_id": "...", "owning_session_name": "tmux"}]}

// tmux tabs
{"tmux_tabs": [{"tab_id": "47", "window_id": "pty-...", "tmux_window_id": "0",
                "tmux_connection_id": "user@host", "session_count": 1}]}

// tmux send
{"connection_id": "user@host", "command": "list-sessions",
 "output": "0: 3 windows (created ...) (attached)"}

// tmux bootstrap
{"connection_id": "user@host", "owning_session_id": "...", "command": "tmux -CC", "elapsed_seconds": 0.5}

// pref tmux-get
{"open_tmux_windows_in": 2, "open_tmux_windows_in_label": "tabs_in_existing",
 "tmux_dashboard_limit": 10, "auto_hide_tmux_client_session": true, "use_tmux_profile": false}

// app alert
{"button_index": 1000, "button_label": "OK"}
// with --button Yes --button No: 1000="Yes", 1001="No"

// app text-input
{"cancelled": false, "text": "hello world"}
{"cancelled": true,  "text": null}

// app file-panel
{"cancelled": false, "files": ["/Users/alex/foo.py", "/Users/alex/bar.py"]}
{"cancelled": true,  "files": []}

// app save-panel
{"cancelled": false, "file": "/Users/alex/output.txt"}
{"cancelled": true,  "file": null}
```

## Errors
```bash
Error: No active tmux connections. Start one with: tmux bootstrap
```
With `--json`: `{"error": "No active tmux connections..."}`
