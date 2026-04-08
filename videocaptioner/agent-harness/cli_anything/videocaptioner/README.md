# VideoCaptioner CLI

AI-powered video captioning tool with beautiful customizable subtitle styles.

## Architecture

- **Subprocess backend** delegates to the production `videocaptioner` CLI (`pip install videocaptioner`)
- **Click** provides the CLI framework with subcommand groups and REPL
- **JSON output mode** (`--json`) for agent consumption
- **Free features included**: bijian ASR (Chinese/English), Bing/Google translation

## Pipeline

```
Audio/Video → ASR Transcription → Subtitle Splitting → LLM Optimization → Translation → Video Synthesis
                  (bijian/whisper)      (semantic)         (fix errors)      (38 languages)  (styled subtitles)
```

## Install

```bash
pip install videocaptioner click prompt-toolkit
```

## Run

```bash
# One-shot: transcribe a Chinese video and add English subtitles
cli-anything-videocaptioner process video.mp4 --asr bijian --translator bing --target-language en --subtitle-mode hard

# Transcribe only
cli-anything-videocaptioner transcribe video.mp4 --asr bijian -o output.srt

# Translate existing subtitles
cli-anything-videocaptioner subtitle input.srt --translator google --target-language ja

# Burn subtitles with anime style
cli-anything-videocaptioner synthesize video.mp4 -s sub.srt --subtitle-mode hard --style anime

# Custom style (red outline, large font)
cli-anything-videocaptioner synthesize video.mp4 -s sub.srt --subtitle-mode hard \
  --style-override '{"outline_color": "#ff0000", "font_size": 48}'

# JSON output mode (for agent consumption)
cli-anything-videocaptioner --json transcribe video.mp4 --asr bijian

# Interactive REPL
cli-anything-videocaptioner
```

## Subtitle Styles

Two rendering modes for beautiful subtitles:

**ASS mode** — traditional outline/shadow:
- Presets: `default` (white+black), `anime` (warm+orange), `vertical` (portrait videos)

**Rounded mode** — modern rounded background boxes:
- Preset: `rounded` (dark text on semi-transparent background)

Fully customizable via `--style-override` with inline JSON.

## Coverage

| Feature | Commands |
|---------|----------|
| Transcription | 4 ASR engines, auto language detection, word timestamps |
| Subtitle Processing | Split + optimize + translate, 3 translators, 38 languages |
| Video Synthesis | Soft/hard subtitles, 4 quality levels, 5 style presets |
| Styles | ASS outline + rounded background, inline JSON customization |
| Utilities | Config management, style listing, video download |
