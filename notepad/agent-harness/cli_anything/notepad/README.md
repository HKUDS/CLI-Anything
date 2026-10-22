# cli-anything-notepad

Windows Notepad — agent-native CLI via UI Automation.

## Layout

```
cli_anything/notepad/
  notepad_cli.py     Click CLI, --json on every command
  core/backend.py    constants + guards baked in from the GUI capture
  skills/SKILL.md    agent-facing workflow manual
  tests/             test_core.py (offline) + test_full_e2e.py (needs a live window)
  utils/uia_runner.py  self-contained UIA driver (needs: pip install uiautomation)
```

## Install

```bash
pip install -e .
pip install uiautomation
```

## Quick start

```bash
cli-anything-notepad ui-menus                 # what can be driven
cli-anything-notepad ui-tree                  # the full actionable tree
cli-anything-notepad ui-set-text "PaneControl > Text editor" "hello" --yes
```

## Safety

Read-only commands need nothing. Driving actions require `--yes`.
Destructive-looking paths are refused unless the runner gets
`--allow-destructive`.
