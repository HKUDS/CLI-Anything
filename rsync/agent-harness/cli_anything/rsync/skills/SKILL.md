# Rsync CLI-Anything Skill

## Purpose
Provide a REPL-driven interface to Rsync (rsync).

## Commands
- `sync <src> <dst>`
- `dry-run <src> <dst>`
- `mirror <src> <dst>`
- `stats <src> <dst>`

## Usage Pattern
All commands use subprocess to call rsync.
Session provides undo/redo via snapshots.
