---
name: musescore
display_name: MuseScore
version: 1.0.0
description: CLI for music notation — transpose, export PDF/audio/MIDI, extract parts, manage instruments
requires: MuseScore 4 (musescore.org)
entry_point: cli-anything-musescore
category: music
---

# MuseScore CLI Skill

## Overview

Wraps MuseScore 4's `mscore` backend for music notation tasks: transposition, export to multiple formats (PDF, PNG, MP3, MIDI, MusicXML, Braille), part extraction, instrument management, and score analysis.

## Commands

### Project Management
```bash
cli-anything-musescore --json project info -i score.mscz
cli-anything-musescore --json project open -i score.mscz
```

### Transposition
```bash
# Transpose to a target key
cli-anything-musescore --json transpose by-key -i score.mscz -o out.mscz --target-key "C major" --direction closest

# Transpose by semitones
cli-anything-musescore --json transpose by-interval -i score.mscz -o out.mscz --semitones 3

# Diatonic transposition
cli-anything-musescore --json transpose diatonic -i score.mscz -o out.mscz --steps 2
```

### Part Extraction
```bash
cli-anything-musescore --json parts list -i score.mscz
cli-anything-musescore --json parts extract -i score.mscz -o piano.mscz --part "Piano"
cli-anything-musescore --json parts generate -i score.mscz -d ./parts/
```

### Export
```bash
cli-anything-musescore --json export pdf -i score.mscz -o score.pdf
cli-anything-musescore --json export mp3 -i score.mscz -o score.mp3 --bitrate 192
cli-anything-musescore --json export png -i score.mscz -o score.png --dpi 300
cli-anything-musescore --json export midi -i score.mscz -o score.mid
cli-anything-musescore --json export musicxml -i score.mscz -o score.musicxml
cli-anything-musescore --json export braille -i score.mscz -o score.brf
cli-anything-musescore --json export batch -i score.mscz -o score.pdf -o score.mid
```

### Instrument Management
```bash
cli-anything-musescore --json instruments list -i score.mscz
cli-anything-musescore --json instruments add -i score.mscz -o out.mscz --id keyboard.piano --name "Piano"
cli-anything-musescore --json instruments remove -i score.mscz -o out.mscz --name "Violin"
```

### Score Analysis
```bash
cli-anything-musescore --json media probe -i score.mscz
cli-anything-musescore --json media stats -i score.mscz
cli-anything-musescore --json media diff --reference a.mscz --compare b.mscz
```

### Session
```bash
cli-anything-musescore --json session status
cli-anything-musescore --json session undo
cli-anything-musescore --json session redo
cli-anything-musescore --json session history
```

## Supported Input Formats
- `.mscz` (MuseScore native)
- `.mxl` (compressed MusicXML)
- `.musicxml` / `.xml` (MusicXML)
- `.mid` / `.midi` (MIDI)

## Key Names for Transposition
Major: Cb, Gb, Db, Ab, Eb, Bb, F, C, G, D, A, E, B, F#, C#
Minor: Ab, Eb, Bb, F, C, G, D, A, E, B, F#, C#, G#, D#, A#

Accepted formats: "C", "C major", "Am", "A minor", "Db major", "F# minor"

## Agent Guidance
- Always use `--json` flag for machine-readable output
- Verify exports with `export verify` after rendering
- Use `media probe` to inspect an unknown score before operating on it
- Transposition requires both `-i` (input) and `-o` (output)
- Part names are case-insensitive for `parts extract`
