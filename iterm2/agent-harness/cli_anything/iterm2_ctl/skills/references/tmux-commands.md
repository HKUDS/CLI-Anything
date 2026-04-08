# tmux Commands

```bash
cli-anything-iterm2 tmux bootstrap                     # start tmux -CC, wait for connection
cli-anything-iterm2 tmux bootstrap --attach            # attach to existing session
cli-anything-iterm2 tmux bootstrap --session-id <id> --timeout 15
cli-anything-iterm2 tmux list                          # active tmux -CC connections
cli-anything-iterm2 tmux tabs                          # iTerm2 tabs backed by tmux
cli-anything-iterm2 tmux create-window                 # new tmux window → iTerm2 tab
cli-anything-iterm2 tmux create-window --use-as-context
cli-anything-iterm2 tmux set-visible @1 off|on         # hide/show a tmux window's tab

# tmux protocol commands (sent to tmux server, not to a pane)
cli-anything-iterm2 tmux send "list-sessions"
cli-anything-iterm2 tmux send "list-windows -a"
cli-anything-iterm2 tmux send "list-panes -a -F '#{session_name}:#{window_index}:#{pane_index} #{pane_current_command} #{pane_current_path}'"
cli-anything-iterm2 tmux send "new-window -n work"
cli-anything-iterm2 tmux send "rename-session dev"
cli-anything-iterm2 tmux send "split-window -h"
cli-anything-iterm2 tmux send "select-pane -t 0"
cli-anything-iterm2 session run-tmux-cmd "rename-window mywork"
```

**Key distinction:** `tmux send` = tmux protocol commands (to tmux server). `session send` = shell text to a specific pane. Use both together.
