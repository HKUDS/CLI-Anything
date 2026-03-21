# Docker CLI-Anything Skill

## Purpose
Provide a REPL-driven interface to Docker (docker).

## Commands
- `ps`
- `run <image>`
- `stop <id>`
- `logs <id>`
- `exec <id> --cmd C`
- `images`
- `pull <name>`
- `build --path P --tag T`
- `rm <id>`
- `volumes`
- `networks`
- `info`

## Usage Pattern
All commands use subprocess to call docker.
Session provides undo/redo via snapshots.
