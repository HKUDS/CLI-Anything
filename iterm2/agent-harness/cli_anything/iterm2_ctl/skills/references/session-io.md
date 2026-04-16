# Session I/O

```bash
# Send input
cli-anything-iterm2 session send "echo hello"          # sends text + newline
cli-anything-iterm2 session send "text" --session-id <id>
cli-anything-iterm2 session send "text" --no-newline

# Inject raw bytes
cli-anything-iterm2 session inject $'\x1b[2J'          # escape sequence
cli-anything-iterm2 session inject "1b5b324a" --hex    # same in hex

# Read visible screen — ALWAYS use --json, output is silently empty without it
cli-anything-iterm2 --json session screen              # visible area only
cli-anything-iterm2 --json session screen --lines 20

# Read full history
cli-anything-iterm2 --json session scrollback
cli-anything-iterm2 --json session scrollback --tail 100
cli-anything-iterm2 --json session scrollback --tail 500 --strip   # no null bytes
cli-anything-iterm2 --json session scrollback --lines 200          # first 200 lines

# Get selected text
cli-anything-iterm2 session selection
```

`session screen` = visible area only. `session scrollback` = entire history, atomically, oldest→newest.
`overflow` in scrollback response = lines lost when buffer was full (set profile limit to "unlimited" to avoid).
