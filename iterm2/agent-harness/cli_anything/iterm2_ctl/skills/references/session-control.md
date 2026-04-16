# Session Control

```bash
# List / activate / close
cli-anything-iterm2 session list [--window-id ID] [--tab-id ID]
cli-anything-iterm2 session activate [SESSION_ID]
cli-anything-iterm2 session close [SESSION_ID]

# Split panes
cli-anything-iterm2 session split                      # horizontal split
cli-anything-iterm2 session split --vertical           # side-by-side
cli-anything-iterm2 session split --use-as-context     # new pane becomes context

# Metadata
cli-anything-iterm2 session set-name "API Worker"
cli-anything-iterm2 session restart
cli-anything-iterm2 session resize --columns 220 --rows 50

# Session variables
# Built-in (read-only): hostname, username, path, pid, columns, rows
cli-anything-iterm2 session get-var hostname
cli-anything-iterm2 session get-var path
# Custom (read/write, must use user. prefix)
cli-anything-iterm2 session set-var user.role "api-worker"
cli-anything-iterm2 session get-var user.role
```
