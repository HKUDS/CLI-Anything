# FFmpeg CLI-Anything Skill

## Purpose
Provide a REPL-driven interface to FFmpeg (ffmpeg).

## Commands
- `convert <in> <out>`
- `extract-audio <in> <out>`
- `trim <in> <out> --start S --duration D`
- `concat <inputs...> --output O`
- `scale <in> <out> --width W --height H`
- `thumbnail <in> <out> --time T`
- `info <file>`

## Usage Pattern
All commands use subprocess to call ffmpeg.
Session provides undo/redo via snapshots.
