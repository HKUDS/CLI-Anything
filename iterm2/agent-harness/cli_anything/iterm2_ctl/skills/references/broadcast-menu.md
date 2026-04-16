# Broadcast & Menu

## Broadcast — sync keystrokes across panes simultaneously
```bash
cli-anything-iterm2 broadcast list
cli-anything-iterm2 broadcast add <s1> <s2>            # group into one domain
cli-anything-iterm2 broadcast set "s1,s2" "s3,s4"     # set all domains at once
cli-anything-iterm2 broadcast all-panes [--window-id ID]
cli-anything-iterm2 broadcast clear                    # stop all broadcasting
```

Pattern — run the same command on all panes at once:
```bash
cli-anything-iterm2 broadcast all-panes
cli-anything-iterm2 session send "export ENV=staging"
cli-anything-iterm2 broadcast clear
```

## Menu — invoke iTerm2 menu items programmatically
```bash
cli-anything-iterm2 menu list-common
cli-anything-iterm2 menu select "Shell/Split Vertically with Current Profile"
cli-anything-iterm2 menu select "Shell/New Window"
cli-anything-iterm2 menu state "View/Enter Full Screen"   # checked + enabled?
```
