---
name: "cli-anything-quietshrink"
description: Compress macOS screen recordings with zero CPU stress using Apple Silicon's hardware HEVC encoder. Typically reduces file size 70-90% while staying visually lossless. Computer stays silent during encoding.
---

# quietshrink — Agent Skill

You have access to `cli-anything-quietshrink`, a CLI for compressing video files on macOS Apple Silicon. It uses the Media Engine (hardware HEVC encoder), not the CPU, so encoding is fast and silent.

## When to use it

- User wants to compress a screen recording, screencast, or any .mov/.mp4 file
- File is too large to share (chat, email, GitHub)
- Need smaller files but cannot tolerate visible quality loss
- Apple Silicon Mac (M1/M2/M3/M4) — best results

**Don't** use this on non-screen content (camera footage, vlogs) — savings will be much smaller because there are no duplicate frames to drop.

## Commands

```bash
# Compress with default transparent quality
cli-anything-quietshrink compress <input> [output]

# Compress with specific preset
cli-anything-quietshrink compress -q tiny <input>     # smallest
cli-anything-quietshrink compress -q transparent <input>  # default, visually lossless
cli-anything-quietshrink compress -q pristine <input>     # near-source quality

# Inspect a file before compressing
cli-anything-quietshrink probe <input>

# List quality presets
cli-anything-quietshrink presets

# Verify environment
cli-anything-quietshrink doctor
```

All commands accept `--json` for machine-readable output.

## Quality presets

| Preset | q | Typical reduction | SSIM | Use case |
|--------|---|-------------------|------|----------|
| `tiny` | 50 | ~90% | ~0.95 | Chat/email — small artifacts OK |
| `balanced` | 55 | ~88% | ~0.99 | Docs/sharing — high quality |
| `transparent` (default) | 60 | ~87% | ~0.99+ | **Anything important** — visually lossless |
| `pristine` | 70 | ~84% | ~0.997 | Archival — near-source |

## JSON output schema

`compress` returns:
```json
{
  "input": "/path/to/input.mov",
  "output": "/path/to/output.mov",
  "input_size": 105952129,
  "output_size": 12345678,
  "saved_bytes": 93606451,
  "saved_percent": 88.3,
  "duration_seconds": 193.3,
  "elapsed_seconds": 87,
  "encoding_speed": "2.2x",
  "quality_preset": "transparent",
  "q_value": 60,
  "gop": 600
}
```

`probe` returns:
```json
{
  "path": "...",
  "size_bytes": 105952129,
  "size_mb": 101.04,
  "codec": "h264",
  "width": 3024,
  "height": 1964,
  "framerate": "120/1",
  "duration_seconds": 193.31
}
```

## Decision flow for agents

```
User wants to share a recording
  ├─ Is it on Apple Silicon Mac? → use quietshrink
  │  ├─ For chat/email/quick share → -q tiny
  │  ├─ For docs/important sharing → -q transparent (default)
  │  └─ For archival/editing → -q pristine
  └─ Not on Mac? → falls back to software, less efficient
```

Before processing, run `doctor` to verify environment.
For unfamiliar files, run `probe` to understand resolution/codec/duration.

## Errors and recovery

- `ffmpeg not found` → `brew install ffmpeg`
- `hevc_videotoolbox not available` → `brew reinstall ffmpeg`
- `compression_failed` → check input file isn't corrupted; try `--verbose` mode to see ffmpeg errors

## Source

- Main repo: https://github.com/achiya-automation/quietshrink
- Bash CLI: `quietshrink` command (via the install script)
- Why this approach works: see [WHY.md](https://github.com/achiya-automation/quietshrink/blob/main/WHY.md)
