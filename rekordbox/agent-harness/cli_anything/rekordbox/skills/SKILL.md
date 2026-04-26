---
name: "cli-anything-rekordbox"
description: >-
  Command-line interface for Pioneer Rekordbox 6/7 - DJ library and live-deck control via direct SQLCipher master.db access (pyrekordbox) + virtual MIDI mapping. Provides library inspection, playlist CRUD, cue/hot-cue management, and live-deck mixing (play/sync/crossfade/EQ). Pioneer ships no playback REST API; this harness combines the only two real surfaces (encrypted DB + MIDI) into one agent-native CLI.
---

# cli-anything-rekordbox

Agent-native CLI for Pioneer Rekordbox 6/7. Drives the DJ library and live decks programmatically.

## Installation

```bash
pip install cli-anything-rekordbox
```

**Prerequisites:**
- Python 3.10+
- Rekordbox 6 or 7 installed (`master.db` must exist)
- Virtual MIDI driver for live-deck control:
  - Windows: loopMIDI / LoopBe / teVirtualMIDI
  - macOS: IAC Driver
  - Linux: ALSA virtual MIDI (`snd-virmidi`)

## Usage

```bash
# Status check
cli-anything-rekordbox status

# REPL mode
cli-anything-rekordbox

# JSON output for agents
cli-anything-rekordbox --json library search "Daft Punk"
```

## Command Groups

### Library
| Command | Description |
|---------|-------------|
| `count` | Total track count |
| `search QUERY` | Find tracks by title/artist substring |
| `info TRACK_ID` | Full track metadata |
| `dump --out FILE.json` | Export full library as JSON |

### Playlist
| Command | Description |
|---------|-------------|
| `list` | All playlists |
| `create NAME` | New playlist |
| `add NAME --track-title T` | Add track |
| `clear NAME` | Empty a playlist |

### Deck (live MIDI)
| Command | Description |
|---------|-------------|
| `play --deck N` | Play/pause |
| `sync --deck N` | Tempo sync |
| `crossfade FROM TO --secs S` | Smooth crossfade |
| `eq --deck N --hi --mid --lo` | EQ control |
| `hot-cue --deck N --slot 1-8` | Trigger hot cue |

### Top-level
| Command | Description |
|---------|-------------|
| `status` | Runtime / DB / MIDI state |
| `install-mapping` | Drop Bunker.midi.csv into rekordbox's MidiMappings folder |
| `mix A B --secs S` | High-level: search + load + sync + crossfade |

## How it works

```
+------------------+
|   Your Agent     |
+--------+---------+
         |
         v
+------------------+
| cli-anything-    |
| rekordbox CLI    |
+--------+---------+
   |          |
   v          v
+----------+  +----------+
|pyrekord- |  |  mido +  |
|box DB    |  |  virtual |
|writes    |  |  MIDI    |
+----------+  +----------+
   |               |
   v               v
+----------+  +-----------+
| master.db|  | Rekordbox |
|SQLCipher |  | live decks|
+----------+  +-----------+
```

- **master.db** is encrypted with a static AES-256 key shared by all rekordbox 6/7 installs (auto-extracted by pyrekordbox)
- **Virtual MIDI** mapping uses Pioneer's standard `.midi.csv` format; this CLI ships `Bunker.midi.csv` and an `install-mapping` command to drop it into rekordbox's `MidiMappings/` folder

## JSON output

Every command supports `--json`:
```bash
$ cli-anything-rekordbox --json library count
{"track_count": 30344}
```

## License
MIT
