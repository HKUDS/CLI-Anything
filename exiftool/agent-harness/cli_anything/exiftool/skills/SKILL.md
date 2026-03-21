# ExifTool CLI-Anything Skill

## Purpose
Provide a REPL-driven interface to ExifTool (exiftool).

## Commands
- `info <file>`
- `set <file> --tag T --value V`
- `remove <file>`
- `gps <file>`
- `dates <file>`
- `copy <src> <dst>`

## Usage Pattern
All commands use subprocess to call exiftool.
Session provides undo/redo via snapshots.
