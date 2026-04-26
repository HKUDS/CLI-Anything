# cli-anything-rekordbox

Agent-native command-line interface for Pioneer Rekordbox 6/7. Provides programmatic access to:
1. The encrypted master.db library (tracks, playlists, cues, hot cues)
2. Live deck control via virtual MIDI (play/pause, sync, crossfade, EQ, hot cues)

## Install

```bash
pip install cli-anything-rekordbox
# Optional Windows extras for UI automation:
pip install cli-anything-rekordbox[windows]
```

Requires Python 3.10+, Rekordbox 6 or 7, and (optionally) a virtual MIDI driver for live-deck control.

## Why

Pioneer ships no public REST API for playback. This harness combines `pyrekordbox` (direct SQLCipher DB access) with `mido` (virtual MIDI) into a single CLI for AI agents.

## Quick start

```bash
cli-anything-rekordbox status
cli-anything-rekordbox library count
cli-anything-rekordbox library search "Daft Punk"
cli-anything-rekordbox playlist create "MyMix"
cli-anything-rekordbox playlist add "MyMix" --track-title "One More Time"
cli-anything-rekordbox install-mapping
cli-anything-rekordbox deck crossfade 1 2 --secs 16
```

## License
MIT
