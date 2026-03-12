# register Command

Register CLI-Anything adapters for other AI coding agents from this repository.
This command is how you manage adapters **after** the initial bootstrap.

First-time users can bootstrap from terminal first:

python3 scripts/register.py bootstrap --target auto

## Usage

```
/cli-anything:register [target...]
```

## Targets

- `all` — register Claude Code, OpenCode, and Codex (default)
- `claude` — Claude Code plugin
- `opencode` — OpenCode commands
- `codex` — Codex skill

## What To Do

1. Run from the CLI-Anything repository root:

```bash
python3 scripts/register.py install --targets <targets>
```

Replace `<targets>` with the comma-separated list the user provided, or `all` if none specified.

2. Show status:

```bash
python3 scripts/register.py status
```

Report what was installed and where.

3. If user asks for one-click install of all agents:

```bash
python3 scripts/register.py install-all
```

## Examples

- `/cli-anything:register` -> `python3 scripts/register.py install --targets all`
- `/cli-anything:register codex` -> `python3 scripts/register.py install --targets codex`
- `/cli-anything:register claude,opencode` -> `python3 scripts/register.py install --targets claude,opencode`
