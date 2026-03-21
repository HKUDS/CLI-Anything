# yt-dlp CLI-Anything Skill

## Purpose
Provide a REPL-driven interface to yt-dlp (yt-dlp).

## Commands
- `download <url>`
- `info <url>`
- `formats <url>`
- `search <query>`
- `playlist <url>`
- `subtitles <url>`

## Usage Pattern
All commands use subprocess to call yt-dlp.
Session provides undo/redo via snapshots.
