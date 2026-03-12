---
description: Register CLI-Anything adapters for all supported AI coding agents
subtask: false
---
# cli-anything-register Command

Register CLI-Anything adapters for Claude Code, OpenCode, and Codex from this repository.

## Usage

```
/cli-anything-register [target...]
```

**Targets:** `all` (default), `claude`, `opencode`, `codex`

## What To Do

Run from the CLI-Anything repository root:

```bash
bash scripts/register.sh install --targets <targets>
```

Replace `<targets>` with the comma-separated list the user provided, or `all` if omitted.

Then show status:

```bash
bash scripts/register.sh status
```

Report what was installed and where.
