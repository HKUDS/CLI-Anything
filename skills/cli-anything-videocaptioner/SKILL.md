---
name: "cli-anything-videocaptioner"
description: >-
  AI-powered video captioning — transcribe speech, optimize/translate subtitles, and burn them into video via the stable VideoCaptioner backend. Free ASR and translation included.
---

# cli-anything-videocaptioner

AI-powered video captioning tool. Transcribe speech → optimize subtitles → translate → burn into video.

## Installation

```bash
pip install cli-anything-videocaptioner
```

**Prerequisites:**
- Python 3.10-3.12 (`videocaptioner` 1.4.1 requires `>=3.10,<3.13`)
- `videocaptioner` must be installed (`pip install videocaptioner`)
- FFmpeg required for video synthesis

## Usage

### Basic Commands

```bash
# Show help
cli-anything-videocaptioner --help

# Start interactive REPL mode
cli-anything-videocaptioner

# Transcribe a video (free, no setup)
cli-anything-videocaptioner transcribe video.mp4 --asr bijian

# Translate subtitles (free Bing translator)
cli-anything-videocaptioner subtitle input.srt --translator bing --target-language en

# Full pipeline: transcribe → translate → burn subtitles
cli-anything-videocaptioner process video.mp4 --asr bijian --translator bing --target-language en --subtitle-mode hard

# Review subtitle/script consistency before a final hard-burn
cli-anything-videocaptioner synthesize video.mp4 -s subtitles.srt \
  --subtitle-mode hard \
  --review-script approved_script.txt

# Render a one-frame subtitle preview for review
cli-anything-videocaptioner review subtitles.srt \
  --script approved_script.txt \
  --preview-video video.mp4 \
  --preview-output review_5s.png

# JSON output (for agent consumption)
cli-anything-videocaptioner --json transcribe video.mp4 --asr bijian
```

### REPL Mode

When invoked without a subcommand, the CLI enters an interactive REPL session:

```bash
cli-anything-videocaptioner
# Enter commands interactively with tab-completion and history
```

## Command Groups

### transcribe — Speech to subtitles
```
transcribe <input> [--asr bijian|jianying|whisper-api|whisper-cpp] [--language CODE] [--format srt|ass|txt|json] [-o PATH]
```
- `bijian` (default): Free, Chinese & English, no setup
- `whisper-api`: All languages, requires `--whisper-api-key`

### subtitle — Optimize and translate
```
subtitle <input.srt> [--translator llm|bing|google] [--target-language CODE] [--layout target-above|source-above|target-only|source-only] [--no-optimize] [--no-translate] [-o PATH]
```
- Three steps: Split → Optimize → Translate
- Bing/Google translators are free
- 38 target languages supported (BCP 47 codes)

### synthesize — Burn subtitles into video
```
synthesize <video> -s <subtitle> [--subtitle-mode soft|hard] [--quality ultra|high|medium|low] [-o PATH] [--review-script PATH] [--max-script-diff-ratio FLOAT]
```
- Mirrors the stable backend synthesize surface
- Subtitle look is controlled by the subtitle asset/backend version, not extra harness flags
- `--review-script` checks subtitle/script drift before the final export
- Lower `--max-script-diff-ratio` when copy accuracy matters more than resilience

### process — Full pipeline
```
process <input> [--asr ...] [--translator ...] [--target-language ...] [--subtitle-mode ...] [--layout ...] [--no-optimize] [--no-translate] [--no-synthesize] [-o PATH]
```

### review — Consistency check and preview
```
review <input.srt|input.ass> [--script PATH] [--max-diff-ratio FLOAT] [--preview-video PATH] [--preview-at TC] [--preview-output PATH]
```
- Detects subtitle/script drift before a hard-burn
- Can render a single review frame instead of producing a full final video

### styles — List style presets
```
styles
```
- Reports whether the installed backend exposes preset styling support

### config — Manage settings
```
config show
config set <key> <value>
```

### download — Download online video
```
download <URL> [-o DIR]
```

## JSON Output

All commands support `--json` for machine-readable output:
```bash
cli-anything-videocaptioner --json transcribe video.mp4 --asr bijian
# {"output_path": "/path/to/output.srt"}
```

## Backend Notes

- The upstream backend currently requires Python `>=3.10,<3.13`; prefer Python `3.12` for matrix runs.
- Advanced synthesize-time style flags are backend-version dependent. Use `styles` to check whether the installed backend exposes them.
- Compatibility flags such as `layout`, `render_mode`, `style`, `style_override`, and `font_file` should be treated as non-stable unless `styles` and the installed backend confirm they are supported.

## Target Languages

BCP 47 codes: `zh-Hans` `zh-Hant` `en` `ja` `ko` `fr` `de` `es` `ru` `pt` `it` `ar` `th` `vi` `id` and 23 more.
