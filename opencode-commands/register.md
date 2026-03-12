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

**Targets:** `all` (default), `claude`, `opencode`, `codex`

## What To Do

Run from the CLI-Anything repository root:

```bash
python3 register.py install --targets <targets>
```

Replace `<targets>` with the comma-separated list the user provided, or `all` if omitted.

Then show status:

```bash
python3 register.py status
```

Report what was installed and where.

If the user wants one-click install for all supported agents:

```bash
python3 register.py install-all
```
