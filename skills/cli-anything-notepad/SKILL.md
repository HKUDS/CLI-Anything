---
name: "cli-anything-notepad"
description: "Windows Notepad — drive the GUI via UI Automation from an agent-native CLI: capture the tree, list menus, invoke elements, set text. Read-only by default; every action gated."
---

# cli-anything-notepad

Windows Notepad harness driven through UI Automation. Windows only.

## Installation

```bash
pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=notepad/agent-harness
pip install uiautomation
```

## Commands

```bash
cli-anything-notepad ui-tree                              # dump the live UIA tree (read-only)
cli-anything-notepad ui-menus                             # list expandable menu paths (read-only)
cli-anything-notepad ui-invoke "<path>" --yes             # invoke one element
cli-anything-notepad ui-select "<path>" --yes             # select one element (tab, list item)
cli-anything-notepad ui-set-text "<path>" "<text>" --yes  # set a Value element's text
```

Paths accept any unique suffix of the full UIA path, e.g.
`"PaneControl > Text editor"` instead of the full window-prefixed path.

## JSON Output

All commands support `--json`:

```bash
cli-anything-notepad --json ui-menus
```

## Rules for agents

- Start with `ui-tree` or `ui-menus` — UIA is a live tree and stored paths go
  stale when the UI changes (the window title changes with the unsaved marker).
- Every driving action requires `--yes`. Do not add it yourself; surface the
  action to the user and let them confirm.
- Destructive-looking paths (save/close/delete/exit/format...) are refused
  even with `--yes` unless the runner is invoked with `--allow-destructive`.
  Never use that flag on a user's document.
- Driving mutates the target app's in-memory state. Prefer read-only
  inspection when answering questions.

## Evidence

Tree captured live from Windows 11 Notepad: 51 nodes, 8 menu paths, a
Value-pattern text editor, SelectionItem tabs, Toggle buttons. Unit tests are
offline; E2E tests are read-only captures against a live window.
