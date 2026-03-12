# cli-anything:register Command

Register CLI-Anything adapters for other AI coding agents from this repository.
This command is how you manage adapters **after** the initial bootstrap.

First-time users can bootstrap from terminal first:

python3 register.py bootstrap --target auto

## Usage

```
/cli-anything:register [target...]
```

## Targets

- `all` — register Claude Code, OpenCode, and Codex (only if user explicitly asks)
- `claude` — Claude Code plugin
- `opencode` — OpenCode commands
- `codex` — Codex skill

## What To Do

1. If the user did not provide targets, ask first. Do not install yet.

Use this question:

"Choose install target: claude / opencode / codex / all"

2. Run from the CLI-Anything repository root:

```bash
python3 register.py install --targets <targets>
```

Replace `<targets>` with the comma-separated list the user explicitly selected.

3. Show status:

```bash
python3 register.py status
```

Report what was installed and where.

4. If user asks for one-click install of all agents:

```bash
python3 register.py install-all
```

## Examples

- `/cli-anything:register` -> ask user to choose target first
- `/cli-anything:register codex` -> `python3 register.py install --targets codex`
- `/cli-anything:register claude,opencode` -> `python3 register.py install --targets claude,opencode`
- `/cli-anything:register all` -> `python3 register.py install --targets all`
