# tmux -CC Workflow Guide

tmux -CC renders each tmux window as a native iTerm2 tab — fully visible, readable, and controllable.

## Full workflow
```bash
# 1. Set context to the target session BEFORE bootstrapping — otherwise bootstrap times out
cli-anything-iterm2 app set-context --session-id <id>

# 2. Bootstrap
cli-anything-iterm2 --json tmux bootstrap

# 2. Enumerate
cli-anything-iterm2 --json tmux send "list-sessions"
cli-anything-iterm2 --json tmux send "list-panes -a -F '#{session_name}:#{window_index}:#{pane_index} #{pane_current_command} #{pane_current_path}'"
cli-anything-iterm2 --json tmux tabs          # maps tmux windows → iTerm2 tab IDs

# 3. Read any pane
cli-anything-iterm2 --json session screen --session-id <pane-session-id>
cli-anything-iterm2 --json session scrollback --session-id <pane-session-id> --tail 500 --strip

# 4. Send to any pane
cli-anything-iterm2 session send "git log --oneline -10" --session-id <pane-session-id>

# 5. Manage layout
cli-anything-iterm2 tmux send "new-window -n logs"
cli-anything-iterm2 tmux send "split-window -h -t logs"
cli-anything-iterm2 tmux send "select-layout -t logs even-horizontal"
cli-anything-iterm2 tmux create-window --use-as-context
```

## Mapping tmux panes → iTerm2 session IDs
tmux panes don't directly expose iTerm2 session IDs. Cross-reference:
```bash
cli-anything-iterm2 --json tmux tabs    # → tab_id per tmux window
cli-anything-iterm2 --json app status   # → session_id per tab_id
```
