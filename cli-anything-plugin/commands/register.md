# register Command

Register CLI-Anything adapters for all supported AI coding agents from this repository.

## Usage

```
/register [target...]
```

## Targets

- `all` — register Claude Code, OpenCode, and Codex (default)
- `claude` — Claude Code plugin
- `opencode` — OpenCode commands
- `codex` — Codex skill

## What To Do

Run from the CLI-Anything repository root:

```bash
bash scripts/register.sh install --targets <targets>
```

Replace `<targets>` with the comma-separated list the user provided, or `all` if none specified.

Then show status:

```bash
bash scripts/register.sh status
```

Report what was installed and where.

## Examples

- `/register` → `bash scripts/register.sh install --targets all`
- `/register codex` → `bash scripts/register.sh install --targets codex`
- `/register claude,opencode` → `bash scripts/register.sh install --targets claude,opencode`
