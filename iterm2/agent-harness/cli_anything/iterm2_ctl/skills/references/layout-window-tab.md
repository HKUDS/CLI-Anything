# Windows & Tabs

## Windows
```bash
cli-anything-iterm2 window list
cli-anything-iterm2 window create [--profile NAME] [--command CMD]
cli-anything-iterm2 window close [WINDOW_ID]           # positional arg, NOT --window-id; uses context if omitted
cli-anything-iterm2 window activate [WINDOW_ID]
cli-anything-iterm2 window set-title "My Window"
cli-anything-iterm2 window frame                       # get position/size
cli-anything-iterm2 window set-frame --x 0 --y 0 --width 1200 --height 800
cli-anything-iterm2 window fullscreen on|off|toggle|status
```

## Tabs
```bash
cli-anything-iterm2 tab list [--window-id ID]
cli-anything-iterm2 tab create [--window-id ID] [--profile NAME]
cli-anything-iterm2 tab close [TAB_ID]
cli-anything-iterm2 tab activate [TAB_ID]
cli-anything-iterm2 tab info [TAB_ID]
cli-anything-iterm2 tab select-pane right              # focus adjacent split pane
cli-anything-iterm2 tab select-pane left|above|below [--tab-id ID]
```
