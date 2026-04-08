---
name: >-
  cli-anything-videocaptioner
description: >-
  AI-powered video captioning — transcribe speech, optimize/translate subtitles, burn into video with beautiful customizable styles (ASS outline or rounded background). Free ASR and translation included.
---

# cli-anything-videocaptioner

AI-powered video captioning tool. Transcribe speech → optimize subtitles → translate → burn into video with beautiful styles.

## Installation

```bash
pip install cli-anything-videocaptioner
```

**Prerequisites:**
- Python 3.10+
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
synthesize <video> -s <subtitle> [--subtitle-mode soft|hard] [--quality ultra|high|medium|low] [--style NAME] [--style-override JSON] [--render-mode ass|rounded] [--font-file PATH] [-o PATH]
```
- **ASS mode**: Outline/shadow style with presets (default, anime, vertical)
- **Rounded mode**: Modern rounded background boxes
- Customizable via `--style-override '{"outline_color": "#ff0000"}'`

### process — Full pipeline
```
process <input> [--asr ...] [--translator ...] [--target-language ...] [--subtitle-mode ...] [--style ...] [--no-optimize] [--no-translate] [--no-synthesize] [-o PATH]
```

### styles — List style presets
```
styles
```

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

## Style Presets

| Name | Mode | Description |
|------|------|-------------|
| `default` | ASS | White text, black outline — clean and universal |
| `anime` | ASS | Warm white, orange outline — anime/cartoon style |
| `vertical` | ASS | High bottom margin — for portrait/vertical videos |
| `rounded` | Rounded | Dark text on semi-transparent rounded background |

Customize any field: `--style-override '{"font_size": 48, "outline_color": "#ff0000"}'`

## Target Languages

BCP 47 codes: `zh-Hans` `zh-Hant` `en` `ja` `ko` `fr` `de` `es` `ru` `pt` `it` `ar` `th` `vi` `id` and 23 more.
