# Profiles & Preferences

## Profiles
```bash
cli-anything-iterm2 profile list [--filter NAME]
cli-anything-iterm2 profile get <guid>                 # detailed settings
cli-anything-iterm2 profile color-presets
cli-anything-iterm2 profile apply-preset "Solarized Dark" [--session-id ID]
```

## Preferences
```bash
cli-anything-iterm2 pref list-keys                     # all valid PreferenceKey names
cli-anything-iterm2 pref list-keys --filter tmux       # filter by substring
cli-anything-iterm2 pref get OPEN_TMUX_WINDOWS_IN
cli-anything-iterm2 pref set OPEN_TMUX_WINDOWS_IN 2
cli-anything-iterm2 pref theme                         # current theme tags + is_dark bool
```

## tmux preferences (shorthand)
```bash
cli-anything-iterm2 pref tmux-get                      # all tmux prefs at once
cli-anything-iterm2 pref tmux-set open_in 2            # 0=native_windows 1=new_window 2=tabs_in_existing
cli-anything-iterm2 pref tmux-set auto_hide_client true
cli-anything-iterm2 pref tmux-set use_profile true
cli-anything-iterm2 pref tmux-set dashboard_limit 10
```
