# VideoCaptioner: Project-Specific Analysis & SOP

## Architecture Summary

VideoCaptioner is an AI-powered video captioning tool that provides a complete
pipeline from speech recognition to styled subtitle synthesis. It ships as a
standalone CLI (`pip install videocaptioner`) with a well-defined command interface.

```
+----------------------------------------------------------+
|                   VideoCaptioner CLI                      |
|  +------------+ +----------+ +-----------+ +-----------+ |
|  | Transcribe | | Subtitle | | Synthesize| |  Process  | |
|  | (ASR)      | | (NLP)    | | (FFmpeg)  | | (Pipeline)| |
|  +-----+------+ +----+-----+ +-----+-----+ +-----+-----+ |
|        |              |             |             |        |
|  +-----+--------------+-------------+-------------+-----+ |
|  |                    Core Engine                       | |
|  |  ASR engines, LLM optimization, Translation,        | |
|  |  Subtitle rendering (ASS + Rounded), FFmpeg          | |
|  +-----------------------------------------------------+ |
+----------------------------------------------------------+
```

## CLI Strategy: Subprocess Wrapper

Unlike applications that need reverse-engineering of internal formats,
VideoCaptioner already provides a production CLI. Our harness:

1. **Click wrapper** provides the CLI-Anything standard interface
2. **Subprocess backend** delegates to `videocaptioner` CLI commands
3. **JSON mode** (`--json`) returns structured output for agents
4. **REPL mode** provides interactive session with tab-completion

### Why Subprocess?

VideoCaptioner's CLI is:
- **Production-tested** with 50+ unit tests and 200+ QA test cases
- **Feature-complete** with 7 subcommands covering the full pipeline
- **Well-documented** with clear `--help` text and exit codes
- **Actively maintained** on PyPI with automated releases

Wrapping via subprocess preserves all these qualities without reimplementation.

## Coverage

### Transcription (4 ASR engines)
- `bijian` — Free, Chinese & English, no setup needed
- `jianying` — Free, Chinese & English, no setup needed
- `whisper-api` — All languages, OpenAI-compatible API
- `whisper-cpp` — All languages, local model

### Subtitle Processing
- **Split** — Semantic re-segmentation via LLM
- **Optimize** — Fix ASR errors, punctuation, formatting via LLM
- **Translate** — 38 languages, 3 translators (LLM, Bing free, Google free)
- **Layout** — target-above, source-above, target-only, source-only

### Video Synthesis
- **Soft subtitles** — Embedded subtitle track (switchable)
- **Hard subtitles** — Burned into video frames
- **ASS style** — Traditional outline/shadow with presets (default, anime, vertical)
- **Rounded style** — Modern rounded background boxes
- **Customizable** — Inline JSON override for any style parameter
- **Quality levels** — ultra (CRF 18), high (CRF 23), medium (CRF 28), low (CRF 32)

### Utilities
- Configuration management (TOML config + env vars)
- Style preset listing with full parameters
- Online video download (YouTube, Bilibili, etc.)

## Testing Strategy

- **Unit tests**: Mock subprocess calls, verify argument construction
- **End-to-end tests**: Real videocaptioner CLI with test media files
- **Prerequisite**: `videocaptioner` and `ffmpeg` must be installed

## Limitations

- Requires `videocaptioner` package to be installed separately
- Free ASR engines (bijian/jianying) only support Chinese & English
- LLM features require an OpenAI-compatible API key
- Hard subtitle styles require FFmpeg
