---
description: Register CLI-Anything adapters for all supported AI coding agents
subtask: false
---
# register Command

Register CLI-Anything adapters for Claude Code, OpenCode, and Codex from this repository.

First-time users can bootstrap from terminal first:

python3 register.py bootstrap --target auto

## Usage

```
/register [target...]
```

**Targets:** `all` (only if user explicitly asks), `claude`, `opencode`, `codex`

## What To Do

1. If the user did not provide targets, ask first. Do not install yet.

Use this question:

"Choose install target: claude / opencode / codex / all"

2. Run from the CLI-Anything repository root:

```bash
python3 register.py install --targets <targets>
```

Replace `<targets>` with the comma-separated list the user explicitly selected.

3. Then show status:

```bash
python3 register.py status
```

Report what was installed and where.

4. If the user wants one-click install for all supported agents:

```bash
python3 register.py install-all
```
