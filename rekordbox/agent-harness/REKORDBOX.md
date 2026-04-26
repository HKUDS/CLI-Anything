# cli-anything-rekordbox

Agent-native command-line interface for **Pioneer Rekordbox 6/7**. Drives library writes (tracks, playlists, cues) and live-deck mixing (play/sync/crossfade) programmatically.

## What it does

Pioneer ships **no public REST/RPC API for playback control**. Rekordbox's only programmatic surfaces are:
1. **`master.db`** — SQLCipher-encrypted SQLite library
2. **Virtual MIDI** — accepts MIDI from any registered controller mapping
3. **Pro DJ Link** — read-only network broadcasts for hardware CDJs

This harness combines (1) + (2) into a single CLI:
- **Library:** direct SQLCipher writes via `pyrekordbox` (auto-extracts the static rekordbox 6/7 master key)
- **Playback:** virtual MIDI sender mapped via a bundled `Bunker.midi.csv` controller mapping
- **Output:** JSON for agent consumption (`--json`) or human-readable

## Installation

```bash
pip install cli-anything-rekordbox
# Optional Windows extras for live-deck UI automation:
pip install cli-anything-rekordbox[windows]
```

**Prerequisites:**
- Python 3.10+
- Rekordbox 6 or 7 installed (master.db must be locatable)
- A virtual MIDI driver if you want live-deck control:
  - **Windows:** [loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html), LoopBe, or teVirtualMIDI
  - **macOS:** IAC Driver (built-in via Audio MIDI Setup)
  - **Linux:** ALSA virtual MIDI (`snd-virmidi`)

## Quick start

```bash
# Library inspection (no MIDI needed)
cli-anything-rekordbox library count
cli-anything-rekordbox library search "Daft Punk"

# Create + populate a playlist
cli-anything-rekordbox playlist create "MyMix"
cli-anything-rekordbox playlist add "MyMix" --track-title "Track A"
cli-anything-rekordbox playlist add "MyMix" --track-title "Track B"

# Live-deck mixing (requires virtual MIDI port + mapping in rekordbox)
cli-anything-rekordbox install-mapping            # one-time: drops Bunker.midi.csv into rekordbox MidiMappings/
cli-anything-rekordbox deck play --deck 1 --port "LoopBe"
cli-anything-rekordbox deck crossfade 1 2 --secs 16

# End-to-end: load + mix two tracks
cli-anything-rekordbox mix "Track A" "Track B" --secs 16

# REPL mode
cli-anything-rekordbox
```

## Command groups

### `library`
| Command | Description |
|---------|-------------|
| `count` | Total tracks in library |
| `search QUERY` | Find tracks by title/artist (substring) |
| `info TRACK_ID` | Show full metadata for a track |
| `dump --out tracks.json` | Export full library as JSON |

### `playlist`
| Command | Description |
|---------|-------------|
| `list` | Show all playlists |
| `create NAME` | Create new playlist |
| `delete NAME` | Delete playlist |
| `add NAME --track-title T` | Add track by title |
| `clear NAME` | Empty a playlist |

### `cue`
| Command | Description |
|---------|-------------|
| `list TRACK_ID` | List all cue points |
| `set TRACK_ID --ms N --color HEX` | Add a cue at offset |
| `hot TRACK_ID --slot N --ms M` | Set hot cue |

### `deck` (live MIDI)
| Command | Description |
|---------|-------------|
| `play --deck N` | Toggle play/pause |
| `cue --deck N` | Cue button |
| `sync --deck N` | Tempo sync |
| `crossfade FROM TO --secs S` | Smooth crossfade between decks |
| `eq --deck N --hi V --mid V --lo V` | EQ control (0..1) |
| `tempo --deck N --offset V` | Pitch slider (-1..+1) |
| `hot-cue --deck N --slot S` | Trigger hot cue 1-8 |

### High-level
| Command | Description |
|---------|-------------|
| `mix A B --secs S` | Search+load A→deck1, B→deck2, sync, crossfade |
| `install-mapping` | Copy Bunker.midi.csv into rekordbox's MidiMappings dir |
| `status` | Report rekordbox running state, DB path, MIDI ports |

## Architecture

```
+-----------------------------+
|  cli-anything-rekordbox     |
+-----------------------------+
            |
   +--------+----------+
   |                   |
   v                   v
+-----------+   +---------------+
| pyrekord- |   | mido +        |
| box       |   | virtual MIDI  |
+-----------+   +---------------+
   |                   |
   v                   v
+----------+    +-----------------+
| master.db|    | Rekordbox 6/7   |
| SQLCipher|    | (live decks)    |
+----------+    +-----------------+
```

## Data files

- `cli_anything/rekordbox/data/Bunker.midi.csv` — MIDI mapping (transport, mixer, EQ, hot cues, beat loops, browser nav). Pioneer-format, drops directly into rekordbox's `MidiMappings/` folder.

## JSON output

Every command supports `--json` for agent consumption:
```bash
$ cli-anything-rekordbox --json library search "Daft Punk"
[{"id": 12345, "title": "One More Time", "artist": "Daft Punk", "bpm": 123.0}, ...]
```

## Notes & caveats

- **SQLCipher key** is auto-extracted by pyrekordbox from rekordbox.exe (the static rekordbox 6/7 master key, hardcoded across all installs).
- **Library writes** require either rekordbox closed OR bypassing pyrekordbox's running-rekordbox safety check (this CLI does the latter via `db.session.commit()` directly).
- **Live-deck control** depends on the user mapping the virtual MIDI port in rekordbox `Preferences → Controller → MIDI` (one-time UI step). The harness ships `Bunker.midi.csv` and an `install-mapping` command to drop it into the right folder.
- **Pioneer offers no playback REST API.** This is the closest thing.

## License
MIT — same as parent CLI-Anything project.
