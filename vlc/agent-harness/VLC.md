# VLC — Agent Harness Analysis (Phase 1)

This document records the Phase 1 codebase analysis for building an agent-native CLI
around **VLC** (`vlc` / `cvlc`), following the cli-anything HARNESS.md methodology.

## 1. Backend engine

VLC media player (VideoLAN) is the backend. It ships a headless-capable command-line
interface (`vlc` on Linux/macOS, `vlc.exe` / `cvlc` on Windows) that can:

- read virtually any container/codec (mp4, mkv, avi, mov, webm, mp3, flac, wav, ogg, ts, …),
- transcode with the `#transcode{...}:std{...}` streaming output chain (`--sout`),
- stream to network (rtp, http, rtsp, udp) via `--sout`,
- extract a still frame via the `scene` video filter (`--video-filter=scene`),
- dump playback statistics in dummy interface mode (`-I dummy --play-and-exit --stats`).

We do **not** reimplement any of this in Python. The harness only builds VLC command
lines and invokes the real binary.

## 2. Data model

VLC has no "project file". The harness introduces a small JSON **job spec** that
captures a reproducible media operation an agent can mutate, save, and re-run:

```json
{
  "version": "1.0.0",
  "software": "vlc",
  "inputs":      ["/abs/in.mp4"],
  "output":      {"path": "/abs/out.mp4", "format": "mp4"},
  "transcode": {
    "vcodec": "h264", "acodec": "mp3",
    "vbitrate": 800, "abitrate": 128,
    "scale": 1.0, "width": null, "height": null, "fps": null,
    "channels": 2, "samplerate": 44100, "extra": []
  },
  "stream":   null,
  "snapshot": null
}
```

Mutation commands (add-input, set-output, set-option, set-stream, set-snapshot) are
undoable through a command stack (see `core/session.py`).

## 3. GUI action → CLI mapping

| GUI action | CLI command |
|---|---|
| Open media | `vlc -I dummy --play-and-exit <file>` |
| Convert / Save (Wizard) | `--sout '#transcode{...}:std{access=file,mux=...,dst=...}'` |
| Stream (Wizard) | `--sout '#transcode{...}:rtp{dst=...,port=...,mux=ts}'` |
| Take snapshot | `--video-filter=scene:scene-path=...,scene-ratio=...` |
| Show media info | `-I dummy --play-and-exit --stats` (parsed) |

## 4. Existing CLI surface

VLC already has a CLI, but it is flag-fragmented and not agent-friendly (no structured
output, no project state, no undo). This harness wraps it with Click, `--json`, a
stateful REPL, and a job-spec model.

## 5. Testing strategy

- **Unit** (`test_core.py`): pure functions — job spec load/save, `--sout` chain
  construction, stats parsing — exercised with synthetic data, no VLC required.
- **E2E** (`test_full_e2e.py`): invokes the real `vlc` binary. Tests **fail** (do not
  skip) when VLC or the sample asset is missing, per HARNESS.md non-negotiables.
- A `tests/assets` sample (WAV synthesized with the stdlib `wave` module) makes the
  basic transcode/info E2E runnable without ffmpeg.

## 6. Limitations

VLC's `--stats` text is not a stable structured format. `info` parsing is best-effort
and may return partial fields; it is sufficient for agent triage, not for precise
metadata extraction. For authoritative metadata, prefer the transcode pipeline which is
fully reliable.
