# Audacity: Project-Specific Analysis & SOP

## Architecture Summary

Audacity is a multi-platform audio editor built on PortAudio for I/O and
libsndfile for file format support. Its native `.aup3` format is a SQLite
database containing audio data and project metadata.

```
+-------------------------------------------------+
|                 Audacity GUI                    |
|  +----------+ +----------+ +----------------+  |
|  | Timeline | |  Mixer   | |    Effects     |  |
|  |  (wxGTK) | | (wxGTK)  | |   (wxGTK)     |  |
|  +----+-----+ +----+-----+ +------+---------+  |
|       |             |              |            |
|  +----+-------------+--------------+----------+ |
|  |         Internal Audio Engine              | |
|  |  Block-based audio storage, real-time      | |
|  |  processing, effect chain, undo history    | |
|  +--------------------+-----------------------+ |
+------------------------+------------------------+
                         |
          +--------------+--------------+
          | PortAudio (I/O) | libsndfile |
          | SoX resampler   | LAME (MP3) |
          +---------------------------------+
```

## CLI Strategy: Python stdlib + JSON Project

Unlike applications with XML project files, Audacity's .aup3 is SQLite,
making direct manipulation complex. Our strategy:

1. **JSON project format** tracks all state (tracks, clips, effects, labels)
2. **Python stdlib** (`wave`, `struct`, `math`) handles WAV I/O and audio processing
3. **pydub** (optional) for advanced format support (MP3, FLAC, OGG)

### Why Not .aup3 Directly?

The .aup3 format is a SQLite database with:
- Binary audio block storage (custom compression)
- Complex relational schema for tracks, clips, envelopes
- Undo history embedded in the database
- Project metadata interleaved with audio data

Parsing and writing this format requires deep knowledge of Audacity internals.
Instead, we use a JSON manifest and render to standard audio formats.

## The Project Format (.audacity-cli.json)

```json
{
  "version": "1.0",
  "name": "my_podcast",
  "settings": {
    "sample_rate": 44100,
    "bit_depth": 16,
    "channels": 2
  },
  "tracks": [...],
  "labels": [...],
  "selection": {"start": 0.0, "end": 0.0},
  "metadata": {"title": "", "artist": "", "album": "", ...}
}
```

## Command Map: GUI Action -> CLI Command

| GUI Action | CLI Command |
|-----------|-------------|
| File -> New | `project new --name "My Project"` |
| File -> Open | `project open <path>` |
| File -> Save | `project save [path]` |
| File -> Export Audio | `export render <output> [--preset wav]` |
| Tracks -> Add New -> Audio | `track add --name "Track"` |
| Track -> Remove | `track remove <index>` |
| Track -> Mute/Solo | `track set <index> mute true` |
| Track -> Volume | `track set <index> volume 0.8` |
| Track -> Pan | `track set <index> pan -0.5` |
| File -> Import -> Audio | `clip add <track> <file>` |
| Edit -> Remove | `clip remove <track> <clip>` |
| Edit -> Clip Boundaries -> Split | `clip split <track> <clip> <time>` |
| Edit -> Move Clip | `clip move <track> <clip> <time>` |
| Effect -> Amplify | `effect add amplify --track 0 -p gain_db=6.0` |
| Effect -> Normalize | `effect add normalize --track 0 -p target_db=-1.0` |
| Effect -> Fade In | `effect add fade_in --track 0 -p duration=2.0` |
| Effect -> Reverse | `effect add reverse --track 0` |
| Effect -> Echo | `effect add echo --track 0 -p delay_ms=500 -p decay=0.5` |
| Edit -> Select All | `selection all` |
| Edit -> Labels -> Add Label | `label add 5.0 --text "Marker"` |
| Edit -> Undo | `session undo` |
| Edit -> Redo | `session redo` |

## Effect Registry

| CLI Name | Category | Key Parameters |
|----------|----------|----------------|
| `amplify` | volume | `gain_db` (-60 to 60) |
| `normalize` | volume | `target_db` (-60 to 0) |
| `fade_in` | fade | `duration` (0.01-300s) |
| `fade_out` | fade | `duration` (0.01-300s) |
| `reverse` | transform | (none) |
| `silence` | generate | `duration` (0.01-3600s) |
| `tone` | generate | `frequency`, `duration`, `amplitude` |
| `change_speed` | transform | `factor` (0.1-10.0) |
| `change_pitch` | transform | `semitones` (-24 to 24) |
| `change_tempo` | transform | `factor` (0.1-10.0) |
| `echo` | delay | `delay_ms`, `decay` |
| `low_pass` | eq | `cutoff` (20-20000 Hz) |
| `high_pass` | eq | `cutoff` (20-20000 Hz) |
| `compress` | dynamics | `threshold`, `ratio`, `attack`, `release` |
| `limit` | dynamics | `threshold_db` (-60 to 0) |
| `noise_reduction` | restoration | `reduction_db` (0-48) |

## Export Formats

| Preset | Format | Bit Depth | Notes |
|--------|--------|-----------|-------|
| `wav` | WAV | 16-bit | Standard, native support |
| `wav-24` | WAV | 24-bit | High quality |
| `wav-32` | WAV | 32-bit | Studio quality |
| `wav-8` | WAV | 8-bit | Low quality |
| `mp3` | MP3 | — | Requires pydub/ffmpeg |
| `flac` | FLAC | — | Requires pydub/ffmpeg |
| `ogg` | OGG | — | Requires pydub/ffmpeg |
| `aiff` | AIFF | — | Requires pydub/ffmpeg |

## Rendering Pipeline

1. For each non-muted track (respecting solo):
   a. For each clip: read source WAV, apply trim, place at timeline position
   b. Mix overlapping clips on the same track
   c. Apply track effects chain in order
   d. Apply track volume
2. Mix all tracks together (with pan and volume)
3. Clamp to [-1.0, 1.0]
4. Write to output format

### Rendering Gap Assessment: **Medium**

- WAV I/O works natively via Python's `wave` module
- Basic effects (gain, fade, reverse, echo, filters) implemented in pure Python
- Advanced effects (pitch shift, time stretch) use simplified algorithms
- MP3/FLAC/OGG export requires external tools (pydub + ffmpeg)
- No real-time preview capability

## Test Coverage

1. **Unit tests** (`test_core.py`): 60+ tests, synthetic data
   - Project CRUD and settings
   - Track add/remove/properties
   - Clip add/remove/split/move/trim
   - Effect registry, validation, add/remove/set
   - Label add/remove/list
   - Selection set/all/none
   - Session undo/redo
   - Audio utility functions

2. **E2E tests** (`test_full_e2e.py`): 40+ tests, real WAV files
   - WAV read/write round-trips (16-bit, 24-bit, stereo)
   - Audio effect verification (gain, fade, reverse, echo, filters)
   - Full render pipeline (single track, multi-track, mute, solo)
   - Project save/load with effects preserved
   - Multi-step workflows (podcast creation)
   - CLI subprocess invocation
   - Media probing
