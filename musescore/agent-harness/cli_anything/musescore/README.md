# cli-anything-musescore

CLI wrapper for **MuseScore 4** — the first music notation tool in the [CLI-Anything](https://github.com/HKUDS/CLI-Anything) ecosystem.

## Features

- **Transpose** scores by key, interval, or diatonically
- **Export** to PDF, PNG, SVG, MP3, FLAC, WAV, MIDI, MusicXML, Braille
- **Extract parts** from multi-instrument scores
- **Manage instruments** — list, add, remove, reorder
- **Analyze scores** — metadata, diff, statistics
- **Interactive REPL** with undo/redo session management

## Requirements

- Python >= 3.10
- [MuseScore 4](https://musescore.org/en/download) installed
- macOS, Linux, or Windows

## Install

```bash
pip install -e .
```

## Quick Start

```bash
# Interactive REPL
cli-anything-musescore

# One-shot commands with JSON output
cli-anything-musescore --json project info -i score.mscz
cli-anything-musescore --json transpose by-key -i score.mscz -o out.mscz --target-key "C major"
cli-anything-musescore --json export pdf -i score.mscz -o score.pdf
cli-anything-musescore --json parts list -i score.mscz
```

## Command Groups

| Group | Commands | Description |
|-------|----------|-------------|
| `project` | open, info, save | Score file management |
| `transpose` | by-key, by-interval, diatonic | Transposition |
| `parts` | list, extract, generate | Part extraction |
| `export` | pdf, png, svg, mp3, flac, wav, midi, musicxml, braille, batch | Rendering |
| `instruments` | list, add, remove, reorder | Instrument management |
| `media` | probe, diff, stats | Score analysis |
| `session` | status, undo, redo, history | Session management |
