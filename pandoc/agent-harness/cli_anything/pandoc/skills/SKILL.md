# Pandoc CLI-Anything Skill

## Purpose
Provide a REPL-driven interface to Pandoc (pandoc).

## Commands
- `convert <input> <output>`
- `info <file>`
- `formats`
- `metadata <file>`
- `toc <file>`

## Usage Pattern
All commands use subprocess to call pandoc.
Session provides undo/redo via snapshots.
