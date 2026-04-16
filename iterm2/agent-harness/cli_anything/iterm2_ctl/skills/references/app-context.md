# App: Context, Variables, Dialogs, File Panels

## Workspace orientation
```bash
cli-anything-iterm2 --json app snapshot                # rich snapshot: all sessions with path, process, role, last output line
cli-anything-iterm2 --json app status                  # lightweight inventory: IDs and names only
```

`app snapshot` is the preferred orientation command — use it when landing in an existing workspace.
Set `user.role` on panes so snapshot can identify them: `session set-var user.role "api-server"`

## Context management
```bash
cli-anything-iterm2 --json app status                  # inventory all windows/tabs/sessions
cli-anything-iterm2 app current                        # focus → saves window/tab/session as context
cli-anything-iterm2 app context                        # show saved context
cli-anything-iterm2 app set-context --session-id <id>
cli-anything-iterm2 app clear-context
```

## App-level variables
```bash
cli-anything-iterm2 app get-var hostname
cli-anything-iterm2 app set-var user.myvar hello
```

## Modal dialogs
```bash
cli-anything-iterm2 app alert "Title" "Message"
cli-anything-iterm2 app alert "Deploy?" "Push?" --button Yes --button No
cli-anything-iterm2 app text-input "Rename" "Enter name:" --default "myapp"
```

## File panels
```bash
cli-anything-iterm2 app file-panel                              # macOS open picker
cli-anything-iterm2 app file-panel --ext py --ext txt --multi   # filter + multi-select
cli-anything-iterm2 app save-panel --filename output.txt        # save dialog
```
