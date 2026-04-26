# quietshrink Agent Harness

Agent-native CLI for [quietshrink](https://github.com/achiya-automation/quietshrink) — compress macOS screen recordings on Apple Silicon with zero CPU stress, achieving 70-90% file size reduction at visually lossless quality.

## What this harness does

Wraps the standalone `quietshrink` bash CLI with a Python (click-based) interface that exposes structured JSON output for AI agents. Agents can:

- **`compress`** a video file with quality presets (tiny / balanced / transparent / pristine)
- **`probe`** a file before compressing to inspect codec, resolution, duration
- **`presets`** list available quality profiles with empirical SSIM/size data
- **`doctor`** verify that ffmpeg, hevc_videotoolbox, and the bash CLI are ready

All commands accept `--json` for machine-readable output and exit with proper error codes.

## Why agents care

Screen recording compression is a frequent agent task: "compress this screencast before sharing", "make this file smaller", "convert recording.mov for email". The agent needs deterministic, predictable behavior:

- Hardware encoding → stays under any budget; computer remains responsive  
- Smart frame deduplication → exploits the static nature of screen content  
- Long GOP + adaptive quantization → matches software-encoder size at hardware speed  
- SSIM-validated quality presets → the agent can pick a preset based on the user's goal (sharing vs archiving)

## Install

```bash
pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=quietshrink/agent-harness
```

The harness depends on the bash `quietshrink` CLI being available in `$PATH`. Install it with:

```bash
curl -fsSL https://raw.githubusercontent.com/achiya-automation/quietshrink/main/install.sh | bash
```

## Usage

```bash
# Inspect a file
cli-anything-quietshrink probe recording.mov --json

# Compress (default: transparent quality)
cli-anything-quietshrink compress recording.mov compressed.mov --json

# List quality presets
cli-anything-quietshrink presets --json

# Verify environment
cli-anything-quietshrink doctor --json
```

## Source

- Main repo: <https://github.com/achiya-automation/quietshrink>
- Why this approach: <https://github.com/achiya-automation/quietshrink/blob/main/WHY.md>
- License: MIT
