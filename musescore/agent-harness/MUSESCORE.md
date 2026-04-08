# MUSESCORE.md — Software-Specific Analysis and SOP

## 1. Software Overview

**MuseScore 4** is a free, open-source music notation editor. It reads and writes `.mscz` (native), `.mxl` (compressed MusicXML), `.mid` (MIDI), and `.musicxml` formats.

- Homepage: https://musescore.org
- Version tested: 4.6.5
- License: GPL v3

## 2. Backend Engine

The `mscore` binary provides all rendering, transposition, and conversion capabilities.

### Binary Locations

| Platform | Path |
|----------|------|
| macOS | `/Applications/MuseScore 4.app/Contents/MacOS/mscore` |
| Linux | `/usr/bin/mscore4` or `/usr/local/bin/mscore4` |
| Windows | `C:\Program Files\MuseScore 4\bin\MuseScore4.exe` |

### Data Model

- `.mscz` = ZIP archive containing:
  - `.mscx` XML (score data)
  - `score_style.mss` (style overrides)
  - `audiosettings.json`
  - `viewsettings.json`
  - `Thumbnails/thumbnail.png`
- `.mxl` = ZIP archive containing MusicXML `score.xml`

## 3. CLI Capabilities

### Export (`-o`)
```bash
mscore -o output.pdf input.mscz       # PDF
mscore -o output.mid input.mscz       # MIDI
mscore -o output.mp3 --bitrate 192 input.mscz  # MP3
mscore -o output.png -r 150 input.mscz  # PNG (per page)
mscore -o output.musicxml input.mscz  # MusicXML
```

### Transpose (`--transpose` + `-o`)
JSON format:
```json
{
  "mode": "to_key|by_interval|diatonically",
  "direction": "up|down|closest",
  "targetKey": 0,
  "transposeInterval": 0,
  "transposeKeySignatures": true,
  "transposeChordNames": true,
  "useDoubleSharpsFlats": false
}
```

### Key Signature Integer Mapping
```
-7=Cb -6=Gb -5=Db -4=Ab -3=Eb -2=Bb -1=F
 0=C   1=G   2=D   3=A   4=E   5=B   6=F#  7=C#
```

### Metadata (`--score-meta`)
Returns JSON: title, composer, keysig, timesig, tempo, duration, measures, pages, parts.

### Parts (`--score-parts`)
Returns JSON with part names and base64-encoded .mscz data per part.

### Media (`--score-media`)
Returns JSON with pngs, svgs, pdf, midi, mxml, metadata.

### Batch Jobs (`-j`)
```json
[{"in": "/path/input.mscz", "out": "/path/output.pdf"}]
```

### Exit Codes
- `0` — success
- `31` — invalid transpose options
- `23` — invalid batch job format

### Output Verification (Magic Bytes)
| Format | Magic |
|--------|-------|
| PDF | `%PDF-` |
| MIDI | `MThd` |
| MP3 | `0xfffb` or `ID3` |
| PNG | `\x89PNG` |
| MSCZ | `PK` (ZIP) |

## 4. GUI-to-CLI Mapping

| GUI Action | CLI Equivalent |
|-----------|---------------|
| File → Export → PDF | `mscore -o output.pdf input.mscz` |
| Tools → Transpose | `mscore --transpose '{...}' -o out.mscz input.mscz` |
| File → Parts | `mscore --score-parts input.mscz` |
| File → Score Properties | `mscore --score-meta input.mscz` |

## 5. CLI Architecture

### Command Groups (v1 MVP)

| Group | Purpose | Backend |
|-------|---------|---------|
| `project` | open, info, save | MusicXML/MSCX parsing |
| `transpose` | by-key, by-interval, diatonic | `--transpose` + `-o` |
| `parts` | list, extract, generate | `--score-parts` |
| `export` | pdf, png, svg, mp3, flac, wav, midi, musicxml, braille, batch | `-o` |
| `instruments` | list, add, remove, reorder | MSCX XML manipulation |
| `media` | probe, diff, stats | `--score-meta`, `--diff` |
| `session` | status, undo, redo, history | In-memory state + JSON persistence |

### State Model
- In-memory `Session` dataclass with undo/redo stacks
- `fcntl.flock()` for safe concurrent JSON writes
- Session singleton via `get_session()`
